"""SQLAlchemy Unit of Work implementation."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SQLAlchemyUnitOfWork:
    """Unit of Work backed by an async SQLAlchemy session factory.

    Parameters
    ----------
    session_factory:
        Factory that produces ``AsyncSession`` instances.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self.session = self._session_factory()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.session is None:
            return
        if exc_type is not None:
            await self.rollback()
        await self.session.close()
        self.session = None

    async def commit(self) -> None:
        if self.session is None:
            msg = "Unit of Work session is not active"
            raise RuntimeError(msg)
        await self.session.commit()

    async def rollback(self) -> None:
        if self.session is None:
            msg = "Unit of Work session is not active"
            raise RuntimeError(msg)
        await self.session.rollback()
