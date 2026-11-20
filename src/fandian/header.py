"""The TOML header between `+++` lines at the top of a profile, persona or focus file. It wires
the file; the text below it is the file's section of the agent's charter."""

import tomllib
from collections.abc import Mapping
from pathlib import Path

DELIMITER = "+++"


class HeaderError(Exception):
    pass


def read(path: Path) -> dict:
    if not path.exists():
        raise HeaderError(f"{path} does not exist")
    lines = path.read_text().splitlines()
    if not lines or lines[0] != DELIMITER or DELIMITER not in lines[1:]:
        raise HeaderError(f"{path}: no header between {DELIMITER} lines at the top")

    end = lines.index(DELIMITER, 1)
    try:
        return tomllib.loads("\n".join(lines[1:end]))
    except tomllib.TOMLDecodeError as e:
        raise HeaderError(f"{path}: its header is not valid TOML ({e})") from None


def body(path: Path) -> str:
    """The file's text below its header."""
    lines = path.read_text().splitlines()
    end = lines.index(DELIMITER, 1)
    return "\n".join(lines[end + 1 :]).strip() + "\n"


def check_keys(
    path: Path,
    table: dict,
    required: Mapping[str, type],
    optional: Mapping[str, type] | None = None,
    where: str = "",
) -> None:
    """Every required key present, every key of its type, and no other key."""
    optional = optional or {}
    known = {**required, **optional}
    missing = sorted(required.keys() - table.keys())
    unknown = sorted(table.keys() - known.keys())
    mistyped = sorted(k for k in known.keys() & table.keys() if not isinstance(table[k], known[k]))
    if missing or unknown or mistyped:
        problems = [
            f"{label}: {', '.join(found)}"
            for label, found in (
                ("missing", missing),
                ("unknown", unknown),
                ("wrong type", mistyped),
            )
            if found
        ]
        raise HeaderError(f"{path}: {where}header keys - {'; '.join(problems)}")
