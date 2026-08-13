# Evals & observability scaffold

Turns "seems to work" into "measurably works" (see
`.claude/skills/llm-evals-standards/SKILL.md`). Every component here exists to attach a
**number** to the system — retrieval precision/recall, generation faithfulness, a red-team
pass rate, per-request cost + latency.

## The golden dataset is the definition of "correct"

`evals/golden_dataset.json` (repo: `platform-backend/evals/`) is a list of
`{question, expected_answer, expected_doc_ids}`. **It ships as a SEED set** (~8 rows about a
fictional business, "Acme Cloud Storage") — it is scaffolding, not a production golden set.

A real golden set is **50–200 hand-verified Q/A + citation pairs drawn from actual usage**
(support tickets, real docs, real user questions). Grow this file from real failures: every
wrong answer or bad citation in production becomes a permanent case here, so the system can
never regress on the same bug twice. Version it in git.

## What to run

All commands from `platform-backend/`, inside the `api` container or an env with the app
installed.

### 1. Retrieval metrics — NO LLM in the loop (run this first)

```
python scripts/eval_retrieval.py --business-id <uuid> --top-k 5
```

Computes **context precision** (fraction of retrieved docs that are relevant) and **context
recall** (fraction of expected docs actually retrieved) of the real retrieval layer
(`src.retrieval.service.retrieve`) against the golden set. Recall tells you whether the
right chunk was retrieved *at all* — the ceiling on everything the generator can do. Exits
non-zero when a metric is below `--min-precision` / `--min-recall`, so it can gate CI once a
real ingested tenant exists. Without `--business-id` it does a format check and exits 0. The
retrieval import is guarded, so the script won't hard-fail before Stage 5 is merged.

### 2. Ragas — faithfulness / relevancy (offline, heavy)

```
pip install -e '.[evals-offline]'      # ragas is NOT in the running image (see pyproject)
python scripts/eval_ragas.py --business-id <uuid>
```

A documented stub: it wires the golden set into a Ragas dataset shape and marks where the
retrieval + generation calls plug in. Faithfulness is the hallucination metric — a drop
there is a regression even if relevancy rises. Fails loudly with install instructions if
`ragas` is missing; never silently no-ops.

### 3. promptfoo — CI regression gate + red-team suite

```
npx promptfoo@latest eval -c promptfooconfig.yaml
```

`promptfooconfig.yaml` (repo root of the backend) has correctness/groundedness assertions
plus a **required red-team section**: prompt-injection, jailbreak, cross-tenant-leak, and
PII-extraction cases. It calls the running `/chat` endpoint so it exercises the whole stack
(retrieval + guardrails + agent). Wire `promptfoo eval` into CI and fail the build on a
non-zero exit. Every real jailbreak/injection found in production becomes a permanent case.

## Observability

`src/observability/tracing.py` initialises Langfuse from `LANGFUSE_PUBLIC_KEY /
SECRET_KEY / HOST`. With keys unset it is a strict **no-op** (never an error). Tracing is
**fail-open** — a Langfuse outage must never break a request. `trace_request(...)` records
per-request latency + redacted metadata under the correlation id; `record_llm_cost(...)` is
for the chat/agent layer to attach cost + latency spans. Cost/latency are always computed
locally, so they work with tracing off.

Per-business production numbers are served by `GET /businesses/{business_id}/metrics`
(`src/usage/router.py`): total messages, tokens, cost, avg latency, and groundedness pass
rate — guarded by super_admin or the business's own admin.
