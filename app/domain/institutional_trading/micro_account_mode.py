"""MICRO_ACCOUNT_MODE — separate sizing profile (does not alter Institutional Mode).

Institutional Mode (``DEFAULT_ITE_CONFIG``) remains:

- Quality = 80, Confluence = 80
- 1% risk per trade
- Never upsize below broker ``min_lot``
- Existing policy unchanged

This module owns only micro-account feasibility math and a declarative
``MicroAccountProfile``. It never mutates institutional thresholds, never
fakes lots, never overrides broker ``VOLUME_MIN``, and never forces execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

from app.domain.trading.gold_only import GOLD_SYMBOL
from app.domain.trading.xauusd_specs import (
    CONTRACT_SIZE,
    VOLUME_MIN,
    VOLUME_STEP,
)

MODE_ID = "MICRO_ACCOUNT_MODE"

# Supported operator balances (USD equity).
SUPPORTED_BALANCES: tuple[Decimal, ...] = (
    Decimal("50"),
    Decimal("100"),
    Decimal("250"),
    Decimal("500"),
)

# Same stop geometry as RiskEngine ATR path (atr × multiplier).
DEFAULT_ATR_STOP_MULTIPLIER = Decimal("1.5")

# Reference ATR (USD price units) for offline feasibility when live ATR absent.
# Typical M15 XAUUSD ATR band used for planning — not a live feed invent.
DEFAULT_REFERENCE_ATR = Decimal("12.00")

# Drawdown horizon requested by the mission.
DRAWDOWN_HORIZON_PCT = Decimal("20")


class MicroTradability(StrEnum):
    """Whether min_lot XAUUSD fits inside the micro risk ceiling."""

    SAFE = "safe"  # min_lot loss ≤ recommended_max_risk_pct
    CONDITIONAL = "conditional"  # ≤ hard_max, above recommended
    NOT_TRADABLE = "not_tradable"  # would exceed hard_max — must reject


@dataclass(frozen=True, slots=True)
class MicroAccountProfile:
    """Configurable micro-account profile — orthogonal to Institutional Mode.

    Sizing still obeys broker minimums. If min_lot risk exceeds
    ``hard_max_risk_pct``, the profile refuses the trade (approved lots = 0
    semantics) — it never upsizes risk to force a fill.
    """

    mode_id: str = MODE_ID
    symbol: str = GOLD_SYMBOL
    supported_balances: tuple[Decimal, ...] = SUPPORTED_BALANCES
    # Recommended ceiling for “safely tradable” labelling.
    recommended_max_risk_pct: Decimal = Decimal("2.0")
    # Absolute ceiling — never exceed; never upsize past this to hit min_lot.
    hard_max_risk_pct: Decimal = Decimal("5.0")
    drawdown_horizon_pct: Decimal = DRAWDOWN_HORIZON_PCT
    # Broker constraints — copied from XAUUSD specs; never overridden.
    broker_min_lot: Decimal = VOLUME_MIN
    broker_lot_step: Decimal = VOLUME_STEP
    contract_size: Decimal = CONTRACT_SIZE
    atr_stop_multiplier: Decimal = DEFAULT_ATR_STOP_MULTIPLIER
    # Micro mode does **not** change institutional quality/confluence gates.
    # Strategy gates remain Institutional unless an operator explicitly selects
    # a future micro strategy overlay (out of scope here).
    notes: tuple[str, ...] = (
        "Does not modify Institutional Mode (Q80/C80/1% risk).",
        "Never fakes lots or bypasses broker VOLUME_MIN.",
        "Never upsizes below min_lot to force execution.",
        "If min_lot risk exceeds hard_max_risk_pct → NOT_TRADABLE (reject).",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode_id": self.mode_id,
            "symbol": self.symbol,
            "supported_balances": [str(b) for b in self.supported_balances],
            "recommended_max_risk_pct": str(self.recommended_max_risk_pct),
            "hard_max_risk_pct": str(self.hard_max_risk_pct),
            "drawdown_horizon_pct": str(self.drawdown_horizon_pct),
            "broker_min_lot": str(self.broker_min_lot),
            "broker_lot_step": str(self.broker_lot_step),
            "contract_size": str(self.contract_size),
            "atr_stop_multiplier": str(self.atr_stop_multiplier),
            "notes": list(self.notes),
            "institutional_mode_modified": False,
        }


DEFAULT_MICRO_ACCOUNT_PROFILE = MicroAccountProfile()


def stop_distance_from_atr(
    atr: Decimal,
    *,
    multiplier: Decimal = DEFAULT_ATR_STOP_MULTIPLIER,
) -> Decimal:
    """Institutional-compatible stop distance: ATR × multiplier."""
    if atr <= 0:
        raise ValueError("atr must be > 0")
    if multiplier <= 0:
        raise ValueError("multiplier must be > 0")
    return (atr * multiplier).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def dollar_risk_at_lots(
    *,
    lots: Decimal,
    stop_distance: Decimal,
    contract_size: Decimal = CONTRACT_SIZE,
) -> Decimal:
    """Exact loss if stop is hit: lots × stop × contract_size."""
    if lots < 0 or stop_distance < 0:
        raise ValueError("lots and stop_distance must be >= 0")
    return (lots * stop_distance * contract_size).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def min_usable_risk_pct(*, equity: Decimal, dollar_risk: Decimal) -> Decimal:
    """Risk % of equity required to place ``dollar_risk`` without upsizing."""
    if equity <= 0:
        raise ValueError("equity must be > 0")
    return (dollar_risk / equity * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def consecutive_losses_to_drawdown(
    *,
    equity: Decimal,
    loss_per_trade: Decimal,
    drawdown_pct: Decimal = DRAWDOWN_HORIZON_PCT,
) -> int:
    """Floor count of identical full-stop losses to reach ``drawdown_pct`` of equity.

    Returns 0 when a single loss already exceeds the drawdown budget.
    """
    if equity <= 0:
        raise ValueError("equity must be > 0")
    if loss_per_trade <= 0:
        return 0
    budget = (equity * drawdown_pct / Decimal("100")).quantize(Decimal("0.01"))
    return int(budget // loss_per_trade)


def equity_floor_for_risk(
    *,
    dollar_risk_at_min_lot: Decimal,
    risk_pct: Decimal,
) -> Decimal:
    """Minimum equity so min_lot stop-loss equals exactly ``risk_pct`` of equity."""
    if risk_pct <= 0:
        raise ValueError("risk_pct must be > 0")
    return (dollar_risk_at_min_lot / (risk_pct / Decimal("100"))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def classify_tradability(
    *,
    required_risk_pct: Decimal,
    profile: MicroAccountProfile = DEFAULT_MICRO_ACCOUNT_PROFILE,
) -> MicroTradability:
    if required_risk_pct > profile.hard_max_risk_pct:
        return MicroTradability.NOT_TRADABLE
    if required_risk_pct > profile.recommended_max_risk_pct:
        return MicroTradability.CONDITIONAL
    return MicroTradability.SAFE


@dataclass(frozen=True, slots=True)
class MicroBalanceFeasibility:
    """Per-balance sizing feasibility under broker min_lot (no fake lots)."""

    equity: Decimal
    atr: Decimal
    stop_distance: Decimal
    broker_min_lot: Decimal
    max_loss_per_trade: Decimal
    min_usable_risk_pct: Decimal
    smallest_executable_lot: Decimal | None
    consecutive_losses_to_20pct_dd: int
    tradability: MicroTradability
    within_hard_max: bool
    within_recommended: bool
    reasons: tuple[str, ...]
    recommendations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "equity": str(self.equity),
            "atr": str(self.atr),
            "stop_distance": str(self.stop_distance),
            "broker_min_lot": str(self.broker_min_lot),
            "max_loss_per_trade": str(self.max_loss_per_trade),
            "min_usable_risk_pct": str(self.min_usable_risk_pct),
            "smallest_executable_lot": (
                str(self.smallest_executable_lot)
                if self.smallest_executable_lot is not None
                else None
            ),
            "consecutive_losses_to_20pct_dd": self.consecutive_losses_to_20pct_dd,
            "tradability": self.tradability.value,
            "within_hard_max": self.within_hard_max,
            "within_recommended": self.within_recommended,
            "reasons": list(self.reasons),
            "recommendations": list(self.recommendations),
        }


def evaluate_balance(
    equity: Decimal,
    *,
    atr: Decimal = DEFAULT_REFERENCE_ATR,
    profile: MicroAccountProfile = DEFAULT_MICRO_ACCOUNT_PROFILE,
) -> MicroBalanceFeasibility:
    """Evaluate one micro balance against broker min_lot + risk ceilings."""
    if equity <= 0:
        raise ValueError("equity must be > 0")

    stop = stop_distance_from_atr(atr, multiplier=profile.atr_stop_multiplier)
    max_loss = dollar_risk_at_lots(
        lots=profile.broker_min_lot,
        stop_distance=stop,
        contract_size=profile.contract_size,
    )
    required_pct = min_usable_risk_pct(equity=equity, dollar_risk=max_loss)
    tradability = classify_tradability(
        required_risk_pct=required_pct, profile=profile
    )
    losses_to_dd = consecutive_losses_to_drawdown(
        equity=equity,
        loss_per_trade=max_loss,
        drawdown_pct=profile.drawdown_horizon_pct,
    )

    reasons: list[str] = []
    recommendations: list[str] = []

    # Smallest executable lot is broker min_lot only when hard_max allows it.
    # Never return a sub-min lot; never invent a fillable size.
    if tradability is MicroTradability.NOT_TRADABLE:
        smallest: Decimal | None = None
        reasons.append(
            f"Broker min_lot {profile.broker_min_lot} implies "
            f"${max_loss} loss ({required_pct}% of ${equity}), which exceeds "
            f"hard_max_risk_pct={profile.hard_max_risk_pct}%. "
            "Cannot execute without faking lots or exceeding max account risk."
        )
        floor_rec = equity_floor_for_risk(
            dollar_risk_at_min_lot=max_loss,
            risk_pct=profile.recommended_max_risk_pct,
        )
        floor_hard = equity_floor_for_risk(
            dollar_risk_at_min_lot=max_loss,
            risk_pct=profile.hard_max_risk_pct,
        )
        recommendations.append(
            f"Higher account balance — ≥ ${floor_rec} for "
            f"≤{profile.recommended_max_risk_pct}% risk at current stop, "
            f"or ≥ ${floor_hard} for hard ceiling "
            f"{profile.hard_max_risk_pct}%."
        )
        recommendations.append(
            "Broker supporting smaller minimum lot (e.g. 0.001) — "
            "would cut dollar risk ~10× at the same stop."
        )
        recommendations.append(
            "Lower-risk instrument — not supported on QuantForg "
            "(XAUUSD-only platform)."
        )
        if equity == Decimal("50"):
            reasons.append(
                "$50 cannot safely trade XAUUSD with broker min_lot 0.01 "
                "under mathematically correct sizing."
            )
    elif tradability is MicroTradability.CONDITIONAL:
        smallest = profile.broker_min_lot
        reasons.append(
            f"Executable at min_lot {profile.broker_min_lot} only by accepting "
            f"{required_pct}% risk (above recommended "
            f"{profile.recommended_max_risk_pct}%, within hard max "
            f"{profile.hard_max_risk_pct}%)."
        )
        recommendations.append(
            "Prefer higher equity so min_lot risk ≤ "
            f"{profile.recommended_max_risk_pct}% "
            f"(need ≥ ${equity_floor_for_risk(dollar_risk_at_min_lot=max_loss, risk_pct=profile.recommended_max_risk_pct)})."
        )
        recommendations.append(
            "Do not force Institutional 1% sizing — it would calculate "
            "sub-min lots and correctly reject (no upsize)."
        )
    else:
        smallest = profile.broker_min_lot
        reasons.append(
            f"Min_lot {profile.broker_min_lot} stop-loss ${max_loss} is "
            f"{required_pct}% of equity — within recommended "
            f"{profile.recommended_max_risk_pct}%."
        )

    if losses_to_dd < 3 and tradability is not MicroTradability.NOT_TRADABLE:
        reasons.append(
            f"Only {losses_to_dd} consecutive full-stop loss(es) to "
            f"{profile.drawdown_horizon_pct}% drawdown — fragile for micro sizing."
        )

    return MicroBalanceFeasibility(
        equity=equity,
        atr=atr,
        stop_distance=stop,
        broker_min_lot=profile.broker_min_lot,
        max_loss_per_trade=max_loss,
        min_usable_risk_pct=required_pct,
        smallest_executable_lot=smallest,
        consecutive_losses_to_20pct_dd=losses_to_dd,
        tradability=tradability,
        within_hard_max=tradability is not MicroTradability.NOT_TRADABLE,
        within_recommended=tradability is MicroTradability.SAFE,
        reasons=tuple(reasons),
        recommendations=tuple(dict.fromkeys(recommendations)),
    )


def size_micro_lots(
    *,
    equity: Decimal,
    stop_distance: Decimal,
    risk_pct: Decimal,
    profile: MicroAccountProfile = DEFAULT_MICRO_ACCOUNT_PROFILE,
) -> Decimal:
    """Percentage-risk lot size with ROUND_DOWN — never upsize to min_lot.

    Returns ``0`` when calculated lots < broker min_lot or when required
    ``risk_pct`` would exceed ``hard_max_risk_pct``.
    """
    if equity <= 0 or stop_distance <= 0 or risk_pct <= 0:
        return Decimal("0")
    if risk_pct > profile.hard_max_risk_pct:
        return Decimal("0")
    budget = equity * (risk_pct / Decimal("100"))
    raw = budget / (stop_distance * profile.contract_size)
    lots = raw.quantize(profile.broker_lot_step, rounding=ROUND_DOWN)
    if lots < profile.broker_min_lot:
        return Decimal("0")
    return lots


def build_recommended_policy(
    *,
    profile: MicroAccountProfile = DEFAULT_MICRO_ACCOUNT_PROFILE,
    atr: Decimal = DEFAULT_REFERENCE_ATR,
) -> dict[str, Any]:
    """Operator-facing recommended micro policy (does not activate live trading)."""
    stop = stop_distance_from_atr(atr, multiplier=profile.atr_stop_multiplier)
    min_loss = dollar_risk_at_lots(
        lots=profile.broker_min_lot,
        stop_distance=stop,
        contract_size=profile.contract_size,
    )
    safe_floor = equity_floor_for_risk(
        dollar_risk_at_min_lot=min_loss,
        risk_pct=profile.recommended_max_risk_pct,
    )
    hard_floor = equity_floor_for_risk(
        dollar_risk_at_min_lot=min_loss,
        risk_pct=profile.hard_max_risk_pct,
    )
    institutional_1pct_floor = equity_floor_for_risk(
        dollar_risk_at_min_lot=min_loss,
        risk_pct=Decimal("1.0"),
    )
    return {
        "mode_id": profile.mode_id,
        "institutional_mode_unchanged": True,
        "institutional_defaults": {
            "quality": 80,
            "confluence": 80,
            "risk_per_trade_pct": "1.0",
            "never_upsize_below_min_lot": True,
        },
        "micro_policy": {
            "enabled_by_default": False,
            "activation": "explicit_operator_selection_only",
            "recommended_max_risk_pct": str(profile.recommended_max_risk_pct),
            "hard_max_risk_pct": str(profile.hard_max_risk_pct),
            "broker_min_lot": str(profile.broker_min_lot),
            "never_fake_lots": True,
            "never_bypass_broker_minimum": True,
            "never_exceed_hard_max_risk": True,
            "if_calculated_lots_below_min_lot": "REJECT (approved_lots=0)",
            "reference_atr": str(atr),
            "reference_stop_distance": str(stop),
            "dollar_risk_at_min_lot": str(min_loss),
            "equity_floor_safe_recommended_pct": str(safe_floor),
            "equity_floor_hard_max_pct": str(hard_floor),
            "equity_floor_institutional_1pct": str(institutional_1pct_floor),
            "supported_balances": [str(b) for b in profile.supported_balances],
            "xauusd_only": True,
            "lower_risk_instrument_supported": False,
        },
        "recommendations": [
            f"Do not enable MICRO_ACCOUNT_MODE for balances below ${hard_floor} "
            f"at ATR={atr} (min_lot stop-loss exceeds hard max "
            f"{profile.hard_max_risk_pct}%).",
            f"Treat balances ≥ ${safe_floor} as the first ‘safe’ XAUUSD micro "
            f"tier at ≤{profile.recommended_max_risk_pct}% risk (still below "
            "Institutional 1% floor).",
            f"Institutional 1% sizing with min_lot 0.01 requires equity "
            f"≥ ${institutional_1pct_floor} at this stop — keep Institutional "
            "Mode for those accounts.",
            "If stuck at $50–$100: fund higher, or use a broker with 0.001 "
            "min lot — do not force 0.01 fills.",
        ],
    }
