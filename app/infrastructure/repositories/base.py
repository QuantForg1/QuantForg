"""SQLAlchemy-backed generic repository base.

Subclass this for each aggregate. Foundation sprint provides the shared
session-handling pattern; no concrete trading aggregates are defined yet.
"""

from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.base import Entity

TEntity = TypeVar("TEntity", bound=Entity)
TModel = TypeVar("TModel")


class SQLAlchemyRepository(Generic[TEntity, TModel]):
    """Generic async repository over a SQLAlchemy mapped model.

    Parameters
    ----------
    session:
        Active async SQLAlchemy session (owned by the Unit of Work).
    model:
        SQLAlchemy declarative model class.
    """

    def __init__(self, session: AsyncSession, model: type[TModel]) -> None:
        self._session = session
        self._model = model

    async def get_by_id(self, entity_id: UUID) -> TModel | None:
        """Fetch a row by primary key UUID."""
        result = await self._session.execute(
            select(self._model).where(self._model.id == entity_id)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    async def add(self, model: TModel) -> TModel:
        """Add a new model instance to the session and flush."""
        self._session.add(model)
        await self._session.flush()
        return model

    async def delete(self, entity_id: UUID) -> bool:
        """Delete a row by primary key. Returns whether a row was deleted."""
        instance = await self.get_by_id(entity_id)
        if instance is None:
            return False
        await self._session.delete(instance)
        await self._session.flush()
        return True
