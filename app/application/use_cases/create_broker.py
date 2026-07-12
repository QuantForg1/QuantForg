"""CreateBrokerUseCase — register a brokerage venue in the catalogue.

Why this use case exists
------------------------
Trading accounts require a Broker. This use case registers catalogue
metadata (name, slug, type) and optionally activates the broker so accounts
can connect. No MetaTrader or broker-API credentials are involved.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.broker import BrokerDTO, CreateBrokerCommand
from app.domain.entities.broker import Broker
from app.domain.exceptions.base import ConflictError
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory
from app.domain.value_objects.identity import EntitySlug


@dataclass(frozen=True, slots=True)
class CreateBrokerUseCase:
    """Register a new broker catalogue entry."""

    uow_factory: UnitOfWorkFactory

    async def execute(self, command: CreateBrokerCommand) -> BrokerDTO:
        """Create a broker, ensuring slug uniqueness."""
        slug = EntitySlug(value=command.slug)

        async with self.uow_factory() as uow:
            existing = await uow.brokers.get_by_slug(slug)
            if existing is not None:
                raise ConflictError(
                    "A broker with this slug already exists",
                    details={"slug": slug.value},
                )

            broker = Broker.register(
                name=command.name,
                slug=slug,
                broker_type=command.broker_type,
                country_code=command.country_code,
                website=command.website,
            )
            if command.activate:
                broker.activate()

            await uow.brokers.add(broker)
            await uow.commit()
            return BrokerDTO.from_entity(broker)
