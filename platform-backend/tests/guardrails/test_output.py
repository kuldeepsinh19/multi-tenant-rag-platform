"""Unit tests for the output groundedness gate + citation enforcement."""

import pytest

from src.core.exceptions import GuardrailBlocked
from src.guardrails.output import (
    INSUFFICIENT_CONTEXT,
    GroundedAnswer,
    assert_grounded,
    citations_are_real,
    enforce_grounded,
)


def test_citations_are_real_true_when_all_cited_retrieved() -> None:
    answer = GroundedAnswer(answer="Refunds take 30 days.", citations=["doc-1"])
    assert citations_are_real(answer, {"doc-1", "doc-2"})


def test_citations_are_real_false_when_cited_id_not_retrieved() -> None:
    answer = GroundedAnswer(answer="Refunds take 30 days.", citations=["doc-99"])
    assert not citations_are_real(answer, {"doc-1", "doc-2"})


def test_no_citation_fails_the_gate() -> None:
    # A substantive answer with no citation is not grounded.
    answer = GroundedAnswer(answer="Refunds take 30 days.", citations=[])
    assert not citations_are_real(answer, {"doc-1"})
    assert not enforce_grounded(answer, {"doc-1"})


def test_insufficient_context_is_not_a_grounded_answer() -> None:
    answer = GroundedAnswer(answer=INSUFFICIENT_CONTEXT, citations=[])
    assert answer.is_insufficient()
    assert not enforce_grounded(answer, {"doc-1"})


def test_enforce_grounded_passes_valid_answer() -> None:
    answer = GroundedAnswer(answer="Yes, within 30 days.", citations=["doc-1"])
    assert enforce_grounded(answer, {"doc-1"})


def test_assert_grounded_raises_on_fabricated_citation() -> None:
    answer = GroundedAnswer(answer="Made up.", citations=["ghost"])
    with pytest.raises(GuardrailBlocked):
        assert_grounded(answer, {"doc-1"})


def test_citations_deduped() -> None:
    answer = GroundedAnswer(answer="x", citations=["a", "a", "b"])
    assert answer.citations == ["a", "b"]
