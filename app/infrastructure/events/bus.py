"""In-process domain event bus.

Composes :class:`EventPublisher` and :class:`EventDispatcher` into a single
:class:`EventBusPort` for subscribe + publish workflows.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.events.base import DomainEvent
from app.domain.interfaces.event_bus import EventSubscriber
from app.infrastructure.events.dispatcher import EventDispatcher
from app.infrastructure.events.publisher import EventPublisher


class InProcessEventBus:
    """Foundation event bus for single-process QuantForg deployments.

    Why it exists
    -------------
    Provides a production-ready *local* bus so application code can publish
    and subscribe without a message broker. Later sprints may replace this
    adapter with Redis Streams / NATS while keeping the same ports.
    """

    def __init__(self) -> None:
        self._dispatcher = EventDispatcher()
        self._publisher = EventPublisher(self._dispatcher)

    @property
    def dispatcher(self) -> EventDispatcher:
        """Expose the underlying dispatcher (for advanced wiring/tests)."""
        return self._dispatcher

    @property
    def publisher(self) -> EventPublisher:
        """Expose the underlying publisher (for advanced wiring/tests)."""
        return self._publisher

    def subscribe(self, subscriber: EventSubscriber) -> None:
        """Register a subscriber for its declared event types."""
        self._dispatcher.register(subscriber)

    def unsubscribe(self, subscriber: EventSubscriber) -> None:
        """Remove a previously registered subscriber."""
        self._dispatcher.unregister(subscriber)

    async def publish(self, event: DomainEvent) -> None:
        """Publish and dispatch a domain event."""
        await self._publisher.publish(event)

    async def publish_many(self, events: Sequence[DomainEvent]) -> None:
        """Publish and dispatch multiple domain events in order."""
        await self._publisher.publish_many(events)
