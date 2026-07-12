"""AuditLog aggregate — immutable security / compliance event record.

Why this entity exists
----------------------
Every significant domain action should leave an audit trail (who, what,
when, outcome). AuditLog is append-only and immutable after creation.
It supports compliance, forensics, and accountability without coupling to
any particular logging sink or database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.exceptions.base import ConflictError


@dataclass(eq=False, kw_only=True)
class AuditLog(Entity):
    """Immutable audit event.

    ``touch()`` is forbidden after construction to preserve forensic integrity.
    """

    action: AuditAction
    outcome: AuditOutcome
    resource_type: str
    resource_id: UUID | None = None
    actor_user_id: UUID | None = None
    occurred_at: datetime | None = None
    ip_address: str = ""
    user_agent: str = ""
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    _frozen: bool = False

    def __post_init__(self) -> None:
        if self.occurred_at is None:
            self.occurred_at = self.created_at
        self.resource_type = self.resource_type.strip().lower()
        self._validate_invariants()
        self._frozen = True

    def _validate_invariants(self) -> None:
        require(bool(self.resource_type), "resource_type must not be blank")
        require(
            len(self.resource_type) <= 64,
            "resource_type must be at most 64 characters",
        )
        require(len(self.message) <= 1000, "message must be at most 1000 characters")
        require(
            len(self.user_agent) <= 512, "user_agent must be at most 512 characters"
        )
        if self.ip_address:
            require(
                self._looks_like_ip(self.ip_address),
                "ip_address format is invalid",
                ip_address=self.ip_address,
            )
        require(len(self.metadata) <= 50, "metadata may contain at most 50 keys")

    @staticmethod
    def _looks_like_ip(value: str) -> bool:
        """Lightweight IP shape check (IPv4 or IPv6) — not a full parser."""
        if "." in value:
            parts = value.split(".")
            if len(parts) != 4:
                return False
            return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
        if ":" in value:
            return 2 <= len(value) <= 45
        return False

    @classmethod
    def record(
        cls,
        *,
        action: AuditAction,
        outcome: AuditOutcome,
        resource_type: str,
        resource_id: UUID | None = None,
        actor_user_id: UUID | None = None,
        occurred_at: datetime | None = None,
        ip_address: str = "",
        user_agent: str = "",
        message: str = "",
        metadata: dict[str, Any] | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: append an immutable audit event."""
        kwargs: dict[str, object] = {
            "action": action,
            "outcome": outcome,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "actor_user_id": actor_user_id,
            "occurred_at": occurred_at or datetime.now(UTC),
            "ip_address": ip_address.strip(),
            "user_agent": user_agent.strip(),
            "message": message.strip(),
            "metadata": dict(metadata or {}),
            "_frozen": False,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def touch(self) -> None:
        """Audit logs are immutable."""
        if self._frozen:
            raise ConflictError("AuditLog records are immutable and cannot be touched")

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "action": self.action.value,
                "outcome": self.outcome.value,
                "resource_type": self.resource_type,
                "resource_id": str(self.resource_id) if self.resource_id else None,
                "actor_user_id": (
                    str(self.actor_user_id) if self.actor_user_id else None
                ),
                "occurred_at": (
                    self.occurred_at.isoformat() if self.occurred_at else None
                ),
                "ip_address": self.ip_address,
                "user_agent": self.user_agent,
                "message": self.message,
                "metadata": dict(self.metadata),
            }
        )
        return base
