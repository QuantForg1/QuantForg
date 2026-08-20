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
from app.domain.trading.xauusd_specs import VOLUME_MIN, VOLUME_STEP

SCALP_MAX_OPEN_TRADES = 10


def class_position_cap(trade_class: TradeClass | str) -> int:
    raw = (
        trade_class.value
        if isinstance(trade_class, TradeClass)
        else str(trade_class or "")
    ).upper()
    if raw == TradeClass.HOLD.value:
        return HOLD_MAX_OPEN_TRADES
    if raw == TradeClass.SCALP.value:
        return SCALP_MAX_OPEN_TRADES
    return 0


def strategy_target_count(
    *,
    trade_class: TradeClass | str,
    opportunity_score: int,
    confidence: int | None = None,
) -> int:
    """Initial mapping from score band. Never the final authorized count."""
    cls = (
        trade_class
        if isinstance(trade_class, TradeClass)
        else TradeClass(str(trade_class).upper())
    )
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


def split_aggregate_lots(
    *,
    aggregate_lots: Decimal,
    count: int,
    min_lot: Decimal = VOLUME_MIN,
    lot_step: Decimal = VOLUME_STEP,
) -> tuple[int, Decimal]:
    """Keep total risk = aggregate. Reduce N until each leg >= min_lot."""
    n = max(0, int(count))
    if n <= 0 or aggregate_lots <= 0:
        return 0, Decimal("0")
    step = lot_step if lot_step > 0 else VOLUME_STEP
    floor = min_lot if min_lot > 0 else VOLUME_MIN
    while n > 0:
        raw = aggregate_lots / Decimal(n)
        per = raw.quantize(step, rounding=ROUND_DOWN)
        if per >= floor:
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
            "aggregate_risk": self.aggregate_risk,
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
    sl: str | None = None,
    tp: str | None = None,
    base_input_hash: str = "",
    entry_policy: str = "same_thesis_market",
) -> PositionPlan:
    cls = (
        trade_class
        if isinstance(trade_class, TradeClass)
        else TradeClass(str(trade_class).upper())
    )
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
    if remaining < target:
        reductions.append(
            f"quantforg_capacity {remaining} < target {target}"
        )
    n = min(target, remaining)
    if risk_allowed_count is not None and int(risk_allowed_count) < n:
        reductions.append(
            f"risk_allowed {int(risk_allowed_count)} < {n}"
        )
        n = int(risk_allowed_count)
    if (
        portfolio_allowed_count is not None
        and int(portfolio_allowed_count) < n
    ):
        reductions.append(
            f"portfolio_allowed {int(portfolio_allowed_count)} < {n}"
        )
        n = int(portfolio_allowed_count)
    if broker_allowed_count is not None and int(broker_allowed_count) < n:
        reductions.append(
            f"broker_allowed {int(broker_allowed_count)} < {n}"
        )
        n = int(broker_allowed_count)

    aggregate = _dec(aggregate_lots)
    n, per = split_aggregate_lots(
        aggregate_lots=aggregate,
        count=n,
        min_lot=min_lot,
        lot_step=lot_step,
    )
    if n < target and aggregate > 0:
        reductions.append("sizing_split_reduced_count")
    n = margin_allowed_count(
        free_margin=free_margin,
        per_position_lots=per,
        margin_per_lot=margin_per_lot,
        requested=n,
    )
    if n > 0 and per < min_lot:
        n, per = split_aggregate_lots(
            aggregate_lots=aggregate,
            count=n,
            min_lot=min_lot,
            lot_step=lot_step,
        )

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
        requested_count=int(n),
        state="POSITION_PLAN_READY" if n > 0 else "SOFT_REJECT",
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
