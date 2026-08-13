"""The SSE wire format is a contract between this service and two independent clients
(the dashboard's src/api/sse.ts and the widget's duplicated copy). Both split frames on a
blank line and JSON-parse everything after `data:`, so the exact bytes `_sse` emits are
load-bearing — a stray newline or a missing terminator silently truncates the answer in the
browser.

`_tokenize`'s round-trip property is the other half of that contract: the client
concatenates token frames with no separator, so joining the tokens must reproduce the
answer character for character."""

import json

import pytest

from src.chat.service import _estimate_tokens, _sse, _tokenize


def test_sse_frame_has_the_data_prefix_and_blank_line_terminator() -> None:
    frame = _sse({"token": "Hello"})

    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")


def test_sse_frame_contains_exactly_one_event() -> None:
    # Clients split on "\n\n"; an extra terminator would emit a phantom frame.
    frame = _sse({"token": "Hello"})

    assert frame.count("\n\n") == 1


def test_sse_payload_round_trips_through_json() -> None:
    payload: dict[str, object] = {
        "done": True,
        "citations": [{"doc_id": "d1", "title": "handbook.pdf"}],
    }

    frame = _sse(payload)
    decoded = json.loads(frame.removeprefix("data: ").rstrip("\n"))

    assert decoded == payload


def test_sse_escapes_newlines_inside_the_payload() -> None:
    # A raw newline in the JSON body would terminate the frame early and the
    # client would drop the rest of the token.
    frame = _sse({"token": "line one\nline two"})

    assert frame.count("\n") == 2  # only the two terminator newlines
    assert "\\n" in frame


def test_sse_escapes_a_double_newline_inside_the_payload() -> None:
    frame = _sse({"token": "para one\n\npara two"})

    assert frame.count("\n\n") == 1
    assert json.loads(frame.removeprefix("data: ").rstrip("\n"))["token"] == "para one\n\npara two"


def test_sse_handles_non_ascii_content() -> None:
    frame = _sse({"token": "café — naïve 日本語"})

    decoded = json.loads(frame.removeprefix("data: ").rstrip("\n"))
    assert decoded["token"] == "café — naïve 日本語"


def test_sse_emits_an_empty_citations_list_rather_than_omitting_it() -> None:
    decoded = json.loads(_sse({"done": True, "citations": []}).removeprefix("data: ").rstrip("\n"))

    assert decoded["citations"] == []


@pytest.mark.parametrize(
    "text",
    [
        "Refunds take 30 days.",
        "single",
        "  leading and trailing  ",
        "multiple   consecutive   spaces",
        "line one\nline two",
        "tabs\tand\tspaces here",
        "café — naïve 日本語",
        "trailing space ",
        " ",
    ],
)
def test_tokenize_round_trips_exactly(text: str) -> None:
    # The client does `content + event.token` with no separator, so this join
    # must be lossless or the rendered answer diverges from the stored one.
    assert "".join(_tokenize(text)) == text


def test_tokenize_returns_nothing_for_an_empty_string() -> None:
    assert _tokenize("") == []


def test_tokenize_keeps_the_space_attached_to_the_preceding_token() -> None:
    assert _tokenize("a b") == ["a ", "b"]


def test_tokenize_emits_a_token_per_word_plus_remainder() -> None:
    assert _tokenize("one two three") == ["one ", "two ", "three"]


def test_estimate_tokens_uses_the_four_chars_per_token_heuristic() -> None:
    assert _estimate_tokens("a" * 400) == 100


def test_estimate_tokens_sums_across_inputs() -> None:
    assert _estimate_tokens("a" * 400, "b" * 40) == 110


def test_estimate_tokens_floors_a_short_string_at_one() -> None:
    # A sub-4-character prompt still costs the provider something; billing must
    # not record it as free.
    assert _estimate_tokens("hi") == 1


def test_estimate_tokens_ignores_empty_strings() -> None:
    assert _estimate_tokens("", "a" * 400, "") == 100


def test_estimate_tokens_of_nothing_is_zero() -> None:
    assert _estimate_tokens() == 0
    assert _estimate_tokens("", "") == 0


def test_estimate_tokens_is_never_negative() -> None:
    assert _estimate_tokens("x") >= 0
