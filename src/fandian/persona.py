"""The personas: one file each, personas/<name>.md for fandian's generic ones and
.fandian/personas/<name>.md for a target's own. A name both define is refused. The header wires
the persona:

    enabled       true or false; a persona switched off is refused by `run`
    account       optional; the key in the target's [accounts] it signs in with. `run` refuses a
                  target that has no such account. Without one, the persona starts signed out.
                  A generic persona names a role docs/TARGETS.md defines.

The text below the header is its section of the agent's charter.
"""

from dataclasses import dataclass
from pathlib import Path

from . import header
from .env import REPO
from .target import Target

GENERIC = REPO / "personas"

_KEYS = {"enabled": bool}
_OPTIONAL_KEYS = {"account": str}


@dataclass(frozen=True)
class Persona:
    name: str
    enabled: bool
    account: str | None
    body: str


def paths(target: Target) -> dict[str, Path]:
    """Every persona a run of this target may use, by name."""
    generic = {path.stem: path for path in GENERIC.glob("*.md")}
    own = {path.stem: path for path in target.personas_directory().glob("*.md")}
    both = sorted(generic.keys() & own.keys())
    if both:
        raise header.HeaderError(
            f"{target.personas_directory()} defines personas fandian already has: {', '.join(both)}"
        )
    return generic | own


def load(target: Target, name: str) -> Persona:
    found = paths(target)
    if name not in found:
        raise header.HeaderError(f"No persona {name!r}; there are: {', '.join(sorted(found))}")

    path = found[name]
    values = header.read(path)
    header.check_keys(path, values, _KEYS, _OPTIONAL_KEYS)
    return Persona(name, values["enabled"], values.get("account"), header.body(path))
