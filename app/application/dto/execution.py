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
    position: int = 0
    order_ticket: int = 0
    oms_kind: str = ""
    ip_address: str = ""
    user_agent: str = ""
    # Terminal audit stage for broker attempt (submit vs manage). Does not change OMS.
    audit_stage: str = "submit"


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
    stages: list[dict[str, object]] | None = None
    latency_ms: float | None = None
    journal_entry: dict[str, object] | None = None

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


@dataclass(frozen=True, slots=True)
class ExecutionCancelCommand:
    user_id: UUID
    request_id: str
    ticket: int
    symbol: str = ""
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class ExecutionCancelDTO:
    request_id: str
    outcome: str
    message: str
    ticket: int
    stages: list[dict[str, object]]
    latency_ms: float
    journal_entry: dict[str, object] | None = None
    rejection_reasons: list[str] | None = None


@dataclass(frozen=True, slots=True)
class ExecutionManageCommand:
    user_id: UUID
    request_id: str
    action: str
    symbol: str
    ticket: int | None = None
    side: str | None = None
    order_type: str | None = None
    volume: str | None = None
    price: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    slippage: int = 10
    magic: int = 0
    comment: str = ""
    trailing_points: str | None = None
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class ExecutionPipelineDTO:
    request_id: str
    action: str
    outcome: str
    message: str
    stages: list[dict[str, object]]
    latency_ms: float
    rejection_reasons: list[str] | None = None
    journal_entry: dict[str, object] | None = None
    order_ticket: int | None = None
    deal_ticket: int | None = None
    price: str | None = None
