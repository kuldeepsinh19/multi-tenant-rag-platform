# platform-backend

FastAPI backend for a multi-tenant RAG chatbot platform. A super-admin manages multiple
businesses; each business admin uploads documents into an isolated knowledge base; each
business gets a dedicated chatbot (dashboard + embeddable public widget) that answers only
from its own documents, with citations. Full design: see the architecture diagram and
summary in the repo-root `README.md`.

## Read the skills first

This repo's engineering standards live in `.claude/skills/` — Claude Code loads them
automatically by relevance. If your tool doesn't support skills, read these directly, in
this order, before touching code:

1. `.claude/skills/project-conventions/SKILL.md` — root: security baseline, secrets,
   error philosophy, architecture principles, git hygiene. Applies to **every** change.
2. `.claude/skills/fastapi-backend-standards/SKILL.md` — routes, Pydantic, async
   correctness, DI, auth, rate limiting, logging, tests.
3. `.claude/skills/rag-retrieval-standards/SKILL.md` — ingestion, chunking, hybrid search,
   reranking, citations, groundedness.
4. `.claude/skills/langgraph-agent-standards/SKILL.md` — the agent loop: bounded state
   machine, verify-before-answer, tool-call safety, resilience.
5. `.claude/skills/llm-guardrails-standards/SKILL.md` — input/output guardrails around the
   model, PII, prompt injection, structured output.
6. `.claude/skills/llm-evals-standards/SKILL.md` — golden dataset, Ragas, CI regression
   gate, red-teaming, tracing.

## Non-negotiables (condensed — see the skills for full detail and rationale)

- **Multi-tenancy is a security boundary.** Every query, vector search, and auth check
  filters by `business_id` (tenant). Never trust `business_id` from the client — derive it
  from the authenticated principal or the validated widget key.
- **No vendor LLM/embedding SDK in business logic.** Everything goes through
  `src/llm/base.py` Protocols (`LLMProvider`, `EmbeddingProvider`). Provider selection is a
  config value (`LLM_PROVIDER`, `EMBED_PROVIDER`), never a hardcoded import.
- **Fail closed.** Auth, guardrails, and rate limits deny on error — never fall through.
- **Async correctness.** Route handlers are `async def`; sync SDK calls go through
  `run_in_threadpool`; long work (ingestion) goes to the Arq worker, not `BackgroundTasks`.
- **Every request/response is a Pydantic v2 model** with an explicit `response_model`.
- **No unverified draft answer leaves the agent.** The LangGraph `verify` node gates on
  groundedness before `END`.
- **`ruff` + `mypy`** are wired into CI and must pass.

## Project layout

```
src/
├── auth/        businesses/    documents/   ingestion/
├── retrieval/   agent/         chat/        guardrails/
├── ratelimit/   llm/{base.py, adapters/, registry.py}
├── evals/       core/{config, logging, exceptions, db, deps}
└── main.py
```

Each domain folder owns its own `router.py`, `schemas.py`, `service.py`, `dependencies.py`,
`exceptions.py`. Business logic lives in `service.py`, not in route handlers.
