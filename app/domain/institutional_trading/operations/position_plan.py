"""Same-cycle multi-position plan for one decision thesis.

Does not send orders. Does not create a second OMS. Risk remains the
authority for aggregate size; count is reduced by risk / portfolio /
margin / QuantForg capacity. Manual tickets never consume capacity.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.operations.quantforg_position_cap import (
    QUANTFORG_MAGIC,
    count_quantforg_positions,
    live_strategy_max_open,
)
from app.domain.institutional_trading.operations.trade_classifier import (
    HOLD_MAX_OPEN_TRADES,
    HOLD_MIN_BURST,
    SCALP_MIN_BURST,
    TradeClass,
)
from app.domain.trading.gold_only import CANONICAL_GOLD_BROKER_DISPLAY
from app.domain.trading.xauusd_specs import VOLUME_MAX, VOLUME_MIN, VOLUME_STEP

SCALP_MAX_OPEN_TRADES = 10


def _coerce_trade_class(trade_class: TradeClass | str) -> TradeClass:
    if isinstance(trade_class, TradeClass):
        return trade_class
    raw = str(trade_class or "").upper()
    if raw == TradeClass.HOLD.value:
        return TradeClass.HOLD
    if raw == TradeClass.SCALP.value:
        return TradeClass.SCALP
    return TradeClass.NO_TRADE


def class_position_cap(trade_class: TradeClass | str) -> int:
    raw = _coerce_trade_class(trade_class)
    if raw is TradeClass.HOLD:
        return HOLD_MAX_OPEN_TRADES
    if raw is TradeClass.SCALP:
        return SCALP_MAX_OPEN_TRADES
    return 0


def strategy_target_count(
    *,
    trade_class: TradeClass | str,
    opportunity_score: int,
    confidence: int | None = None,
) -> int:
    """Initial mapping from score band. Never the final authorized count."""
    cls = _coerce_trade_class(trade_class)
    score = max(0, min(100, int(opportunity_score)))
    conf = int(confidence) if confidence is not None else score
    # Slight confidence tilt inside a band — never jumps a class cap.
    tilt = 1 if conf >= min(100, score + 5) else 0
    if cls is TradeClass.NO_TRADE:
        return 0
    if cls is TradeClass.HOLD:
        if score < 75:
            n = 1
        elif score < 80:
            n = 2
        elif score < 85:
            n = 3
        elif score < 90:
            n = 4
        else:
            n = 5
        return max(HOLD_MIN_BURST, min(HOLD_MAX_OPEN_TRADES, n))
    # SCALP
    if score < 75:
        n = 2
    elif score < 80:
        n = 3 + tilt
    elif score < 85:
        n = 5 + tilt
    elif score < 90:
        n = 7 + tilt
    else:
        n = 9 + (1 if score >= 95 or tilt else 0)
    return max(SCALP_MIN_BURST, min(SCALP_MAX_OPEN_TRADES, n))


def remaining_quantforg_capacity(
    *,
    current_count: int,
    configured_max: int,
    class_cap: int,
) -> int:
    live = max(0, int(configured_max) - max(0, int(current_count)))
    return max(0, min(live, max(0, int(class_cap))))


def _dec(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except Exception:
        return Decimal(default)


def risk_allowed_count_from_lots(
    *,
    aggregate_lots: Decimal,
    min_lot: Decimal = VOLUME_MIN,
    cap: int = SCALP_MAX_OPEN_TRADES,
) -> int:
    """How many min-lot positions fit in approved aggregate. Never upsizes."""
    if aggregate_lots <= 0 or min_lot <= 0 or cap <= 0:
        return 0
    return max(0, min(int(cap), int(aggregate_lots // min_lot)))


def split_aggregate_lots(
    *,
    aggregate_lots: Decimal,
    count: int,
    min_lot: Decimal = VOLUME_MIN,
    lot_step: Decimal = VOLUME_STEP,
    max_lot: Decimal = VOLUME_MAX,
) -> tuple[int, Decimal]:
    """Keep total risk <= aggregate. Reduce N until each leg is broker-legal.

    Naive ``aggregate / requested_count`` below min_lot must reduce N, not
    reject the thesis. MIN_LOT only when even one legal leg cannot fit.
    """
    n = max(0, int(count))
    if n <= 0 or aggregate_lots <= 0:
        return 0, Decimal("0")
    step = lot_step if lot_step > 0 else VOLUME_STEP
    floor = min_lot if min_lot > 0 else VOLUME_MIN
    ceiling = max_lot if max_lot > 0 else VOLUME_MAX
    while n > 0:
        raw = aggregate_lots / Decimal(n)
        per = raw.quantize(step, rounding=ROUND_DOWN)
        if per > ceiling:
            per = ceiling.quantize(step, rounding=ROUND_DOWN)
        if per >= floor and (per * Decimal(n)) <= aggregate_lots:
            return n, per
        n -= 1
    return 0, Decimal("0")


def margin_allowed_count(
    *,
    free_margin: Decimal | None,
    per_position_lots: Decimal,
    margin_per_lot: Decimal | None,
    requested: int,
) -> int:
    if requested <= 0:
        return 0
    if free_margin is None or margin_per_lot is None:
        return requested
    if margin_per_lot <= 0 or per_position_lots <= 0:
        return requested
    need = per_position_lots * margin_per_lot
    if need <= 0:
        return requested
    allowed = int(free_margin // need)
    return max(0, min(requested, allowed))


@dataclass(frozen=True, slots=True)
class PositionLeg:
    leg_index: int
    lots: Decimal
    input_hash: str
    idempotency_key: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "leg_index": self.leg_index,
            "lots": str(self.lots),
            "input_hash": self.input_hash,
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True, slots=True)
class PositionPlan:
    position_plan_id: str
    cycle_id: str
    snapshot_id: str
    symbol: str
    direction: str
    trade_class: str
    opportunity_score: int
    confidence: int | None
    target_count: int
    effective_count: int
    per_position_lots: Decimal
    aggregate_lots: Decimal
    aggregate_risk: str
    sl: str | None
    tp: str | None
    entry_policy: str
    idempotency_key: str
    reductions: tuple[str, ...]
    legs: tuple[PositionLeg, ...]
    requested_count: int = 0
    submitted_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    unknown_count: int = 0
    state: str = "POSITION_PLAN_READY"
    strategy_target_count: int = 0
    risk_allowed_count: int = 0
    portfolio_allowed_count: int | None = None
    broker_allowed_count: int | None = None
    remaining_capacity: int = 0
    broker_min_lot: Decimal = VOLUME_MIN
    broker_step: Decimal = VOLUME_STEP
    broker_max_lot: Decimal = VOLUME_MAX
    margin_required: str | None = None
    margin_available: str | None = None
    min_lot_constraint_reason: str | None = None
    margin_allowed_count: int | None = None
    blocking_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_plan_id": self.position_plan_id,
            "cycle_id": self.cycle_id,
            "snapshot_id": self.snapshot_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "trade_class": self.trade_class,
            "opportunity_score": self.opportunity_score,
            "confidence": self.confidence,
            "target_count": self.target_count,
            "effective_count": self.effective_count,
            "per_position_size": str(self.per_position_lots),
            "per_position_lots": str(self.per_position_lots),
            "aggregate_risk": self.aggregate_risk,
            "approved_risk": self.aggregate_risk,
            "approved_lots": str(self.aggregate_lots),
            "sl": self.sl,
            "tp": self.tp,
            "entry_policy": self.entry_policy,
            "idempotency_key": self.idempotency_key,
            "reductions": list(self.reductions),
            "legs": [leg.to_dict() for leg in self.legs],
            "requested_count": self.requested_count,
            "submitted_count": self.submitted_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "unknown_count": self.unknown_count,
            "state": self.state,
            "strategy_target_count": self.strategy_target_count,
            "risk_allowed_count": self.risk_allowed_count,
            "portfolio_allowed_count": self.portfolio_allowed_count,
            "broker_allowed_count": self.broker_allowed_count,
            "remaining_capacity": self.remaining_capacity,
            "broker_min_lot": str(self.broker_min_lot),
            "broker_step": str(self.broker_step),
            "broker_max_lot": str(self.broker_max_lot),
            "margin_required": self.margin_required,
            "margin_available": self.margin_available,
            "min_lot_constraint_reason": self.min_lot_constraint_reason,
            "margin_allowed_count": self.margin_allowed_count,
            "blocking_reason": self.blocking_reason,
        }


def leg_input_hash(base_hash: str, plan_id: str, leg_index: int) -> str:
    payload = f"{base_hash}|plan:{plan_id}|leg:{leg_index}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_position_plan(
    *,
    cycle_id: str,
    snapshot_id: str,
    symbol: str,
    direction: str,
    trade_class: TradeClass | str,
    opportunity_score: int,
    confidence: int | None,
    aggregate_lots: Decimal | None,
    current_quantforg_count: int,
    ite_config: Any | None,
    risk_allowed_count: int | None = None,
    portfolio_allowed_count: int | None = None,
    broker_allowed_count: int | None = None,
    free_margin: Decimal | None = None,
    margin_per_lot: Decimal | None = None,
    min_lot: Decimal = VOLUME_MIN,
    lot_step: Decimal = VOLUME_STEP,
    max_lot: Decimal = VOLUME_MAX,
    sl: str | None = None,
    tp: str | None = None,
    base_input_hash: str = "",
    entry_policy: str = "same_thesis_market",
) -> PositionPlan:
    cls = _coerce_trade_class(trade_class)
    target = strategy_target_count(
        trade_class=cls,
        opportunity_score=opportunity_score,
        confidence=confidence,
    )
    reductions: list[str] = []
    class_cap = class_position_cap(cls)
    live_cap = live_strategy_max_open(ite_config)
    if cls is TradeClass.SCALP:
        live_cap = min(live_cap, SCALP_MAX_OPEN_TRADES)
    else:
        live_cap = min(live_cap, HOLD_MAX_OPEN_TRADES)
    remaining = remaining_quantforg_capacity(
        current_count=current_quantforg_count,
        configured_max=live_cap,
        class_cap=class_cap,
    )
    aggregate = _dec(aggregate_lots)
    floor = min_lot if min_lot > 0 else VOLUME_MIN
    ceiling = max_lot if max_lot > 0 else VOLUME_MAX
    implied_risk_n = risk_allowed_count_from_lots(
        aggregate_lots=aggregate,
        min_lot=floor,
        cap=max(class_cap, target),
    )
    risk_n = implied_risk_n
    if risk_allowed_count is not None:
        risk_n = min(risk_n, max(0, int(risk_allowed_count)))
    portfolio_n = (
        max(0, int(portfolio_allowed_count))
        if portfolio_allowed_count is not None
        else None
    )
    broker_n = (
        max(0, int(broker_allowed_count))
        if broker_allowed_count is not None
        else None
    )

    if remaining < target:
        reductions.append(
            f"quantforg_capacity {remaining} < target {target}"
        )
    n = min(target, remaining)
    if risk_n < n:
        reductions.append(f"risk_allowed {risk_n} < {n}")
        n = risk_n
    if portfolio_n is not None and portfolio_n < n:
        reductions.append(f"portfolio_allowed {portfolio_n} < {n}")
        n = portfolio_n
    if broker_n is not None and broker_n < n:
        reductions.append(f"broker_allowed {broker_n} < {n}")
        n = broker_n

    n, per = split_aggregate_lots(
        aggregate_lots=aggregate,
        count=n,
        min_lot=floor,
        lot_step=lot_step,
        max_lot=ceiling,
    )
    if n < target and aggregate > 0:
        reductions.append("sizing_split_reduced_count")
    before_margin = n
    n = margin_allowed_count(
        free_margin=free_margin,
        per_position_lots=per,
        margin_per_lot=margin_per_lot,
        requested=n,
    )
    if n < before_margin:
        reductions.append(f"margin_allowed {n} < {before_margin}")
    margin_n = int(n)
    # Keep per-leg size after margin reduction — do not re-concentrate
    # leftover aggregate into fewer legs (that would raise per-leg risk).
    if n > 0 and (per < floor or per > ceiling):
        n, per = split_aggregate_lots(
            aggregate_lots=aggregate,
            count=n,
            min_lot=floor,
            lot_step=lot_step,
            max_lot=ceiling,
        )

    min_lot_reason: str | None = None
    skip_min_lot = (
        cls is TradeClass.NO_TRADE
        or str(direction or "").upper() == "NONE"
        or (n <= 0 and remaining <= 0 and int(current_quantforg_count) > 0)
    )
    if skip_min_lot:
        min_lot_reason = None
    elif n <= 0:
        if aggregate < floor:
            min_lot_reason = (
                "MIN_LOT_CONSTRAINT: even one broker-compliant position "
                f"cannot fit approved_lots={aggregate} min_lot={floor}"
            )
        elif aggregate > 0:
            min_lot_reason = (
                "MIN_LOT_CONSTRAINT: no lot-step allocation within "
                f"approved_lots={aggregate} min_lot={floor} step={lot_step}"
            )

    blocking: str | None = None
    if min_lot_reason:
        blocking = min_lot_reason
    elif reductions:
        blocking = "; ".join(reductions)
    elif n <= 0:
        blocking = "effective_position_count=0"

    margin_need: str | None = None
    margin_avail: str | None = None
    if n > 0 and per > 0 and margin_per_lot is not None and margin_per_lot > 0:
        margin_need = str((per * margin_per_lot * Decimal(n)).quantize(Decimal("0.01")))
    if free_margin is not None:
        margin_avail = str(_dec(free_margin))

    plan_id = f"plan-{uuid4().hex[:16]}"
    idem = hashlib.sha256(
        f"{cycle_id}|{snapshot_id}|{plan_id}".encode()
    ).hexdigest()[:24]
    legs: list[PositionLeg] = []
    for i in range(n):
        h = leg_input_hash(base_input_hash or idem, plan_id, i)
        legs.append(
            PositionLeg(
                leg_index=i,
                lots=per,
                input_hash=h,
                idempotency_key=f"{idem}:leg:{i}",
            )
        )
    return PositionPlan(
        position_plan_id=plan_id,
        cycle_id=str(cycle_id),
        snapshot_id=str(snapshot_id),
        symbol=str(symbol or CANONICAL_GOLD_BROKER_DISPLAY),
        direction=str(direction or "NONE").upper(),
        trade_class=cls.value,
        opportunity_score=int(opportunity_score),
        confidence=confidence,
        target_count=int(target),
        effective_count=int(n),
        per_position_lots=per,
        aggregate_lots=aggregate,
        aggregate_risk=str(aggregate),
        sl=sl,
        tp=tp,
        entry_policy=entry_policy,
        idempotency_key=idem,
        reductions=tuple(reductions),
        legs=tuple(legs),
        requested_count=int(target),
        state="POSITION_PLAN_READY" if n > 0 else "SOFT_REJECT",
        strategy_target_count=int(target),
        risk_allowed_count=int(risk_n),
        portfolio_allowed_count=portfolio_n,
        broker_allowed_count=broker_n,
        remaining_capacity=int(remaining),
        broker_min_lot=floor,
        broker_step=lot_step if lot_step > 0 else VOLUME_STEP,
        broker_max_lot=ceiling,
        margin_required=margin_need,
        margin_available=margin_avail,
        min_lot_constraint_reason=min_lot_reason,
        margin_allowed_count=margin_n,
        blocking_reason=blocking,
    )


_LOCK = threading.Lock()
_EXECUTED_CYCLES: dict[str, str] = {}


def reset_position_plan_guard() -> None:
    with _LOCK:
        _EXECUTED_CYCLES.clear()


def cycle_already_executed(cycle_id: str, snapshot_id: str) -> str | None:
    key = f"{cycle_id}:{snapshot_id}"
    with _LOCK:
        return _EXECUTED_CYCLES.get(key)


def mark_cycle_executed(
    cycle_id: str, snapshot_id: str, plan_id: str
) -> bool:
    """True when this cycle/snapshot is newly reserved (not a duplicate)."""
    key = f"{cycle_id}:{snapshot_id}"
    with _LOCK:
        if key in _EXECUTED_CYCLES:
            return False
        _EXECUTED_CYCLES[key] = plan_id
        return True


def owned_count_from_rows(
    rows: list[Any] | tuple[Any, ...] | None,
    *,
    symbol: str = CANONICAL_GOLD_BROKER_DISPLAY,
) -> int:
    return count_quantforg_positions(
        rows, symbol=symbol, execution_identity=QUANTFORG_MAGIC
    )


@dataclass
class BatchFillTally:
    requested_count: int = 0
    submitted_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    unknown_count: int = 0
    retried_count: int = 0
    state: str = "BATCH_SUBMITTING"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_count": self.requested_count,
            "submitted_count": self.submitted_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "unknown_count": self.unknown_count,
            "retried_count": self.retried_count,
            "state": self.state,
            "reasons": list(self.reasons),
        }


def apply_tally(plan: PositionPlan, tally: BatchFillTally) -> PositionPlan:
    from dataclasses import replace

    state = tally.state
    if tally.unknown_count > 0:
        state = "RECONCILIATION_REQUIRED"
    elif tally.accepted_count == tally.requested_count and tally.requested_count:
        state = "FULL_FILL"
    elif tally.accepted_count > 0:
        state = "PARTIAL_FILL"
    elif tally.submitted_count > 0:
        state = "REJECTED"
    return replace(
        plan,
        requested_count=tally.requested_count,
        submitted_count=tally.submitted_count,
        accepted_count=tally.accepted_count,
        rejected_count=tally.rejected_count,
        unknown_count=tally.unknown_count,
        state=state,
    )
