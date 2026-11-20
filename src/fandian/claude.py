"""Claude Code in the image: which release to build in, the model it runs and the plan the agent's
token draws on."""

import json
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

# The reasons the API gives for refusing paid overage that mean it is switched off (or capped at
# nothing) for the plan, org, seat or member. The rest - out of credits, a spend cap that lifts at
# a reset, an unknown or failed lookup - leave it able to come back mid-run.
_OVERAGE_OFF = frozenset(
    {
        "overage_not_provisioned",
        "org_level_disabled",
        "org_service_level_disabled",
        "seat_tier_level_disabled",
        "member_level_disabled",
        "seat_tier_zero_credit_limit",
        "group_zero_credit_limit",
        "member_zero_credit_limit",
    }
)


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
    problem, at_limit = _inspect(token)
    if problem is not None:
        raise PlanError(f"FANDIAN_CLAUDE_TOKEN cannot run the agent: {problem}.")
    if at_limit:
        raise PlanError("The Claude plan is at its usage limit; start the run once it resets.")


def _inspect(token: str) -> tuple[str | None, bool]:
    """Why this token cannot run the agent (None if it can), and whether its plan is at its usage
    limit right now.

    An API key (sk-ant-api...) bills at API rates. Only usage counted against a plan comes back
    with the `anthropic-ratelimit-unified-*` headers (its 5-hour and weekly limits); a call billed
    at API rates gets the per-minute `requests-*`/`tokens-*` ones instead. A plan at its limit
    answers 429 with the same headers. Paid overage must be off too, since it carries a run past
    the plan's limits at API rates. The headers are undocumented, so a rename fails the check
    closed rather than letting a run through unchecked. A 429 without them is raised as a
    PlanError: it says nothing about the token."""
    if not token.startswith("sk-ant-oat"):
        return "it is not a `claude setup-token` token (sk-ant-oat...)", False

    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "oauth-2025-04-20",
    }
    try:
        status, response = _probe(headers)
    except ApiError as e:
        return f"the plan check failed: HTTP {e.status}: {e.body[:200]}", False
    except OSError as e:
        return f"the plan check failed: {e}", False

    if response.get("anthropic-ratelimit-unified-status") is None:
        if status == 429:
            # Says nothing about the token, so it is no reason to replace it.
            raise PlanError("The Claude plan check was rate limited (HTTP 429); try again shortly.")
        return "it does not draw on a Claude plan (the API reported no plan limits)", False

    overage = response.get("anthropic-ratelimit-unified-overage-status")
    reason = response.get("anthropic-ratelimit-unified-overage-disabled-reason")
    if overage != "rejected" or reason not in _OVERAGE_OFF:
        return (
            f"paid overage is not confirmed off on its plan (status {overage!r}, reason "
            f"{reason!r}); overage bills at API rates past the plan's limits"
        ), False

    return None, status == 429


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
