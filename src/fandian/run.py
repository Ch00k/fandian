"""`fand run`: check what can be checked on the host, build both images, start the target's
instance and run one persona's session against it in the agent's container.

The container gets exactly what the charter names: the target and its mode, the instance's and
the inbox's addresses, the persona's account, the repository and its token, and the run
directory. Secrets travel in the docker client's environment and are named with `-e NAME`, so none
appears in a process listing.
"""

import datetime as dt
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from . import charter, claude, github, instance
from .console import working
from .env import REPO, setting
from .persona import Persona
from .target import Target


def run_name(target: Target, persona: Persona, focus: str | None) -> str:
    """What names the run's directory after its stamp."""
    name = f"{target.name}-{persona.name}"
    return name if focus is None else f"{name}-{focus}"


def container_settings(target: Target, persona: Persona, focus: str | None) -> dict[str, str]:
    """What the agent's container receives from the target and the persona, by the names the
    entrypoint and the charter use. The repository's visibility and the secrets come from the
    checks."""
    if not persona.enabled:
        raise SystemExit(f"The {persona.name} persona is switched off (enabled = false).")

    passed = {
        "TARGET": target.name,
        "PERSONA": persona.name,
        "MODE": target.mode,
        "BASE_URL": target.base_url,
        "GH_REPO": target.repo,
    }
    if focus is not None:
        passed["FOCUS"] = focus
    if target.mail is not None:
        passed["INBOX_URL"] = instance.INBOX_URL
    if target.guide_urls is not None:
        passed["GUIDE_URLS"] = " ".join(f"{target.base_url}{url}" for url in target.guide_urls)

    if persona.account is not None:
        account = target.accounts.get(persona.account)
        if account is None:
            raise SystemExit(
                f"The {persona.name} persona signs in as {persona.account!r}, which the "
                f"{target.name} profile's [accounts] lacks."
            )
        passed |= {
            "ACCOUNT": persona.account,
            "ACCOUNT_EMAIL": account.email,
            "ACCOUNT_PASSWORD": account.password,
        }

    return passed


def agent_argv(
    names: list[str], run: str, charter_file: Path, run_dir: Path | None, *, tty: bool
) -> list[str]:
    """The agent's `docker run` command line. Each setting is named, never given a value.

    It joins the instance's network namespace, so it reaches the instance on loopback and the
    inbox by its name, and none of the host's loopback services. It has no capabilities and cannot
    gain privileges, and of the host it sees only its charter, read-only, and this run's
    directory. Claude Code's session transcript is kept in the run directory's transcript/."""
    argv = ["docker", "run", "--rm", "-i", "--init", "--name", f"{run}-agent"]
    if tty:
        argv.append("-t")
    argv += ["--label", f"{instance.LABEL}={run}", "--network", f"container:{run}-instance"]
    argv += ["--cap-drop", "ALL", "--security-opt", "no-new-privileges"]
    argv += ["-v", f"{charter_file}:/work/CLAUDE.md:ro"]
    if run_dir is not None:
        argv += ["-v", f"{run_dir}:/work/findings/{run_dir.name}"]
        argv += ["-v", f"{run_dir / 'transcript'}:/home/node/.claude/projects"]
    for name in names:
        argv += ["-e", name]
    argv.append(instance.AGENT_IMAGE)
    return argv


def _stop(signum: int, _frame) -> None:
    """A SIGTERM or SIGHUP ends the run as Ctrl-C does, so the instance is still removed."""
    raise SystemExit(f"\nStopped by {signal.Signals(signum).name}.")


def run(target: Target, persona: Persona, *, focus: str | None, check: bool) -> None:
    passed = container_settings(target, persona, focus)

    token = setting(target.token_setting)
    with working(f"Checking the GitHub token for {target.repo}"):
        try:
            visibility = github.check(token, target.repo, github.labels(persona.name, focus))
        except github.TokenError as e:
            raise SystemExit(f"FANDIAN_{target.token_setting} cannot file findings: {e}.") from None
    passed["REPO_VISIBILITY"] = visibility
    passed["GH_TOKEN"] = token

    # A wiring check never starts Claude, so it needs no Claude token.
    if check:
        passed["FANDIAN_CHECK"] = "1"
    else:
        claude_token = setting("CLAUDE_TOKEN")
        with working("Checking the Claude plan"):
            claude.check_plan(claude_token)
        passed["CLAUDE_CODE_OAUTH_TOKEN"] = claude_token
    passed |= claude.model_choice()
    if sys.stdout.isatty():
        passed["FANDIAN_COLOR"] = "1"

    version = claude.latest_version()
    instance.build(instance.AGENT_IMAGE, REPO, {"CLAUDE_VERSION": version})
    instance.build(instance.target_image(target), target.checkout)

    stamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d-%H%M%S")
    run = f"fandian-{stamp}-{target.name}".lower()
    run_dir = REPO / "findings" / f"run-{stamp}-{run_name(target, persona, focus)}"
    passed["RUN_DIR"] = f"/work/findings/{run_dir.name}"
    # A wiring check writes nothing there, so it gets none. A session's is created here so it
    # belongs to the operator: docker would create it as root, and the container's user could not
    # write to it.
    if not check:
        (run_dir / "transcript").mkdir(parents=True)

    # The charter the agent was given stays with the run; a wiring check's is thrown away.
    with tempfile.TemporaryDirectory() as scratch:
        charter_file = (Path(scratch) if check else run_dir) / "charter.md"
        charter_file.write_text(charter.compose(target, persona, focus))

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGHUP, _stop)
        with instance.started(target, run, None if check else run_dir / "instance.log"):
            mounted = None if check else run_dir
            argv = agent_argv(list(passed), run, charter_file, mounted, tty=sys.stdin.isatty())
            code = subprocess.run(argv, env=os.environ | passed).returncode

    if not check:
        print(f"Run directory: {run_dir}")
    if code != 0:
        raise SystemExit(code)
