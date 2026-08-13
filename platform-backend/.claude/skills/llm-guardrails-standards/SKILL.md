---
name: llm-guardrails-standards
description: Safety-guardrail standards for the LLM layer of this AI project — input and output guardrails, PII handling, prompt-injection defense, structured-output enforcement, groundedness and citation checks. Use this whenever building, reviewing, or hardening anything that screens what goes into or comes out of the model, or the system prompt itself, so Claude ships layered guardrails instead of an unprotected model call. Triggers on any mention of guardrails, prompt injection, PII, jailbreak, safety, groundedness, hallucination, structured output, the system prompt, or output validation, even for a small change.
---

# LLM guardrails standards

Assumes the root `project-conventions` skill. Guardrails are **layered and defense-in-depth**,
not a single filter. A model call with no guardrail on either side is the raw demo this
project exists to replace.

## The core principle: the model is untrusted on both sides

Treat the LLM like any other untrusted component: **its input can be adversarial and its
output can be wrong or unsafe.** Every guardrail either sits *before* the model (screen the
input) or *after* it (screen the output). Both layers are required.

## The system prompt is a versioned contract

- The system prompt is **code**: stored in git, diffed, and gated by the eval suite on
  every change (see `llm-evals-standards`). A prompt tweak is a code change, not a config
  edit you make in prod.
- Structure it explicitly with sections: role, scope, grounding rule, citation rule,
  tool-use rule, escalation rule, output format. Ambiguous prompts produce ambiguous
  (and exploitable) behavior.
- **State the grounding contract in the prompt AND enforce it in code.** The prompt says
  "answer only from provided context, cite every claim, say 'I don't know' otherwise" —
  but the prompt is a request, not a guarantee. The output guardrails below are the
  guarantee.

## Input guardrails (before the model sees anything)

- **PII detection / redaction** (e.g. Microsoft Presidio): strip or mask PII before it
  reaches the model or the logs. PII in a prompt is PII in your telemetry.
- **Prompt-injection and jailbreak screening.** User input — and *retrieved documents*,
  which can contain planted instructions — must be treated as data, never as instructions.
  Delimit untrusted content clearly in the prompt and screen for known injection patterns.
  Retrieved-context injection is the sneaky one: a poisoned document can carry "ignore
  your instructions" into the prompt.
- **Scope / topic check.** Reject or redirect out-of-domain requests *before* spending a
  generation call. If the assistant is a returns-support copilot, an off-topic request
  gets a polite decline, not a best-effort answer.
- **Size and shape limits.** Enforce max input length and expected structure at the API
  boundary (Pydantic) so oversized or malformed input never reaches the model.

## Output guardrails (before the response leaves the system)

- **Structured-output enforcement.** Force the model into a typed schema (Instructor +
  Pydantic). Malformed output then fails loudly and is retried/rejected — it never reaches
  the user as a silent format bug.
- **Groundedness gate — the one most demos skip.** Verify that every claim in the answer
  is supported by the retrieved context. Two levels:
  - *Cheap*: every citation the answer makes must correspond to a chunk that was actually
    retrieved. Fails fast, near-zero cost.
  - *Stronger*: an entailment/NLI check or a narrowly-scoped judge call (yes/no: "is this
    claim supported by this chunk?") — **never the same open-ended call that wrote the
    answer.** A model grading its own free-form output isn't a guardrail.
- **Citation enforcement.** Reject answers with claims that have no supporting `[doc_id]`
  and force a retry or the honest "I can't verify this" fallback. No citation → no claim.
- **Output PII / safety scan.** Check the outgoing answer doesn't leak PII, secrets, or
  internal detail, and doesn't contain unsafe content.

Minimal groundedness gate (illustrative — the cheap layer):

```python
from pydantic import BaseModel, field_validator

class GroundedAnswer(BaseModel):
    answer: str
    citations: list[str]                 # doc_ids the answer relies on

    @field_validator("citations")
    @classmethod
    def must_cite(cls, v):
        if not v:
            raise ValueError("Answer must cite at least one retrieved source")
        return v

def citations_are_real(answer: GroundedAnswer, retrieved_ids: set[str]) -> bool:
    # every cited source must actually have been retrieved
    return all(c in retrieved_ids for c in answer.citations)
```

## Fail closed

- If any guardrail errors (the PII service is down, the judge call times out), **deny or
  escalate — never fall through to "let it pass."** A broken safety check is a blocked
  request, not an open door. This mirrors the root convention.

## Config-driven rails where it helps

- For conversational rails (topic boundaries, refusal patterns), a config-driven tool
  (NeMo Guardrails / Guardrails AI) keeps the rules auditable in one place rather than
  buried across prompts. Reach for it when the rail logic gets complex enough that reading
  the prompt no longer tells you what's blocked.

## Test the guardrails like an adversary

- Guardrails without adversarial tests are decoration. Maintain a red-team suite
  (injection attempts, jailbreaks, out-of-scope probes, PII-leak attempts) and run it in
  CI — see the red-teaming section of `llm-evals-standards`. Tools: `garak`, or a
  promptfoo red-team config.
