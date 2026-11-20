"""The live log progress.jq makes of Claude's stream-json events, run through jq itself."""

import json
import re
import subprocess
import time

from fandian.env import REPO

STAMP = re.compile(r"^\d+:\d\d:\d\d ", re.MULTILINE)


def log(*events: dict | str, color: bool = False, elapsed: int = 0) -> str:
    """The log jq prints for `events` (a dict goes in as one JSON line, a str as it is), `elapsed`
    seconds into the run."""
    lines = [e if isinstance(e, str) else json.dumps(e) for e in events]
    result = subprocess.run(
        ["jq", "-R", "-r", "--argjson", "color", json.dumps(color)]
        + ["--argjson", "start", str(int(time.time()) - elapsed), "-f", str(REPO / "progress.jq")],
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stderr == ""
    return result.stdout


def unstamped(*events: dict | str) -> str:
    """The log for `events` with each line's time stamp replaced by `T `."""
    return STAMP.sub("T ", log(*events))


def assistant(*content: dict) -> dict:
    return {"type": "assistant", "message": {"content": list(content)}}


def tool_use(name: str, **input: str) -> dict:
    return {"type": "tool_use", "name": name, "input": input}


def test_the_session_start_names_the_model_and_mcp_servers():
    init = {
        "type": "system",
        "subtype": "init",
        "model": "claude-opus-5-5",
        "mcp_servers": [{"name": "playwright", "status": "connected"}],
    }

    assert unstamped(init) == "T model claude-opus-5-5, MCP playwright connected\n"


def test_every_line_of_an_agent_message_is_stamped_after_a_blank_line():
    text = {"type": "text", "text": "Mapping the site.\n\nThen the legal pages."}

    assert unstamped(assistant(text)) == "\nT Mapping the site.\nT \nT Then the legal pages.\n"


def test_a_shell_command_shows_as_its_description():
    bash = tool_use(
        "Bash", command="curl -sS http://localhost:8080/", description="Fetch home page"
    )

    assert unstamped(assistant(bash)) == "T   Bash Fetch home page\n"


def test_an_mcp_tool_shows_without_its_server_prefix():
    navigate = tool_use("mcp__playwright__browser_navigate", url="http://localhost:8080/")

    assert unstamped(assistant(navigate)) == "T   browser_navigate http://localhost:8080/\n"


def test_an_issue_write_shows_its_gh_command_on_one_line():
    """A finding filed shows from `gh issue` on, whatever the command did before it, and by the
    command even though it has a description."""
    create = tool_use(
        "Bash",
        command='cd $RUN_DIR &&\n  gh issue create --title "Typo"\n  --label fandian',
        description="File finding",
    )

    assert unstamped(assistant(create)) == (
        'T   issues gh issue create --title "Typo" --label fandian\n'
    )


def test_an_issue_read_shows_as_an_ordinary_command():
    view = tool_use("Bash", command="gh issue view 12 --comments", description="Read finding 12")

    assert unstamped(assistant(view)) == "T   Bash Read finding 12\n"


def test_only_a_failed_tool_result_shows():
    results = {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "is_error": False, "content": "fine"},
                {
                    "type": "tool_result",
                    "is_error": True,
                    "content": [{"type": "text", "text": "no\nsuch element"}],
                },
            ]
        },
    }

    assert unstamped(results) == "T   ! no such element\n"


def test_the_final_status_follows_a_blank_line():
    result = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "num_turns": 120,
        "duration_ms": 5_700_000,
    }

    assert unstamped(result) == "\nT --- success: 120 turns in 95 min\n"


def test_a_line_that_is_not_an_event_is_dropped():
    assert unstamped("not json", {"type": "rate_limit_event"}) == ""


def test_the_stamp_is_the_time_since_the_start():
    """jq reads the clock itself, so the second may tick over between the start and the line."""
    text = assistant({"type": "text", "text": "Done."})

    assert log(text, elapsed=3725) in ("\n1:02:05 Done.\n", "\n1:02:06 Done.\n")


def test_colour_paints_each_part_of_a_line():
    failed = {
        "type": "user",
        "message": {"content": [{"type": "tool_result", "is_error": True, "content": "boom"}]},
    }

    painted = log(failed, color=True)

    assert re.fullmatch(r"\x1b\[2m\d+:\d\d:\d\d\x1b\[0m   \x1b\[31m! boom\x1b\[0m\n", painted)
