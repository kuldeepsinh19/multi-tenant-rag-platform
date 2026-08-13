"""Startup config validation: a production ENV must fail fast on an insecure setup (weak
JWT secret, missing provider API keys), while non-production stays frictionless. These are
pure unit tests on Settings — no DB, no app."""

import secrets

import pytest
from pydantic import ValidationError

from src.core.config import Settings

_STRONG_SECRET = secrets.token_urlsafe(48)


def _prod_settings(**overrides: object) -> Settings:
    """Build a production-shaped Settings, overriding individual fields per test.

    `BaseSettings.__init__` declares typed keyword-only parameters (`_env_file`,
    `_cli_parse_args`, ...), so mypy cannot match a `**dict[str, object]` splat against it.
    The values are validated by pydantic at runtime, which is the whole point of these
    tests. Suppressed once here rather than at each call site — same approach as
    tests/llm/test_registry.py.
    """
    kwargs: dict[str, object] = {
        "env": "production",
        "jwt_secret": _STRONG_SECRET,
        "llm_provider": "gemini",
        "llm_fallback_provider": "gemini",
        "embed_provider": "gemini",
        "groq_api_key": "test-groq-key",
        "gemini_api_key": "test-gemini-key",
    }
    kwargs.update(overrides)
    return Settings(**kwargs)  # type: ignore[arg-type]


def test_production_rejects_placeholder_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        _prod_settings(jwt_secret="change-me-to-a-long-random-value")


def test_production_rejects_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        _prod_settings(jwt_secret="tooshort")


def test_production_requires_selected_provider_api_key() -> None:
    with pytest.raises(ValidationError, match="Missing API key"):
        _prod_settings(gemini_api_key="")


def test_production_valid_config_passes_and_disables_docs() -> None:
    settings = _prod_settings()
    assert settings.is_production is True
    assert settings.docs_enabled is False


def test_development_skips_strict_checks_and_enables_docs() -> None:
    # A placeholder secret and blank provider keys are tolerated in development.
    settings = Settings(
        env="development",
        jwt_secret="change-me-to-a-long-random-value",
        groq_api_key="",
        gemini_api_key="",
    )
    assert settings.is_production is False
    assert settings.docs_enabled is True
