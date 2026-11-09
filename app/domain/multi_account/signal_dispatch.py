"""Durable central-signal and per-account execution intent models.

Phase 1 ships the contracts and state vocabulary only. Persistence and
worker handoff land in later phases. Idempotency keys are mandatory so
retries never invent duplicate broker orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class AccountExecutionState(StrEnum):
    """Per-account lifecycle for one central signal."""

    RECEIVED = "received"
    ELIGIBILITY_PENDING = "eligibility_pending"
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"
    RISK_VALIDATED = "risk_validated"
    QUEUED = "queued"
    SUBMITTING = "submitting"
    ACKNOWLEDGED = "acknowledged"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"
    UNKNOWN = "unknown"


_TERMINAL = frozenset(
    {
        AccountExecutionState.BLOCKED,
        AccountExecutionState.FILLED,
        AccountExecutionState.REJECTED,
        AccountExecutionState.CANCELLED,
        AccountExecutionState.DEAD_LETTER,
    }
)


@dataclass(frozen=True, slots=True)
class CentralSignalIntent:
    """One centrally generated, qualified trading signal."""

    signal_id: UUID
    symbol: str
    side: str
    quality: int
    entry: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    strategy_id: str = ""
    trace_id: str = ""
    idempotency_key: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        symbol: str,
        side: str,
        quality: int,
        entry: Decimal | None = None,
        stop_loss: Decimal | None = None,
        take_profit: Decimal | None = None,
        strategy_id: str = "",
        trace_id: str = "",
        idempotency_key: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CentralSignalIntent:
        sid = uuid4()
        key = (idempotency_key or "").strip() or f"signal:{sid}"
        return cls(
            signal_id=sid,
            symbol=symbol.strip().upper(),
            side=side.strip().upper(),
            quality=int(quality),
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy_id=strategy_id.strip(),
            trace_id=trace_id.strip(),
            idempotency_key=key,
            metadata=dict(metadata or {}),
        )


@dataclass(frozen=True, slots=True)
class AccountExecutionIntent:
    """Independent execution decision for one connected account."""

    execution_id: UUID
    signal_id: UUID
    user_id: UUID
    broker_account_id: UUID
    state: AccountExecutionState
    idempotency_key: str
    block_reason: str | None = None
    planned_volume: Decimal | None = None
    broker_ticket: str | None = None
    attempt_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def for_account(
        cls,
        *,
        signal: CentralSignalIntent,
        user_id: UUID,
        broker_account_id: UUID,
    ) -> AccountExecutionIntent:
        eid = uuid4()
        return cls(
            execution_id=eid,
            signal_id=signal.signal_id,
            user_id=user_id,
            broker_account_id=broker_account_id,
            state=AccountExecutionState.RECEIVED,
            idempotency_key=f"{signal.idempotency_key}:acct:{broker_account_id}",
        )

    @property
    def is_terminal(self) -> bool:
        return self.state in _TERMINAL

    def transition(
        self,
        new_state: AccountExecutionState,
        *,
        block_reason: str | None = None,
        planned_volume: Decimal | None = None,
        broker_ticket: str | None = None,
    ) -> AccountExecutionIntent:
        """Return a new intent with updated state (immutable)."""
        if self.is_terminal and new_state != self.state:
            raise ValueError(
                "cannot transition terminal state "
                f"{self.state.value} → {new_state.value}"
            )
        reason = block_reason if block_reason is not None else self.block_reason
        volume = planned_volume if planned_volume is not None else self.planned_volume
        ticket = broker_ticket if broker_ticket is not None else self.broker_ticket
        attempts = self.attempt_count
        if new_state is AccountExecutionState.SUBMITTING:
            attempts += 1
        return AccountExecutionIntent(
            execution_id=self.execution_id,
            signal_id=self.signal_id,
            user_id=self.user_id,
            broker_account_id=self.broker_account_id,
            state=new_state,
            idempotency_key=self.idempotency_key,
            block_reason=reason,
            planned_volume=volume,
            broker_ticket=ticket,
            attempt_count=attempts,
            created_at=self.created_at,
            updated_at=datetime.now(UTC),
            metadata=dict(self.metadata),
        )
