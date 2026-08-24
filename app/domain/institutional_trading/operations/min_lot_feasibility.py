"""Pre-Risk min-lot feasibility — audit / early-reject only.

Does not change stops, lots, the 5% hard ceiling, or Risk semantics.
The Risk Engine remains authoritative on the continue path.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.micro_account_mode import MicroAccountProfile
from app.domain.trading.xauusd_specs import CONTRACT_SIZE, VOLUME_MIN

CLASS_INFEASIBLE = "MIN_LOT_INFEASIBLE"
CLASS_FEASIBLE = "FEASIBLE"
CLASS_INSUFFICIENT = "INSUFFICIENT_DATA"

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
            (
                "MIN_LOT_CONSTRAINT: strategy-approved stop "
                f"{stop} exceeds max_allowed_stop_at_min_lot {max_stop} "
                f"(min_lot {lot} needed_pct={needed}% > hard_max={hard}% "
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
