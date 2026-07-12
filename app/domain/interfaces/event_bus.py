"""Event bus ports — publisher, dispatcher, subscriber contracts.

Why these ports exist
---------------------
They formalise Dependency Inversion for the event system: producers publish
through :class:`EventPublisherPort`, the bus dispatches via
:class:`EventDispatcherPort`, and consumers implement
:class:`EventSubscriber`. Infrastructure provides a concrete bus; the domain
never knows about queues or brokers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from app.domain.events.base import DomainEvent


@runtime_checkable
class EventSubscriber(Protocol):
    """Consumer of one or more domain event types.

    Why it exists
    -------------
    Subscribers react to domain facts (e.g. persist a tick, update a
    projection). Each subscriber declares which event types it handles.
    """

    @property
    def name(self) -> str:
        """Human-readable subscriber name for diagnostics."""
        ...

    @property
    def subscribed_types(self) -> frozenset[type[DomainEvent]]:
        """Event classes this subscriber wants to receive."""
        ...

    async def handle(self, event: DomainEvent) -> None:
        """Process a single event. Must be idempotent where possible."""
        ...


class EventPublisherPort(Protocol):
    """Port for emitting domain events onto the bus.

    Why it exists
    -------------
    Application use cases publish facts without knowing how they are
    transported or who is listening.
    """

    async def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event."""
        ...

    async def publish_many(self, events: Sequence[DomainEvent]) -> None:
        """Publish multiple domain events in order."""
        ...


class EventDispatcherPort(Protocol):
    """Port for delivering an event to matching subscribers.

    Why it exists
    -------------
    Separates routing/delivery from publication so the bus can swap
    in-process dispatch for a message broker later without changing
    publishers.
    """

    async def dispatch(self, event: DomainEvent) -> None:
        """Deliver ``event`` to all subscribers registered for its type."""
        ...


class EventBusPort(Protocol):
    """Combined subscribe + publish façade for the domain event bus.

    Why it exists
    -------------
    Composition root / application code registers subscribers and publishes
    events through one abstraction.
    """

    def subscribe(self, subscriber: EventSubscriber) -> None:
        """Register a subscriber for its declared event types."""
        ...

    def unsubscribe(self, subscriber: EventSubscriber) -> None:
        """Remove a previously registered subscriber."""
        ...

    async def publish(self, event: DomainEvent) -> None:
        """Publish and dispatch a domain event."""
        ...

    async def publish_many(self, events: Sequence[DomainEvent]) -> None:
        """Publish and dispatch multiple domain events in order."""
        ...
