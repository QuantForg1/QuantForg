"""Execution gateway domain models — results only; live send gated by flag."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.enums.execution import ExecutionOutcome
from app.domain.interfaces.mt5_order import (
    RETCODE_DONE,
    RETCODE_INVALID,
    RETCODE_INVALID_PRICE,
    RETCODE_INVALID_STOPS,
    RETCODE_INVALID_VOLUME,
    RETCODE_MARKET_CLOSED,
    RETCODE_NO_MONEY,
    RETCODE_TRADE_DISABLED,
)

# Additional MT5 retcodes used by gateway mapping (mock / real).
RETCODE_REQUOTE = 10004
RETCODE_REJECT = 10006
RETCODE_CANCEL = 10007
RETCODE_TIMEOUT = 10012
RETCODE_PRICE_OFF = 10021
RETCODE_EXECUTION_DISABLED = 90001  # QuantForg synthetic — flag off


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Domain-mapped broker execution outcome (never a raw MT5 struct)."""

    outcome: ExecutionOutcome
    retcode: int
    message: str
    order_ticket: int | None = None
    deal_ticket: int | None = None
    volume: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    symbol: str = ""
    request_id: str = ""
    retryable: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "outcome": self.outcome.value,
            "retcode": self.retcode,
            "message": self.message,
            "order_ticket": self.order_ticket,
            "deal_ticket": self.deal_ticket,
            "volume": str(self.volume),
            "price": str(self.price),
            "symbol": self.symbol,
            "request_id": self.request_id,
            "retryable": self.retryable,
        }

    @classmethod
    def disabled(cls, *, request_id: str = "", symbol: str = "") -> Self:
        return cls(
            outcome=ExecutionOutcome.DISABLED,
            retcode=RETCODE_EXECUTION_DISABLED,
            message=(
                "Execution is disabled. Set EXECUTION_ENABLED=true to allow "
                "order submission via the Execution Gateway."
            ),
            request_id=request_id,
            symbol=symbol,
            retryable=False,
        )


def map_retcode_to_outcome(retcode: int) -> tuple[ExecutionOutcome, bool, str]:
    """Map MT5 retcode → (outcome, retryable, default message)."""
    if retcode in {0, RETCODE_DONE}:
        return ExecutionOutcome.SUCCESS, False, "done"
    if retcode == RETCODE_EXECUTION_DISABLED:
        return ExecutionOutcome.DISABLED, False, "execution disabled"
    if retcode in {RETCODE_REQUOTE, RETCODE_TIMEOUT, RETCODE_PRICE_OFF}:
        return ExecutionOutcome.RETRY, True, "transient broker condition"
    if retcode == RETCODE_CANCEL:
        return ExecutionOutcome.CANCELLED, False, "cancelled"
    messages = {
        RETCODE_REJECT: "request rejected",
        RETCODE_INVALID: "invalid request",
        RETCODE_INVALID_VOLUME: "invalid volume",
        RETCODE_INVALID_PRICE: "invalid price",
        RETCODE_INVALID_STOPS: "invalid stops",
        RETCODE_TRADE_DISABLED: "trade disabled",
        RETCODE_MARKET_CLOSED: "market closed",
        RETCODE_NO_MONEY: "not enough money",
    }
    return (
        ExecutionOutcome.FAILED,
        False,
        messages.get(retcode, f"broker retcode {retcode}"),
    )


@dataclass(eq=False, kw_only=True)
class ExecutionAttempt(Entity):
    """Persisted execution request + result (no credentials)."""

    user_id: UUID
    request_id: str
    symbol: str
    side: str
    order_type: str
    volume: Decimal
    outcome: ExecutionOutcome
    retcode: int
    message: str
    order_ticket: int | None = None
    deal_ticket: int | None = None
    price: Decimal = Decimal("0")
    retryable: bool = False
    request_snapshot: dict[str, object] = field(default_factory=dict)
    result_snapshot: dict[str, object] = field(default_factory=dict)
    idempotent_replay: bool = False
    submitted_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        self.request_id = self.request_id.strip()
        require(len(self.request_id) > 0, "request_id is required")
        require(len(self.symbol) > 0, "symbol is required")

    @classmethod
    def record(
        cls,
        *,
        user_id: UUID,
        request_id: str,
        symbol: str,
        side: str,
        order_type: str,
        volume: Decimal,
        result: ExecutionResult,
        request_snapshot: dict[str, object] | None = None,
        idempotent_replay: bool = False,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "request_id": request_id,
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "volume": volume,
            "outcome": result.outcome,
            "retcode": result.retcode,
            "message": result.message,
            "order_ticket": result.order_ticket,
            "deal_ticket": result.deal_ticket,
            "price": result.price,
            "retryable": result.retryable,
            "request_snapshot": dict(request_snapshot or {}),
            "result_snapshot": result.to_dict(),
            "idempotent_replay": idempotent_replay,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
                "side": self.side,
                "order_type": self.order_type,
                "volume": str(self.volume),
                "outcome": self.outcome.value,
                "retcode": self.retcode,
                "message": self.message,
                "order_ticket": self.order_ticket,
                "deal_ticket": self.deal_ticket,
                "price": str(self.price),
                "retryable": self.retryable,
                "request_snapshot": dict(self.request_snapshot),
                "result_snapshot": dict(self.result_snapshot),
                "idempotent_replay": self.idempotent_replay,
                "submitted_at": self.submitted_at.isoformat(),
            }
        )
        return base
