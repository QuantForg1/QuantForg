"""License aggregate — commercial entitlement granted to a user.

Why this entity exists
----------------------
QuantForg features are gated by licenses. The License aggregate captures
who owns the entitlement, which tier they hold, validity window, and
revocation state — without implementing billing or payment gateways.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require, require_state
from app.domain.entities.base import Entity
from app.domain.enums.license import LicenseStatus, LicenseTier


@dataclass(eq=False, kw_only=True)
class License(Entity):
    """Rich domain model for a user license grant."""

    user_id: UUID
    tier: LicenseTier
    status: LicenseStatus = LicenseStatus.PENDING
    seats: int = 1
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        require(
            self.seats >= 1, "License must have at least one seat", seats=self.seats
        )
        require(self.seats <= 10_000, "License seats exceed maximum", seats=self.seats)
        if self.issued_at is not None and self.expires_at is not None:
            require(
                self.expires_at > self.issued_at,
                "License expires_at must be after issued_at",
                issued_at=self.issued_at.isoformat(),
                expires_at=self.expires_at.isoformat(),
            )
        if self.status == LicenseStatus.REVOKED:
            require(
                self.revoked_at is not None,
                "Revoked licenses must record revoked_at",
            )

    @classmethod
    def issue(
        cls,
        *,
        user_id: UUID,
        tier: LicenseTier,
        seats: int = 1,
        issued_at: datetime | None = None,
        expires_at: datetime | None = None,
        notes: str = "",
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: issue an active license for a user."""
        now = issued_at or datetime.now(UTC)
        require(
            expires_at is None or expires_at > now,
            "expires_at must be in the future relative to issued_at",
        )
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "tier": tier,
            "status": LicenseStatus.ACTIVE,
            "seats": seats,
            "issued_at": now,
            "expires_at": expires_at,
            "notes": notes.strip(),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def is_valid_at(self, moment: datetime | None = None) -> bool:
        """Return True if the license is active and not past expiry."""
        moment = moment or datetime.now(UTC)
        if self.status != LicenseStatus.ACTIVE:
            return False
        return self.expires_at is None or moment < self.expires_at

    def renew(self, *, expires_at: datetime) -> None:
        """Extend expiry. Only active or expired licenses may be renewed."""
        require_state(
            self.status in {LicenseStatus.ACTIVE, LicenseStatus.EXPIRED},
            "Only active or expired licenses can be renewed",
            status=self.status.value,
        )
        now = datetime.now(UTC)
        require(expires_at > now, "Renewal expiry must be in the future")
        if self.issued_at is None:
            self.issued_at = now
        self.expires_at = expires_at
        self.status = LicenseStatus.ACTIVE
        self.revoked_at = None
        self.touch()
        self._validate_invariants()

    def revoke(self, *, reason: str = "") -> None:
        """Permanently revoke the license."""
        require_state(
            self.status not in {LicenseStatus.REVOKED},
            "License is already revoked",
            status=self.status.value,
        )
        self.status = LicenseStatus.REVOKED
        self.revoked_at = datetime.now(UTC)
        if reason:
            self.notes = f"{self.notes}\nRevoked: {reason}".strip()
        self.touch()

    def suspend(self) -> None:
        """Temporarily suspend an active license."""
        require_state(
            self.status == LicenseStatus.ACTIVE,
            "Only active licenses can be suspended",
            status=self.status.value,
        )
        self.status = LicenseStatus.SUSPENDED
        self.touch()

    def activate(self) -> None:
        """Activate a pending or suspended license."""
        require_state(
            self.status in {LicenseStatus.PENDING, LicenseStatus.SUSPENDED},
            "Only pending or suspended licenses can be activated",
            status=self.status.value,
        )
        self.status = LicenseStatus.ACTIVE
        if self.issued_at is None:
            self.issued_at = datetime.now(UTC)
        self.revoked_at = None
        self.touch()

    @classmethod
    def create_pending(
        cls,
        *,
        user_id: UUID,
        tier: LicenseTier,
        seats: int = 1,
        expires_at: datetime | None = None,
        notes: str = "",
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: create a PENDING license awaiting activation."""
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "tier": tier,
            "status": LicenseStatus.PENDING,
            "seats": seats,
            "issued_at": None,
            "expires_at": expires_at,
            "notes": notes.strip(),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def mark_expired(self, *, at: datetime | None = None) -> None:
        """Mark the license expired when the validity window has passed."""
        moment = at or datetime.now(UTC)
        require_state(
            self.status == LicenseStatus.ACTIVE,
            "Only active licenses can expire",
            status=self.status.value,
        )
        require(
            self.expires_at is not None and moment >= self.expires_at,
            "Cannot mark expired before expires_at",
        )
        self.status = LicenseStatus.EXPIRED
        self.touch()

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "tier": self.tier.value,
                "status": self.status.value,
                "seats": self.seats,
                "issued_at": self.issued_at.isoformat() if self.issued_at else None,
                "expires_at": self.expires_at.isoformat() if self.expires_at else None,
                "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
                "notes": self.notes,
            }
        )
        return base
