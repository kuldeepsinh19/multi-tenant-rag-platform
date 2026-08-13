"""Arq worker entrypoint. Long-running work (document ingestion, batch embedding) is
enqueued here instead of FastAPI's BackgroundTasks, per fastapi-backend-standards.

Task functions are registered as they land (ingestion in stage 4).
"""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from arq.connections import RedisSettings

import src.core.models  # noqa: F401 — registers all ORM models for the worker process
from src.core.config import get_settings
from src.core.logging import configure_logging, get_logger
from src.ingestion.service import ingest_document

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    logger.info("worker_startup")


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("worker_shutdown")


async def healthcheck(ctx: dict[str, Any]) -> str:
    """Placeholder task so Arq has at least one registered function before real
    ingestion tasks land in stage 4. Safe to keep as a liveness probe afterward."""
    return "ok"


async def ingest_document_task(ctx: dict[str, Any], document_id: str, file_path: str) -> None:
    """Arq entrypoint enqueued from src/documents/router.py on upload. Delegates to the
    pipeline in src/ingestion/service.py; the document_id round-trips as a str because
    Arq job args are JSON-serialized."""
    await ingest_document(UUID(document_id), file_path)


class WorkerSettings:
    functions: list[Callable[..., Any]] = [healthcheck, ingest_document_task]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
