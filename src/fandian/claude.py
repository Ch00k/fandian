"""Claude Code in the image: which release to build in, the model it runs and the plan the agent's
token draws on."""

import json
import math
import urllib.error
import urllib.request
from pathlib import Path

from .api import ApiError
from .env import setting

RELEASE_URL = "https://downloads.claude.ai/claude-code-releases/latest"

# The smallest request that tells a plan's usage from API billing (see _inspect).
_PLAN_PROBE = {
    "model": "claude-haiku-5-5",
    "max_tokens": 1,
    "system": "You are Claude Code, Anthropic's official CLI for Claude.",
    "messages": [{"role": "user", "content": "ok"}],
}

# The share of the plan's 5-hour and weekly limits past which no run starts: a run that starts
# close to a limit is likely to finish past it, on paid overage at API rates.
_UTILIZATION_CEILINGS = {"5h": 0.90, "7d": 0.95}


class PlanError(Exception):
    pass


def latest_version() -> str:
    """The current Claude Code release, or "latest" when the lookup fails. The image is built
    against it so a release invalidates the install layer; the installer resolves "latest" itself,
    so a failed lookup costs only that cache-busting."""
    try:
        with urllib.request.urlopen(RELEASE_URL, timeout=15) as response:
            return response.read().decode().strip()
    except OSError:
        return "latest"


def model_choice() -> dict[str, str]:
    """The model and effort the agent runs with, by the names the entrypoint takes them under: the
    operator's own Claude Code choice (`model` and `effortLevel` in ~/.claude/settings.json), with
    the CLAUDE_MODEL setting over the model. One that is set nowhere is left out, so the CLI's
    default applies."""
    path = Path.home() / ".claude" / "settings.json"
    host = json.loads(path.read_text()) if path.exists() else {}
    choice = {
        "FANDIAN_MODEL": setting("CLAUDE_MODEL") or host.get("model"),
        "FANDIAN_EFFORT": host.get("effortLevel"),
    }
    return {name: value for name, value in choice.items() if isinstance(value, str) and value}


def check_plan(token: str) -> None:
    problem, wait = _inspect(token)
    if problem is not None:
        raise PlanError(f"FANDIAN_CLAUDE_TOKEN cannot run the agent: {problem}.")
    if wait is not None:
        raise PlanError(wait)


def _inspect(token: str) -> tuple[str | None, str | None]:
    """Why this token cannot run the agent (None if it can), and why no run may start on its plan
    right now (None if one may).

    An API key (sk-ant-api...) bills at API rates. Only usage counted against a plan comes back
    with the `anthropic-ratelimit-unified-*` headers (its 5-hour and weekly limits); a call billed
    at API rates gets the per-minute `requests-*`/`tokens-*` ones instead. A plan at its limit
    answers 429 with the same headers. Paid overage carries a run past the plan's limits at API
    rates, so neither limit may be nearly used up (`_UTILIZATION_CEILINGS`). The headers are
    undocumented, so a rename fails the check closed rather than letting a run through
    unchecked. A 429 without them is raised as a PlanError: it says nothing about the token."""
    if not token.startswith("sk-ant-oat"):
        return "it is not a `claude setup-token` token (sk-ant-oat...)", None

    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "oauth-2025-04-20",
    }
    try:
        status, response = _probe(headers)
    except ApiError as e:
        return f"the plan check failed: HTTP {e.status}: {e.body[:200]}", None
    except OSError as e:
        return f"the plan check failed: {e}", None

    if response.get("anthropic-ratelimit-unified-status") is None:
        if status == 429:
            # Says nothing about the token, so it is no reason to replace it.
            raise PlanError("The Claude plan check was rate limited (HTTP 429); try again shortly.")
        return "it does not draw on a Claude plan (the API reported no plan limits)", None

    if status == 429:
        return None, "The Claude plan is at its usage limit; start the run once it resets."

    for window, ceiling in _UTILIZATION_CEILINGS.items():
        reported = response.get(f"anthropic-ratelimit-unified-{window}-utilization", "")
        try:
            utilization = float(reported)
        except ValueError:
            utilization = None
        if utilization is None or not math.isfinite(utilization) or utilization < 0:
            return None, (
                f"The Claude plan check failed: the API reported no usable {window} limit "
                f"utilization ({reported!r})."
            )
        if utilization >= ceiling:
            return None, (
                f"The Claude plan's {window} limit is {utilization:.0%} used, at or past the "
                f"{ceiling:.0%} a run may start at; a run from here would likely go on to paid "
                "overage at API rates. Start it once the limit resets."
            )

    return None, None


def _probe(headers: dict[str, str]) -> tuple[int, dict[str, str]]:
    """Send the plan probe; returns the status and the response headers, lower-cased. A 429 is
    returned too: a plan at its limit answers with one."""
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(_PLAN_PROBE).encode(),
        headers={**headers, "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return e.code, {k.lower(): v for k, v in e.headers.items()}
        raise ApiError(
            "POST", request.full_url, e.code, e.read().decode(errors="replace")
        ) from None
