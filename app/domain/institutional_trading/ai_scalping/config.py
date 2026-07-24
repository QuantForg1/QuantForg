"""AI Scalping Mode — all knobs configurable (nothing hardcoded at call sites)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any, Literal

from app.domain.institutional_trading.config import ITEConfig
from app.domain.market_context.enums import MarketSession
from app.domain.market_data.timeframe import Timeframe
from app.domain.trading.gold_only import GOLD_SYMBOL

TradingMode = Literal["swing", "scalping"]
VolatilityBand = Literal["high", "normal", "low"]
MarketRegimeLabel = Literal[
    "trending",
    "range",
    "breakout",
    "reversal",
    "accumulation",
    "distribution",
]


@dataclass(frozen=True, slots=True)
class AdaptiveThresholdBand:
    """Quality / confidence floors for one volatility band."""

    quality: int
    confidence: int


@dataclass(frozen=True, slots=True)
class AiScalpingConfig:
    """Institutional AI Scalping Engine configuration."""

    version: str = "ai-scalping-v4.0.0"
    symbol: str = GOLD_SYMBOL
    trading_mode: TradingMode = "scalping"

    # MTF stack — H1 direction · M15 structure · M5 entry · M1 timing
    direction_tf: Timeframe = Timeframe.H1
    structure_tf: Timeframe = Timeframe.M15
    entry_tf: Timeframe = Timeframe.M5
    execution_tf: Timeframe = Timeframe.M1

    # Adaptive thresholds (never fixed at evaluation — resolved from ATR%)
    high_vol: AdaptiveThresholdBand = field(
        default_factory=lambda: AdaptiveThresholdBand(quality=70, confidence=72)
    )
    normal_vol: AdaptiveThresholdBand = field(
        default_factory=lambda: AdaptiveThresholdBand(quality=78, confidence=78)
    )
    low_vol: AdaptiveThresholdBand = field(
        default_factory=lambda: AdaptiveThresholdBand(quality=85, confidence=85)
    )
    atr_high_pct: Decimal = Decimal("1.50")
    atr_low_pct: Decimal = Decimal("0.40")

    # Multi-trade
    max_open_trades: int = 3
    require_probability_improvement: bool = True
    min_confidence_delta_for_add: int = 3

    # Dynamic sizing
    risk_per_trade_pct: Decimal = Decimal("0.75")
    compounding_enabled: bool = False
    max_daily_exposure_pct: Decimal = Decimal("3.00")
    broker_min_lot: Decimal = Decimal("0.01")
    broker_lot_step: Decimal = Decimal("0.01")
    broker_max_lot: Decimal = Decimal("50.00")
    stop_atr_mult: Decimal = Decimal("1.25")

    # Smart TP / management (fed into PME)
    partial_tp_enabled: bool = True
    break_even_at_r: Decimal = Decimal("0.8")
    partial_at_r: Decimal = Decimal("1.5")
    partial_close_pct: Decimal = Decimal("50")
    trail_after_r: Decimal = Decimal("1.2")
    atr_trail_enabled: bool = True
    liquidity_trail_enabled: bool = True
    structure_trail_enabled: bool = True

    # Session aggression (1–5 stars)
    session_stars: dict[str, int] = field(
        default_factory=lambda: {
            MarketSession.LONDON.value: 5,
            MarketSession.NEW_YORK.value: 5,
            MarketSession.LONDON_NY_OVERLAP.value: 5,
            MarketSession.TOKYO.value: 2,
            MarketSession.SYDNEY.value: 2,
            MarketSession.OFF_HOURS.value: 1,
            MarketSession.CLOSED.value: 0,
        }
    )
    aggressive_session_min_stars: int = 5
    weak_session_confidence_penalty: int = 8

    # Spread intelligence — soft score, hard reject only above ceiling
    max_spread_for_full_score: Decimal = Decimal("0.50")
    max_spread_reject: Decimal = Decimal("2.00")
    spread_soft_penalty_max: int = 18

    # News protection
    news_protection_enabled: bool = True
    news_high_impact_pause: bool = True
    news_medium_risk_mult: Decimal = Decimal("0.50")
    news_blackout_minutes_before: int = 30
    news_blackout_minutes_after: int = 30

    # Execution budget (observational target)
    target_pipeline_latency_ms: int = 250

    # Self-learning
    learning_enabled: bool = True
    learning_max_records: int = 5000

    # Hard safety — never disable via this config alone
    allow_martingale: bool = False
    allow_grid: bool = False
    allow_unlimited_averaging: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", GOLD_SYMBOL)
        object.__setattr__(self, "allow_martingale", False)
        object.__setattr__(self, "allow_grid", False)
        object.__setattr__(self, "allow_unlimited_averaging", False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "trading_mode": self.trading_mode,
            "timeframes": {
                "direction": self.direction_tf.value,
                "structure": self.structure_tf.value,
                "entry": self.entry_tf.value,
                "execution": self.execution_tf.value,
            },
            "adaptive_thresholds": {
                "high_vol": {
                    "quality": self.high_vol.quality,
                    "confidence": self.high_vol.confidence,
                },
                "normal_vol": {
                    "quality": self.normal_vol.quality,
                    "confidence": self.normal_vol.confidence,
                },
                "low_vol": {
                    "quality": self.low_vol.quality,
                    "confidence": self.low_vol.confidence,
                },
                "atr_high_pct": str(self.atr_high_pct),
                "atr_low_pct": str(self.atr_low_pct),
            },
            "max_open_trades": self.max_open_trades,
            "require_probability_improvement": self.require_probability_improvement,
            "min_confidence_delta_for_add": self.min_confidence_delta_for_add,
            "risk_per_trade_pct": str(self.risk_per_trade_pct),
            "compounding_enabled": self.compounding_enabled,
            "max_daily_exposure_pct": str(self.max_daily_exposure_pct),
            "broker_min_lot": str(self.broker_min_lot),
            "broker_lot_step": str(self.broker_lot_step),
            "broker_max_lot": str(self.broker_max_lot),
            "stop_atr_mult": str(self.stop_atr_mult),
            "partial_tp_enabled": self.partial_tp_enabled,
            "break_even_at_r": str(self.break_even_at_r),
            "partial_at_r": str(self.partial_at_r),
            "partial_close_pct": str(self.partial_close_pct),
            "trail_after_r": str(self.trail_after_r),
            "atr_trail_enabled": self.atr_trail_enabled,
            "liquidity_trail_enabled": self.liquidity_trail_enabled,
            "structure_trail_enabled": self.structure_trail_enabled,
            "session_stars": dict(self.session_stars),
            "aggressive_session_min_stars": self.aggressive_session_min_stars,
            "weak_session_confidence_penalty": self.weak_session_confidence_penalty,
            "max_spread_for_full_score": str(self.max_spread_for_full_score),
            "max_spread_reject": str(self.max_spread_reject),
            "spread_soft_penalty_max": self.spread_soft_penalty_max,
            "news_protection_enabled": self.news_protection_enabled,
            "news_high_impact_pause": self.news_high_impact_pause,
            "news_medium_risk_mult": str(self.news_medium_risk_mult),
            "target_pipeline_latency_ms": self.target_pipeline_latency_ms,
            "learning_enabled": self.learning_enabled,
            "allow_martingale": self.allow_martingale,
            "allow_grid": self.allow_grid,
            "allow_unlimited_averaging": self.allow_unlimited_averaging,
        }


DEFAULT_AI_SCALPING_CONFIG = AiScalpingConfig()


def scalping_ite_config(
    base: ITEConfig | None = None,
    *,
    scalp: AiScalpingConfig | None = None,
) -> ITEConfig:
    """Map AI Scalping knobs onto ITEConfig (no H4 requirement)."""
    from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG

    src = base or DEFAULT_ITE_CONFIG
    cfg = scalp or DEFAULT_AI_SCALPING_CONFIG
    return replace(
        src,
        config_version=f"{src.config_version}+{cfg.version}",
        trading_mode="scalping",
        macro_bias_tf=cfg.direction_tf,
        primary_structure_tf=cfg.structure_tf,
        entry_confirmation_tf=cfg.entry_tf,
        execution_management_tf=cfg.execution_tf,
        min_confluence_score=cfg.normal_vol.confidence,
        min_trade_quality_score=cfg.normal_vol.quality,
        high_confidence_score=max(90, cfg.low_vol.confidence + 5),
        risk_per_trade_pct=cfg.risk_per_trade_pct,
        max_open_trades=cfg.max_open_trades,
        break_even_at_r=cfg.break_even_at_r,
        partial_at_r=cfg.partial_at_r,
        partial_close_pct=cfg.partial_close_pct,
        trail_after_r=cfg.trail_after_r,
        max_spread_for_full_score=cfg.max_spread_for_full_score,
        max_spread_reject=cfg.max_spread_reject,
        news_protection_enabled=cfg.news_protection_enabled,
        news_blackout_minutes_before=cfg.news_blackout_minutes_before,
        news_blackout_minutes_after=cfg.news_blackout_minutes_after,
    )
