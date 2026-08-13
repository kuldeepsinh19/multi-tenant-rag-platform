---
name: langgraph-agent-standards
description: Safety and architecture standards for the LangGraph agent orchestration layer of this AI project. Use this whenever building, reviewing, or debugging the agent — graph nodes, state, tool calls, the reasoning/verification loop, retries, escalation — so Claude builds a bounded, observable, non-hallucinating agent instead of an infinite-loop demo. Triggers on any mention of LangGraph, the agent, the agent loop, graph nodes, tool calling, orchestration, or agent state, even for a small change.
---

# LangGraph agent standards

Assumes the root `project-conventions` skill. This is the reasoning layer: a bounded
state machine that plans, retrieves, acts, and *verifies before answering*. The retrieval
and guardrail details live in `rag-retrieval-standards` and `llm-guardrails-standards`;
this skill governs the control flow that ties them together.

## The core principle: an agent is a bounded state machine, not a while-loop with vibes

The single thing that separates a production agent from a demo is that **every loop has a
hard cap and every path has a defined exit.** An agent that can loop forever, or that
answers when it shouldn't, is the failure this layer exists to prevent.

## Typed, explicit state

- **Define the graph state as a `TypedDict`** (or Pydantic model) with every field the
  graph reads or writes — including control fields like `retry_count`, `max_retries`, and
  `verified`. State that isn't in the schema is state you can't reason about or observe.
- State is passed and returned explicitly by each node. No hidden globals, no mutating
  shared objects across nodes.
- Keep the state minimal — carry what downstream nodes need, not the entire conversation
  history if a summary suffices (that also controls token cost).

## Bounded loops — non-negotiable

- **Every cycle has `max_retries`/`max_iterations` enforced in the state**, checked by a
  conditional edge. "It'll probably converge" is not a bound.
- **Every loop has an explicit escape hatch that is neither a crash nor a hallucination.**
  When retries are exhausted, route to a designed `escalate` node that hands off to a
  human (or returns a safe "I can't verify this") — a *designed outcome*, not a fallthrough.
- Model the loop with `add_conditional_edges`, and make the routing function a small, pure
  function of state (`should_retry(state) -> "done" | "retry" | "escalate"`). Control flow
  is deterministic code; only generation is probabilistic.

```python
def should_retry(state: AgentState) -> str:
    if state["verified"]:
        return "done"
    if state["retry_count"] >= state["max_retries"]:
        return "escalate"          # designed exit, not a crash
    return "retry"

graph.add_conditional_edges("verify", should_retry, {
    "done": END, "retry": "retrieve", "escalate": "escalate",
})
```

## The verify-before-answer node

- **No draft answer leaves the graph unverified.** After generation, a `verify` node
  checks the draft against retrieved context (groundedness) before the graph can reach
  `END`. If it fails, loop back or escalate — never emit the unverified draft.
- Verification uses a *separate, narrowly-scoped* check (a groundedness gate or a judge
  call with a yes/no rubric), never the same open-ended generation call that produced the
  answer. See `llm-guardrails-standards`.

## Tool-call safety

- **Tools have typed inputs and outputs** (Pydantic). The model proposes a tool call; you
  validate the arguments before executing. Never execute a tool with unvalidated
  model-supplied arguments — especially anything that touches a DB, a filesystem, an
  external API, or money.
- **Enforce preconditions and permissions in code**, not in the prompt. A prompt saying
  "only refund if eligible" is a suggestion; a code check is a guarantee.
- **Acting tools are idempotent** (create-ticket, place-order): safe to retry without
  duplicating the effect. Pair with an idempotency key.
- **Never let the model fabricate a tool result.** Tool outputs come from real execution
  and are fed back as observations; the model doesn't get to imagine them.

## Resilience around every external call

- Wrap every LLM call, tool call, and retrieval call with **retries + exponential backoff**
  and a **timeout**. A hung provider call should time out and route to fallback, not hang
  the request.
- Add a **circuit breaker** / fallback model (via an AI gateway like LiteLLM) so a primary
  provider outage degrades gracefully instead of taking the system down.
- Distinguish retryable errors (timeout, 429, transient 5xx) from non-retryable ones (bad
  request, auth) — don't burn your retry budget on errors that won't recover.

## Observability

- **Every node, tool call, and LLM call is a traced span** (LangSmith/Langfuse), carrying
  the request correlation ID from the backend. When an answer is wrong, you need to see
  *which node* and *which retrieval* produced it — see `llm-evals-standards`.
- Log the routing decisions (why it retried, why it escalated) — these are the moments you
  debug in production.

## Determinism and testability

- Keep as much of the graph as possible in **plain, testable functions**. Routing,
  precondition checks, and state transitions should be unit-testable without calling a
  model.
- Make the agent runnable against **recorded/mocked LLM and tool responses** so its
  control flow can be tested deterministically in CI.
