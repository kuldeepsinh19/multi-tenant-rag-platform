"""Guard for the agent generate/retrieve timeout constants (src/agent/graph.py).

The timeouts were raised (retrieve 15->30s, generate 30->90s) because gemini "thinking"
models are slow to first token. Generation must always be allowed at least as long as
retrieval; this cheap guard stops anyone accidentally setting generate below retrieve.
"""

from src.agent.graph import _GENERATE_TIMEOUT_S, _RETRIEVE_TIMEOUT_S


def test_timeouts_are_positive() -> None:
    assert _RETRIEVE_TIMEOUT_S > 0
    assert _GENERATE_TIMEOUT_S > 0


def test_generate_timeout_at_least_retrieve_timeout() -> None:
    assert _GENERATE_TIMEOUT_S >= _RETRIEVE_TIMEOUT_S
