---
name: fastapi-backend-standards
description: Clean-architecture and safety standards for the Python + FastAPI backend of this AI project. Use this whenever writing, reviewing, or refactoring backend code — routes, Pydantic schemas, dependencies, auth, rate limiting, background tasks, DB access — so Claude produces async-correct, well-structured, secure API code without being re-told the rules. Triggers on any mention of FastAPI, endpoints, routes, Pydantic, the API, the backend, or server-side Python, even for a small change.
---

# FastAPI backend standards

Assumes the root `project-conventions` skill. This is the transport, auth, rate-limiting,
and orchestration-entry layer that sits in front of the LangGraph agent.

## Project structure — organize by domain, not by layer

Group code by feature/domain, each self-contained. This scales; a flat `routers/`,
`models/`, `services/` split does not.

```
src/
├── auth/          # router.py, schemas.py, dependencies.py, service.py
├── chat/          # the conversation endpoints
├── agent/         # thin adapter that calls the LangGraph app
├── ratelimit/     # middleware + redis token bucket
├── core/          # config, logging, shared deps, exceptions
└── main.py
```

Each domain owns its `router.py`, `schemas.py` (Pydantic), `service.py` (logic),
`dependencies.py`, and `exceptions.py`.

## Pydantic everywhere

- **Every request body and response is a Pydantic v2 model.** No raw dicts crossing the
  boundary. This is your first, cheapest guardrail — malformed input fails at the edge
  with a clear 422 instead of corrupting logic downstream.
- **Response models are explicit** (`response_model=...`) so you never accidentally leak
  internal fields (hashes, internal IDs, provider metadata) to the client.
- **Config comes from `BaseSettings`**, read from env — never hardcoded. One settings
  object, imported where needed.
- Constrain inputs at the schema level: `max_length` on user text, bounded lists, enums
  for fixed choices. Reject a 2 MB "message" before it ever reaches the model.

## Async correctness (the #1 FastAPI footgun)

- **Route handlers are `async def`.** But an `async` handler that calls a blocking/sync
  function *blocks the whole event loop* — this silently kills throughput.
- **If you must call a sync SDK** (some vector stores, some provider clients), run it in a
  thread pool (`await run_in_threadpool(...)` / `asyncio.to_thread`), never call it
  directly inside an async handler.
- Use async DB drivers and an async HTTP client (`httpx.AsyncClient`) for outbound calls.
- **Long work does not block the request.** Anything slow that the user doesn't need to
  wait for goes to a real task queue (Celery/RQ/Arq) — `BackgroundTasks` is only for
  small fire-and-forget work, not for a 30-second agent run you should be streaming.

## Dependency injection

- **Use FastAPI `Depends` for cross-cutting concerns**: current user, DB session, rate-limit
  check, request-scoped config. Don't re-implement auth in every handler.
- Keep route handlers thin: parse (Pydantic) → authorize (dependency) → call a service
  function → return a response model. Business logic lives in `service.py`, not the route.

## Auth and authorization

- Authenticate via a dependency that resolves the caller and **fails closed** on any
  error (missing/invalid token → 401, no exceptions).
- Authorize per-action: verify the caller may do *this specific thing* to *this specific
  resource*, not just "is logged in."
- Passwords hashed (bcrypt/argon2) if you store them; tokens short-lived; secrets from env.

## Rate limiting and cost control

- **Enforce rate limits in middleware, before the request reaches the LLM** — reject with
  `429` early so abuse costs you a Redis `INCR`, not a model call. (See the reference
  implementation in the production blueprint: Redis fixed-window token bucket keyed per
  user/API key.)
- Track and cap per-key cost budgets. An LLM endpoint without a spend cap is an
  unbounded liability.
- Consider fronting provider calls with an AI gateway (LiteLLM) for multi-provider
  fallback + built-in budget tracking rather than hand-rolling it.

## Error handling

- **Central exception handlers** map domain exceptions to HTTP responses with clean,
  non-leaky messages. Don't return stack traces or internal detail to clients.
- Define typed domain exceptions (`RateLimitExceeded`, `RetrievalFailed`,
  `GuardrailBlocked`) and handle them explicitly — a caught, named exception is
  self-documenting.
- Validate `ValueError`s raised in Pydantic validators become clean 422s.

## Observability

- **Structured (JSON) logging** with a request/correlation ID propagated through the whole
  request, including into the agent run — so one user problem maps to one trace.
- Emit latency, token, and cost metrics per request. Redact PII and secrets before
  logging (see `project-conventions`).
- This backend is where you attach LangSmith/Langfuse tracing (see `llm-evals-standards`).

## Testing

- **Async test client from day one** (`httpx.AsyncClient` + `pytest-asyncio`). Retrofitting
  async tests later is painful.
- Test each endpoint's happy path *and* its failure paths: 401, 422, 429, and the
  guardrail-blocked / escalation paths this app has.
- Mock external calls (LLM, vector store) at the service boundary so tests are fast and
  deterministic.

## Tooling

- **`ruff`** for lint + format (fast, replaces flake8/black/isort). Wire it into CI.
- Type-check with `mypy` or `pyright`. Types are documentation the compiler enforces.
