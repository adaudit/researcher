"""Tests for startup config validation — must fail fast in production."""

import pytest


def test_validation_passes_in_dev_with_no_keys(monkeypatch):
    """Development env should NOT raise even with no LLM keys configured."""
    from app.core.config import settings
    from app.core.startup_validation import validate_startup_config

    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "ZAI_API_KEY", "")
    monkeypatch.setattr(settings, "XAI_API_KEY", "")

    # Should not raise — just logs warnings
    validate_startup_config()


def test_validation_raises_in_prod_with_default_secret_key(monkeypatch):
    """Production env must raise when SECRET_KEY is the default."""
    from app.core.config import settings
    from app.core.startup_validation import validate_startup_config

    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", "change-me-in-production")

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_startup_config()


def test_validation_raises_in_prod_with_no_llm_provider(monkeypatch):
    """Production env must raise when no LLM provider is configured."""
    from app.core.config import settings
    from app.core.startup_validation import validate_startup_config

    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", "real-secret-key")
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://x")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://x")
    monkeypatch.setattr(settings, "HINDSIGHT_API_KEY", "k")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "ZAI_API_KEY", "")
    monkeypatch.setattr(settings, "XAI_API_KEY", "")

    with pytest.raises(RuntimeError, match="No LLM provider configured"):
        validate_startup_config()


def test_validation_raises_in_prod_when_required_missing(monkeypatch):
    """Production env must raise when a required key is missing."""
    from app.core.config import settings
    from app.core.startup_validation import validate_startup_config

    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", "real-secret-key")
    monkeypatch.setattr(settings, "DATABASE_URL", "")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://x")
    monkeypatch.setattr(settings, "HINDSIGHT_API_KEY", "k")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "k")

    with pytest.raises(RuntimeError, match="Required config missing"):
        validate_startup_config()


def test_validation_passes_in_prod_with_complete_config(monkeypatch):
    """Production env passes when everything required is set."""
    from app.core.config import settings
    from app.core.startup_validation import validate_startup_config

    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", "real-secret-key")
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://x")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://x")
    monkeypatch.setattr(settings, "HINDSIGHT_API_KEY", "k")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "k")

    # Should not raise
    validate_startup_config()
