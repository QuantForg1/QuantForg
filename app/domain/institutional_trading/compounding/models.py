"""Aggressive compounding — observe/shadow models only.

Never mutates Risk, Safety, OMS, PME, stops, or lots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from app.domain.institutional_trading.micro_account_mode import MicroAccountProfile
from app.domain.trading.xauusd_specs import VOLUME_MIN

CompoundingMode = Literal[
    "DEFENSIVE",
    "NORMAL",
    "AGGRESSIVE",
    "HIGH_CONVICTION",
    "CAPITAL_ATTACK",
]

DrawdownState = Literal[
    "GREEN",
    "CAUTION",
    "DEFENSIVE",
    "CAPITAL_PRESERVATION",
]

LIVE_ACTIVATION = "SHADOW_ONLY"
HARD_MAX_RISK_PCT = MicroAccountProfile().hard_max_risk_pct  # 5.0
BROKER_MIN_LOT = VOLUME_MIN  # 0.01


@dataclass(frozen=True, slots=True)
class CompoundingInputs:
    """Facts already produced by the live cycle — never invented prices."""

    symbol: str = ""
    direction: str = ""
    trade_class: str = "SCALP"
    score: dict[str, Any] = field(default_factory=dict)
    confidence: int | None = None
    quality: int | None = None
    expected_rr: Decimal | None = None
    equity: Decimal | None = None
    peak_equity: Decimal | None = None
    daily_pnl: Decimal | None = None
    daily_loss_pct: Decimal | None = None
    max_daily_loss_pct: Decimal | None = None
    max_weekly_drawdown_pct: Decimal | None = None
    open_positions: int = 0
    quantforg_open_count: int = 0
    remaining_capacity: int | None = None
    configured_max_open: int = 10
    exposure_pct: Decimal | None = None
    free_margin: Decimal | None = None
    margin_per_lot: Decimal | None = None
    risk_approved_volume: Decimal | None = None
    min_lot: Decimal = BROKER_MIN_LOT
    lot_step: Decimal | None = None
    max_lot: Decimal | None = None
    session: str | None = None
    news_blocked: bool = False
    same_symbol_blocked: bool = False
    candidate_allowed: bool = True
    min_lot_classification: str | None = None
    forwarded_to_oms: bool = False
    blocking_stage: str | None = None
    fault_code: str | None = None
    open_profits: tuple[Decimal, ...] = ()
    open_directions: tuple[str, ...] = ()
    open_entries: tuple[Decimal, ...] = ()
    entry: Decimal | None = None
    sequential_scale_in_live_enabled: bool = False
    cycle_id: str | None = None


@dataclass(frozen=True, slots=True)
class ConvictionResult:
    conviction_score: int
    confidence_adjusted_score: int
    conviction_regime: str
    conviction_reasons: tuple[str, ...]
    conviction_penalties: tuple[str, ...]
    opportunity_score: int
    components: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "conviction_score": self.conviction_score,
            "confidence_adjusted_score": self.confidence_adjusted_score,
            "conviction_regime": self.conviction_regime,
            "conviction_reasons": list(self.conviction_reasons),
            "conviction_penalties": list(self.conviction_penalties),
            "opportunity_score": self.opportunity_score,
            "components": dict(self.components),
        }


@dataclass(frozen=True, slots=True)
class CountPlan:
    strategy_target_count: int
    conviction_count: int
    risk_allowed_count: int
    portfolio_allowed_count: int
    margin_allowed_count: int
    broker_allowed_count: int
    remaining_capacity: int
    mode_count_cap: int
    effective_count: int
    reductions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_target_count": self.strategy_target_count,
            "conviction_count": self.conviction_count,
            "risk_allowed_count": self.risk_allowed_count,
            "portfolio_allowed_count": self.portfolio_allowed_count,
            "margin_allowed_count": self.margin_allowed_count,
            "broker_allowed_count": self.broker_allowed_count,
            "remaining_capacity": self.remaining_capacity,
            "mode_count_cap": self.mode_count_cap,
            "effective_count": self.effective_count,
            "reductions": list(self.reductions),
        }


@dataclass(frozen=True, slots=True)
class SizingAdvice:
    quality_multiplier: Decimal
    risk_approved_volume: Decimal
    suggested_volume: Decimal
    per_leg_volume: Decimal
    approved_aggregate_volume: Decimal
    capped_by_risk: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "quality_multiplier": str(self.quality_multiplier),
            "risk_approved_volume": str(self.risk_approved_volume),
            "suggested_volume": str(self.suggested_volume),
            "per_leg_volume": str(self.per_leg_volume),
            "approved_aggregate_volume": str(self.approved_aggregate_volume),
            "capped_by_risk": self.capped_by_risk,
            "invariant": "suggested_volume <= risk_approved_volume",
        }


@dataclass(frozen=True, slots=True)
class ScaleInAdvice:
    scale_in_allowed: bool
    scale_in_live_enabled: bool
    shadow_eligible: bool
    scale_in_block_reason: str
    winners_only: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "scale_in_allowed": self.scale_in_allowed,
            "scale_in_live_enabled": self.scale_in_live_enabled,
            "shadow_eligible": self.shadow_eligible,
            "scale_in_block_reason": self.scale_in_block_reason,
            "winners_only": self.winners_only,
        }


@dataclass(frozen=True, slots=True)
class CompoundingObservation:
    """Shadow recommendation. Live OMS/Risk are never driven by this object."""

    live_activation: str
    mutates_engines: bool
    mode: CompoundingMode
    drawdown_state: DrawdownState
    compounding_bias: str
    conviction: ConvictionResult
    counts: CountPlan
    sizing: SizingAdvice
    scale_in: ScaleInAdvice
    equity: str | None
    risk_budget_pct: str
    portfolio_exposure_pct: str | None
    expected_r: str | None
    signal_quality: int | None
    signal_confidence: int | None
    min_lot_classification: str | None
    live_hard_max_risk_pct: str
    live_min_lot: str
    cycle_id: str | None
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "live_activation": self.live_activation,
            "mutates_engines": self.mutates_engines,
            "mode": self.mode,
            "drawdown_state": self.drawdown_state,
            "compounding_bias": self.compounding_bias,
            "conviction": self.conviction.to_dict(),
            "counts": self.counts.to_dict(),
            "sizing": self.sizing.to_dict(),
            "scale_in": self.scale_in.to_dict(),
            "equity": self.equity,
            "risk_budget_pct": self.risk_budget_pct,
            "portfolio_exposure": self.portfolio_exposure_pct,
            "expected_R": self.expected_r,
            "signal_quality": self.signal_quality,
            "signal_confidence": self.signal_confidence,
            "min_lot_classification": self.min_lot_classification,
            "live_hard_max_risk_pct": self.live_hard_max_risk_pct,
            "live_min_lot": self.live_min_lot,
            "cycle_id": self.cycle_id,
            "notes": list(self.notes),
        }
