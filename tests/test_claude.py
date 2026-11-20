import json

import pytest

from fandian import claude
from fandian.api import ApiError

TOKEN = "sk-ant-oat01-test"


def plan(status=200, overage="rejected", reason="org_level_disabled"):
    """The plan probe answering with `status` and a plan's headers."""
    headers = {"anthropic-ratelimit-unified-status": "allowed"}
    if overage is not None:
        headers["anthropic-ratelimit-unified-overage-status"] = overage
    if reason is not None:
        headers["anthropic-ratelimit-unified-overage-disabled-reason"] = reason
    return lambda _headers: (status, headers)


def test_accepts_a_plan_token_with_overage_switched_off(monkeypatch):
    monkeypatch.setattr(claude, "_probe", plan())

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
    ("overage", "reason"),
    [("allowed", None), ("rejected", "out_of_credits"), ("rejected", None), (None, None)],
)
def test_refuses_a_plan_whose_overage_is_not_confirmed_off(monkeypatch, overage, reason):
    monkeypatch.setattr(claude, "_probe", plan(overage=overage, reason=reason))

    with pytest.raises(claude.PlanError, match="paid overage is not confirmed off"):
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
