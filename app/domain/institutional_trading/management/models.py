"""Phase D PME contracts — state, managed position, journal row, context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class PositionLifecycleState(StrEnum):
    """Institutional position lifecycle — progressive; EXITED is terminal."""

    OPEN = "OPEN"
    BE_MOVED = "BE_MOVED"
    PARTIAL = "PARTIAL"
    TRAILING = "TRAILING"
    EXITED = "EXITED"


class ManageActionKind(StrEnum):
    BREAK_EVEN = "break_even"
    TRAIL = "trail"
    PARTIAL_CLOSE = "partial_close"
    TIME_STOP = "time_stop"
    EMERGENCY_EXIT = "emergency_exit"
    DAILY_SHUTDOWN = "daily_shutdown"
    NOOP = "noop"
    SKIP = "skip"  # already exited / not managed / duplicate


class ManageOutcome(StrEnum):
    SUCCESS = "success"
    ABORTED = "aborted"
    DUPLICATE = "duplicate"
    OMS_FAILURE = "oms_failure"
    GATEWAY_FAILURE = "gateway_failure"
    MT5_FAILURE = "mt5_failure"
    SKIPPED = "skipped"


class VolatilityRegime(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class OmsManageResult:
    """Normalized OMS manage outcome — adapter-mapped; OMS unchanged."""

    outcome: str
    message: str
    retcode: int = 0
    order_ticket: int | None = None
    deal_ticket: int | None = None
    latency_ms: float = 0.0
    gateway_status: str = ""
    oms_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "message": self.message,
            "retcode": self.retcode,
            "order_ticket": self.order_ticket,
            "deal_ticket": self.deal_ticket,
            "latency_ms": round(self.latency_ms, 3),
            "gateway_status": self.gateway_status,
            "oms_status": self.oms_status,
        }

    @property
    def ok(self) -> bool:
        return (self.outcome or "").lower() in {"success", "filled", "done"}


@dataclass
class ManagedPosition:
    """Tracked open position under PME control."""

    ticket: int
    symbol: str
    side: str  # buy | sell
    entry_price: Decimal
    initial_volume: Decimal
    remaining_volume: Decimal
    initial_stop: Decimal
    risk_distance: Decimal  # |entry - initial_stop| = 1R
    opened_at: datetime
    state: PositionLifecycleState = PositionLifecycleState.OPEN
    current_stop: Decimal = Decimal("0")
    current_tp: Decimal = Decimal("0")
    be_moved: bool = False
    partial_done: bool = False
    trailing_active: bool = False
    max_favorable_r: Decimal = Decimal("0")
    last_manage_fingerprint: str | None = None
    exit_reason: str | None = None
    magic: int = 260720
    comment: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket": self.ticket,
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": str(self.entry_price),
            "initial_volume": str(self.initial_volume),
            "remaining_volume": str(self.remaining_volume),
            "initial_stop": str(self.initial_stop),
            "risk_distance": str(self.risk_distance),
            "opened_at": self.opened_at.isoformat(),
            "state": self.state.value,
            "current_stop": str(self.current_stop),
            "current_tp": str(self.current_tp),
            "be_moved": self.be_moved,
            "partial_done": self.partial_done,
            "trailing_active": self.trailing_active,
            "max_favorable_r": str(self.max_favorable_r),
            "exit_reason": self.exit_reason,
            "magic": self.magic,
            "comment": self.comment,
        }


@dataclass(frozen=True, slots=True)
class PositionManageContext:
    """Fresh market / account facts for one PME evaluation tick."""

    now: datetime
    current_price: Decimal
    atr: Decimal
    mid_price: Decimal | None = None
    spread: Decimal | None = None
    market_open: bool = True
    connection_stable: bool = True
    structure_broken: bool = False
    trend_reversed: bool = False
    risk_requests_exit: bool = False
    daily_loss_exceeded: bool = False
    kill_switch_armed: bool = False
    news_requests_exit: bool = False
    position_still_open: bool = True  # False if manually closed / missing from book
    book_volume: Decimal | None = None  # live broker volume if known
    book_stop: Decimal | None = None
    user_id: UUID = field(default_factory=uuid4)
    request_id: str | None = None
    connected: bool = True
    login: int | None = None


@dataclass(frozen=True, slots=True)
class PositionManageRecord:
    """Persisted PME action — every SL/TP/partial/trail/exit."""

    ticket: int
    action: ManageActionKind
    from_state: PositionLifecycleState
    to_state: PositionLifecycleState
    reason: str
    timestamp: datetime
    latency_ms: float
    outcome: ManageOutcome
    old_sl: Decimal | None = None
    new_sl: Decimal | None = None
    old_tp: Decimal | None = None
    new_tp: Decimal | None = None
    volume: Decimal | None = None
    r_multiple: Decimal | None = None
    retcode: int | None = None
    comment: str = ""
    fingerprint: str = ""
    id: UUID = field(default_factory=uuid4)
    schema_version: str = "1.0.0"
    symbol: str = "XAUUSD"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "schema_version": self.schema_version,
            "ticket": self.ticket,
            "symbol": self.symbol,
            "action": self.action.value,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "latency_ms": round(self.latency_ms, 3),
            "outcome": self.outcome.value,
            "old_sl": str(self.old_sl) if self.old_sl is not None else None,
            "new_sl": str(self.new_sl) if self.new_sl is not None else None,
            "old_tp": str(self.old_tp) if self.old_tp is not None else None,
            "new_tp": str(self.new_tp) if self.new_tp is not None else None,
            "volume": str(self.volume) if self.volume is not None else None,
            "r_multiple": str(self.r_multiple) if self.r_multiple is not None else None,
            "retcode": self.retcode,
            "comment": self.comment,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class PositionManageResult:
    """Result of one PME.evaluate call."""

    position: ManagedPosition
    action: ManageActionKind
    record: PositionManageRecord | None
    oms_result: OmsManageResult | None = None
    skipped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "position": self.position.to_dict(),
            "action": self.action.value,
            "record": self.record.to_dict() if self.record else None,
            "oms_result": self.oms_result.to_dict() if self.oms_result else None,
            "skipped": self.skipped,
        }
