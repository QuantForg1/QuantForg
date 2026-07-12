"""Generic repository port.

Concrete repositories in the infrastructure layer implement this protocol
for specific aggregate roots. Foundation sprint defines the contract only.
"""

from __future__ import annotations

from typing import Protocol, TypeVar
from uuid import UUID

from app.domain.entities.base import Entity

TEntity = TypeVar("TEntity", bound=Entity)


class RepositoryPort(Protocol[TEntity]):
    """Async repository contract for a single aggregate type."""

    async def get_by_id(self, entity_id: UUID) -> TEntity | None:
        """Fetch an entity by its identity, or ``None`` if absent."""
        ...

    async def add(self, entity: TEntity) -> TEntity:
        """Persist a new entity and return it."""
        ...

    async def delete(self, entity_id: UUID) -> bool:
        """Delete an entity by identity. Returns ``True`` if deleted."""
        ...
