"""Base helper for building event subscribers."""

from __future__ import annotations

from app.domain.events.base import DomainEvent


class BaseEventSubscriber:
    """Convenience base for concrete subscribers.

    Why it exists
    -------------
    Provides ``name`` / ``subscribed_types`` storage so adapters only
    implement ``handle``. Not required — any object matching
    :class:`EventSubscriber` works.
    """

    def __init__(
        self,
        *,
        name: str,
        subscribed_types: frozenset[type[DomainEvent]],
    ) -> None:
        self._name = name
        self._subscribed_types = subscribed_types

    @property
    def name(self) -> str:
        return self._name

    @property
    def subscribed_types(self) -> frozenset[type[DomainEvent]]:
        return self._subscribed_types

    async def handle(self, event: DomainEvent) -> None:
        """Override in subclasses."""
        raise NotImplementedError
