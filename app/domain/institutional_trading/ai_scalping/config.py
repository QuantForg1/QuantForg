"""Institutional AI Scalping v6 - execution-quality config (never raise risk casually)."""

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

# Same institutional universe as Alpha - trade only the best opportunity.
DEFAULT_SCALPING_UNIVERSE: tuple[str, ...] = (
    "XAUUSD",
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "NAS100",
    "US30",
    "BTCUSD",
)


@dataclass(frozen=True, slots=True)
class AdaptiveThresholdBand:
    """Quality / confidence floors for one volatility band."""

    quality: int
    confidence: int


@dataclass(frozen=True, slots=True)
class AiScalpingConfig:
    """Institutional AI Scalping Engine - quality over quantity."""

    version: str = "ai-scalping-v6.2.0"
    symbol: str = GOLD_SYMBOL
    trading_mode: TradingMode = "scalping"
    universe: tuple[str, ...] = DEFAULT_SCALPING_UNIVERSE

    # MTF stack - H1 direction · M15 structure · M5 entry · M1 precision
    direction_tf: Timeframe = Timeframe.H1
    structure_tf: Timeframe = Timeframe.M15
    entry_tf: Timeframe = Timeframe.M5
    execution_tf: Timeframe = Timeframe.M1

    # Tighter adaptive floors - reject weak setups (do NOT loosen for fill rate)
    high_vol: AdaptiveThresholdBand = field(
        default_factory=lambda: AdaptiveThresholdBand(quality=75, confidence=76)
    )
    normal_vol: AdaptiveThresholdBand = field(
        default_factory=lambda: AdaptiveThresholdBand(quality=82, confidence=82)
    )
    low_vol: AdaptiveThresholdBand = field(
        default_factory=lambda: AdaptiveThresholdBand(quality=88, confidence=88)
    )
    atr_high_pct: Decimal = Decimal("1.50")
    atr_low_pct: Decimal = Decimal("0.40")

    # Quality gates (all required for a take)
    require_strong_structure: bool = True
    require_liquidity_event: bool = True
    require_momentum_confirm: bool = True
    require_tight_spread: bool = True
    require_valid_volatility: bool = True
    require_session_quality: bool = True
    require_pa_confluence: bool = True
    min_structure_score: int = 70
    min_momentum_score: int = 65
    min_liquidity_score: int = 60
    min_session_stars: int = 4
    min_expected_rr: Decimal = Decimal("1.3")
    # EMA / RSI / candle PA composite — never below prior quality floors
    min_pa_confluence_score: int = 55

    # Real scalping hold window
    typical_hold_min_minutes: int = 1
    typical_hold_max_minutes: int = 10
    max_hold_minutes_if_confident: int = 20
    high_confidence_for_extend: int = 88
    # Absolute flatten — do not keep scalps open unnecessarily
    absolute_max_hold_minutes: int = 25

    # Multi-trade - prefer quality, not stacking losers
    max_open_trades: int = 2
    require_probability_improvement: bool = True
    min_confidence_delta_for_add: int = 5

    # Dynamic sizing - DO NOT increase risk vs prior default without evidence
    risk_per_trade_pct: Decimal = Decimal("0.50")
    compounding_enabled: bool = False
    max_daily_exposure_pct: Decimal = Decimal("2.00")
    broker_min_lot: Decimal = Decimal("0.01")
    broker_lot_step: Decimal = Decimal("0.01")
    broker_max_lot: Decimal = Decimal("50.00")
    stop_atr_mult: Decimal = Decimal("1.10")  # structure-first; ATR is fallback

    # Profit management - scale out fast
    partial_tp_enabled: bool = True
    break_even_at_r: Decimal = Decimal("0.5")
    partial_at_r: Decimal = Decimal("1.0")
    partial_close_pct: Decimal = Decimal("50")
    trail_after_r: Decimal = Decimal("1.0")
    atr_trail_enabled: bool = True
    liquidity_trail_enabled: bool = True
    structure_trail_enabled: bool = True
    # Optional fixed-R TP preference (None = structure/ATR targets only)
    fixed_tp_r: Decimal | None = Decimal("1.5")
    atr_tp_mult: Decimal = Decimal("1.8")
    time_stop_minutes: int = 10
    time_stop_min_r: Decimal = Decimal("0.3")
    momentum_fade_exit: bool = True
    momentum_fade_threshold: int = 40

    # Session aggression (1-5 stars) — London / NY / overlap preferred
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
    weak_session_confidence_penalty: int = 10
    # Configurable session allow-list (maps onto ITE when applying scalping mode)
    allowed_sessions: tuple[str, ...] = (
        MarketSession.LONDON.value,
        MarketSession.NEW_YORK.value,
        MarketSession.LONDON_NY_OVERLAP.value,
    )

    # Spread - hard reject weak liquidity
    max_spread_for_full_score: Decimal = Decimal("0.40")
    max_spread_reject: Decimal = Decimal("1.50")
    spread_soft_penalty_max: int = 22
    # Reject when spread > ATR * this fraction (in addition to absolute max)
    max_spread_atr_pct: Decimal = Decimal("15.0")  # 15% of ATR

    # Slippage protection (price units)
    max_entry_slippage: Decimal = Decimal("0.50")
    slippage_protection_enabled: bool = True

    # Optional volatility-adjusted sizing — never exceeds risk_per_trade_pct
    volatility_adjusted_sizing: bool = True
    high_vol_risk_scale: Decimal = Decimal("0.75")  # reduce risk in high vol
    low_vol_risk_scale: Decimal = Decimal("1.00")  # never above base risk

    # Self-protection (pause NEW entries only)
    self_protection_enabled: bool = True
    pause_drawdown_pct: Decimal = Decimal("3.0")
    pause_reject_burst: int = 5
    pause_slippage_burst: int = 3
    pause_gateway_fail_burst: int = 3
    high_latency_pause_ms: float = 2000.0

    # News protection — existing trades still managed by risk/PME
    news_protection_enabled: bool = True
    news_high_impact_pause: bool = True
    news_medium_risk_mult: Decimal = Decimal("0.50")
    news_blackout_minutes_before: int = 30
    news_blackout_minutes_after: int = 30
    # Default False preserves availability when calendar feed is absent
    news_fail_closed_without_feed: bool = False

    target_pipeline_latency_ms: int = 200
    learning_enabled: bool = True
    learning_max_records: int = 5000

    # Hard safety - never disable
    allow_martingale: bool = False
    allow_grid: bool = False
    allow_unlimited_averaging: bool = False
    never_prefer_buy_only: bool = True
    risk_increase_locked: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "allow_martingale", False)
        object.__setattr__(self, "allow_grid", False)
        object.__setattr__(self, "allow_unlimited_averaging", False)
        object.__setattr__(self, "never_prefer_buy_only", True)
        # Cap risk - quality upgrade must not silently raise risk
        if self.risk_per_trade_pct > Decimal("0.75"):
            object.__setattr__(self, "risk_per_trade_pct", Decimal("0.75"))
        # Never loosen hold beyond absolute max
        if self.absolute_max_hold_minutes < self.typical_hold_max_minutes:
            object.__setattr__(
                self,
                "absolute_max_hold_minutes",
                self.typical_hold_max_minutes,
            )
        if self.max_hold_minutes_if_confident > self.absolute_max_hold_minutes:
            object.__setattr__(
                self,
                "max_hold_minutes_if_confident",
                self.absolute_max_hold_minutes,
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "trading_mode": self.trading_mode,
            "universe": list(self.universe),
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
            "quality_gates": {
                "require_strong_structure": self.require_strong_structure,
                "require_liquidity_event": self.require_liquidity_event,
                "require_momentum_confirm": self.require_momentum_confirm,
                "require_tight_spread": self.require_tight_spread,
                "require_valid_volatility": self.require_valid_volatility,
                "require_session_quality": self.require_session_quality,
                "require_pa_confluence": self.require_pa_confluence,
                "min_structure_score": self.min_structure_score,
                "min_momentum_score": self.min_momentum_score,
                "min_liquidity_score": self.min_liquidity_score,
                "min_session_stars": self.min_session_stars,
                "min_expected_rr": str(self.min_expected_rr),
                "min_pa_confluence_score": self.min_pa_confluence_score,
            },
            "hold_window": {
                "typical_min": self.typical_hold_min_minutes,
                "typical_max": self.typical_hold_max_minutes,
                "max_if_confident": self.max_hold_minutes_if_confident,
                "absolute_max": self.absolute_max_hold_minutes,
            },
            "max_open_trades": self.max_open_trades,
            "risk_per_trade_pct": str(self.risk_per_trade_pct),
            "risk_increase_locked": True,
            "break_even_at_r": str(self.break_even_at_r),
            "partial_at_r": str(self.partial_at_r),
            "partial_tp_enabled": self.partial_tp_enabled,
            "trail_after_r": str(self.trail_after_r),
            "atr_trail_enabled": self.atr_trail_enabled,
            "structure_trail_enabled": self.structure_trail_enabled,
            "liquidity_trail_enabled": self.liquidity_trail_enabled,
            "fixed_tp_r": str(self.fixed_tp_r) if self.fixed_tp_r is not None else None,
            "time_stop_minutes": self.time_stop_minutes,
            "momentum_fade_exit": self.momentum_fade_exit,
            "momentum_fade_threshold": self.momentum_fade_threshold,
            "allowed_sessions": list(self.allowed_sessions),
            "news_protection_enabled": self.news_protection_enabled,
            "news_fail_closed_without_feed": self.news_fail_closed_without_feed,
            "max_spread_atr_pct": str(self.max_spread_atr_pct),
            "max_entry_slippage": str(self.max_entry_slippage),
            "slippage_protection_enabled": self.slippage_protection_enabled,
            "volatility_adjusted_sizing": self.volatility_adjusted_sizing,
            "self_protection_enabled": self.self_protection_enabled,
            "pause_drawdown_pct": str(self.pause_drawdown_pct),
            "never_prefer_buy_only": True,
            "allow_martingale": False,
            "allow_grid": False,
        }


DEFAULT_AI_SCALPING_CONFIG = AiScalpingConfig()


def scalping_ite_config(
    base: ITEConfig | None = None,
    *,
    scalp: AiScalpingConfig | None = None,
) -> ITEConfig:
    """Map AI Scalping knobs onto ITEConfig (H1/M15/M5/M1 - no H4)."""
    from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG

    src = base or DEFAULT_ITE_CONFIG
    cfg = scalp or DEFAULT_AI_SCALPING_CONFIG
    sessions: list[MarketSession] = []
    for name in cfg.allowed_sessions:
        try:
            sessions.append(MarketSession(str(name)))
        except ValueError:
            continue
    if not sessions:
        sessions = list(src.allowed_sessions)
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
        high_confidence_score=max(90, cfg.low_vol.confidence + 2),
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
        allowed_sessions=tuple(sessions),
    )
