import pytest
from conftest import write

from fandian import persona, target
from fandian.header import HeaderError


def test_a_generic_persona_loads_with_its_body(project):
    explorer = persona.load(target.load(str(project)), "explorer")

    assert explorer.enabled
    assert explorer.account == "user"
    assert explorer.body.startswith("## PERSONA: explorer\n")


def test_a_project_adds_personas_of_its_own(project):
    write(project, "personas/accountant.md", '+++\nenabled = true\naccount = "user"\n+++\n\nBody\n')
    loaded = target.load(str(project))

    assert "accountant" in persona.paths(loaded)
    assert persona.load(loaded, "accountant").body == "Body\n"


def test_a_name_both_define_is_refused(project):
    write(project, "personas/explorer.md", "+++\nenabled = true\n+++\n")

    with pytest.raises(HeaderError, match="already has: explorer"):
        persona.load(target.load(str(project)), "explorer")


def test_an_unknown_persona_is_refused_with_the_ones_there_are(project):
    with pytest.raises(HeaderError, match="No persona 'nobody'; there are: explorer"):
        persona.load(target.load(str(project)), "nobody")


def test_every_generic_persona_names_a_role_the_convention_defines(project):
    for name in persona.paths(target.load(str(project))):
        assert persona.load(target.load(str(project)), name).account in (None, "user", "empty")
