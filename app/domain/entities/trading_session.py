"""TradingSession aggregate — authenticated connection window to an account.

Why this entity exists
----------------------
A TradingSession represents a period during which a client is connected to
a TradingAccount (heartbeat, idle, termination). It models session
lifecycle only — not order routing or market connectivity protocols.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require, require_state
from app.domain.entities.base import Entity
from app.domain.enums.trading_session import SessionStatus


@dataclass(eq=False, kw_only=True)
class TradingSession(Entity):
    """Rich domain model for a trading session."""

    trading_account_id: UUID
    user_id: UUID
    status: SessionStatus = SessionStatus.ACTIVE
    started_at: datetime | None = None
    ended_at: datetime | None = None
    last_seen_at: datetime | None = None
    client_label: str = ""
    termination_reason: str = ""

    def __post_init__(self) -> None:
        if self.started_at is None:
            self.started_at = self.created_at
        if self.last_seen_at is None:
            self.last_seen_at = self.started_at
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        require(self.started_at is not None, "Session must have started_at")
        if self.ended_at is not None:
            require(
                self.ended_at >= self.started_at,  # type: ignore[operator]
                "ended_at must be at or after started_at",
            )
            require(
                self.status
                in {
                    SessionStatus.CLOSED,
                    SessionStatus.EXPIRED,
                    SessionStatus.TERMINATED,
                },
                "Sessions with ended_at must be in a terminal status",
                status=self.status.value,
            )

    @classmethod
    def open(
        cls,
        *,
        trading_account_id: UUID,
        user_id: UUID,
        client_label: str = "",
        started_at: datetime | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: open a new ACTIVE session."""
        now = started_at or datetime.now(UTC)
        kwargs: dict[str, object] = {
            "trading_account_id": trading_account_id,
            "user_id": user_id,
            "status": SessionStatus.ACTIVE,
            "started_at": now,
            "last_seen_at": now,
            "client_label": client_label.strip(),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def heartbeat(self, *, at: datetime | None = None) -> None:
        """Record activity and clear idle state."""
        require_state(
            self.status in {SessionStatus.ACTIVE, SessionStatus.IDLE},
            "Cannot heartbeat a closed session",
            status=self.status.value,
        )
        self.last_seen_at = at or datetime.now(UTC)
        self.status = SessionStatus.ACTIVE
        self.touch()

    def mark_idle(self) -> None:
        """Mark the session idle after inactivity."""
        require_state(
            self.status == SessionStatus.ACTIVE,
            "Only active sessions can become idle",
            status=self.status.value,
        )
        self.status = SessionStatus.IDLE
        self.touch()

    def close(self, *, reason: str = "") -> None:
        """Gracefully close the session."""
        self._terminate(SessionStatus.CLOSED, reason=reason)

    def expire(self, *, reason: str = "expired") -> None:
        """Expire the session due to timeout."""
        self._terminate(SessionStatus.EXPIRED, reason=reason)

    def terminate(self, *, reason: str = "terminated") -> None:
        """Force-terminate the session."""
        self._terminate(SessionStatus.TERMINATED, reason=reason)

    def _terminate(self, status: SessionStatus, *, reason: str) -> None:
        require_state(
            self.status
            not in {
                SessionStatus.CLOSED,
                SessionStatus.EXPIRED,
                SessionStatus.TERMINATED,
            },
            "Session is already terminated",
            status=self.status.value,
        )
        self.status = status
        self.ended_at = datetime.now(UTC)
        self.termination_reason = reason.strip()
        self.touch()
        self._validate_invariants()

    @property
    def is_open(self) -> bool:
        return self.status in {SessionStatus.ACTIVE, SessionStatus.IDLE}

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "trading_account_id": str(self.trading_account_id),
                "user_id": str(self.user_id),
                "status": self.status.value,
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "ended_at": self.ended_at.isoformat() if self.ended_at else None,
                "last_seen_at": (
                    self.last_seen_at.isoformat() if self.last_seen_at else None
                ),
                "client_label": self.client_label,
                "termination_reason": self.termination_reason,
            }
        )
        return base
