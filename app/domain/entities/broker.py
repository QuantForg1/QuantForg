"""Broker aggregate — registered brokerage venue metadata.

Why this entity exists
----------------------
Trading accounts belong to brokers. The Broker aggregate stores the
catalogue of venues QuantForg knows about (name, type, status, platform).
It does **not** contain MetaTrader connection details or broker-API
credentials — those live on BrokerCredential / BrokerConnection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require, require_state
from app.domain.entities.base import Entity
from app.domain.enums.broker import BrokerPlatform, BrokerStatus, BrokerType
from app.domain.value_objects.identity import EntitySlug, PersonName


@dataclass(eq=False, kw_only=True)
class Broker(Entity):
    """Rich domain model for a brokerage venue."""

    name: PersonName
    slug: EntitySlug
    broker_type: BrokerType = BrokerType.RETAIL
    status: BrokerStatus = BrokerStatus.PENDING
    platform_code: BrokerPlatform = BrokerPlatform.OTHER
    country_code: str = ""
    website: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        require(isinstance(self.name, PersonName), "Broker.name must be a PersonName")
        require(isinstance(self.slug, EntitySlug), "Broker.slug must be an EntitySlug")
        if self.country_code:
            require(
                len(self.country_code) == 2 and self.country_code.isalpha(),
                "country_code must be an ISO 3166-1 alpha-2 code",
                country_code=self.country_code,
            )
            self.country_code = self.country_code.upper()
        if self.website:
            require(
                self.website.startswith(("http://", "https://")),
                "website must be an absolute http(s) URL",
                website=self.website,
            )
        self.description = self.description.strip()

    @classmethod
    def register(
        cls,
        *,
        name: str | PersonName,
        slug: str | EntitySlug,
        broker_type: BrokerType = BrokerType.RETAIL,
        platform_code: BrokerPlatform = BrokerPlatform.OTHER,
        country_code: str = "",
        website: str = "",
        description: str = "",
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: register a new broker in PENDING status."""
        name_vo = name if isinstance(name, PersonName) else PersonName(value=name)
        slug_vo = slug if isinstance(slug, EntitySlug) else EntitySlug(value=slug)
        kwargs: dict[str, object] = {
            "name": name_vo,
            "slug": slug_vo,
            "broker_type": broker_type,
            "status": BrokerStatus.PENDING,
            "platform_code": platform_code,
            "country_code": country_code.strip().upper(),
            "website": website.strip(),
            "description": description.strip(),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def activate(self) -> None:
        """Approve the broker for use by trading accounts."""
        require_state(
            self.status in {BrokerStatus.PENDING, BrokerStatus.INACTIVE},
            "Only pending or inactive brokers can be activated",
            status=self.status.value,
        )
        self.status = BrokerStatus.ACTIVE
        self.touch()

    def deactivate(self) -> None:
        """Take an active broker offline without blocking permanently."""
        require_state(
            self.status == BrokerStatus.ACTIVE,
            "Only active brokers can be deactivated",
            status=self.status.value,
        )
        self.status = BrokerStatus.INACTIVE
        self.touch()

    def block(self) -> None:
        """Permanently block a broker from the platform."""
        require_state(
            self.status != BrokerStatus.BLOCKED,
            "Broker is already blocked",
            status=self.status.value,
        )
        self.status = BrokerStatus.BLOCKED
        self.touch()

    def update_catalogue(
        self,
        *,
        name: str | PersonName | None = None,
        broker_type: BrokerType | None = None,
        platform_code: BrokerPlatform | None = None,
        country_code: str | None = None,
        website: str | None = None,
        description: str | None = None,
    ) -> None:
        """Update catalogue metadata. Blocked brokers cannot be edited."""
        require_state(
            self.status != BrokerStatus.BLOCKED,
            "Cannot update a blocked broker",
            status=self.status.value,
        )
        if name is not None:
            self.name = name if isinstance(name, PersonName) else PersonName(value=name)
        if broker_type is not None:
            self.broker_type = broker_type
        if platform_code is not None:
            self.platform_code = platform_code
        if country_code is not None:
            self.country_code = country_code.strip().upper()
        if website is not None:
            self.website = website.strip()
        if description is not None:
            self.description = description.strip()
        self._validate_invariants()
        self.touch()

    @property
    def is_usable(self) -> bool:
        return self.status == BrokerStatus.ACTIVE

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "name": str(self.name),
                "slug": str(self.slug),
                "broker_type": self.broker_type.value,
                "status": self.status.value,
                "platform_code": self.platform_code.value,
                "country_code": self.country_code,
                "website": self.website,
                "description": self.description,
            }
        )
        return base
