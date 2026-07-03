from app.core.config import Settings, get_settings


def test_settings_defaults_ignore_missing_env_file(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.ENV == "local"
    assert settings.DATABASE_URL == "sqlite+aiosqlite:///./pluto.db"
    assert settings.SQL_ECHO is False
    assert settings.OPENAI_API_KEY is None
    assert settings.ANTHROPIC_API_KEY is None
    assert settings.OPENROUTER_API_KEY is None
    assert settings.LLM_PROVIDER == "openai"
    assert settings.LLM_MODEL == "gpt-5.2"
    assert settings.ADMIN_TOKEN is None


def test_settings_env_override_tolerates_legacy_keys(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "ENV=test",
                "DATABASE_URL=sqlite+aiosqlite:///./override.db",
                "SQL_ECHO=true",
                "OPENAI_API_KEY=openai-key",
                "ANTHROPIC_API_KEY=anthropic-key",
                "OPENROUTER_API_KEY=openrouter-key",
                "LLM_PROVIDER=anthropic",
                "LLM_MODEL=claude-test",
                "ADMIN_TOKEN=admin-token",
                "DATABASE_URI=legacy-value",
                "ODDS_API_KEY=legacy-odds",
            ]
        )
    )

    settings = Settings()

    assert settings.ENV == "test"
    assert settings.DATABASE_URL == "sqlite+aiosqlite:///./override.db"
    assert settings.SQL_ECHO is True
    assert settings.OPENAI_API_KEY == "openai-key"
    assert settings.ANTHROPIC_API_KEY == "anthropic-key"
    assert settings.OPENROUTER_API_KEY == "openrouter-key"
    assert settings.LLM_PROVIDER == "anthropic"
    assert settings.LLM_MODEL == "claude-test"
    assert settings.ADMIN_TOKEN == "admin-token"
