"""The target's GitHub repository, where findings are filed as issues, and the token the agent
files them with. `run` checks the token here and creates the labels the agent uses, so a run
never starts with a token that cannot file a finding."""

import urllib.parse

from .api import ApiError, call

API = "https://api.github.com"

# Every label the agent uses, with its colour and description. The persona's and the focus's
# labels are added per run (labels()).
_SEVERITY = "b60205"
_ORACLE = "5319e7"
LABELS = {
    "fandian": ("d93f0b", "A finding of the exploratory tester"),
    "fandian-run": ("c5def5", "The exploratory tester's record of one run"),
    "fandian:appears-fixed": ("0e8a16", "The exploratory tester no longer reproduces it"),
    **{
        f"severity:{severity}": (_SEVERITY, description)
        for severity, description in (
            ("blocker", "Stops a core task, loses data or opens a security hole"),
            ("major", "Breaks a feature, or gives a wrong answer a user would act on"),
            ("minor", "Works around a defect, or confuses without misleading"),
            ("cosmetic", "Looks wrong, works right"),
        )
    },
    **{
        f"oracle:{layer}": (_ORACLE, description)
        for layer, description in (
            ("guide", "Diverges from the user guide"),
            ("mechanical", "A crash, an error response, a broken link or overflowing layout"),
            ("claims", "Contradicts what the product says about itself"),
            ("invariants", "Breaks a property any app should hold"),
            ("consistency", "The product contradicts itself"),
            ("purpose", "Defeats what the product is for"),
            ("conventions", "Surprises a user of an ordinary control"),
        )
    },
}


class TokenError(Exception):
    pass


def labels(persona: str, focus: str | None) -> dict[str, tuple[str, str]]:
    """The labels a run of this persona, on this focus, may use."""
    found = LABELS | {f"persona:{persona}": ("1d76db", f"Found by the {persona} persona")}
    if focus is not None:
        found[f"focus:{focus}"] = ("fbca04", f"In the {focus} focus")
    return found


def check(token: str, repo: str, wanted: dict[str, tuple[str, str]]) -> str:
    """The repository's visibility ("private" or "public"), once the token can file findings in it
    and every wanted label exists; TokenError if it cannot.

    Only a fine-grained token can be confined to one repository. One reaching the repository proves
    it can read; saving the `fandian` label unchanged proves it can write issues. A token GitHub
    refuses is reported as such; any other failure is raised as it is, so an outage is not taken
    for a bad token."""
    if not token:
        raise TokenError("it is not set")
    if not token.startswith("github_pat_"):
        raise TokenError("it is not a fine-grained token (github_pat_...)")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        info = call("GET", f"{API}/repos/{repo}", headers=headers)
    except ApiError as e:
        if e.status == 401:
            raise TokenError("GitHub refuses it (401; expired or revoked?)") from None
        if e.status in (403, 404):
            raise TokenError(f"it does not reach {repo}") from None
        raise
    if not info.get("has_issues"):
        raise TokenError(f"{repo} has issues switched off")

    try:
        existing = _label_names(repo, headers)
        for name, (color, description) in wanted.items():
            if name not in existing:
                body = {"name": name, "color": color, "description": description}
                call("POST", f"{API}/repos/{repo}/labels", body=body, headers=headers)
        color, description = wanted["fandian"]
        call(
            "PATCH",
            f"{API}/repos/{repo}/labels/{urllib.parse.quote('fandian', safe='')}",
            body={"color": color, "description": description},
            headers=headers,
        )
    except ApiError as e:
        if e.status == 403:
            raise TokenError(
                f"it cannot write issues in {repo}; give it Issues read and write"
            ) from None
        raise

    return "private" if info["private"] else "public"


def _label_names(repo: str, headers: dict[str, str]) -> set[str]:
    names: set[str] = set()
    page = 1
    while True:
        found = call(
            "GET",
            f"{API}/repos/{repo}/labels",
            headers=headers,
            params={"per_page": 100, "page": page},
        )
        names |= {label["name"] for label in found}
        if len(found) < 100:
            return names
        page += 1
