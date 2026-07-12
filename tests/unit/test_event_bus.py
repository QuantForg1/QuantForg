"""Unit tests for the in-process event bus foundation."""

from __future__ import annotations

import pytest

from app.domain.events.base import DomainEvent
from app.domain.events.market import TickReceived
from app.domain.market_data.tick import Tick
from app.infrastructure.events.bus import InProcessEventBus
from app.infrastructure.events.dispatcher import EventDispatcher
from app.infrastructure.events.publisher import EventPublisher
from app.infrastructure.events.subscriber import BaseEventSubscriber


class _RecordingSubscriber(BaseEventSubscriber):
    def __init__(self, *types: type[DomainEvent]) -> None:
        super().__init__(
            name="recorder",
            subscribed_types=frozenset(types),
        )
        self.received: list[DomainEvent] = []

    async def handle(self, event: DomainEvent) -> None:
        self.received.append(event)


@pytest.mark.unit
class TestEventDispatcherAndPublisher:
    @pytest.mark.asyncio
    async def test_dispatch_to_matching_subscriber(self) -> None:
        dispatcher = EventDispatcher()
        publisher = EventPublisher(dispatcher)
        tick_sub = _RecordingSubscriber(TickReceived)
        all_sub = _RecordingSubscriber(DomainEvent)
        dispatcher.register(tick_sub)
        dispatcher.register(all_sub)

        tick = Tick.create(symbol_code="EURUSD", price="1.1")
        event = TickReceived(tick=tick)
        await publisher.publish(event)

        assert len(tick_sub.received) == 1
        assert len(all_sub.received) == 1
        assert tick_sub.received[0] is event

    @pytest.mark.asyncio
    async def test_unsubscribe(self) -> None:
        bus = InProcessEventBus()
        sub = _RecordingSubscriber(TickReceived)
        bus.subscribe(sub)
        bus.unsubscribe(sub)
        await bus.publish(
            TickReceived(tick=Tick.create(symbol_code="EURUSD", price="1.0"))
        )
        assert sub.received == []

    @pytest.mark.asyncio
    async def test_publish_many_preserves_order(self) -> None:
        bus = InProcessEventBus()
        sub = _RecordingSubscriber(TickReceived)
        bus.subscribe(sub)
        events = [
            TickReceived(tick=Tick.create(symbol_code="EURUSD", price="1.0")),
            TickReceived(tick=Tick.create(symbol_code="EURUSD", price="1.1")),
            TickReceived(tick=Tick.create(symbol_code="GBPUSD", price="1.2")),
        ]
        await bus.publish_many(events)
        assert [e.tick.price.value for e in sub.received] == [  # type: ignore[attr-defined]
            events[0].tick.price.value,
            events[1].tick.price.value,
            events[2].tick.price.value,
        ]

    def test_subscriber_requires_types(self) -> None:
        dispatcher = EventDispatcher()
        with pytest.raises(ValueError):
            dispatcher.register(_RecordingSubscriber())
