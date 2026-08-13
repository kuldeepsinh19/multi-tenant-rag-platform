"""Proves the core loose-coupling guarantee: which provider gets constructed is decided
entirely by a config string, never by which code path runs. Swapping LLM_PROVIDER in
.env is the only change required to switch providers."""

import pytest

from src.core.config import Settings
from src.llm.adapters.gemini_embeddings import GeminiEmbeddings
from src.llm.adapters.gemini_provider import GeminiProvider
from src.llm.adapters.groq_provider import GroqProvider
from src.llm.registry import _build_chat_adapter, _build_embedding_adapter


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "jwt_secret": "test-secret",
        "groq_api_key": "test-groq-key",
        "gemini_api_key": "test-gemini-key",
    }
    return Settings(**{**defaults, **overrides})  # type: ignore[arg-type]


def test_build_chat_adapter_selects_groq() -> None:
    adapter = _build_chat_adapter("groq", "llama-3.3-70b-versatile", _settings())
    assert isinstance(adapter, GroqProvider)


def test_build_chat_adapter_selects_gemini() -> None:
    adapter = _build_chat_adapter("gemini", "gemini-2.0-flash", _settings())
    assert isinstance(adapter, GeminiProvider)


def test_build_chat_adapter_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        _build_chat_adapter("openai", "gpt-4", _settings())


def test_build_embedding_adapter_selects_gemini() -> None:
    settings = _settings()
    adapter = _build_embedding_adapter("gemini", settings)
    assert isinstance(adapter, GeminiEmbeddings)
    assert adapter.dim == settings.embed_dim


def test_build_embedding_adapter_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        _build_embedding_adapter("openai", _settings())


def test_swapping_llm_provider_env_value_changes_the_adapter_with_no_code_change() -> None:
    settings = _settings(llm_provider="gemini", llm_fallback_provider="groq")
    primary = _build_chat_adapter(settings.llm_provider, settings.llm_model, settings)
    fallback = _build_chat_adapter(
        settings.llm_fallback_provider, settings.llm_fallback_model, settings
    )
    assert isinstance(primary, GeminiProvider)
    assert isinstance(fallback, GroqProvider)
