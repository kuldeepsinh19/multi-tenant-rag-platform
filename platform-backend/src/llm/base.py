"""Provider-agnostic LLM/embedding contracts.

No vendor SDK (Groq, Google, OpenAI, Anthropic, ...) and no LangChain type is ever imported
outside `src/llm/adapters/`. Every other module in this codebase depends only on these
Protocols, obtained via `src.llm.registry.get_llm()` / `get_embedder()`. Swapping providers
is a config change (`LLM_PROVIDER`, `EMBED_PROVIDER`), never a code change.
"""

from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMProvider(Protocol):
    """A chat-completion provider. Implementations wrap a vendor SDK (optionally via
    LangChain's BaseChatModel) but return only plain str/ChatMessage — never a vendor or
    LangChain type — so callers stay decoupled from both."""

    async def chat(self, messages: list[ChatMessage], **kwargs: Any) -> str: ...

    def stream(self, messages: list[ChatMessage], **kwargs: Any) -> AsyncIterator[str]: ...


class EmbeddingProvider(Protocol):
    """An embedding provider. `dim` must match the pgvector column size (see
    Settings.embed_dim) — changing providers/models with a different `dim` requires a
    migration and a full re-index, not just an env change."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dim(self) -> int: ...
