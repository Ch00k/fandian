"""The target: a project that makes itself testable with a `.fandian/` directory at its root, as
docs/TARGETS.md describes. fandian reads only that directory, and builds the instance's image from
the checkout's own Dockerfile.

A target is named by a local checkout or by a repository on a forge, which fandian clones into a
cache of its own and brings up to date on every run.

The profile, `.fandian/profile.md`, has a header that wires the instance:

    repo          the GitHub repository findings are filed in, "owner/name"

    [instance]    the fresh instance each run starts
      command     the container's command, split as a shell would split it
      env         the container's environment (optional); public values only, since they are
                  passed on docker's command line
      port        the port it serves on, inside its own network namespace
      health      the path polled until it answers, before the agent starts

    [mail]        optional; present = a Mailpit inbox beside the instance, as `mailpit`
      allowed_recipients  optional; Mailpit refuses every other recipient at RCPT

    [accounts]    from the seed, by a key a persona names: { email, password }

    [guide]       optional; present = oracle mode
      urls        the in-app guide's pages, as paths on the instance

The body below the header is the target's section of the charter. Focuses are
`.fandian/focus/<focus>.md`, each with a header naming the personas it is written for:

    personas      a list of persona names; `run` refuses any other
"""

import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import header
from .console import working

DIRECTORY = ".fandian"

_KEYS = {"repo": str, "instance": dict, "accounts": dict}
_OPTIONAL_KEYS = {"mail": dict, "guide": dict}
_INSTANCE_KEYS = {"command": str, "port": int, "health": str}
_INSTANCE_OPTIONAL_KEYS = {"env": dict}
_MAIL_KEYS = {"allowed_recipients": str}
_ACCOUNT_KEYS = {"email": str, "password": str}
_GUIDE_KEYS = {"urls": list}
_FOCUS_KEYS = {"personas": list}


class TargetError(Exception):
    pass


@dataclass(frozen=True)
class Account:
    email: str
    password: str


@dataclass(frozen=True)
class Instance:
    command: tuple[str, ...]
    env: dict[str, str]
    port: int
    health: str


@dataclass(frozen=True)
class Mail:
    allowed_recipients: str | None


@dataclass(frozen=True)
class Target:
    # The checkout the image is built from, holding .fandian/.
    checkout: Path
    repo: str
    instance: Instance
    mail: Mail | None
    accounts: dict[str, Account]
    # The guide's pages, as paths on the instance; None in explorer mode.
    guide_urls: tuple[str, ...] | None
    # The profile's charter section.
    body: str

    @property
    def name(self) -> str:
        """The repository's name, made fit for Docker's names and the run directory's."""
        return slug(self.repo.split("/")[1])

    @property
    def mode(self) -> str:
        return "explorer" if self.guide_urls is None else "oracle"

    @property
    def base_url(self) -> str:
        """Where the agent reaches the instance: on loopback, since it shares the instance's
        network namespace. A framework that accepts only loopback host names in development
        accepts this one."""
        return f"http://localhost:{self.instance.port}"

    @property
    def token_setting(self) -> str:
        """The name of the setting that holds the GitHub token for this target's repository."""
        return f"GITHUB_TOKEN_{re.sub('[^A-Z0-9]', '_', self.repo.upper())}"

    def focus_path(self, focus: str) -> Path:
        return self.checkout / DIRECTORY / "focus" / f"{focus}.md"

    def personas_directory(self) -> Path:
        return self.checkout / DIRECTORY / "personas"


def slug(text: str) -> str:
    return re.sub("[^a-z0-9]+", "-", text.lower()).strip("-")


def is_remote(location: str) -> bool:
    return "://" in location or location.startswith("git@")


def cache() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "fandian"


def checkout(location: str) -> Path:
    """The checkout a target is named by: the directory itself, or the repository cloned into
    fandian's cache and brought up to date with its default branch. The cache is fandian's own,
    so whatever it holds is replaced by the forge's."""
    if not is_remote(location):
        path = Path(location).expanduser().resolve()
        if not path.is_dir():
            raise TargetError(f"{location} is not a directory, nor a repository's URL")
        return path

    parts = [part for part in re.split("[/:]", location.removesuffix(".git")) if part]
    path = cache() / slug(parts[-2]) / slug(parts[-1])
    with working(f"Bringing {location} up to date"):
        if (path / ".git").is_dir():
            _git("-C", str(path), "fetch", "--depth", "1", "origin", "HEAD")
            _git("-C", str(path), "reset", "--hard", "FETCH_HEAD")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            _git("clone", "--depth", "1", location, str(path))
    return path


def load(location: str) -> Target:
    root = checkout(location)
    path = root / DIRECTORY / "profile.md"
    if not path.exists():
        raise TargetError(f"{root} has no {DIRECTORY}/profile.md; see docs/TARGETS.md")
    if not (root / "Dockerfile").exists():
        raise TargetError(f"{root} has no Dockerfile to build the instance from")

    found = header.read(path)
    header.check_keys(path, found, _KEYS, _OPTIONAL_KEYS)
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", found["repo"]):
        raise header.HeaderError(f"{path}: repo {found['repo']!r} is not owner/name")

    raw = found["instance"]
    header.check_keys(path, raw, _INSTANCE_KEYS, _INSTANCE_OPTIONAL_KEYS, "[instance] ")
    env = raw.get("env", {})
    if not all(isinstance(value, str) for value in env.values()):
        raise header.HeaderError(f"{path}: [instance] env values must be strings")
    if not raw["health"].startswith("/"):
        raise header.HeaderError(f"{path}: [instance] health must be a path, starting with /")
    instance = Instance(tuple(shlex.split(raw["command"])), env, raw["port"], raw["health"])

    mail = None
    if "mail" in found:
        header.check_keys(path, found["mail"], {}, _MAIL_KEYS, "[mail] ")
        mail = Mail(found["mail"].get("allowed_recipients"))

    accounts = {}
    for key, account in found["accounts"].items():
        if not isinstance(account, dict):
            raise header.HeaderError(f"{path}: [accounts] {key} must be {{ email, password }}")
        header.check_keys(path, account, _ACCOUNT_KEYS, where=f"[accounts] {key} ")
        accounts[key] = Account(account["email"], account["password"])

    guide_urls = None
    if "guide" in found:
        header.check_keys(path, found["guide"], _GUIDE_KEYS, where="[guide] ")
        guide_urls = tuple(found["guide"]["urls"])
        if not guide_urls or not all(
            isinstance(url, str) and url.startswith("/") for url in guide_urls
        ):
            raise header.HeaderError(f"{path}: [guide] urls must be paths, starting with /")

    return Target(root, found["repo"], instance, mail, accounts, guide_urls, header.body(path))


def check_focus(target: Target, focus: str, persona: str) -> None:
    """The focus exists in the target and is written for this persona."""
    path = target.focus_path(focus)
    found = header.read(path)
    header.check_keys(path, found, _FOCUS_KEYS)
    if persona not in found["personas"]:
        raise header.HeaderError(
            f"{path}: written for {', '.join(found['personas']) or 'no persona'}, not {persona}"
        )


def _git(*args: str) -> None:
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise TargetError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
