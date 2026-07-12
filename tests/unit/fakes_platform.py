"""Test re-exports for platform in-memory UoW."""

from app.infrastructure.persistence.memory_platform import (
    InMemoryPlatformUnitOfWork,
    MemoryPlatformUnitOfWorkFactory,
)

# Backwards-compatible alias used by unit tests
SharedPlatformUnitOfWorkFactory = MemoryPlatformUnitOfWorkFactory

__all__ = [
    "InMemoryPlatformUnitOfWork",
    "MemoryPlatformUnitOfWorkFactory",
    "SharedPlatformUnitOfWorkFactory",
]
