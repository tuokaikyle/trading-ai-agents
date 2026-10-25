import pytest

from trading_ai_agents.config import Settings


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    monkeypatch.setattr("trading_ai_agents.config.load_dotenv", lambda: None)
    for name in (
        "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL",
        "LLM_THINKING", "LLM_REASONING_EFFORT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_key_alone_uses_deepseek_defaults(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-only")
    settings = Settings.from_env()
    assert settings.model == "deepseek-flash"
    assert settings.base_url == "https://api.deepseek.com"
    assert settings.thinking is None
    assert settings.reasoning_effort is None
    client = settings.create_model()
    assert client.model_name == settings.model
    assert str(client.openai_api_base) == settings.base_url
    assert client.openai_api_key.get_secret_value() == "test-only"
    assert "test-only" not in repr(settings)


def test_model_and_endpoint_come_from_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", " test-only ")
    monkeypatch.setenv("LLM_MODEL", "custom-model")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1/")
    assert Settings.from_env() == Settings(
        "custom-model", "http://localhost:11434/v1", "test-only",
    )


def test_blank_overrides_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-only")
    monkeypatch.setenv("LLM_MODEL", "  ")
    monkeypatch.setenv("LLM_BASE_URL", "")
    settings = Settings.from_env()
    assert settings.model == "deepseek-flash"
    assert settings.base_url == "https://api.deepseek.com"


def test_invalid_base_url_is_rejected(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-only")
    monkeypatch.setenv("LLM_BASE_URL", "api.example.com/v1")
    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        Settings.from_env()


def test_missing_key_explains_setup():
    with pytest.raises(ValueError, match="Set LLM_API_KEY"):
        Settings.from_env()


@pytest.mark.parametrize("env, attribute, expected", [
    ({"LLM_THINKING": "disabled"}, "extra_body", {"thinking": {"type": "disabled"}}),
    ({"LLM_REASONING_EFFORT": "high"}, "reasoning_effort", "high"),
])
def test_thinking_controls_are_forwarded(monkeypatch, env, attribute, expected):
    monkeypatch.setenv("LLM_API_KEY", "test-only")
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    client = Settings.from_env().create_model()
    assert getattr(client, attribute) == expected


def test_thinking_controls_are_mutually_exclusive(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-only")
    monkeypatch.setenv("LLM_THINKING", "disabled")
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    with pytest.raises(ValueError, match="not both"):
        Settings.from_env()


@pytest.mark.parametrize("name, value", [
    ("LLM_THINKING", "maybe"),
    ("LLM_REASONING_EFFORT", "extreme"),
])
def test_invalid_thinking_value_is_rejected(monkeypatch, name, value):
    monkeypatch.setenv("LLM_API_KEY", "test-only")
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        Settings.from_env()
