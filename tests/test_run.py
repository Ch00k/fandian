from dataclasses import replace
from pathlib import Path

import pytest

from fandian import instance, run, target
from fandian.persona import Persona

NEWCOMER = Persona("newcomer", enabled=True, account="user", body="")


@pytest.fixture
def example(project):
    return target.load(str(project))


def test_the_container_gets_the_address_login_mailbox_and_harness(example):
    """What a user would have, and nothing about how the product is set up."""
    assert run.container_settings(example, NEWCOMER, None) == {
        "TARGET": "example-app",
        "PERSONA": "newcomer",
        "BASE_URL": "http://localhost:8000",
        "GH_REPO": "owner/Example.app",
        "HARNESS_URL": "http://localhost:8000/fake/",
        "ACCOUNT_EMAIL": "dev@example.com",
        "ACCOUNT_PASSWORD": "devpassword",
        "MAILBOX_URL": "http://mailbox:8000",
    }


def test_a_target_without_mail_or_harness_passes_neither(example):
    passed = run.container_settings(replace(example, mail=None, harness=None), NEWCOMER, None)

    assert "MAILBOX_URL" not in passed
    assert "HARNESS_URL" not in passed
    assert passed["ACCOUNT_EMAIL"] == "dev@example.com"


def test_a_persona_without_an_account_starts_signed_out(example):
    passed = run.container_settings(example, replace(NEWCOMER, account=None), None)

    assert not any(name.startswith("ACCOUNT") for name in passed)
    assert "MAILBOX_URL" not in passed


def test_a_focused_run_passes_its_focus_and_is_named_by_it(example):
    assert run.container_settings(example, NEWCOMER, "search")["FOCUS"] == "search"
    assert run.run_name(example, NEWCOMER, "search") == "example-app-newcomer-search"
    assert run.run_name(example, NEWCOMER, None) == "example-app-newcomer"


def test_a_switched_off_persona_is_refused(example):
    with pytest.raises(SystemExit, match="switched off"):
        run.container_settings(example, replace(NEWCOMER, enabled=False), None)


def test_a_persona_whose_account_the_target_lacks_is_refused(example):
    with pytest.raises(SystemExit, match="'admin', which the example-app profile"):
        run.container_settings(example, replace(NEWCOMER, account="admin"), None)


def test_the_agent_joins_the_instance_and_gets_settings_by_name_only():
    names = ["GH_TOKEN", "ACCOUNT_PASSWORD"]
    run_dir = Path("/f/run-x")

    argv = run.agent_argv(names, "fandian-x", run_dir / "charter.md", run_dir, tty=False)

    assert argv[argv.index("GH_TOKEN") - 1] == "-e"
    assert argv[argv.index("ACCOUNT_PASSWORD") - 1] == "-e"
    assert not any("=" in arg for arg in argv if not arg.startswith(instance.LABEL))
    assert argv[argv.index("--network") + 1] == "container:fandian-x-instance"
    assert argv[argv.index("--label") + 1] == "fandian.run=fandian-x"
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert "-p" not in argv
    mounts = [argv[i + 1] for i, arg in enumerate(argv) if arg == "-v"]
    assert mounts == [
        "/f/run-x/charter.md:/work/CLAUDE.md:ro",
        "/f/run-x:/work/findings/run-x",
        "/f/run-x/transcript:/home/node/.claude/projects",
    ]
    assert argv[-1] == instance.AGENT_IMAGE


def test_a_wiring_check_mounts_nothing():
    argv = run.agent_argv(["PERSONA"], "fandian-x", Path("/tmp/c/charter.md"), None, tty=False)

    assert [argv[i + 1] for i, arg in enumerate(argv) if arg == "-v"] == [
        "/tmp/c/charter.md:/work/CLAUDE.md:ro"
    ]
