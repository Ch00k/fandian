from fandian import env


def test_a_setting_comes_from_env_file(env_file):
    env_file.write_text("FANDIAN_CLAUDE_TOKEN=from-file\nOTHER=x\n")

    assert env.setting("CLAUDE_TOKEN") == "from-file"


def test_the_environment_overrides_the_file(env_file, monkeypatch):
    env_file.write_text("FANDIAN_CLAUDE_TOKEN=from-file\n")
    monkeypatch.setenv("FANDIAN_CLAUDE_TOKEN", "from-env")

    assert env.setting("CLAUDE_TOKEN") == "from-env"


def test_a_setting_set_nowhere_is_empty(env_file):
    assert env.setting("CLAUDE_TOKEN") == ""
