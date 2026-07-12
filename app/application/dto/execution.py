"""Application DTOs for execution safety checks and gateway submit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.execution_gateway import ExecutionAttempt
from app.domain.entities.execution_safety import ExecutionDecisionRecord


@dataclass(frozen=True, slots=True)
class ExecutionCheckCommand:
    user_id: UUID
    request_id: str
    symbol: str
    side: str
    order_type: str = "market"
    volume: str = "0.01"
    price: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    slippage: int = 10
    magic: int = 0
    comment: str = ""
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class ExecutionCheckDTO:
    id: UUID
    request_id: str
    decision: str
    symbol: str
    side: str
    order_type: str
    volume: str
    rejection_reasons: list[str]
    warnings: list[str]
    calculated_risk: dict[str, object]
    checks: dict[str, bool]
    idempotent_replay: bool
    decided_at: datetime

    @classmethod
    def from_entity(cls, entity: ExecutionDecisionRecord) -> ExecutionCheckDTO:
        return cls(
            id=entity.id,
            request_id=entity.request_id,
            decision=entity.decision.value,
            symbol=entity.symbol,
            side=entity.side,
            order_type=entity.order_type,
            volume=str(entity.volume),
            rejection_reasons=list(entity.rejection_reasons),
            warnings=list(entity.warnings),
            calculated_risk=dict(entity.calculated_risk),
            checks=dict(entity.checks),
            idempotent_replay=entity.idempotent_replay,
            decided_at=entity.decided_at,
        )


@dataclass(frozen=True, slots=True)
class ExecutionSubmitCommand:
    user_id: UUID
    request_id: str
    symbol: str
    side: str
    order_type: str = "market"
    volume: str = "0.01"
    price: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    slippage: int = 10
    magic: int = 0
    comment: str = ""
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class ExecutionSubmitDTO:
    id: UUID
    request_id: str
    outcome: str
    retcode: int
    message: str
    symbol: str
    side: str
    order_type: str
    volume: str
    order_ticket: int | None
    deal_ticket: int | None
    price: str
    retryable: bool
    idempotent_replay: bool
    submitted_at: datetime

    @classmethod
    def from_entity(cls, entity: ExecutionAttempt) -> ExecutionSubmitDTO:
        return cls(
            id=entity.id,
            request_id=entity.request_id,
            outcome=entity.outcome.value,
            retcode=entity.retcode,
            message=entity.message,
            symbol=entity.symbol,
            side=entity.side,
            order_type=entity.order_type,
            volume=str(entity.volume),
            order_ticket=entity.order_ticket,
            deal_ticket=entity.deal_ticket,
            price=str(entity.price),
            retryable=entity.retryable,
            idempotent_replay=entity.idempotent_replay,
            submitted_at=entity.submitted_at,
        )
