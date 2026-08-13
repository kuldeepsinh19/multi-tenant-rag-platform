"""Regression tests for `content_to_text` (src/llm/_langchain_bridge.py).

gemini-2.5-class "thinking" models return message `content` as a LIST of parts rather
than a `str`. The old adapters did `str(response.content)`, which produced a Python repr
of the list and broke downstream JSON parsing. `content_to_text` must flatten a list to
just the concatenated text of its text parts, ignoring reasoning/signature parts.
"""

from typing import Any

from src.llm._langchain_bridge import content_to_text


def test_plain_string_passes_through() -> None:
    assert content_to_text("hello world") == "hello world"


def test_list_of_text_parts_concatenates() -> None:
    content: list[Any] = [
        {"type": "text", "text": "Hello, "},
        {"type": "text", "text": "world"},
    ]
    assert content_to_text(content) == "Hello, world"


def test_list_mixing_text_and_thinking_yields_only_text() -> None:
    content: list[Any] = [
        {"type": "text", "text": "The answer is 42."},
        {"type": "thinking", "thinking": "let me reason about this..."},
    ]
    assert content_to_text(content) == "The answer is 42."


def test_list_ignores_signature_extras_dict_without_text() -> None:
    content: list[Any] = [
        {"type": "text", "text": "final answer"},
        {"type": "signature", "signature": "abc123"},
    ]
    assert content_to_text(content) == "final answer"


def test_bare_string_parts_in_list_are_included() -> None:
    content: list[Any] = ["a", {"type": "text", "text": "b"}, "c"]
    assert content_to_text(content) == "abc"


def test_empty_list_yields_empty_string() -> None:
    assert content_to_text([]) == ""


def test_non_str_non_list_falls_back_to_str() -> None:
    assert content_to_text(123) == "123"
