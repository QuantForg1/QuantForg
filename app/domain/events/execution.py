"""Execution safety domain events — decision facts only, never fills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class ExecutionApproved(DomainEvent):
    """Emitted when the safety layer returns ALLOW (still no order_send)."""

    event_type: ClassVar[str] = "execution.approved"
    user_id: UUID
    decision_id: UUID
    request_id: str
    symbol: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "decision_id": str(self.decision_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class ExecutionRejected(DomainEvent):
    """Emitted when the safety layer returns REJECT."""

    event_type: ClassVar[str] = "execution.rejected"
    user_id: UUID
    decision_id: UUID
    request_id: str
    symbol: str
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "decision_id": str(self.decision_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
                "reasons": list(self.reasons),
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class ExecutionRetryRequested(DomainEvent):
    """Emitted when the safety layer returns RETRY (transient / duplicate pressure)."""

    event_type: ClassVar[str] = "execution.retry_requested"
    user_id: UUID
    decision_id: UUID
    request_id: str
    symbol: str
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "decision_id": str(self.decision_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
                "reasons": list(self.reasons),
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class ExecutionRequested(DomainEvent):
    """Emitted when the gateway begins preparing a submit."""

    event_type: ClassVar[str] = "execution.requested"
    user_id: UUID
    request_id: str
    symbol: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class ExecutionSubmitted(DomainEvent):
    """Emitted after a successful broker order_send (flag must be on)."""

    event_type: ClassVar[str] = "execution.submitted"
    user_id: UUID
    request_id: str
    symbol: str
    order_ticket: int | None
    retcode: int

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
                "order_ticket": self.order_ticket,
                "retcode": self.retcode,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class ExecutionFailed(DomainEvent):
    """Emitted when broker submit fails or maps to FAILED/RETRY."""

    event_type: ClassVar[str] = "execution.failed"
    user_id: UUID
    request_id: str
    symbol: str
    retcode: int
    message: str
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
                "retcode": self.retcode,
                "message": self.message,
                "retryable": self.retryable,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class ExecutionDisabled(DomainEvent):
    """Emitted when submit is blocked because EXECUTION_ENABLED=false."""

    event_type: ClassVar[str] = "execution.disabled"
    user_id: UUID
    request_id: str
    symbol: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
            }
        )
        return payload
