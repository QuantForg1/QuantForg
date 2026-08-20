"""One authoritative decision cycle — snapshot, state machine, latency.

Downstream stages consume this snapshot. Mutations stay sequential.
Does not call OMS, order_send, or invent a second execution path.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from app.domain.trading.gold_only import (
    CANONICAL_GOLD_BROKER_DISPLAY,
    GOLD_SYMBOL,
    display_autonomous_symbol,
    is_gold_symbol,
)

AUTHORITATIVE_MAX_AGE_MS = 15_000
STALE_RISK_MAX_AGE_MS = 8_000
STALE_SAFETY_MAX_AGE_MS = 8_000


class CycleState(StrEnum):
    NEW_SIGNAL = "NEW_SIGNAL"
    SNAPSHOT_READY = "SNAPSHOT_READY"
    OPPORTUNITY_SCORED = "OPPORTUNITY_SCORED"
    CLASSIFIED = "CLASSIFIED"
    POSITION_PLAN_READY = "POSITION_PLAN_READY"
    RISK_CHECKED = "RISK_CHECKED"
    SAFETY_CHECKED = "SAFETY_CHECKED"
    EXECUTION_AUTHORIZED = "EXECUTION_AUTHORIZED"
    BATCH_SUBMITTING = "BATCH_SUBMITTING"
    PARTIAL_FILL = "PARTIAL_FILL"
    FULL_FILL = "FULL_FILL"
    RECONCILIATION = "RECONCILIATION"
    POSITION_MANAGEMENT = "POSITION_MANAGEMENT"
    WATCH_NEXT_SIGNAL = "WATCH_NEXT_SIGNAL"
    WAITING = "WAITING"
    SOFT_REJECT = "SOFT_REJECT"
    HARD_BLOCK = "HARD_BLOCK"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    SYSTEM_DEGRADED = "SYSTEM_DEGRADED"


@dataclass
class LatencyBudget:
    market_ms: float = 0.0
    scan_ms: float = 0.0
    probability_ms: float = 0.0
    decision_ms: float = 0.0
    risk_ms: float = 0.0
    safety_ms: float = 0.0
    sizing_ms: float = 0.0
    portfolio_ms: float = 0.0
    optimizer_ms: float = 0.0
    oms_ms: float = 0.0
    gateway_ms: float = 0.0
    reconciliation_ms: float = 0.0
    total_cycle_ms: float = 0.0
    decision_cycle_latency_ms: float = 0.0
    signal_detect_to_snapshot_ms: float = 0.0
    snapshot_to_probability_ms: float = 0.0
    probability_to_decision_ms: float = 0.0
    decision_to_risk_ms: float = 0.0
    risk_to_safety_ms: float = 0.0
    safety_to_plan_ms: float = 0.0
    plan_to_oms_ms: float = 0.0
    oms_to_gateway_ms: float = 0.0
    gateway_to_broker_ms: float = 0.0
    total_decision_cycle_ms: float = 0.0
    time_from_signal_to_first_order_send: float | None = None
    time_from_signal_to_last_order_send: float | None = None
    largest_stage: str | None = None
    largest_stage_ms: float = 0.0
    api_connectivity_ms: float = 0.0
    auth_ms: float = 0.0
    strategy_ms: float = 0.0
    market_data_ms: float = 0.0
    signal_to_decision_ms: float = 0.0
    signal_to_execution_ready_ms: float = 0.0

    def finalize(self) -> None:
        named = {
            "market_ms": self.market_ms,
            "scan_ms": self.scan_ms,
            "probability_ms": self.probability_ms,
            "decision_ms": self.decision_ms,
            "risk_ms": self.risk_ms,
            "safety_ms": self.safety_ms,
            "sizing_ms": self.sizing_ms,
            "portfolio_ms": self.portfolio_ms,
            "optimizer_ms": self.optimizer_ms,
            "oms_ms": self.oms_ms,
            "gateway_ms": self.gateway_ms,
            "reconciliation_ms": self.reconciliation_ms,
        }
        if self.total_cycle_ms <= 0:
            self.total_cycle_ms = round(sum(named.values()), 3)
        self.decision_cycle_latency_ms = round(self.total_cycle_ms, 3)
        self.total_decision_cycle_ms = self.decision_cycle_latency_ms
        if self.market_data_ms <= 0:
            self.market_data_ms = round(self.market_ms, 3)
        if self.strategy_ms <= 0:
            self.strategy_ms = round(self.probability_ms, 3)
        if self.signal_to_decision_ms <= 0:
            self.signal_to_decision_ms = round(
                self.signal_detect_to_snapshot_ms
                + self.snapshot_to_probability_ms
                + self.probability_to_decision_ms,
                3,
            )
        if self.signal_to_execution_ready_ms <= 0:
            self.signal_to_execution_ready_ms = round(
                self.signal_to_decision_ms
                + self.decision_to_risk_ms
                + self.risk_to_safety_ms
                + self.safety_to_plan_ms,
                3,
            )
        if named:
            key = max(named, key=named.get)
            self.largest_stage = key
            self.largest_stage_ms = round(float(named[key]), 3)

    def to_dict(self) -> dict[str, Any]:
        self.finalize()
        return {
            "market_ms": round(self.market_ms, 3),
            "scan_ms": round(self.scan_ms, 3),
            "probability_ms": round(self.probability_ms, 3),
            "decision_ms": round(self.decision_ms, 3),
            "risk_ms": round(self.risk_ms, 3),
            "safety_ms": round(self.safety_ms, 3),
            "sizing_ms": round(self.sizing_ms, 3),
            "portfolio_ms": round(self.portfolio_ms, 3),
            "optimizer_ms": round(self.optimizer_ms, 3),
            "oms_ms": round(self.oms_ms, 3),
            "gateway_ms": round(self.gateway_ms, 3),
            "reconciliation_ms": round(self.reconciliation_ms, 3),
            "total_cycle_ms": round(self.total_cycle_ms, 3),
            "decision_cycle_latency_ms": round(self.decision_cycle_latency_ms, 3),
            "signal_detect_to_snapshot_ms": round(self.signal_detect_to_snapshot_ms, 3),
            "snapshot_to_probability_ms": round(self.snapshot_to_probability_ms, 3),
            "probability_to_decision_ms": round(self.probability_to_decision_ms, 3),
            "decision_to_risk_ms": round(self.decision_to_risk_ms, 3),
            "risk_to_safety_ms": round(self.risk_to_safety_ms, 3),
            "safety_to_plan_ms": round(self.safety_to_plan_ms, 3),
            "plan_to_oms_ms": round(self.plan_to_oms_ms, 3),
            "oms_to_gateway_ms": round(self.oms_to_gateway_ms, 3),
            "gateway_to_broker_ms": round(self.gateway_to_broker_ms, 3),
            "total_decision_cycle_ms": round(self.total_decision_cycle_ms, 3),
            "time_from_signal_to_first_order_send": (
                None
                if self.time_from_signal_to_first_order_send is None
                else round(self.time_from_signal_to_first_order_send, 3)
            ),
            "time_from_signal_to_last_order_send": (
                None
                if self.time_from_signal_to_last_order_send is None
                else round(self.time_from_signal_to_last_order_send, 3)
            ),
            "largest_stage": self.largest_stage,
            "largest_stage_ms": self.largest_stage_ms,
            "api_connectivity_ms": round(self.api_connectivity_ms, 3),
            "auth_ms": round(self.auth_ms, 3),
            "strategy_ms": round(self.strategy_ms, 3),
            "market_data_ms": round(self.market_data_ms, 3),
            "signal_to_decision_ms": round(self.signal_to_decision_ms, 3),
            "signal_to_execution_ready_ms": round(self.signal_to_execution_ready_ms, 3),
            "measured": True,
        }


def _symbol_identity(code: str | None) -> tuple[str, str]:
    raw = str(code or "").strip()
    if not raw or is_gold_symbol(raw):
        return GOLD_SYMBOL, display_autonomous_symbol(
            raw or CANONICAL_GOLD_BROKER_DISPLAY
        )
    return raw.upper(), raw


def utc_stamp(value: datetime | None = None) -> str:
    stamp = value or datetime.now(UTC)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def age_ms_from(stamp: str | None, *, now: datetime | None = None) -> int | None:
    if not stamp:
        return None
    try:
        raw = str(stamp).replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        moment = now or datetime.now(UTC)
        return max(0, int((moment - dt).total_seconds() * 1000.0))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class AuthoritativeCycleSnapshot:
    cycle_id: str
    snapshot_id: str
    symbol: str
    logical_symbol: str
    canonical_symbol: str
    timestamp: str
    source: str
    quote: dict[str, Any]
    spread: str | None
    atr: str | None
    market_regime: str | None
    structure: int | None
    momentum: int | None
    price_action: int | None
    liquidity: int | None
    mtf: int | None
    strategy_consensus: int | None
    opportunity_score: int | None
    direction: str
    confidence: int | None
    quality: int | None
    rr: str | None
    execution_quality: int | None
    session: str | None
    existing_quantforg_positions: int
    account_risk_state: dict[str, Any]
    broker_readiness: dict[str, Any]
    risk_as_of: str | None = None
    safety_as_of: str | None = None
    optimizer_as_of: str | None = None
    age_ms: int = 0
    state: str = CycleState.SNAPSHOT_READY.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "snapshot_id": self.snapshot_id,
            "symbol": self.symbol,
            "logical_symbol": self.logical_symbol,
            "canonical_symbol": self.canonical_symbol,
            "timestamp": self.timestamp,
            "source": self.source,
            "quote": dict(self.quote),
            "spread": self.spread,
            "atr": self.atr,
            "market_regime": self.market_regime,
            "structure": self.structure,
            "momentum": self.momentum,
            "price_action": self.price_action,
            "liquidity": self.liquidity,
            "mtf": self.mtf,
            "strategy_consensus": self.strategy_consensus,
            "opportunity_score": self.opportunity_score,
            "direction": self.direction,
            "confidence": self.confidence,
            "quality": self.quality,
            "rr": self.rr,
            "execution_quality": self.execution_quality,
            "session": self.session,
            "existing_quantforg_positions": self.existing_quantforg_positions,
            "account_risk_state": dict(self.account_risk_state),
            "broker_readiness": dict(self.broker_readiness),
            "risk_as_of": self.risk_as_of,
            "safety_as_of": self.safety_as_of,
            "optimizer_as_of": self.optimizer_as_of,
            "age_ms": self.age_ms,
            "state": self.state,
        }


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value))
    except (TypeError, ValueError):
        return None


def build_authoritative_snapshot(
    *,
    cycle_id: str | None = None,
    snapshot_id: str | None = None,
    snapshot: Any = None,
    account: Any = None,
    diagnostics: dict[str, Any] | None = None,
    opportunity: dict[str, Any] | None = None,
    quantforg_count: int | None = None,
    broker_ready: bool | None = None,
    source: str = "ite_cycle",
) -> AuthoritativeCycleSnapshot:
    diag = dict(diagnostics or {})
    opp = dict(opportunity or {})
    cid = str(cycle_id or f"cycle-{uuid4().hex[:12]}")
    sid = str(snapshot_id or f"snap-{uuid4().hex[:12]}")
    symbol = str(
        getattr(snapshot, "symbol", None)
        or diag.get("canonical_broker_symbol")
        or diag.get("symbol")
        or CANONICAL_GOLD_BROKER_DISPLAY
    )
    logical, canonical = _symbol_identity(symbol)
    stamp = utc_stamp(getattr(snapshot, "as_of", None))
    sess = getattr(snapshot, "session", None)
    session_name = (
        str(
            getattr(getattr(sess, "session", None), "value", None)
            or getattr(sess, "session", None)
            or diag.get("trading_session")
            or ""
        )
        or None
    )
    quote = {
        "bid": str(getattr(account, "bid", None) or diag.get("bid") or ""),
        "ask": str(getattr(account, "ask", None) or diag.get("ask") or ""),
        "age_seconds": getattr(account, "quote_age_seconds", None)
        or diag.get("quote_age_seconds"),
    }
    spread = getattr(snapshot, "spread", None)
    atr = getattr(snapshot, "atr", None) or getattr(account, "atr", None)
    struct = getattr(snapshot, "structure", None)
    structure_score = _as_int(
        getattr(struct, "score", None)
        if struct is not None
        else opp.get("structure") or diag.get("structure")
    )
    mom = getattr(snapshot, "momentum", None)
    momentum_score = _as_int(
        getattr(mom, "score", None)
        if mom is not None
        else opp.get("momentum") or diag.get("momentum")
    )
    qf = int(quantforg_count) if quantforg_count is not None else 0
    account_dict = account.to_dict() if hasattr(account, "to_dict") else {}
    direction = str(
        opp.get("direction")
        or getattr(getattr(snapshot, "direction", None), "value", None)
        or "NONE"
    ).upper()
    return AuthoritativeCycleSnapshot(
        cycle_id=cid,
        snapshot_id=sid,
        symbol=canonical,
        logical_symbol=logical,
        canonical_symbol=canonical,
        timestamp=stamp,
        source=source,
        quote=quote,
        spread=str(spread) if spread is not None else diag.get("spread"),
        atr=str(atr) if atr is not None else diag.get("atr"),
        market_regime=str(
            opp.get("regime")
            or getattr(getattr(snapshot, "regime", None), "value", None)
            or getattr(snapshot, "regime", None)
            or ""
        )
        or None,
        structure=structure_score,
        momentum=momentum_score,
        price_action=_as_int(opp.get("price_action") or opp.get("pa")),
        liquidity=_as_int(opp.get("liquidity")),
        mtf=_as_int(opp.get("mtf_alignment") or opp.get("mtf")),
        strategy_consensus=_as_int(opp.get("consensus")),
        opportunity_score=_as_int(opp.get("opportunity_score")),
        direction=direction,
        confidence=_as_int(opp.get("confidence")),
        quality=_as_int(opp.get("quality")),
        rr=(
            str(opp.get("rr") or opp.get("risk_reward"))
            if opp.get("rr") or opp.get("risk_reward")
            else None
        ),
        execution_quality=_as_int(opp.get("execution_quality")),
        session=session_name,
        existing_quantforg_positions=qf,
        account_risk_state=dict(account_dict),
        broker_readiness={
            "ready": (
                bool(broker_ready)
                if broker_ready is not None
                else bool(diag.get("account") == "OK")
            ),
            "mt5_autotrading_enabled": diag.get("mt5_autotrading_enabled"),
            "account_trading_enabled": diag.get("account_trading_enabled"),
        },
        risk_as_of=stamp,
        safety_as_of=stamp,
        age_ms=0,
        state=CycleState.SNAPSHOT_READY.value,
    )


def stale_authorization(
    snap: AuthoritativeCycleSnapshot,
    *,
    now: datetime | None = None,
    require_risk: bool = True,
    require_safety: bool = True,
) -> str | None:
    """Return a specific block reason. Never authorize on stale Risk/Safety."""
    age = age_ms_from(snap.timestamp, now=now)
    if age is not None and age > AUTHORITATIVE_MAX_AGE_MS:
        return "STALE_MARKET_SNAPSHOT"
    if require_risk:
        risk_age = age_ms_from(snap.risk_as_of, now=now)
        if snap.risk_as_of is None:
            return "STALE_RISK"
        if risk_age is not None and risk_age > STALE_RISK_MAX_AGE_MS:
            return "STALE_RISK"
    if require_safety:
        safety_age = age_ms_from(snap.safety_as_of, now=now)
        if snap.safety_as_of is None:
            return "STALE_SAFETY"
        if safety_age is not None and safety_age > STALE_SAFETY_MAX_AGE_MS:
            return "STALE_SAFETY"
    return None


@dataclass
class _TriggerState:
    wakeup: bool = False
    last_score: int | None = None
    last_direction: str | None = None
    last_trade_class: str | None = None
    last_reason: str | None = None


_LOCK = threading.Lock()
_TRIGGERS = _TriggerState()
_CURRENT: dict[str, Any] = {}


def reset_decision_cycle() -> None:
    global _TRIGGERS, _CURRENT
    with _LOCK:
        _TRIGGERS = _TriggerState()
        _CURRENT = {}
    try:
        from app.domain.institutional_trading.operations.position_plan import (
            reset_position_plan_guard,
        )

        reset_position_plan_guard()
    except Exception:
        return


def note_cycle_event(reason: str) -> None:
    with _LOCK:
        _TRIGGERS.wakeup = True
        _TRIGGERS.last_reason = str(reason)


def note_opportunity_change(
    *,
    score: int | None,
    direction: str | None,
    trade_class: str | None,
) -> None:
    with _LOCK:
        prev_score = _TRIGGERS.last_score
        prev_dir = _TRIGGERS.last_direction
        prev_cls = _TRIGGERS.last_trade_class
        reason = None
        if (
            prev_score is not None
            and score is not None
            and prev_score < 70 <= int(score)
        ):
            reason = "score_crossed_70"
        if (
            reason is None
            and prev_dir
            and direction
            and str(prev_dir).upper() != str(direction).upper()
        ):
            reason = "direction_change"
        if (
            reason is None
            and prev_cls
            and trade_class
            and str(prev_cls).upper() != str(trade_class).upper()
        ):
            reason = "trade_classification_change"
        if reason:
            _TRIGGERS.wakeup = True
            _TRIGGERS.last_reason = reason
        if score is not None:
            _TRIGGERS.last_score = int(score)
        if direction:
            _TRIGGERS.last_direction = str(direction).upper()
        if trade_class:
            _TRIGGERS.last_trade_class = str(trade_class).upper()


def consume_immediate_wakeup() -> str | None:
    with _LOCK:
        if not _TRIGGERS.wakeup:
            return None
        _TRIGGERS.wakeup = False
        return _TRIGGERS.last_reason or "event_driven"


def bind_current_cycle(payload: dict[str, Any]) -> None:
    with _LOCK:
        _CURRENT = dict(payload)


def current_cycle_view() -> dict[str, Any]:
    with _LOCK:
        return dict(_CURRENT)


class StageTimer:
    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self._marks: dict[str, float] = {}

    def mark(self, name: str) -> float:
        now = time.perf_counter()
        ms = (now - self._t0) * 1000.0
        prev = self._marks.get("_last", self._t0)
        delta = (now - prev) * 1000.0 if prev != self._t0 else ms
        self._marks[name] = now
        self._marks["_last"] = now
        return round(delta, 3)

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._t0) * 1000.0, 3)
