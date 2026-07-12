"""In-process event dispatcher.

Routes domain events to registered :class:`EventSubscriber` instances by
exact type and inheritance (``isinstance``). Foundation only — not a
distributed message broker.
"""

from __future__ import annotations

from collections import defaultdict

from app.domain.events.base import DomainEvent
from app.domain.interfaces.event_bus import EventSubscriber


class EventDispatcher:
    """Synchronous in-process delivery of domain events to subscribers.

    Why it exists
    -------------
    Implements :class:`EventDispatcherPort` for local development, tests, and
    single-process deployments. Matches subscribers whose
    ``subscribed_types`` include the event's class or any base class.
    """

    def __init__(self) -> None:
        self._registry: dict[type[DomainEvent], list[EventSubscriber]] = defaultdict(
            list
        )

    def register(self, subscriber: EventSubscriber) -> None:
        """Register ``subscriber`` for each of its declared event types."""
        if not subscriber.subscribed_types:
            msg = f"Subscriber '{subscriber.name}' declares no subscribed_types"
            raise ValueError(msg)
        for event_type in subscriber.subscribed_types:
            if subscriber not in self._registry[event_type]:
                self._registry[event_type].append(subscriber)

    def unregister(self, subscriber: EventSubscriber) -> None:
        """Remove ``subscriber`` from all registry entries."""
        for event_type, subscribers in list(self._registry.items()):
            self._registry[event_type] = [s for s in subscribers if s is not subscriber]
            if not self._registry[event_type]:
                del self._registry[event_type]

    def subscribers_for(self, event: DomainEvent) -> list[EventSubscriber]:
        """Return unique subscribers matching ``event`` (order preserved)."""
        matched: list[EventSubscriber] = []
        seen: set[int] = set()
        for event_type, subscribers in self._registry.items():
            if isinstance(event, event_type):
                for subscriber in subscribers:
                    identity = id(subscriber)
                    if identity not in seen:
                        seen.add(identity)
                        matched.append(subscriber)
        return matched

    async def dispatch(self, event: DomainEvent) -> None:
        """Deliver ``event`` to every matching subscriber sequentially."""
        for subscriber in self.subscribers_for(event):
            await subscriber.handle(event)
