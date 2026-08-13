"""Registers every ORM model with SQLAlchemy's mapper registry.

Importing this module has the side effect of importing all model modules, so that any
process touching the database — the API, the Arq worker, or a standalone script — has the
*complete* table graph available. Without it, a process that imports only a subset of
models (e.g. the worker importing just Document + Chunk) fails to resolve cross-table
foreign keys on flush (e.g. `documents.uploaded_by -> users`) with NoReferencedTableError.

Import this for its side effects near the top of any DB-touching entrypoint.
"""

from src.auth.models import User  # noqa: F401
from src.businesses.models import Business, WidgetKey  # noqa: F401
from src.chat.models import Conversation, Message  # noqa: F401
from src.documents.models import Document  # noqa: F401
from src.ingestion.models import Chunk  # noqa: F401
from src.usage.models import UsageEvent  # noqa: F401
