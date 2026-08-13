"""The single place that turns config into live provider instances.

Swapping `LLM_PROVIDER` / `EMBED_PROVIDER` in env is the *only* change needed to switch
providers — nothing outside this file and src/llm/adapters/ knows a vendor SDK exists.
Adding a new provider (OpenAI, Anthropic, Ollama, ...) means: write one adapter file that
satisfies LLMProvider/EmbeddingProvider, register it in `_CHAT_ADAPTERS`/`_EMBED_ADAPTERS`
below, done.
"""

from collections.abc import AsyncIterator, Callable
from functools import lru_cache
from typing import Any

from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from src.core.config import Settings, get_settings
from src.core.exceptions import ProviderUnavailable
from src.core.logging import get_logger
from src.llm.adapters.gemini_embeddings import GeminiEmbeddings
from src.llm.adapters.gemini_provider import GeminiProvider
from src.llm.adapters.groq_provider import GroqProvider
from src.llm.base import ChatMessage, EmbeddingProvider, LLMProvider
from src.llm.circuit_breaker import CircuitBreaker
from src.llm.resilience import is_retryable

logger = get_logger(__name__)

_CHAT_ADAPTERS: dict[str, Callable[[Settings, str], LLMProvider]] = {
    "groq": lambda s, model: GroqProvider(api_key=s.groq_api_key, model=model),
    "gemini": lambda s, model: GeminiProvider(api_key=s.gemini_api_key, model=model),
}

_EMBED_ADAPTERS: dict[str, Callable[[Settings], EmbeddingProvider]] = {
    "gemini": lambda s: GeminiEmbeddings(
        api_key=s.gemini_api_key, model=s.embed_model, dim=s.embed_dim
    ),
}


def _build_chat_adapter(provider: str, model: str, settings: Settings) -> LLMProvider:
    try:
        builder = _CHAT_ADAPTERS[provider]
    except KeyError:
        raise ValueError(
            f"Unknown LLM provider {provider!r}. Known providers: {sorted(_CHAT_ADAPTERS)}"
        ) from None
    return builder(settings, model)


def _build_embedding_adapter(provider: str, settings: Settings) -> EmbeddingProvider:
    try:
        builder = _EMBED_ADAPTERS[provider]
    except KeyError:
        raise ValueError(
            f"Unknown embedding provider {provider!r}. Known providers: {sorted(_EMBED_ADAPTERS)}"
        ) from None
    return builder(settings)


class ResilientLLM:
    """Wraps a primary + fallback LLMProvider with retry/backoff and a circuit breaker,
    so a primary provider outage degrades to the fallback instead of failing every
    request. Itself satisfies LLMProvider, so callers never know a fallback exists."""

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self._primary = primary
        self._fallback = fallback
        self._breaker = CircuitBreaker()

    async def chat(self, messages: list[ChatMessage], **kwargs: Any) -> str:
        if not self._breaker.is_open():
            try:
                result = await self._retrying_chat(self._primary, messages, kwargs)
                self._breaker.record_success()
                return result
            except Exception:
                logger.warning("llm_primary_failed", exc_info=True)
                self._breaker.record_failure()
        try:
            return await self._retrying_chat(self._fallback, messages, kwargs)
        except Exception as exc:
            logger.error("llm_fallback_failed", exc_info=True)
            raise ProviderUnavailable() from exc

    async def stream(
        self, messages: list[ChatMessage], **kwargs: Any
    ) -> AsyncIterator[str]:
        if not self._breaker.is_open():
            try:
                agen = self._primary.stream(messages, **kwargs)
                first_chunk = await agen.__anext__()
            except StopAsyncIteration:
                self._breaker.record_success()
                return
            except Exception:
                logger.warning("llm_primary_stream_failed", exc_info=True)
                self._breaker.record_failure()
            else:
                self._breaker.record_success()
                yield first_chunk
                async for chunk in agen:
                    yield chunk
                return
        try:
            async for chunk in self._fallback.stream(messages, **kwargs):
                yield chunk
        except Exception as exc:
            logger.error("llm_fallback_stream_failed", exc_info=True)
            raise ProviderUnavailable() from exc

    @staticmethod
    async def _retrying_chat(
        provider: LLMProvider, messages: list[ChatMessage], kwargs: dict[str, Any]
    ) -> str:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, max=4),
            retry=retry_if_exception(is_retryable),
            reraise=True,
        ):
            with attempt:
                return await provider.chat(messages, **kwargs)
        raise AssertionError("unreachable")  # AsyncRetrying always returns or raises


@lru_cache
def get_llm() -> LLMProvider:
    settings = get_settings()
    primary = _build_chat_adapter(settings.llm_provider, settings.llm_model, settings)
    fallback = _build_chat_adapter(
        settings.llm_fallback_provider, settings.llm_fallback_model, settings
    )
    return ResilientLLM(primary, fallback)


@lru_cache
def get_embedder() -> EmbeddingProvider:
    settings = get_settings()
    return _build_embedding_adapter(settings.embed_provider, settings)
