"""Pre-Risk min-lot feasibility — audit / early-reject only.

Does not change stops, lots, the 5% hard ceiling, or Risk semantics.
The Risk Engine remains authoritative on the continue path.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Any

from app.domain.institutional_trading.micro_account_mode import MicroAccountProfile
from app.domain.trading.xauusd_specs import CONTRACT_SIZE, VOLUME_MIN

CLASS_INFEASIBLE = "MIN_LOT_INFEASIBLE"
CLASS_FEASIBLE = "FEASIBLE"
CLASS_INSUFFICIENT = "INSUFFICIENT_DATA"

# Truthful sizing / abort codes — do not collapse budget-exceed into a generic
# MIN_LOT_CONSTRAINT hide. MIN_LOT_CONSTRAINT remains the institutional
# never-upsize label (equity above the existing micro cap).
CODE_MIN_LOT_EXCEEDS_RISK_BUDGET = "MIN_LOT_EXCEEDS_RISK_BUDGET"
CODE_MIN_LOT_CONSTRAINT = "MIN_LOT_CONSTRAINT"
CODE_INVALID_BROKER_SPEC = "INVALID_BROKER_SPEC"

STATUS_OK = "ok"
STATUS_NORMALIZED_TO_MIN = "normalized_to_min_lot"
STATUS_CAPPED_MAX = "capped_max_lot"
STATUS_EXCEEDS_BUDGET = "min_lot_exceeds_risk_budget"
STATUS_BELOW_MIN = "below_min_lot"
STATUS_INVALID_SPEC = "invalid_broker_spec"

# Existing micro-account ceiling for a min-lot bump (RiskEngine / scalping).
MICRO_EQUITY_CAP = Decimal("500")

_PCT = Decimal("100")
_CENTS = Decimal("0.01")


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        out = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception:
        return None
    return out


def max_allowed_stop_at_min_lot(
    *,
    equity: Decimal,
    hard_max_risk_pct: Decimal,
    min_lot: Decimal,
    contract_size: Decimal,
) -> Decimal:
    """Largest strategy stop at which 0.01 (min lot) still stays <= hard max.

    max_allowed_stop = equity * (hard_max_risk_pct / 100)
                       / (min_lot * contract_size)

    ``hard_max_risk_pct`` is the percent figure used by MicroAccountProfile
    (80.0 means 80%), not a 0.80 fraction.
    """
    if equity <= 0 or min_lot <= 0 or contract_size <= 0 or hard_max_risk_pct <= 0:
        return Decimal("0")
    return (equity * hard_max_risk_pct / _PCT) / (min_lot * contract_size)


def min_lot_needed_pct(
    *,
    stop_distance: Decimal,
    equity: Decimal,
    min_lot: Decimal,
    contract_size: Decimal,
) -> Decimal:
    """Risk-identical min-lot open risk percent (2 d.p.).

    min_loss = (min_lot * contract_size * stop).quantize(0.01)
    needed_pct = (min_loss / equity * 100).quantize(0.01)
    """
    min_loss = (min_lot * contract_size * stop_distance).quantize(_CENTS)
    return (min_loss / equity * _PCT).quantize(_CENTS)


@dataclass(frozen=True, slots=True)
class MinLotFeasibilityResult:
    classification: str
    infeasible: bool
    skip_expensive_downstream: bool
    stop_distance: Decimal | None
    max_allowed_stop: Decimal | None
    equity: Decimal | None
    min_lot: Decimal | None
    contract_size: Decimal | None
    hard_max_risk_pct: Decimal
    needed_pct: Decimal | None
    risk_reasons: tuple[str, ...]
    risk_engine_authoritative: bool
    stop_changed: bool = False
    lot_changed: bool = False
    hard_max_changed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "infeasible": self.infeasible,
            "skip_expensive_downstream": self.skip_expensive_downstream,
            "stop_distance": (
                str(self.stop_distance) if self.stop_distance is not None else None
            ),
            "max_allowed_stop_at_min_lot": (
                str(self.max_allowed_stop)
                if self.max_allowed_stop is not None
                else None
            ),
            "equity": str(self.equity) if self.equity is not None else None,
            "min_lot": str(self.min_lot) if self.min_lot is not None else None,
            "contract_size": (
                str(self.contract_size) if self.contract_size is not None else None
            ),
            "hard_max_risk_pct": str(self.hard_max_risk_pct),
            "needed_pct": str(self.needed_pct) if self.needed_pct is not None else None,
            "risk_reasons": list(self.risk_reasons),
            "risk_engine_authoritative": self.risk_engine_authoritative,
            "stop_changed": self.stop_changed,
            "lot_changed": self.lot_changed,
            "hard_max_changed": self.hard_max_changed,
        }


def evaluate_min_lot_feasibility(
    *,
    stop_distance: Any,
    equity: Any,
    min_lot: Any = None,
    contract_size: Any = None,
    hard_max_risk_pct: Any = None,
) -> MinLotFeasibilityResult:
    """Classify whether the existing strategy stop can fit min lot under 5%.

    Infeasible → early MIN_LOT_INFEASIBLE (skip Risk overlay / OMS work).
    Feasible / insufficient data → continue; Risk remains authoritative.
    Never mutates stop, lot, or the hard ceiling.
    """
    profile = MicroAccountProfile()
    hard = _dec(hard_max_risk_pct) or profile.hard_max_risk_pct
    lot = _dec(min_lot) or VOLUME_MIN
    cs = _dec(contract_size) or CONTRACT_SIZE
    stop = _dec(stop_distance)
    eq = _dec(equity)

    if stop is None or stop <= 0 or eq is None or eq <= 0 or lot <= 0 or cs <= 0:
        return MinLotFeasibilityResult(
            classification=CLASS_INSUFFICIENT,
            infeasible=False,
            skip_expensive_downstream=False,
            stop_distance=stop,
            max_allowed_stop=None,
            equity=eq,
            min_lot=lot,
            contract_size=cs,
            hard_max_risk_pct=hard,
            needed_pct=None,
            risk_reasons=(),
            risk_engine_authoritative=True,
        )

    max_stop = max_allowed_stop_at_min_lot(
        equity=eq,
        hard_max_risk_pct=hard,
        min_lot=lot,
        contract_size=cs,
    )
    needed = min_lot_needed_pct(
        stop_distance=stop,
        equity=eq,
        min_lot=lot,
        contract_size=cs,
    )
    # Match RiskEngine: reject only when quantized needed_pct > hard max.
    # A stop slightly above the raw formula can still round to <= 80.00%.
    infeasible = needed > hard
    if infeasible:
        reasons = (
            CLASS_INFEASIBLE,
            CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
            (
                f"{CODE_MIN_LOT_EXCEEDS_RISK_BUDGET}: min_lot {lot} "
                f"needed_pct={needed}% > hard_max={hard}% "
                f"(stop {stop} > max_allowed_stop_at_min_lot {max_stop} "
                "— do not upsize)"
            ),
        )
        return MinLotFeasibilityResult(
            classification=CLASS_INFEASIBLE,
            infeasible=True,
            skip_expensive_downstream=True,
            stop_distance=stop,
            max_allowed_stop=max_stop,
            equity=eq,
            min_lot=lot,
            contract_size=cs,
            hard_max_risk_pct=hard,
            needed_pct=needed,
            risk_reasons=reasons,
            risk_engine_authoritative=True,
        )

    return MinLotFeasibilityResult(
        classification=CLASS_FEASIBLE,
        infeasible=False,
        skip_expensive_downstream=False,
        stop_distance=stop,
        max_allowed_stop=max_stop,
        equity=eq,
        min_lot=lot,
        contract_size=cs,
        hard_max_risk_pct=hard,
        needed_pct=needed,
        risk_reasons=(),
        risk_engine_authoritative=True,
    )


def lot_dollar_risk(
    lots: Decimal,
    *,
    stop_distance: Decimal,
    contract_size: Decimal,
    tick_size: Decimal | None = None,
    tick_value: Decimal | None = None,
) -> Decimal:
    """Monetary open risk at ``lots`` for the strategy stop.

    Prefer tick-value path when both tick_size and tick_value are valid;
    otherwise lots * contract_size * stop (gold CFD identity).
    """
    if lots <= 0 or stop_distance <= 0:
        return Decimal("0")
    if (
        tick_size is not None
        and tick_size > 0
        and tick_value is not None
        and tick_value > 0
    ):
        ticks = stop_distance / tick_size
        return (lots * ticks * tick_value).quantize(_CENTS)
    if contract_size <= 0:
        return Decimal("0")
    return (lots * contract_size * stop_distance).quantize(_CENTS)


def resolve_target_risk_budget_usd(
    *,
    equity: Decimal,
    target_usd: Decimal,
    hard_max_risk_pct: Decimal | None = None,
) -> Decimal:
    """USD SL-loss budget, never above the micro hard-max percent of equity."""
    profile = MicroAccountProfile()
    hard = (
        hard_max_risk_pct
        if hard_max_risk_pct is not None
        else profile.hard_max_risk_pct
    )
    if equity <= 0 or target_usd <= 0:
        return Decimal("0")
    hard_usd = (equity * hard / _PCT).quantize(_CENTS)
    target = target_usd.quantize(_CENTS)
    return min(target, hard_usd) if hard_usd > 0 else target


def planned_sl_risk_usd(
    *,
    volume: Decimal,
    entry: Decimal,
    stop_loss: Decimal,
    contract_size: Decimal,
    tick_size: Decimal | None = None,
    tick_value: Decimal | None = None,
) -> Decimal:
    """Monetary loss if the current protective SL is hit."""
    if volume <= 0 or entry <= 0 or stop_loss <= 0:
        return Decimal("0")
    dist = abs(entry - stop_loss)
    if dist <= 0:
        return Decimal("0")
    return lot_dollar_risk(
        volume,
        stop_distance=dist,
        contract_size=contract_size,
        tick_size=tick_size,
        tick_value=tick_value,
    )


def first_valid_broker_lot(
    *,
    min_lot: Decimal,
    lot_step: Decimal,
    max_lot: Decimal,
) -> Decimal | None:
    """Smallest step-aligned volume that is >= min_lot and <= max_lot."""
    if min_lot <= 0 or lot_step <= 0 or max_lot <= 0 or min_lot > max_lot:
        return None
    steps = (min_lot / lot_step).to_integral_value(rounding=ROUND_DOWN)
    candidate = steps * lot_step
    if candidate < min_lot:
        candidate = (steps + 1) * lot_step
    if candidate > max_lot:
        return None
    return candidate.quantize(lot_step)


@dataclass(frozen=True, slots=True)
class BrokerLotNormalization:
    """Risk-based lot after broker min/step/max and monetary-risk recheck."""

    calculated_lot: Decimal
    broker_min_lot: Decimal
    broker_lot_step: Decimal
    broker_max_lot: Decimal
    normalized_lot: Decimal
    estimated_risk_amount: Decimal
    risk_budget: Decimal
    sizing_status: str
    block_reason: str | None
    needed_pct: Decimal | None = None
    hard_max_risk_pct: Decimal | None = None
    remaining_portfolio_risk: Decimal | None = None
    min_planned_risk: Decimal | None = None
    max_planned_sl_risk: Decimal | None = None

    @property
    def approved(self) -> bool:
        return self.normalized_lot > 0 and self.block_reason is None

    def to_observability(self) -> dict[str, Any]:
        return {
            "calculated_lot": str(self.calculated_lot),
            "broker_min_lot": str(self.broker_min_lot),
            "broker_lot_step": str(self.broker_lot_step),
            "broker_max_lot": str(self.broker_max_lot),
            "normalized_lot": str(self.normalized_lot),
            "estimated_risk_amount": str(self.estimated_risk_amount),
            "risk_budget": str(self.risk_budget),
            "sizing_status": self.sizing_status,
            "block_reason": self.block_reason,
            "needed_pct": str(self.needed_pct) if self.needed_pct is not None else None,
            "hard_max_risk_pct": (
                str(self.hard_max_risk_pct)
                if self.hard_max_risk_pct is not None
                else None
            ),
            "remaining_portfolio_risk": (
                str(self.remaining_portfolio_risk)
                if self.remaining_portfolio_risk is not None
                else None
            ),
            "min_planned_risk": (
                str(self.min_planned_risk)
                if self.min_planned_risk is not None
                else None
            ),
            "max_planned_sl_risk": (
                str(self.max_planned_sl_risk)
                if self.max_planned_sl_risk is not None
                else None
            ),
        }


def normalize_lots_against_broker(
    *,
    calculated_lot: Decimal,
    min_lot: Decimal,
    lot_step: Decimal,
    max_lot: Decimal,
    equity: Decimal,
    stop_distance: Decimal,
    contract_size: Decimal,
    risk_budget: Decimal | None = None,
    hard_max_risk_pct: Decimal | None = None,
    tick_size: Decimal | None = None,
    tick_value: Decimal | None = None,
    allow_min_lot_upsize: bool | None = None,
    remaining_portfolio_risk: Decimal | None = None,
    min_planned_risk: Decimal | None = None,
    max_planned_sl_risk: Decimal | None = None,
    allow_below_min_planned: bool = False,
) -> BrokerLotNormalization:
    """Size to the USD target, round DOWN, then step UP until planned SL > min.

    Min lot is used when the raw volume is below volume_min AND that min lot
    still fits remaining portfolio risk, the per-trade SL cap, and the micro
    hard-max percent. If the next broker step would exceed remaining portfolio
    risk or the per-trade cap, reject — never force an unsafe lot.
    Quality/safety may pass allow_below_min_planned.
    """
    from app.domain.institutional_trading.config import (
        MAX_PLANNED_SL_RISK_USD,
        MAX_TOTAL_PLANNED_RISK_USD,
        MIN_PLANNED_RISK_USD,
    )

    profile = MicroAccountProfile()
    hard = (
        hard_max_risk_pct
        if hard_max_risk_pct is not None
        else profile.hard_max_risk_pct
    )
    calc = calculated_lot if calculated_lot > 0 else Decimal("0")
    budget = risk_budget if risk_budget is not None else Decimal("0")
    min_floor = (
        min_planned_risk if min_planned_risk is not None else MIN_PLANNED_RISK_USD
    )
    per_trade_max = (
        max_planned_sl_risk
        if max_planned_sl_risk is not None
        else MAX_PLANNED_SL_RISK_USD
    )
    hard_usd = (
        (equity * hard / _PCT).quantize(_CENTS)
        if equity > 0 and hard > 0
        else Decimal("0")
    )
    remaining = remaining_portfolio_risk
    if remaining is None:
        remaining = MAX_TOTAL_PLANNED_RISK_USD
    ceiling = remaining
    if hard_usd > 0:
        ceiling = min(ceiling, hard_usd) if ceiling > 0 else hard_usd
    if per_trade_max > 0:
        ceiling = min(ceiling, per_trade_max) if ceiling > 0 else per_trade_max
    _ = allow_min_lot_upsize  # always upsize toward min planned when ceiling allows

    def _blank(
        *,
        status: str,
        reason: str | None,
        lot: Decimal = Decimal("0"),
        est: Decimal = Decimal("0"),
        needed: Decimal | None = None,
    ) -> BrokerLotNormalization:
        return BrokerLotNormalization(
            calculated_lot=calc,
            broker_min_lot=min_lot,
            broker_lot_step=lot_step,
            broker_max_lot=max_lot,
            normalized_lot=lot,
            estimated_risk_amount=est,
            risk_budget=budget,
            sizing_status=status,
            block_reason=reason,
            needed_pct=needed,
            hard_max_risk_pct=hard,
            remaining_portfolio_risk=remaining,
            min_planned_risk=min_floor,
            max_planned_sl_risk=per_trade_max,
        )

    def _ok(
        *,
        lot: Decimal,
        est: Decimal,
        status: str,
        needed: Decimal | None = None,
    ) -> BrokerLotNormalization:
        return BrokerLotNormalization(
            calculated_lot=calc,
            broker_min_lot=min_lot,
            broker_lot_step=lot_step,
            broker_max_lot=max_lot,
            normalized_lot=lot,
            estimated_risk_amount=est,
            risk_budget=budget,
            sizing_status=status,
            block_reason=None,
            needed_pct=needed,
            hard_max_risk_pct=hard,
            remaining_portfolio_risk=remaining,
            min_planned_risk=min_floor,
            max_planned_sl_risk=per_trade_max,
        )

    if min_lot <= 0 or lot_step <= 0 or max_lot <= 0 or min_lot > max_lot:
        return _blank(
            status=STATUS_INVALID_SPEC,
            reason=CODE_INVALID_BROKER_SPEC,
        )

    first_valid = first_valid_broker_lot(
        min_lot=min_lot, lot_step=lot_step, max_lot=max_lot
    )
    if first_valid is None:
        return _blank(
            status=STATUS_INVALID_SPEC,
            reason=CODE_INVALID_BROKER_SPEC,
        )

    if contract_size <= 0:
        return _blank(
            status=STATUS_INVALID_SPEC,
            reason=CODE_INVALID_BROKER_SPEC,
        )

    if equity <= 0 or stop_distance <= 0:
        return _blank(
            status=STATUS_BELOW_MIN,
            reason=CODE_MIN_LOT_CONSTRAINT,
        )

    if ceiling <= 0:
        return _blank(
            status=STATUS_EXCEEDS_BUDGET,
            reason=CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
        )

    per_lot = lot_dollar_risk(
        Decimal("1"),
        stop_distance=stop_distance,
        contract_size=contract_size,
        tick_size=tick_size,
        tick_value=tick_value,
    )
    if per_lot <= 0:
        return _blank(
            status=STATUS_INVALID_SPEC,
            reason=CODE_INVALID_BROKER_SPEC,
        )

    steps = (calc / lot_step).to_integral_value(rounding=ROUND_DOWN)
    quantized = (steps * lot_step).quantize(lot_step)
    capped_max = False
    if quantized > max_lot:
        max_steps = (max_lot / lot_step).to_integral_value(rounding=ROUND_DOWN)
        quantized = (max_steps * lot_step).quantize(lot_step)
        capped_max = True

    min_loss = (first_valid * per_lot).quantize(_CENTS)
    needed = (min_loss / equity * _PCT).quantize(_CENTS) if equity > 0 else None

    if quantized < first_valid:
        if needed is not None and needed > hard:
            return _blank(
                status=STATUS_EXCEEDS_BUDGET,
                reason=CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
                est=min_loss,
                needed=needed,
            )
        if min_loss > ceiling:
            return _blank(
                status=STATUS_EXCEEDS_BUDGET,
                reason=CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
                est=min_loss,
                needed=needed,
            )
        quantized = first_valid
        capped_max = False

    est = (quantized * per_lot).quantize(_CENTS)
    status = STATUS_CAPPED_MAX if capped_max else STATUS_OK
    if quantized == first_valid and calc < first_valid:
        status = STATUS_NORMALIZED_TO_MIN

    if not allow_below_min_planned and min_floor > 0:
        guard = 0
        while est <= min_floor and guard < 10000:
            guard += 1
            next_vol = (quantized + lot_step).quantize(lot_step)
            if next_vol > max_lot:
                return _blank(
                    status=STATUS_EXCEEDS_BUDGET,
                    reason=CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
                    est=est,
                    needed=needed,
                    lot=Decimal("0"),
                )
            next_loss = (next_vol * per_lot).quantize(_CENTS)
            if next_loss > ceiling:
                return _blank(
                    status=STATUS_EXCEEDS_BUDGET,
                    reason=CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
                    est=next_loss,
                    needed=needed,
                    lot=Decimal("0"),
                )
            quantized = next_vol
            est = next_loss
            status = STATUS_OK

    if quantized < first_valid or est > ceiling:
        return _blank(
            status=STATUS_EXCEEDS_BUDGET,
            reason=CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
            est=est,
            needed=needed,
        )
    return _ok(lot=quantized, est=est, status=status, needed=needed)



TRADEABLE = "TRADEABLE"
NOT_TRADEABLE = "NOT_TRADEABLE"

EXEC_TRADEABLE = "TRADEABLE"
EXEC_NOT_TRADEABLE = "NOT_TRADEABLE"
EXEC_RISK_BLOCKED = "RISK_BLOCKED"
EXEC_WAITING_FOR_SETUP = "WAITING_FOR_SETUP"
EXEC_EXECUTING = "EXECUTING"
EXEC_EXECUTED = "EXECUTED"
EXEC_EXECUTION_FAILED = "EXECUTION_FAILED"

_HARD_BLOCK_ABORTS = frozenset(
    {
        "DAILY_LOSS_BLOCK",
        "DAILY_LOSS_EXCEEDED",
        "SAFETY_BLOCKED",
        "KILL_SWITCH",
        "HALTED_BY_RISK",
    }
)
_FAIL_ABORTS = frozenset(
    {
        "OMS_NOT_READY",
        "GATEWAY_UNAVAILABLE",
        "MT5_UNAVAILABLE",
        "CYCLE_TIMEOUT",
        "CYCLE_EXCEPTION",
        "NO_MARKET_CONTEXT",
    }
)


@dataclass(frozen=True, slots=True)
class SetupTradeability:
    """Pre-submit: can broker min lot fit the existing hard risk ceiling?"""

    tradeability: str
    tradeability_reason: str
    estimated_risk_at_min_lot: Decimal | None
    maximum_tradeable_stop_distance: Decimal | None
    stop_distance: Decimal | None
    risk_budget: Decimal | None
    equity: Decimal | None
    broker_min_lot: Decimal | None
    broker_lot_step: Decimal | None
    broker_max_lot: Decimal | None
    feasibility: MinLotFeasibilityResult

    def to_observability(self) -> dict[str, Any]:
        return {
            "tradeability": self.tradeability,
            "tradeability_reason": self.tradeability_reason,
            "estimated_risk_at_min_lot": (
                str(self.estimated_risk_at_min_lot)
                if self.estimated_risk_at_min_lot is not None
                else None
            ),
            "maximum_tradeable_stop_distance": (
                str(self.maximum_tradeable_stop_distance)
                if self.maximum_tradeable_stop_distance is not None
                else None
            ),
            "stop_distance": (
                str(self.stop_distance) if self.stop_distance is not None else None
            ),
            "risk_budget": (
                str(self.risk_budget) if self.risk_budget is not None else None
            ),
            "equity": str(self.equity) if self.equity is not None else None,
            "broker_min_lot": (
                str(self.broker_min_lot) if self.broker_min_lot is not None else None
            ),
            "broker_lot_step": (
                str(self.broker_lot_step) if self.broker_lot_step is not None else None
            ),
            "broker_max_lot": (
                str(self.broker_max_lot) if self.broker_max_lot is not None else None
            ),
        }


def evaluate_setup_tradeability(
    *,
    stop_distance: Any,
    equity: Any,
    min_lot: Any = None,
    lot_step: Any = None,
    max_lot: Any = None,
    contract_size: Any = None,
    hard_max_risk_pct: Any = None,
    tick_size: Any = None,
    tick_value: Any = None,
) -> SetupTradeability:
    """Can the smallest broker-valid lot open inside the existing 5% ceiling?

    Does not move the stop. Infeasible setups return NOT_TRADEABLE and the
    caller must continue scanning — never force min lot.
    """
    feas = evaluate_min_lot_feasibility(
        stop_distance=stop_distance,
        equity=equity,
        min_lot=min_lot,
        contract_size=contract_size,
        hard_max_risk_pct=hard_max_risk_pct,
    )
    lot = feas.min_lot
    step = _dec(lot_step)
    mx = _dec(max_lot)
    est: Decimal | None = None
    if (
        feas.stop_distance is not None
        and feas.stop_distance > 0
        and lot is not None
        and lot > 0
        and feas.contract_size is not None
        and feas.contract_size > 0
    ):
        est = lot_dollar_risk(
            lot,
            stop_distance=feas.stop_distance,
            contract_size=feas.contract_size,
            tick_size=_dec(tick_size),
            tick_value=_dec(tick_value),
        )
    budget: Decimal | None = None
    if feas.equity is not None and feas.equity > 0 and feas.hard_max_risk_pct > 0:
        budget = (feas.equity * feas.hard_max_risk_pct / _PCT).quantize(_CENTS)

    if feas.classification == CLASS_INSUFFICIENT:
        status = NOT_TRADEABLE
        reason = CLASS_INSUFFICIENT
    elif feas.infeasible:
        status = NOT_TRADEABLE
        reason = CODE_MIN_LOT_EXCEEDS_RISK_BUDGET
    else:
        status = TRADEABLE
        reason = CLASS_FEASIBLE

    return SetupTradeability(
        tradeability=status,
        tradeability_reason=reason,
        estimated_risk_at_min_lot=est,
        maximum_tradeable_stop_distance=feas.max_allowed_stop,
        stop_distance=feas.stop_distance,
        risk_budget=budget,
        equity=feas.equity,
        broker_min_lot=lot,
        broker_lot_step=step,
        broker_max_lot=mx,
        feasibility=feas,
    )


def _has_broker_ticket(ticket: Any) -> bool:
    return ticket not in (None, "", 0, "0", "None")


def classify_cycle_execution_status(
    *,
    abort_reason: str | None = None,
    cycle_outcome: str | None = None,
    forwarded_to_oms: bool = False,
    mt5_ticket: Any = None,
    kill_switch: bool = False,
    tradeability: str | None = None,
) -> str:
    """Truthful cycle status. LIVE / running is never proof of a fill."""
    if _has_broker_ticket(mt5_ticket):
        return EXEC_EXECUTED
    abort = str(abort_reason or "").upper()
    outcome = str(cycle_outcome or "").lower()
    if kill_switch or abort in _HARD_BLOCK_ABORTS or "KILL" in abort:
        return EXEC_RISK_BLOCKED
    if "DAILY_LOSS" in abort:
        return EXEC_RISK_BLOCKED
    if forwarded_to_oms and not _has_broker_ticket(mt5_ticket):
        return EXEC_EXECUTION_FAILED
    if outcome == "error" or abort in _FAIL_ABORTS:
        return EXEC_EXECUTION_FAILED
    if abort == CODE_MIN_LOT_EXCEEDS_RISK_BUDGET or "MIN_LOT" in abort:
        return EXEC_WAITING_FOR_SETUP
    if tradeability == NOT_TRADEABLE:
        return EXEC_WAITING_FOR_SETUP
    if tradeability == TRADEABLE:
        return EXEC_TRADEABLE
    if outcome in {"waiting_next_cycle", "execution_contract", "no_snapshot"}:
        return EXEC_WAITING_FOR_SETUP
    return EXEC_WAITING_FOR_SETUP
