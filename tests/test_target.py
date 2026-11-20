import subprocess

import pytest
from conftest import PROFILE, write

from fandian import target
from fandian.header import HeaderError


def test_a_profile_loads_with_its_instance_mail_harness_and_motive(project):
    loaded = target.load(str(project))

    assert loaded.checkout == project
    assert loaded.repo == "owner/Example.app"
    assert loaded.name == "example-app"
    assert loaded.base_url == "http://localhost:8000"
    assert loaded.instance == target.Instance(
        ("sh", "-c", "seed && serve"), {"SMTP_HOST": "mailpit"}, 8000, "/health/"
    )
    assert loaded.mail == target.Mail(r"@example\.[a-z]+$")
    assert loaded.accounts == {
        "user": target.Account("dev@example.com", "devpassword"),
        "empty": target.Account("new@example.com", "devpassword"),
    }
    assert loaded.harness == "/fake/"
    assert loaded.motive == "You keep examples, and came here to keep them in one place.\n"
    assert loaded.token_setting == "GITHUB_TOKEN_OWNER_EXAMPLE_APP"


def test_a_profile_without_mail_or_harness_has_neither(project):
    text = PROFILE.replace("[mail]\nallowed_recipients = '@example\\.[a-z]+$'\n", "")
    write(project, "profile.md", text.replace('[harness]\npath = "/fake/"\n', ""))

    loaded = target.load(str(project))

    assert loaded.mail is None
    assert loaded.harness is None


def test_mail_without_an_allow_list_takes_every_recipient(project):
    write(project, "profile.md", PROFILE.replace("allowed_recipients = '@example\\.[a-z]+$'\n", ""))

    assert target.load(str(project)).mail == target.Mail(None)


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (("allowed_recipients", "allowed"), "unknown: allowed"),
        (('path = "/fake/"', 'path = "fake/"'), "path must start with /"),
        (('path = "/fake/"', 'where = "/fake/"'), "unknown: where"),
        (("You keep examples, and came here to keep them in one place.", ""), "is empty"),
        (('SMTP_HOST = "mailpit"', "SMTP_HOST = 1"), "env values must be strings"),
        (('health = "/health/"', 'health = "health"'), "health must be a path"),
        (("port = 8000\n", ""), "missing: port"),
        (('repo = "owner/Example.app"', 'repo = "example"'), "not owner/name"),
        (("[harness]", "[other]"), "unknown: other"),
    ],
)
def test_a_malformed_profile_is_refused(project, change, problem):
    write(project, "profile.md", PROFILE.replace(*change))

    with pytest.raises(HeaderError, match=problem):
        target.load(str(project))


def test_a_checkout_without_a_profile_or_a_dockerfile_is_refused(project):
    (project / "Dockerfile").unlink()
    with pytest.raises(target.TargetError, match="no Dockerfile"):
        target.load(str(project))

    (project / ".fandian" / "profile.md").unlink()
    with pytest.raises(target.TargetError, match="no .fandian/profile.md"):
        target.load(str(project))


def test_a_path_that_is_no_directory_is_refused(tmp_path):
    with pytest.raises(target.TargetError, match="not a directory"):
        target.load(str(tmp_path / "missing"))


def test_a_profile_without_a_header_is_refused(project):
    write(project, "profile.md", "## TARGET: Example\n")

    with pytest.raises(HeaderError, match="no header"):
        target.load(str(project))


@pytest.mark.parametrize(
    "location", ["https://github.com/owner/example", "git@github.com:owner/example.git"]
)
def test_a_url_names_a_repository_to_clone(location):
    assert target.is_remote(location)


def test_a_repository_is_cloned_into_the_cache_and_brought_up_to_date(
    project, tmp_path, monkeypatch
):
    """A file:// URL stands in for a forge: the first run clones, the next takes what changed."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    git = ["git", "-C", str(project), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([*git[:3], "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "profile"], check=True)

    loaded = target.load(f"file://{project}")

    owner = target.slug(project.parent.name)
    assert loaded.checkout == tmp_path / "cache" / "fandian" / owner / "example"
    assert loaded.harness == "/fake/"

    write(project, "profile.md", PROFILE.replace('[harness]\npath = "/fake/"\n', ""))
    subprocess.run([*git, "commit", "-q", "-am", "no harness"], check=True)

    assert target.load(f"file://{project}").harness is None


def test_a_focus_is_refused_for_a_persona_it_is_not_written_for(project):
    write(project, "focus/search.md", '+++\npersonas = ["newcomer"]\n+++\n\n## FOCUS\n')
    loaded = target.load(str(project))

    target.check_focus(loaded, "search", "newcomer")
    with pytest.raises(HeaderError, match="written for newcomer, not tourist"):
        target.check_focus(loaded, "search", "tourist")


def test_a_missing_focus_is_refused(project):
    with pytest.raises(HeaderError, match="does not exist"):
        target.check_focus(target.load(str(project)), "nothing", "newcomer")
