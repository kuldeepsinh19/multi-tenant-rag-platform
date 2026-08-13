---
name: project-conventions
description: Cross-cutting engineering standards for this production AI project (React frontend + Python/FastAPI backend + LangGraph agent). Read this FIRST for any coding task in this repo — it defines the security baseline, secrets handling, error philosophy, git hygiene, and how the per-stack skills fit together. Use this whenever writing, reviewing, or refactoring ANY code in this project, even for a small change, so the same conventions apply everywhere and Claude never has to be re-told the rules.
---

# Project conventions (root)

This is the shared spine for the whole codebase. The per-stack skills
(`react-frontend-standards`, `fastapi-backend-standards`, `langgraph-agent-standards`,
`rag-retrieval-standards`, `llm-guardrails-standards`, `llm-evals-standards`) inherit
everything here. When a task touches a specific stack, read that skill too.

## The one rule that governs everything

This is a **production AI system, not a demo.** The difference is measurable: every
component either has a test, a bound, a guardrail, or an observable metric attached to
it, or it doesn't ship. If you find yourself writing code that "usually works" or that
would silently produce a wrong answer, stop — that is the demo failure mode this project
exists to avoid.

## Security baseline (non-negotiable)

- **No secrets in code, ever.** API keys, tokens, DB URLs, and model provider keys come
  from environment variables (backend) or a server-side proxy (frontend). If you see a
  literal key in source, treat it as a bug to fix, not a style choice.
- **The frontend never holds a model provider key.** All LLM/provider calls go through
  the backend. A key shipped to the browser is a key leaked to the world.
- **Validate at every trust boundary.** Data crossing from client→server, server→LLM,
  or LLM→user is untrusted until validated. Never interpolate raw user input into a
  prompt, a SQL query, a shell command, or a file path.
- **Fail closed, not open.** If auth, a guardrail, or a validation check errors, deny
  the request. A crashed guardrail must never mean "let it through."
- **Log decisions, not secrets.** Structured logs are good; logging a full prompt with a
  user's PII or an auth token in it is a data leak. Redact before logging.

## Error handling philosophy

- Errors are **expected control flow**, not surprises. Every external call (LLM, vector
  store, third-party API, DB) can fail — wrap it, and decide explicitly what happens when
  it does (retry, fall back, escalate, or return a typed error to the user).
- **Never swallow an exception silently.** Either handle it meaningfully or let it
  propagate to a layer that will. A bare `except: pass` (Python) or empty `catch {}` (TS)
  is a bug.
- **User-facing errors are honest and safe.** Tell the user something actionable
  ("I couldn't verify that — escalating to a human") without leaking stack traces,
  internal IDs, or infrastructure details.

## Architecture principles

- **Separation of concerns by layer.** Frontend = presentation + user interaction.
  Backend API = transport, auth, rate limiting, orchestration entry point. Agent/RAG
  layer = reasoning and retrieval. Keep business logic out of route handlers and out of
  React components.
- **Typed contracts at every boundary.** Pydantic models (backend) and TypeScript types
  (frontend) that mirror each other. A shape mismatch should fail at the boundary, loudly,
  not three layers deep.
- **Deterministic where possible, probabilistic only where necessary.** Routing,
  validation, and control flow should be plain code. Only the actual generation step is
  allowed to be non-deterministic — and even then it's bounded and checked.
- **Idempotency for anything that acts.** Any endpoint or tool that creates/mutates
  (tickets, orders, records) must be safe to retry without duplicating the effect.

## Code quality conventions

- **Small, single-purpose functions.** If a function needs a comment to explain its
  second half, it's two functions.
- **Names describe intent, not implementation.** `verify_answer_is_grounded()` beats
  `check2()`.
- **Comments explain WHY, not WHAT.** The code says what it does; comments justify
  non-obvious decisions. Delete comments that just restate the line below them.
- **No dead code, no commented-out blocks left in.** Version control remembers; the file
  shouldn't.
- **Consistent formatting is automated, not debated.** Backend: `ruff` (format + lint).
  Frontend: Prettier + ESLint. Run them; don't hand-format.

## Git and PR hygiene

- **Conventional commits**: `feat(agent): add retry cap to verification loop`,
  `fix(api): reject oversized payloads before LLM call`, `test(evals): add injection cases`.
- **Small, reviewable PRs.** One concern per PR. A PR that touches the frontend, the
  agent loop, and the eval suite at once is three PRs.
- **Every behavior change ships with a test or an eval.** In this project specifically,
  a prompt change or agent-logic change is a code change and gates on the eval suite
  (see `llm-evals-standards`).

## Dependency discipline

- Pin versions (lockfiles committed). Don't add a dependency for something the standard
  library or an existing dep already does.
- Before adding an LLM/agent dependency, check whether it's actively maintained — this
  ecosystem churns fast and abandoned wrappers become liabilities.

## When in doubt

Prefer the boring, well-understood solution (a Redis token bucket, a Pydantic validator,
a typed error) over the clever one. Production reliability comes from predictability.
