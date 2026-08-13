"""Regression test for the worker model registry (src/core/models.py).

The Arq worker (and create_superadmin.py) originally imported only Document + Chunk, so
SQLAlchemy couldn't resolve the `documents.uploaded_by -> users` FK and every ingestion
flush raised NoReferencedTableError. `src.core.models` imports every ORM model for its
side effects; importing it must make the full mapper graph configurable and register all
tables. This locks in that no model is ever silently dropped from the registry.
"""

from sqlalchemy.orm import configure_mappers

import src.core.models  # noqa: F401  (imported for registration side effect)
from src.core.db import Base

_EXPECTED_TABLES = {
    "users",
    "businesses",
    "documents",
    "chunks",
    "conversations",
    "messages",
    "usage_events",
    "widget_keys",
}


def test_importing_core_models_makes_mapper_graph_configurable() -> None:
    # Would raise NoReferencedTableError / InvalidRequestError if any model referenced by
    # a FK were missing from the registry.
    configure_mappers()


def test_all_key_tables_registered_in_metadata() -> None:
    tables = set(Base.metadata.tables)
    missing = _EXPECTED_TABLES - tables
    assert not missing, f"missing tables from registry: {missing}"
