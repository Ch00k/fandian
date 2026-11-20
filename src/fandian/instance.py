"""The target's instance: a Docker network of the run's own holding the instance and, for a
target with [mail], its Mailpit and the tester's mailbox in front of it, all destroyed with their
data when the run ends.

Nothing is published to the host. The agent joins the instance's network namespace, and the
host's own checks (Mailpit's SMTP greeting, the health path) run in short-lived containers of the
agent's image on the same network, so they work wherever Docker runs. Every container of a run
carries the label `fandian.run=<run>`, which is how the run removes them, the agent's included.
"""

import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from .console import working
from .target import Target

AGENT_IMAGE = "fandian-agent:latest"
MAILPIT_IMAGE = "axllent/mailpit:v1.34.0"
# The name the instance reaches its Mailpit by, and Mailpit's ports.
MAILPIT_HOST = "mailpit"
SMTP_PORT = 1025
MAILPIT_URL = f"http://{MAILPIT_HOST}:8025"
# Where the tester reads its own mail (src/fandian/mailbox.py, in the tester's image).
MAILBOX_HOST = "mailbox"
MAILBOX_URL = f"http://{MAILBOX_HOST}:8000"

LABEL = "fandian.run"
MAIL_TIMEOUT = 60
# A first seed may reach outside services (rates, holidays) for a while.
HEALTH_TIMEOUT = 300


class InstanceError(Exception):
    pass


def target_image(target: Target) -> str:
    return f"fandian-target-{target.name}:latest"


def build(tag: str, context: Path, build_args: dict[str, str] | None = None) -> None:
    """Build an image; its output is shown only when it fails."""
    argv = ["docker", "build", "-t", tag]
    for name, value in (build_args or {}).items():
        argv += ["--build-arg", f"{name}={value}"]
    argv.append(str(context))

    with working(f"Building {tag}"):
        result = subprocess.run(argv, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        raise InstanceError(f"{tag} did not build from {context}.")


def instance_argv(target: Target, run: str) -> list[str]:
    """The `docker run` command line of the instance. Its environment is the profile's, all public
    values, so it is given on the command line."""
    argv = ["docker", "run", "-d", "--name", f"{run}-instance", "--network", run]
    argv += ["--label", f"{LABEL}={run}"]
    for name, value in target.instance.env.items():
        argv += ["-e", f"{name}={value}"]
    argv.append(target_image(target))
    return argv + list(target.instance.command)


def mailpit_argv(target: Target, run: str) -> list[str]:
    assert target.mail is not None

    argv = ["docker", "run", "-d", "--name", f"{run}-mailpit", "--network", run]
    argv += ["--network-alias", MAILPIT_HOST, "--label", f"{LABEL}={run}"]
    if target.mail.allowed_recipients is not None:
        argv += ["-e", f"MP_SMTP_ALLOWED_RECIPIENTS={target.mail.allowed_recipients}"]
    return argv + [MAILPIT_IMAGE]


def mailbox_argv(run: str, address: str) -> list[str]:
    """The tester's mailbox, serving only the mail sent to `address`."""
    argv = ["docker", "run", "-d", "--name", f"{run}-mailbox", "--network", run]
    argv += ["--network-alias", MAILBOX_HOST, "--label", f"{LABEL}={run}"]
    argv += ["--cap-drop", "ALL", "--security-opt", "no-new-privileges"]
    argv += ["-e", f"ADDRESS={address}", "-e", f"MAILPIT_URL={MAILPIT_URL}"]
    return argv + [AGENT_IMAGE, "python3", "/opt/mailbox.py"]


def probe_argv(network: str, script: str) -> list[str]:
    """A check run from inside the run's network, in the agent's image, with nothing to spare."""
    return [
        "docker", "run", "--rm", "--network", network, "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", AGENT_IMAGE, "bash", "-c", script,
    ]  # fmt: skip


@contextmanager
def started(target: Target, run: str, mailbox: str | None, log: Path | None) -> Generator[str]:
    """Start the run's network, Mailpit with the mailbox of the address `mailbox`, and the
    instance, and yield the instance's container name once its health path answers. Afterwards
    the instance's log goes to `log`, when given, and everything the run started is removed,
    whatever happened."""
    instance = f"{run}-instance"
    _docker("network", "create", "--label", f"{LABEL}={run}", run)
    try:
        if target.mail is not None:
            with working("Starting Mailpit"):
                _docker(*mailpit_argv(target, run)[1:])
                _wait_for_smtp(run)
            if mailbox is not None:
                with working(f"Starting the mailbox of {mailbox}"):
                    _docker(*mailbox_argv(run, mailbox)[1:])
                    _wait_for(
                        run, f"curl -fsS -o /dev/null --max-time 5 {MAILBOX_URL}/", "The mailbox"
                    )

        with working(f"Starting {target.name} and waiting for {target.instance.health}"):
            _docker(*instance_argv(target, run)[1:])
            _wait_for_health(target, instance)

        yield instance
    finally:
        if log is not None:
            _save_log(instance, log)
        _remove(run)


def _wait_for_smtp(run: str) -> None:
    """Mailpit answers with an SMTP greeting. Its own health check asks its web server, which
    Mailpit starts apart from the SMTP one."""
    script = (
        f"exec 3<>/dev/tcp/{MAILPIT_HOST}/{SMTP_PORT} && read -r -t 5 greeting <&3 "
        '&& [[ "$greeting" == 220* ]]'
    )
    _wait_for(run, script, "Mailpit's SMTP server")


def _wait_for(run: str, script: str, what: str) -> None:
    """Until the probe succeeds from the run's network, or MAIL_TIMEOUT runs out."""
    deadline = time.monotonic() + MAIL_TIMEOUT
    while subprocess.run(probe_argv(run, script), capture_output=True).returncode != 0:
        if time.monotonic() > deadline:
            raise InstanceError(f"{what} did not answer within {MAIL_TIMEOUT} seconds.")
        time.sleep(1)


def _wait_for_health(target: Target, instance: str) -> None:
    url = f"{target.base_url}{target.instance.health}"
    script = f"curl -fsS -o /dev/null --max-time 5 {url}"
    deadline = time.monotonic() + HEALTH_TIMEOUT
    while subprocess.run(
        probe_argv(f"container:{instance}", script), capture_output=True
    ).returncode:
        if not _running(instance):
            raise InstanceError(f"The instance stopped before {url} answered:\n{_tail(instance)}")
        if time.monotonic() > deadline:
            raise InstanceError(
                f"{url} did not answer within {HEALTH_TIMEOUT} seconds:\n{_tail(instance)}"
            )
        time.sleep(1)


def _running(container: str) -> bool:
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", container],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == "true"


def _tail(container: str) -> str:
    result = subprocess.run(
        ["docker", "logs", "--tail", "30", container], capture_output=True, text=True
    )
    return result.stdout + result.stderr


def _save_log(container: str, log: Path) -> None:
    with log.open("w") as file:
        subprocess.run(["docker", "logs", container], stdout=file, stderr=subprocess.STDOUT)


def _remove(run: str) -> None:
    found = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"label={LABEL}={run}"],
        capture_output=True,
        text=True,
    ).stdout.split()
    if found:
        subprocess.run(["docker", "rm", "-f", *found], capture_output=True)
    subprocess.run(["docker", "network", "rm", run], capture_output=True)


def _docker(*args: str) -> None:
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise InstanceError(f"docker {args[0]} failed: {result.stderr.strip()}")
