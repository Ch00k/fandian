"""The repository's paths and its .env file, which holds the operator's secrets."""

import os
import re
from pathlib import Path

# The CLI is installed editable, so it runs from the checkout: the agent image's build context,
# the charter, the targets, .env and findings/ are all found beside its source.
REPO = Path(__file__).resolve().parents[2]
ENV_FILE = REPO / ".env"

# Every setting is named with this prefix in .env and in the environment, so none collides with a
# variable the operator's shell sets for something else (GH_TOKEN for gh, say). The code names
# settings without it.
PREFIX = "FANDIAN_"
NAME = "[A-Z0-9_]+"


def read_env() -> dict[str, str]:
    """The settings in .env, by their names without the prefix."""
    values = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            match = re.match(rf"^{PREFIX}({NAME})=(.*)$", line)
            if match:
                values[match[1]] = match[2]
    return values


def setting(name: str) -> str:
    """The setting from the process environment, else from .env, else empty. The environment wins,
    so one run can differ from what .env says."""
    return os.environ.get(f"{PREFIX}{name}") or read_env().get(name, "")
