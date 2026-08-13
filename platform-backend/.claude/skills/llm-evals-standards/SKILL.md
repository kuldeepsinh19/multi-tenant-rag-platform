---
name: llm-evals-standards
description: Evaluation and observability standards for this AI project — golden datasets, RAG metrics (Ragas), regression gating in CI (promptfoo/DeepEval), red-teaming, and production tracing (LangSmith/Langfuse). Use this whenever building or reviewing evals, test datasets, CI checks for prompt/model changes, tracing, or anything measuring the system's quality — so quality is a number that gates deploys, not a vibe. Triggers on any mention of evals, evaluation, Ragas, promptfoo, DeepEval, golden dataset, faithfulness, tracing, observability, LangSmith, Langfuse, red-teaming, or measuring quality, even for a small change.
---

# LLM evals and observability standards

Assumes the root `project-conventions` skill. This is the layer that turns "seems to work"
into "measurably works." **The presence of a real eval suite is the single clearest signal
that a system is production-grade rather than a lucky demo** — and the absence of one is
the clearest signal that it isn't.

## The core principle: eval-driven development

Every prompt change, model swap, retrieval-tuning change, or agent-logic change is a code
change, and **gates on the eval suite the same way code gates on unit tests.** If you can't
measure whether a change made the system better or worse, you're guessing — and guesses
regress silently in production.

## Build the golden dataset first (highest-leverage step)

- **A golden dataset is 50–200 real question/answer pairs** with hand-verified correct
  answers *and* correct source citations, drawn from actual usage (support tickets, real
  docs, real user questions) — not invented examples.
- This is tedious and it is also the single most valuable thing you can build. An eval
  suite without a real golden set is decoration; the dataset *is* the definition of
  "correct" for this system.
- Build it **before** optimizing generation, so you're optimizing toward a fixed target
  instead of moving the goalposts as you go.
- Version it in git and grow it: every production failure becomes a new golden-set case,
  so the system can't regress on the same bug twice.

## Offline metrics — Ragas for the RAG pipeline

Measure these on every prompt/model/retrieval change:

- **Faithfulness** — is the answer actually supported by the retrieved context? (This is
  your hallucination metric.)
- **Answer relevancy** — does the answer address the question?
- **Context precision / context recall** — retrieval-quality metrics (see
  `rag-retrieval-standards`); recall tells you if the right chunk was retrieved at all.

Track these as numbers over time. A change that lifts relevancy but drops faithfulness is
a regression, not an improvement — you only see that if you measure both.

## Regression gate in CI — the thing that makes it a system

- **Wire evals into CI** (promptfoo or DeepEval). A change that drops a key metric below a
  threshold **fails the build**, exactly like a failing unit test. This gate is what makes
  the eval suite load-bearing instead of a report nobody reads.
- Keep the CI eval set fast (a representative subset) and run the full set nightly or
  pre-release.
- promptfoo uses declarative config and is what OpenAI and Anthropic use internally for
  red-teaming — a good pattern to copy directly.

## Red-teaming — test like an adversary

- Maintain an **adversarial suite**: prompt-injection attempts, jailbreaks, out-of-scope
  probes, PII-extraction attempts, and known-bad inputs. This pairs with
  `llm-guardrails-standards` — the guardrails are the defense, the red-team suite is the
  test that they hold.
- Run it in CI as a required suite, not a one-time launch check. Tools: `garak` (dedicated
  LLM vulnerability scanner) or a promptfoo red-team config.
- Every real jailbreak/injection you find in production becomes a permanent red-team case.

## Production tracing and online eval

- **Trace every request end-to-end** (LangSmith or Langfuse): retrieval, each agent node,
  each tool call, each LLM call — tokens, latency, and cost per span — carrying the
  correlation ID set by the backend. When an answer is wrong, one trace should show you
  exactly where it went wrong.
- **Track cost and latency as first-class metrics.** p95 latency and cost-per-request are
  production SLOs, not afterthoughts — an accurate-but-slow-and-expensive system still
  fails in production.
- **Sample real traffic for online eval.** Route a percentage of production interactions
  into a human-review queue and track **score drift over time** — model providers change,
  data changes, and quality decays silently without this.

## What "done" looks like for any component

A component is production-ready when it has a number attached to it: retrieval has
precision/recall, generation has faithfulness/relevancy, the API has p95 latency and
cost-per-request, guardrails have a red-team pass rate. If a component has no metric, it
isn't finished — it's just running.
