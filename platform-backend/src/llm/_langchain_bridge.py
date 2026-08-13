"""Internal helper shared by adapters that happen to use LangChain's chat model interface.
Not part of the public llm/ API surface — only files under llm/adapters/ import this."""

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from src.llm.base import ChatMessage

_ROLE_TO_LC_MESSAGE: dict[str, type[BaseMessage]] = {
    "system": SystemMessage,
    "user": HumanMessage,
    "assistant": AIMessage,
}


def to_lc_messages(messages: list[ChatMessage]) -> list[BaseMessage]:
    return [_ROLE_TO_LC_MESSAGE[m.role](content=m.content) for m in messages]


def content_to_text(content: Any) -> str:
    """Flatten a LangChain message's `content` to plain text.

    Older/simple models return a `str`. Newer multimodal / "thinking" models (e.g.
    gemini-2.5 / gemini-flash-latest) return a LIST of content parts —
    `[{"type": "text", "text": "..."}, {"type": "thinking", ...}]` — where the answer text
    lives in the `text` field of the text parts. Naively `str()`-ing that list yields a
    Python repr, not the model's text, which then breaks downstream JSON parsing. This
    extracts and concatenates only the text, ignoring non-text parts (reasoning traces,
    signatures, etc.).
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content)
