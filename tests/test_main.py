import sys

from fandian import main


def no_run(*_args, **_kwargs):
    raise AssertionError("--charter started a run")


def test_charter_shows_the_composed_charter_and_starts_no_run(project, monkeypatch, capsys):
    """Without a terminal the pager prints the charter as it is."""
    monkeypatch.setattr(sys, "argv", ["fand", "run", str(project), "newcomer", "--charter"])
    monkeypatch.setattr(
        main, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError)
    )

    main.main()

    shown = capsys.readouterr().out
    assert shown.startswith("# Exploratory test charter\n")
    assert "## PERSONA: newcomer" in shown
