"""Base entity contract for QuantForg domain models.

An entity is distinguished by a stable identity (``id``), not by its
attribute values. Equality is identity-based.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(eq=False, kw_only=True)
class Entity:
    """Abstract base for all domain entities.

    Attributes
    ----------
    id:
        Stable unique identifier assigned at creation.
    created_at:
        UTC timestamp of entity creation.
    updated_at:
        UTC timestamp of the most recent mutation.
    """

    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def touch(self) -> None:
        """Update ``updated_at`` to the current UTC time."""
        self.updated_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Serialize entity fields to a plain dictionary."""
        return {
            "id": str(self.id),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
