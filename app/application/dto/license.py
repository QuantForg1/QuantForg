"""License-related application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.license import License


@dataclass(frozen=True, slots=True)
class ActivateLicenseCommand:
    """Input for ActivateLicenseUseCase."""

    license_id: UUID


@dataclass(frozen=True, slots=True)
class LicenseDTO:
    """License representation returned to the presentation layer."""

    id: UUID
    user_id: UUID
    tier: str
    status: str
    seats: int
    issued_at: str | None
    expires_at: str | None

    @classmethod
    def from_entity(cls, license_: License) -> LicenseDTO:
        return cls(
            id=license_.id,
            user_id=license_.user_id,
            tier=license_.tier.value,
            status=license_.status.value,
            seats=license_.seats,
            issued_at=license_.issued_at.isoformat() if license_.issued_at else None,
            expires_at=license_.expires_at.isoformat() if license_.expires_at else None,
        )
