import os
from pathlib import Path

import pytest

from fandian import env

PROFILE = """\
+++
repo = "owner/Example.app"

[instance]
command = "sh -c 'seed && serve'"
port = 8000
health = "/health/"

[instance.env]
SMTP_HOST = "mailpit"

[mail]
allowed_recipients = '@example\\.[a-z]+$'

[accounts]
user = { email = "dev@example.com", password = "devpassword" }

[guide]
urls = ["/help/"]
+++

## TARGET: Example

### Purpose

Keeps examples.
"""


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    """An .env of the test's own (not yet created), with no FANDIAN_ setting in the environment
    to override it."""
    for name in list(os.environ):
        if name.startswith(env.PREFIX):
            monkeypatch.delenv(name)
    path = tmp_path / ".env"
    monkeypatch.setattr(env, "ENV_FILE", path)
    return path


@pytest.fixture
def project(tmp_path) -> Path:
    """A checkout made testable: a Dockerfile, and a .fandian/ holding a profile with an inbox
    and a guide."""
    root = tmp_path / "example"
    (root / ".fandian").mkdir(parents=True)
    (root / "Dockerfile").write_text("FROM scratch\n")
    (root / ".fandian" / "profile.md").write_text(PROFILE)
    return root


def write(project: Path, relative: str, text: str) -> None:
    path = project / ".fandian" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
