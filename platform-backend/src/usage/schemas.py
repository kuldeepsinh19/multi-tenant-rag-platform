"""Response contract for the metrics endpoint. Per llm-evals-standards, a component isn't
done until it has a number attached — these are the numbers for a business's chatbot:
volume, cost, p95-ish latency, and a groundedness pass rate."""

from pydantic import BaseModel


class BusinessMetrics(BaseModel):
    """Aggregated production metrics for one business over its recorded usage events."""

    total_messages: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    # Fraction of answered turns that passed the groundedness gate (0.0–1.0). Derived from
    # usage events whose event_type marks a grounded answer; see router for the exact
    # derivation and the placeholder behaviour when no such events exist yet.
    groundedness_pass_rate: float


__all__ = ["BusinessMetrics"]
