"""Phase 6.1 — durable dispatch delivery vocabulary.

Maps operator-facing labels onto ``AccountExecutionState`` for execution
decisions and a separate ``DeliveryStatus`` for worker handoff. This module
never authorizes OMS / order_send.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from app.domain.multi_account.signal_dispatch import AccountExecutionState

DEFAULT_LEASE_SECONDS = 60
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_RETRY_BASE_SECONDS = 5


class DeliveryStatus(StrEnum):
    """Worker delivery lifecycle (orthogonal to AccountExecutionState)."""

    NONE = "none"
    PENDING = "pending"
    CLAIMED = "claimed"
    DELIVERED = "delivered"
    ACKED = "acked"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


# Operator labels → (execution state hint, delivery status)
OPERATOR_LABEL_MAP: dict[str, tuple[str, DeliveryStatus]] = {
    "PENDING": ("received", DeliveryStatus.NONE),
    "ELIGIBILITY_CHECK": ("eligibility_pending", DeliveryStatus.NONE),
    "BLOCKED": ("blocked", DeliveryStatus.NONE),
    "QUEUED": ("queued", DeliveryStatus.PENDING),
    "DELIVERED": ("queued", DeliveryStatus.DELIVERED),
    "ACKNOWLEDGED": ("queued", DeliveryStatus.ACKED),
    "EXECUTION_REPORTED": ("acknowledged", DeliveryStatus.ACKED),
    "FAILED": ("rejected", DeliveryStatus.FAILED),
    "EXPIRED": ("cancelled", DeliveryStatus.EXPIRED),
    "CANCELLED": ("cancelled", DeliveryStatus.CANCELLED),
}

_ALLOWED_DELIVERY: dict[DeliveryStatus, frozenset[DeliveryStatus]] = {
    DeliveryStatus.NONE: frozenset({DeliveryStatus.PENDING, DeliveryStatus.CANCELLED}),
    DeliveryStatus.PENDING: frozenset(
        {
            DeliveryStatus.CLAIMED,
            DeliveryStatus.CANCELLED,
            DeliveryStatus.EXPIRED,
            DeliveryStatus.DEAD_LETTER,
        }
    ),
    DeliveryStatus.CLAIMED: frozenset(
        {
            DeliveryStatus.DELIVERED,
            DeliveryStatus.FAILED,
            DeliveryStatus.EXPIRED,
            DeliveryStatus.PENDING,  # lease release / restart recovery
            DeliveryStatus.CANCELLED,
        }
    ),
    DeliveryStatus.DELIVERED: frozenset(
        {
            DeliveryStatus.ACKED,
            DeliveryStatus.FAILED,
            DeliveryStatus.EXPIRED,
        }
    ),
    DeliveryStatus.ACKED: frozenset(),
    DeliveryStatus.FAILED: frozenset(
        {
            DeliveryStatus.PENDING,  # retry
            DeliveryStatus.DEAD_LETTER,
            DeliveryStatus.CANCELLED,
        }
    ),
    DeliveryStatus.EXPIRED: frozenset(
        {DeliveryStatus.PENDING, DeliveryStatus.DEAD_LETTER, DeliveryStatus.CANCELLED}
    ),
    DeliveryStatus.CANCELLED: frozenset(),
    DeliveryStatus.DEAD_LETTER: frozenset(),
}


def can_transition_delivery(current: DeliveryStatus, new: DeliveryStatus) -> bool:
    if current is new:
        return True
    return new in _ALLOWED_DELIVERY.get(current, frozenset())


def assert_delivery_transition(current: DeliveryStatus, new: DeliveryStatus) -> None:
    if not can_transition_delivery(current, new):
        raise ValueError(f"invalid delivery transition {current.value} → {new.value}")


def retry_delay_seconds(attempt: int, *, base: int = DEFAULT_RETRY_BASE_SECONDS) -> int:
    """Exponential backoff capped at 5 minutes."""
    exp = max(0, int(attempt) - 1)
    delay: int = int(base) * (2**exp)
    return min(300, delay)


@dataclass(slots=True)
class DispatchJob:
    """One durable per-account dispatch job (no credentials)."""

    intent_id: UUID
    signal_id: UUID
    user_id: UUID
    broker_account_id: UUID
    idempotency_key: str
    state: AccountExecutionState
    delivery_status: DeliveryStatus
    block_reason: str | None = None
    attempt_count: int = 0
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    lease_owner_worker_id: UUID | None = None
    lease_expires_at: datetime | None = None
    available_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    next_retry_at: datetime | None = None
    kill_switch: bool = False
    delivered_at: datetime | None = None
    acked_at: datetime | None = None
    last_error: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_public_dict(self) -> dict[str, Any]:
        """Safe serialization — strips any secret-like keys."""
        safe_payload = {
            k: v
            for k, v in self.payload.items()
            if k.lower()
            not in {
                "password",
                "token",
                "secret",
                "sealed_credentials",
                "credential",
                "api_key",
            }
        }
        return {
            "intent_id": str(self.intent_id),
            "signal_id": str(self.signal_id),
            "user_id": str(self.user_id),
            "broker_account_id": str(self.broker_account_id),
            "idempotency_key": self.idempotency_key,
            "state": self.state.value,
            "delivery_status": self.delivery_status.value,
            "block_reason": self.block_reason,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "lease_owner_worker_id": (
                str(self.lease_owner_worker_id) if self.lease_owner_worker_id else None
            ),
            "lease_expires_at": (
                self.lease_expires_at.isoformat() if self.lease_expires_at else None
            ),
            "available_at": self.available_at.isoformat(),
            "kill_switch": self.kill_switch,
            "last_error": self.last_error,
            "payload": safe_payload,
            "live_submit_allowed": False,
            "delivery_suppressed": True,
        }


@dataclass(frozen=True, slots=True)
class DispatchEvent:
    event_id: UUID
    intent_id: UUID
    user_id: UUID
    broker_account_id: UUID
    worker_id: UUID | None
    event_type: str
    detail: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        intent_id: UUID,
        user_id: UUID,
        broker_account_id: UUID,
        event_type: str,
        worker_id: UUID | None = None,
        detail: str = "",
    ) -> DispatchEvent:
        return cls(
            event_id=uuid4(),
            intent_id=intent_id,
            user_id=user_id,
            broker_account_id=broker_account_id,
            worker_id=worker_id,
            event_type=event_type,
            detail=detail,
        )


@dataclass(frozen=True, slots=True)
class QueueMetrics:
    depth: int
    by_delivery_status: dict[str, int]
    by_execution_state: dict[str, int]
    claimed: int
    failed: int
    dead_letter: int
    expired_leases: int
    kill_switched: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "depth": self.depth,
            "by_delivery_status": dict(self.by_delivery_status),
            "by_execution_state": dict(self.by_execution_state),
            "claimed": self.claimed,
            "failed": self.failed,
            "dead_letter": self.dead_letter,
            "expired_leases": self.expired_leases,
            "kill_switched": self.kill_switched,
            "live_submit_enabled": False,
        }


def lease_deadline(
    *, now: datetime | None = None, seconds: int = DEFAULT_LEASE_SECONDS
) -> datetime:
    base = now or datetime.now(UTC)
    return base + timedelta(seconds=int(seconds))
