"""Phase C execution bridge contracts — journal, results, runtime context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    DecisionAction,
)
from app.domain.institutional_trading.models import MarketAnalysisSnapshot


class ExecutionMode(StrEnum):
    """Deployment modes for the bridge."""

    SHADOW = "SHADOW"  # decide + journal; never call OMS
    CANARY_LIVE = "CANARY_LIVE"  # live OMS, max N trades/day
    LIVE = "LIVE"  # full live (still gated by EXECUTION_ENABLED)


class BridgeAbortReason(StrEnum):
    """Why the bridge refused to call OMS (or recorded a non-forward)."""

    IGNORED_ACTION = "ignored_action"  # WATCH / NO_TRADE
    INPUT_HASH_MISMATCH = "input_hash_mismatch"
    DECISION_EXPIRED = "decision_expired"
    SESSION_INVALID = "session_invalid"
    MARKET_CLOSED = "market_closed"
    SPREAD_UNACCEPTABLE = "spread_unacceptable"
    ELIGIBILITY_FAILED = "eligibility_failed"
    EXECUTION_DISABLED = "execution_disabled"
    KILL_SWITCH = "kill_switch"
    DUPLICATE_DECISION = "duplicate_decision"
    CANARY_DAILY_CAP = "canary_daily_cap"
    MISSING_LOTS = "missing_lots"
    MISSING_ZONES = "missing_zones"
    OMS_FAILURE = "oms_failure"
    GATEWAY_FAILURE = "gateway_failure"
    MT5_REJECTION = "mt5_rejection"
    NONE = "none"


class ExecutionAttemptStatus(StrEnum):
    ABORTED = "aborted"
    SHADOW = "shadow"
    FORWARDED = "forwarded"
    DUPLICATE = "duplicate"
    OMS_REJECTED = "oms_rejected"
    OMS_SUCCESS = "oms_success"


@dataclass(frozen=True, slots=True)
class OmsSubmitResult:
    """Normalized OMS outcome — mapped by adapter; OMS itself unchanged."""

    outcome: str  # success | failed | disabled | rejected | …
    message: str
    retcode: int = 0
    order_ticket: int | None = None
    deal_ticket: int | None = None
    oms_status: str = ""
    gateway_status: str = ""
    latency_ms: float = 0.0
    retryable: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "message": self.message,
            "retcode": self.retcode,
            "order_ticket": self.order_ticket,
            "deal_ticket": self.deal_ticket,
            "oms_status": self.oms_status,
            "gateway_status": self.gateway_status,
            "latency_ms": round(self.latency_ms, 3),
            "retryable": self.retryable,
        }


@dataclass(frozen=True, slots=True)
class ExecutionBridgeContext:
    """Fresh market / account facts for bridge re-verification."""

    expected_input_hash: str
    now: datetime
    snapshot: MarketAnalysisSnapshot
    account: AccountRiskState
    risk_allowed: bool = True
    risk_reasons: tuple[str, ...] = ()
    execution_enabled: bool = False
    connected: bool = True
    login: int | None = None
    user_id: UUID = field(default_factory=uuid4)
    request_id: str | None = None

    @property
    def session_valid(self) -> bool:
        return self.snapshot.session.allowed

    @property
    def market_open(self) -> bool:
        return self.account.market_open

    @property
    def spread(self) -> Decimal | None:
        return self.snapshot.spread


@dataclass(frozen=True, slots=True)
class ExecutionAttemptRecord:
    """Persisted execution attempt — every bridge evaluation."""

    decision_hash: str
    input_hash: str
    timestamp: datetime
    decision_action: DecisionAction
    confidence: int
    quality: int
    approved_lots: Decimal | None
    oms_status: str
    gateway_status: str
    mt5_ticket: int | None
    mt5_deal: int | None
    retcode: int | None
    comment: str
    latency_ms: float
    execution_result: str
    abort_reason: BridgeAbortReason = BridgeAbortReason.NONE
    mode: ExecutionMode = ExecutionMode.SHADOW
    status: ExecutionAttemptStatus = ExecutionAttemptStatus.ABORTED
    id: UUID = field(default_factory=uuid4)
    schema_version: str = "1.0.0"
    symbol: str = "XAUUSD"
    request_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "schema_version": self.schema_version,
            "decision_hash": self.decision_hash,
            "input_hash": self.input_hash,
            "timestamp": self.timestamp.isoformat(),
            "decision_action": self.decision_action.value,
            "confidence": self.confidence,
            "quality": self.quality,
            "approved_lots": (
                str(self.approved_lots) if self.approved_lots is not None else None
            ),
            "oms_status": self.oms_status,
            "gateway_status": self.gateway_status,
            "mt5_ticket": self.mt5_ticket,
            "mt5_deal": self.mt5_deal,
            "retcode": self.retcode,
            "comment": self.comment,
            "latency_ms": round(self.latency_ms, 3),
            "execution_result": self.execution_result,
            "abort_reason": self.abort_reason.value,
            "mode": self.mode.value,
            "status": self.status.value,
            "symbol": self.symbol,
            "request_id": self.request_id,
        }


@dataclass(frozen=True, slots=True)
class ExecutionBridgeResult:
    """Outcome of one bridge.handle(decision) call."""

    forwarded_to_oms: bool
    aborted: bool
    abort_reason: BridgeAbortReason
    decision_hash: str
    journal_entry: ExecutionAttemptRecord
    oms_result: OmsSubmitResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "forwarded_to_oms": self.forwarded_to_oms,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason.value,
            "decision_hash": self.decision_hash,
            "journal_entry": self.journal_entry.to_dict(),
            "oms_result": self.oms_result.to_dict() if self.oms_result else None,
        }
