from dataclasses import replace

from conftest import write

from fandian import charter, persona, target


def sections(text: str) -> list[str]:
    """The charter's own top-level parts: its title and each section named in capitals."""
    named = (
        "## MAILBOX",
        "## HARNESS",
        "## Reporting",
        "## WHY YOU ARE HERE",
        "## PERSONA",
        "## FOCUS",
    )
    return [line for line in text.splitlines() if line.startswith("# ") or line.startswith(named)]


def test_the_charter_runs_core_mailbox_harness_reporting_motive_persona_focus(project):
    write(project, "focus/search.md", '+++\npersonas = ["newcomer"]\n+++\n\n## FOCUS: search\n')
    loaded = target.load(str(project))

    composed = charter.compose(loaded, persona.load(loaded, "newcomer"), "search")

    assert sections(composed) == [
        "# Exploratory test charter",
        "## MAILBOX",
        "## HARNESS",
        "## Reporting: GitHub issues and your run directory",
        "## WHY YOU ARE HERE",
        "## PERSONA: newcomer",
        "## FOCUS: search",
    ]
    assert "You keep examples" in composed
    assert "+++" not in composed


def test_without_mail_harness_or_an_account_the_charter_has_neither_section(project):
    loaded = target.load(str(project))
    newcomer = persona.load(loaded, "newcomer")

    for target_, persona_ in [
        (replace(loaded, mail=None, harness=None), newcomer),
        (replace(loaded, harness=None), replace(newcomer, account=None)),
    ]:
        assert sections(charter.compose(target_, persona_, None))[1:2] == [
            "## Reporting: GitHub issues and your run directory"
        ]


def test_the_charter_tells_nothing_of_how_the_product_is_set_up(project):
    """The profile's header is fandian's: its accounts, command and mail settings never reach the
    tester."""
    loaded = target.load(str(project))

    composed = charter.compose(loaded, persona.load(loaded, "newcomer"), None)

    for internal in (
        "dev@example.com",
        "devpassword",
        "seed && serve",
        "mailpit",
        "SMTP_HOST",
        "Mailpit",
    ):
        assert internal not in composed
