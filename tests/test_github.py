import pytest

from fandian import github
from fandian.api import ApiError

TOKEN = "github_pat_test"
REPO = "owner/project"


class GitHub:
    """The API calls github.check makes, answered from a repository's state, and recorded."""

    def __init__(self, labels=(), private=True, has_issues=True, refuse=None):
        self.labels = set(labels)
        self.repo = {"private": private, "has_issues": has_issues}
        # (method, status): the first call of that method fails with that status.
        self.refuse = refuse
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method, url, *, body=None, headers=None, params=None):
        assert headers["Authorization"] == f"Bearer {TOKEN}"
        self.calls.append((method, url.removeprefix(github.API)))
        if self.refuse is not None and self.refuse[0] == method:
            raise ApiError(method, url, self.refuse[1], "refused")
        if method == "GET" and url.endswith("/labels"):
            names = sorted(self.labels)[(params["page"] - 1) * 100 : params["page"] * 100]
            return [{"name": name} for name in names]
        if method == "GET":
            return self.repo
        if method == "POST":
            self.labels.add(body["name"])
        return {}


def test_a_token_that_reaches_the_repository_creates_the_missing_labels(monkeypatch):
    api = GitHub(labels=["fandian", "bug"])
    monkeypatch.setattr(github, "call", api)

    wanted = github.labels("explorer", "invoices")
    assert github.check(TOKEN, REPO, wanted) == "private"

    assert set(wanted) <= api.labels
    created = [url for method, url in api.calls if method == "POST"]
    assert len(created) == len(wanted) - 1
    assert ("PATCH", f"/repos/{REPO}/labels/fandian") in api.calls


def test_labels_cover_every_severity_oracle_and_the_runs_persona_and_focus():
    wanted = github.labels("explorer", "invoices")

    assert {"fandian", "fandian-run", "fandian:appears-fixed"} <= set(wanted)
    assert {f"severity:{s}" for s in ("blocker", "major", "minor", "cosmetic")} <= set(wanted)
    assert "oracle:guide" in wanted and "oracle:conventions" in wanted
    assert {"persona:explorer", "focus:invoices"} <= set(wanted)
    assert "focus:invoices" not in github.labels("explorer", None)


def test_every_label_page_is_read(monkeypatch):
    many = [f"label-{i:03}" for i in range(150)] + list(github.LABELS) + ["persona:explorer"]
    api = GitHub(labels=many)
    monkeypatch.setattr(github, "call", api)

    github.check(TOKEN, REPO, github.labels("explorer", None))

    assert not [call for call in api.calls if call[0] == "POST"]


def test_a_public_repository_is_reported_as_such(monkeypatch):
    monkeypatch.setattr(github, "call", GitHub(private=False))

    assert github.check(TOKEN, REPO, github.labels("explorer", None)) == "public"


@pytest.mark.parametrize("token", ["", "ghp_classic", "gho_oauth"])
def test_only_a_fine_grained_token_is_accepted(token):
    with pytest.raises(github.TokenError):
        github.check(token, REPO, github.LABELS)


@pytest.mark.parametrize(
    ("api", "problem"),
    [
        (GitHub(refuse=("GET", 401)), "refuses it"),
        (GitHub(refuse=("GET", 404)), "does not reach owner/project"),
        (GitHub(has_issues=False), "issues switched off"),
        (GitHub(refuse=("POST", 403)), "cannot write issues"),
        (GitHub(labels=github.LABELS, refuse=("PATCH", 403)), "cannot write issues"),
    ],
)
def test_a_token_that_cannot_file_findings_is_refused(monkeypatch, api, problem):
    monkeypatch.setattr(github, "call", api)

    with pytest.raises(github.TokenError, match=problem):
        github.check(TOKEN, REPO, github.labels("explorer", None))


def test_an_outage_is_raised_as_it_is(monkeypatch):
    monkeypatch.setattr(github, "call", GitHub(refuse=("GET", 502)))

    with pytest.raises(ApiError):
        github.check(TOKEN, REPO, github.LABELS)
