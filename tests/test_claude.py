import json

import pytest

from fandian import claude
from fandian.api import ApiError

TOKEN = "sk-ant-oat01-test"


def plan(status=200, five_hour="0.5", week="0.5"):
    """The plan probe answering with `status` and a plan's headers, its 5-hour and weekly limits
    used as given (a None leaves the header out)."""
    headers = {"anthropic-ratelimit-unified-status": "allowed"}
    if five_hour is not None:
        headers["anthropic-ratelimit-unified-5h-utilization"] = five_hour
    if week is not None:
        headers["anthropic-ratelimit-unified-7d-utilization"] = week
    return lambda _headers: (status, headers)


def test_accepts_a_plan_token_with_room_on_both_limits(monkeypatch):
    """Paid overage plays no part: only how much of each limit is used does."""
    monkeypatch.setattr(claude, "_probe", plan(five_hour="0.89", week="0.94"))

    claude.check_plan(TOKEN)


def test_refuses_anything_but_a_setup_token():
    with pytest.raises(claude.PlanError, match="sk-ant-oat"):
        claude.check_plan("sk-ant-api03-key")


def test_refuses_a_token_billed_at_api_rates(monkeypatch):
    """No plan headers means the call was billed at API rates."""
    monkeypatch.setattr(claude, "_probe", lambda _headers: (200, {"requests-limit": "50"}))

    with pytest.raises(claude.PlanError, match="does not draw on a Claude plan"):
        claude.check_plan(TOKEN)


@pytest.mark.parametrize(
    ("five_hour", "week", "message"),
    [
        ("0.9", "0.5", "5h limit is 90% used"),
        ("0.5", "0.95", "7d limit is 95% used"),
    ],
)
def test_a_plan_near_a_limit_cannot_start_a_run(monkeypatch, five_hour, week, message):
    """A run that starts at or past a limit's ceiling would likely finish on paid overage."""
    monkeypatch.setattr(claude, "_probe", plan(five_hour=five_hour, week=week))

    with pytest.raises(claude.PlanError, match=message):
        claude.check_plan(TOKEN)


@pytest.mark.parametrize(
    ("five_hour", "week"),
    [
        (None, "0.5"),
        ("0.5", "lots"),
        ("nan", "0.5"),
        ("0.5", "-0.1"),
        ("-inf", "0.5"),
        ("inf", "0.5"),
    ],
)
def test_a_plan_without_a_usable_utilization_fails_closed(monkeypatch, five_hour, week):
    """The utilization headers are undocumented: a missing one, or one that is no share of a limit
    (not a number, negative or infinite), refuses the run rather than letting it start
    unchecked."""
    monkeypatch.setattr(claude, "_probe", plan(five_hour=five_hour, week=week))

    with pytest.raises(claude.PlanError, match="no usable"):
        claude.check_plan(TOKEN)


def test_a_plan_at_its_limit_cannot_start_a_run(monkeypatch):
    monkeypatch.setattr(claude, "_probe", plan(status=429))

    with pytest.raises(claude.PlanError, match="usage limit"):
        claude.check_plan(TOKEN)


def test_a_rate_limit_without_plan_headers_is_no_verdict_on_the_token(monkeypatch):
    monkeypatch.setattr(claude, "_probe", lambda _headers: (429, {}))

    with pytest.raises(claude.PlanError, match="try again shortly"):
        claude.check_plan(TOKEN)


@pytest.mark.parametrize(
    "error", [ApiError("POST", "u", 401, "invalid token"), OSError("unreachable")]
)
def test_a_failed_probe_fails_closed(monkeypatch, error):
    def failing(_headers):
        raise error

    monkeypatch.setattr(claude, "_probe", failing)

    with pytest.raises(claude.PlanError, match="the plan check failed"):
        claude.check_plan(TOKEN)


def test_model_choice_follows_the_operators_claude_settings(tmp_path, monkeypatch, env_file):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(
        json.dumps({"model": "opus[1m]", "effortLevel": "high"})
    )
    monkeypatch.setattr(claude.Path, "home", lambda: tmp_path)

    assert claude.model_choice() == {"FANDIAN_MODEL": "opus[1m]", "FANDIAN_EFFORT": "high"}

    monkeypatch.setenv("FANDIAN_CLAUDE_MODEL", "sonnet")
    assert claude.model_choice() == {"FANDIAN_MODEL": "sonnet", "FANDIAN_EFFORT": "high"}


def test_model_choice_is_empty_without_claude_settings(tmp_path, monkeypatch, env_file):
    monkeypatch.setattr(claude.Path, "home", lambda: tmp_path)

    assert claude.model_choice() == {}
