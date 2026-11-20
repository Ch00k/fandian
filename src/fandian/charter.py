"""The agent's charter, composed on the host from fandian's sections and the target's, in this
order: core, mode, inbox (for a target with mail), reporting, the target's profile, the persona and
the focus. Each file's header is left out. It reaches the container as one read-only file, so the
target's checkout never does."""

from . import header
from .env import REPO
from .persona import Persona
from .target import Target

SECTIONS = REPO / "charter"


def compose(target: Target, persona: Persona, focus: str | None) -> str:
    parts = [(SECTIONS / "core.md").read_text(), (SECTIONS / f"{target.mode}.md").read_text()]
    if target.mail is not None:
        parts.append((SECTIONS / "inbox.md").read_text())
    parts += [(SECTIONS / "reporting.md").read_text(), target.body, persona.body]
    if focus is not None:
        parts.append(header.body(target.focus_path(focus)))
    return "\n".join(part.strip() + "\n" for part in parts)
