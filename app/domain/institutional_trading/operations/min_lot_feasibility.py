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
    (5.0 means 5%), not a 0.05 fraction.
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
    # A stop slightly above the raw formula can still round to <= 5.00%.
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
) -> BrokerLotNormalization:
    """risk calc → broker constraints → safe normalize → re-check $ risk.

    Never blindly forces broker min lot. If min lot exceeds the existing
    micro hard-max risk ceiling, block with MIN_LOT_EXCEEDS_RISK_BUDGET.
    """
    profile = MicroAccountProfile()
    hard = (
        hard_max_risk_pct
        if hard_max_risk_pct is not None
        else profile.hard_max_risk_pct
    )
    calc = calculated_lot if calculated_lot > 0 else Decimal("0")
    budget = risk_budget if risk_budget is not None else Decimal("0")
    upsize = (
        allow_min_lot_upsize
        if allow_min_lot_upsize is not None
        else (equity > 0 and equity <= MICRO_EQUITY_CAP)
    )

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

    steps = (calc / lot_step).to_integral_value(rounding=ROUND_DOWN)
    quantized = (steps * lot_step).quantize(lot_step)
    capped_max = False
    if quantized > max_lot:
        max_steps = (max_lot / lot_step).to_integral_value(rounding=ROUND_DOWN)
        quantized = (max_steps * lot_step).quantize(lot_step)
        capped_max = True

    if quantized >= first_valid:
        est = Decimal("0")
        if stop_distance > 0:
            est = lot_dollar_risk(
                quantized,
                stop_distance=stop_distance,
                contract_size=contract_size,
                tick_size=tick_size,
                tick_value=tick_value,
            )
        return BrokerLotNormalization(
            calculated_lot=calc,
            broker_min_lot=min_lot,
            broker_lot_step=lot_step,
            broker_max_lot=max_lot,
            normalized_lot=quantized,
            estimated_risk_amount=est,
            risk_budget=budget,
            sizing_status=STATUS_CAPPED_MAX if capped_max else STATUS_OK,
            block_reason=None,
            needed_pct=None,
            hard_max_risk_pct=hard,
        )

    if equity <= 0 or stop_distance <= 0:
        return _blank(
            status=STATUS_BELOW_MIN,
            reason=CODE_MIN_LOT_CONSTRAINT,
        )

    min_loss = lot_dollar_risk(
        first_valid,
        stop_distance=stop_distance,
        contract_size=contract_size,
        tick_size=tick_size,
        tick_value=tick_value,
    )
    needed = (min_loss / equity * _PCT).quantize(_CENTS) if equity > 0 else None

    if needed is not None and needed > hard:
        return _blank(
            status=STATUS_EXCEEDS_BUDGET,
            reason=CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
            est=min_loss,
            needed=needed,
        )
    if not upsize:
        return _blank(
            status=STATUS_BELOW_MIN,
            reason=CODE_MIN_LOT_CONSTRAINT,
            est=min_loss,
            needed=needed,
        )
    return BrokerLotNormalization(
        calculated_lot=calc,
        broker_min_lot=min_lot,
        broker_lot_step=lot_step,
        broker_max_lot=max_lot,
        normalized_lot=first_valid,
        estimated_risk_amount=min_loss,
        risk_budget=budget,
        sizing_status=STATUS_NORMALIZED_TO_MIN,
        block_reason=None,
        needed_pct=needed,
        hard_max_risk_pct=hard,
    )
