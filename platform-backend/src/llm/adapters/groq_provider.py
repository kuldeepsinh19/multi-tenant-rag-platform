"""LLMProvider adapter for Groq's free-tier hosted models. This is the only file in the
codebase that imports langchain_groq — everything else depends on src.llm.base.LLMProvider."""

from collections.abc import AsyncIterator
from typing import Any

from langchain_groq import ChatGroq

from src.llm._langchain_bridge import content_to_text, to_lc_messages
from src.llm.base import ChatMessage


class GroqProvider:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30.0) -> None:
        self._client = ChatGroq(api_key=api_key, model_name=model, timeout=timeout_seconds)

    async def chat(self, messages: list[ChatMessage], **kwargs: Any) -> str:
        response = await self._client.ainvoke(to_lc_messages(messages), **kwargs)
        return content_to_text(response.content)

    async def stream(self, messages: list[ChatMessage], **kwargs: Any) -> AsyncIterator[str]:
        async for chunk in self._client.astream(to_lc_messages(messages), **kwargs):
            text = content_to_text(chunk.content)
            if text:
                yield text
