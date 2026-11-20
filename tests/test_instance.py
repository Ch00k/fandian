from dataclasses import replace

import pytest

from fandian import instance, target


@pytest.fixture
def pilot(project):
    return target.load(str(project))


def test_the_instance_runs_on_the_runs_network_with_its_profiles_environment(pilot):
    argv = instance.instance_argv(pilot, "fandian-x")

    assert argv[argv.index("--name") + 1] == "fandian-x-instance"
    assert argv[argv.index("--network") + 1] == "fandian-x"
    assert argv[argv.index("--label") + 1] == "fandian.run=fandian-x"
    assert "SMTP_HOST=mailpit" in argv
    assert "-p" not in argv
    image = argv.index("fandian-target-example-app:latest")
    assert tuple(argv[image + 1 :]) == pilot.instance.command


def test_mailpit_answers_as_mailpit_and_refuses_what_the_allow_list_does_not_match(pilot):
    argv = instance.mailpit_argv(pilot, "fandian-x")

    assert argv[argv.index("--network-alias") + 1] == "mailpit"
    assert r"MP_SMTP_ALLOWED_RECIPIENTS=@example\.[a-z]+$" in argv
    assert argv[-1] == instance.MAILPIT_IMAGE


def test_mailpit_without_an_allow_list_takes_every_recipient(pilot):
    argv = instance.mailpit_argv(replace(pilot, mail=target.Mail(None)), "fandian-x")

    assert not any(arg.startswith("MP_SMTP_ALLOWED_RECIPIENTS") for arg in argv)


def test_a_probe_runs_unprivileged_in_the_agents_image():
    argv = instance.probe_argv("container:fandian-x-instance", "curl -fsS http://localhost/")

    assert argv[argv.index("--network") + 1] == "container:fandian-x-instance"
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert argv[-4:] == [instance.AGENT_IMAGE, "bash", "-c", "curl -fsS http://localhost/"]
