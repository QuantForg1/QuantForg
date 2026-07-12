"""Database session and engine management.

Owns the SQLAlchemy async engine lifecycle. Repository implementations
in the infrastructure layer consume sessions from here; domain and
application layers never import this module directly.
"""

from core.database.session import (
    DatabaseManager,
    create_engine,
    get_database_manager,
)

__all__ = [
    "DatabaseManager",
    "create_engine",
    "get_database_manager",
]
