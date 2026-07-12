"""Domain event base types.

Domain events are immutable facts about something that happened in the
domain. They carry a unique identity, a UTC occurrence timestamp, and a
stable event-type name for routing on the event bus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4


@dataclass(frozen=True, kw_only=True, slots=True)
class DomainEvent:
    """Immutable base for all QuantForg domain events.

    Why it exists
    -------------
    Decouples producers of domain facts from consumers. Application and
    infrastructure layers react to events without the producer knowing who
    is listening.

    Attributes
    ----------
    event_id:
        Unique identity of this event instance.
    occurred_at:
        UTC timestamp when the domain fact occurred.
    correlation_id:
        Optional correlation key for tracing related events.
    causation_id:
        Optional identity of the event that caused this one.
    """

    event_type: ClassVar[str] = "domain_event"

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    causation_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            object.__setattr__(
                self,
                "occurred_at",
                self.occurred_at.replace(tzinfo=UTC),
            )
        else:
            object.__setattr__(
                self,
                "occurred_at",
                self.occurred_at.astimezone(UTC),
            )

    @property
    def name(self) -> str:
        """Stable event type name used for subscriber routing."""
        return self.event_type

    def to_dict(self) -> dict[str, Any]:
        """Serialize common envelope fields."""
        return {
            "event_type": self.event_type,
            "event_id": str(self.event_id),
            "occurred_at": self.occurred_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": str(self.causation_id) if self.causation_id else None,
        }
