from dataclasses import replace

from conftest import write

from fandian import charter, persona, target


def sections(text: str) -> list[str]:
    """The charter's own top-level parts: its title and each section named in capitals."""
    return [
        line
        for line in text.splitlines()
        if line.startswith("# ")
        or line.startswith(
            ("## MODE", "## INBOX", "## Reporting", "## TARGET", "## PERSONA", "## FOCUS")
        )
    ]


def test_the_charter_runs_core_mode_inbox_reporting_target_persona_focus(project):
    write(project, "focus/search.md", '+++\npersonas = ["newcomer"]\n+++\n\n## FOCUS: search\n')
    loaded = target.load(str(project))

    composed = charter.compose(loaded, persona.load(loaded, "newcomer"), "search")

    assert sections(composed) == [
        "# Exploratory test charter",
        "## MODE: oracle",
        "## INBOX",
        "## Reporting: GitHub issues and your run directory",
        "## TARGET: Example",
        "## PERSONA: newcomer",
        "## FOCUS: search",
    ]
    assert "+++" not in composed


def test_a_target_without_mail_or_guide_gets_explorer_mode_and_no_inbox(project):
    loaded = replace(target.load(str(project)), mail=None, guide_urls=None)

    composed = charter.compose(loaded, persona.load(loaded, "newcomer"), None)

    assert sections(composed)[1:3] == [
        "## MODE: explorer",
        "## Reporting: GitHub issues and your run directory",
    ]
