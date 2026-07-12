"""Repository adapters.

Concrete implementations of :class:`~app.domain.interfaces.repository.RepositoryPort`.
Foundation sprint provides the base SQLAlchemy repository skeleton.
"""

from app.infrastructure.repositories.base import SQLAlchemyRepository

__all__ = ["SQLAlchemyRepository"]
