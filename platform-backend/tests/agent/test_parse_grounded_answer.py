"""Structured-output parsing for the agent's draft answer.

This is the Instructor role in the pipeline: the model is *asked* for JSON, but a model
that returns prose, a fenced block, or malformed JSON must never be silently passed through
as an answer. `_parse_grounded_answer` returning None routes the graph to retry/escalate, so
every failure mode below must produce None rather than a partially-parsed GroundedAnswer.

tests/agent/test_graph.py covers the graph's routing; this covers the parser it depends on."""

from src.agent.graph import _parse_grounded_answer
from src.guardrails.output import GroundedAnswer


def test_parses_a_bare_json_object() -> None:
    parsed = _parse_grounded_answer('{"answer": "Refunds take 30 days.", "citations": ["d1"]}')

    assert parsed == GroundedAnswer(answer="Refunds take 30 days.", citations=["d1"])


def test_parses_json_wrapped_in_a_json_fence() -> None:
    raw = '```json\n{"answer": "Refunds take 30 days.", "citations": ["d1"]}\n```'

    parsed = _parse_grounded_answer(raw)

    assert parsed is not None
    assert parsed.answer == "Refunds take 30 days."
    assert parsed.citations == ["d1"]


def test_parses_json_wrapped_in_a_bare_fence() -> None:
    raw = '```\n{"answer": "Refunds take 30 days.", "citations": ["d1"]}\n```'

    parsed = _parse_grounded_answer(raw)

    assert parsed is not None
    assert parsed.answer == "Refunds take 30 days."


def test_parses_json_surrounded_by_prose() -> None:
    # Chatty models prepend "Sure! Here's the JSON:" — the find/rfind slice
    # recovers the object rather than discarding an otherwise valid answer.
    raw = (
        "Sure! Here you go:\n"
        '{"answer": "Refunds take 30 days.", "citations": ["d1"]}\n'
        "Hope that helps!"
    )

    parsed = _parse_grounded_answer(raw)

    assert parsed is not None
    assert parsed.answer == "Refunds take 30 days."


def test_parses_json_with_surrounding_whitespace() -> None:
    parsed = _parse_grounded_answer('\n\n  {"answer": "ok", "citations": []}  \n\n')

    assert parsed is not None
    assert parsed.answer == "ok"


def test_parses_an_answer_with_no_citations() -> None:
    # Valid shape: an ungrounded answer still parses, and is rejected later by
    # enforce_grounded rather than here.
    parsed = _parse_grounded_answer('{"answer": "I am not sure.", "citations": []}')

    assert parsed is not None
    assert parsed.citations == []


def test_omitted_citations_default_to_empty() -> None:
    parsed = _parse_grounded_answer('{"answer": "I am not sure."}')

    assert parsed is not None
    assert parsed.citations == []


def test_dedups_repeated_citations_during_validation() -> None:
    parsed = _parse_grounded_answer('{"answer": "ok", "citations": ["d1", "d1", "d2"]}')

    assert parsed is not None
    assert parsed.citations == ["d1", "d2"]


def test_returns_none_for_plain_prose() -> None:
    assert _parse_grounded_answer("Refunds take 30 days.") is None


def test_returns_none_for_malformed_json() -> None:
    assert _parse_grounded_answer('{"answer": "unterminated, "citations": [}') is None


def test_returns_none_for_an_empty_string() -> None:
    assert _parse_grounded_answer("") is None


def test_returns_none_for_whitespace_only_output() -> None:
    assert _parse_grounded_answer("   \n\t  ") is None


def test_returns_none_when_the_required_answer_field_is_missing() -> None:
    assert _parse_grounded_answer('{"citations": ["d1"]}') is None


def test_returns_none_for_an_empty_answer_string() -> None:
    # GroundedAnswer pins min_length=1 — an empty answer is not an answer.
    assert _parse_grounded_answer('{"answer": "", "citations": ["d1"]}') is None


def test_returns_none_when_citations_are_not_a_list() -> None:
    assert _parse_grounded_answer('{"answer": "ok", "citations": "d1"}') is None


def test_returns_none_for_a_json_array_rather_than_an_object() -> None:
    assert _parse_grounded_answer('["not", "an", "object"]') is None


def test_never_passes_raw_text_through_as_the_answer() -> None:
    # The central safety property: a failed parse must not degrade into
    # "return whatever the model said".
    for raw in ["I refuse.", "```json\nnot json\n```", "{", "}"]:
        assert _parse_grounded_answer(raw) is None
