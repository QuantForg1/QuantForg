"""XAUUSD opportunity quality gates — fail-safe skip reasons, no invented confidence.

Pure domain helpers used by the Gold setup scanner and micro-account path.
Does not size positions, send orders, or invent win-rate percentages.
Historical confidence must come from measured outcome stores elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.trading.xauusd_specs import MAX_SPREAD, VOLUME_MIN


@dataclass(frozen=True, slots=True)
class GoldOpportunityAssessment:
    """Pass/skip verdict with explicit, auditable reasons."""

    tradable: bool
    skip_reasons: tuple[str, ...]
    entry_conditions: tuple[str, ...]
    invalidation: tuple[str, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tradable": self.tradable,
            "skip_reasons": list(self.skip_reasons),
            "entry_conditions": list(self.entry_conditions),
            "invalidation": list(self.invalidation),
            "notes": list(self.notes),
            "confidence": None,  # never invent confidence %
        }


def assess_gold_opportunity(
    *,
    mtf_aligned: bool = True,
    mtf_conflict: bool = False,
    range_bound: bool = False,
    false_breakout_risk: bool = False,
    spread: Decimal | float | None = None,
    max_spread: Decimal | float | None = None,
    session_allowed: bool = True,
    abnormal_volatility: bool = False,
    data_fresh: bool = True,
    missing_candles: bool = False,
    stop_loss_present: bool = True,
    risk_reward_ok: bool = True,
    duplicate_signal: bool = False,
    min_lot_fits_risk: bool = True,
) -> GoldOpportunityAssessment:
    """Evaluate structural / session / data gates for a Gold candidate.

    Correlated indicators are not treated as independent confirmation — callers
    must supply already-reduced flags (mtf_aligned, false_breakout_risk, etc.).
    """
    skips: list[str] = []
    entries: list[str] = []
    invalidation: list[str] = []
    notes: list[str] = []

    ceiling = Decimal(str(max_spread if max_spread is not None else MAX_SPREAD))
    if ceiling <= 0:
        ceiling = MAX_SPREAD

    if not data_fresh:
        skips.append("Stale market data — skip until quotes refresh")
    if missing_candles:
        skips.append("Missing candles on required timeframe — fail-safe skip")
    if mtf_conflict or not mtf_aligned:
        skips.append("Multi-timeframe trend conflict — no independent confirmation")
    if range_bound and false_breakout_risk:
        skips.append("Range-bound + false-breakout risk — skip breakout chase")
    elif false_breakout_risk:
        skips.append("False-breakout risk elevated — require reclaim/confirmation")
    elif range_bound:
        notes.append("Range-bound regime — prefer mean-reversion families only")
    if not session_allowed:
        skips.append("Session / market window not allowed for Gold entries")
    if abnormal_volatility:
        skips.append("Abnormal volatility — spread/slippage unsuitable")
    if spread is not None:
        spread_d = Decimal(str(spread))
        if spread_d < 0:
            skips.append("Invalid spread reading — fail-safe skip")
        elif spread_d > ceiling:
            skips.append(f"Spread {spread_d} exceeds Gold ceiling {ceiling} — skip")
        else:
            entries.append(f"Spread {spread_d} within Gold ceiling {ceiling}")
    if not stop_loss_present:
        skips.append("Stop-loss required — missing invalidation level")
    if not risk_reward_ok:
        skips.append("Risk/reward below configured backtested minimum")
    if duplicate_signal:
        skips.append("Duplicate / idempotent signal — no repeat entry")
    if not min_lot_fits_risk:
        skips.append(
            f"Broker min lot {VOLUME_MIN} exceeds risk budget — skip "
            "(do not violate risk or force size)"
        )

    if mtf_aligned and not mtf_conflict:
        entries.append("Higher-timeframe bias aligned with entry timeframe")
    if stop_loss_present:
        invalidation.append(
            "Invalidate if stop-loss is hit or structure breaks against bias"
        )
    if not skips and mtf_aligned:
        entries.append("No hard skip gates — candidate may proceed to Risk Engine")

    return GoldOpportunityAssessment(
        tradable=len(skips) == 0,
        skip_reasons=tuple(skips),
        entry_conditions=tuple(entries),
        invalidation=tuple(invalidation),
        notes=tuple(notes),
    )


def min_lot_risk_dollars(
    *,
    stop_distance: Decimal | float,
    contract_size: Decimal | float = Decimal("100"),
    min_lot: Decimal | float = VOLUME_MIN,
) -> Decimal:
    """Dollar risk of broker minimum lot at the given stop distance."""
    dist = Decimal(str(stop_distance))
    if dist <= 0:
        return Decimal("0")
    return (Decimal(str(min_lot)) * Decimal(str(contract_size)) * dist).quantize(
        Decimal("0.01")
    )


def min_lot_fits_equity_risk(
    *,
    equity: Decimal | float,
    risk_pct: Decimal | float,
    stop_distance: Decimal | float,
    contract_size: Decimal | float = Decimal("100"),
    min_lot: Decimal | float = VOLUME_MIN,
) -> bool:
    """True when min-lot dollar risk is within equity * risk_pct / 100."""
    eq = Decimal(str(equity))
    pct = Decimal(str(risk_pct))
    if eq <= 0 or pct <= 0:
        return False
    budget = (eq * pct / Decimal("100")).quantize(Decimal("0.01"))
    return (
        min_lot_risk_dollars(
            stop_distance=stop_distance,
            contract_size=contract_size,
            min_lot=min_lot,
        )
        <= budget
    )
