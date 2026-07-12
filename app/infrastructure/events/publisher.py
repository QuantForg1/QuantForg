"""In-process event publisher.

Publishes domain events by handing them to an :class:`EventDispatcherPort`.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.events.base import DomainEvent
from app.domain.interfaces.event_bus import EventDispatcherPort


class EventPublisher:
    """Publish domain events through a dispatcher.

    Why it exists
    -------------
    Application code depends on :class:`EventPublisherPort`. This foundation
    adapter forwards each event to the configured dispatcher without knowing
    about subscribers.
    """

    def __init__(self, dispatcher: EventDispatcherPort) -> None:
        self._dispatcher = dispatcher

    async def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event."""
        await self._dispatcher.dispatch(event)

    async def publish_many(self, events: Sequence[DomainEvent]) -> None:
        """Publish multiple domain events in the given order."""
        for event in events:
            await self.publish(event)
