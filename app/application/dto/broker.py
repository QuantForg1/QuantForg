"""Broker-related application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.broker import Broker
from app.domain.enums.broker import BrokerType


@dataclass(frozen=True, slots=True)
class CreateBrokerCommand:
    """Input for CreateBrokerUseCase."""

    name: str
    slug: str
    broker_type: BrokerType = BrokerType.RETAIL
    country_code: str = ""
    website: str = ""
    activate: bool = True


@dataclass(frozen=True, slots=True)
class BrokerDTO:
    """Broker representation returned to the presentation layer."""

    id: UUID
    name: str
    slug: str
    broker_type: str
    status: str
    country_code: str
    website: str

    @classmethod
    def from_entity(cls, broker: Broker) -> BrokerDTO:
        return cls(
            id=broker.id,
            name=str(broker.name),
            slug=str(broker.slug),
            broker_type=broker.broker_type.value,
            status=broker.status.value,
            country_code=broker.country_code,
            website=broker.website,
        )
