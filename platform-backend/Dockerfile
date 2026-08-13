FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts
COPY migrations ./migrations
COPY alembic.ini ./
COPY entrypoint.sh ./

# Extras are added incrementally as each build stage needs them:
#   .[dev]                    -> stage 1 (scaffold)
#   .[dev,llm]                -> stage 2 (provider abstraction)
#   .[dev,llm,agent]          -> stage 3+ (agent wiring)
#   .[dev,llm,agent,rag]      -> stage 4-5 (ingestion/retrieval)
#   .[dev,llm,agent,rag,guardrails,evals] -> stage 6-8 (full platform)
ARG INSTALL_EXTRAS=dev
RUN uv pip install --system -e ".[${INSTALL_EXTRAS}]"
RUN chmod +x entrypoint.sh

EXPOSE 8000
CMD ["./entrypoint.sh"]
