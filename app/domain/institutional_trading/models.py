"""Immutable ITE analysis read models (ADR-0008 composite)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.domain.fair_value_gap.models import FairValueGapSnapshot
from app.domain.liquidity.models import LiquiditySnapshot
from app.domain.market_context.enums import MarketSession
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import TrendDirection
from app.domain.market_structure.models import StructureSnapshot
from app.domain.order_block.models import OrderBlockSnapshot


@dataclass(frozen=True, slots=True)
class TrendSnapshot:
    """Multi-timeframe bias under the approved hierarchy."""

    macro_bias: TrendDirection  # H4
    primary: TrendDirection  # H1
    entry: TrendDirection  # M15
    execution: TrendDirection  # M5
    alignment_score: int  # 0-100
    aligned: bool
    frames: dict[str, str] = field(default_factory=dict)
    why: str = ""
    # AI Decision Engine v2 — optional telemetry (defaults preserve v1 callers)
    market_regime: str = "unknown"  # trending | ranging
    mtf_policy: str = "v1"
    trade_bias: TrendDirection | None = None  # regime-aware bias (may differ from H4)
    mtf_contributions: dict[str, int] = field(default_factory=dict)
    h4_is_context: bool = False
    # M15 Trend Semantics v2 telemetry (optional)
    m15_semantics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "macro_bias": self.macro_bias.value,
            "primary": self.primary.value,
            "entry": self.entry.value,
            "execution": self.execution.value,
            "alignment_score": self.alignment_score,
            "aligned": self.aligned,
            "frames": dict(self.frames),
            "why": self.why,
            "market_regime": self.market_regime,
            "mtf_policy": self.mtf_policy,
            "trade_bias": (
                self.trade_bias.value if self.trade_bias is not None else None
            ),
            "mtf_contributions": dict(self.mtf_contributions),
            "h4_is_context": self.h4_is_context,
            "m15_semantics": dict(self.m15_semantics),
        }

    @property
    def effective_bias(self) -> TrendDirection:
        """Directional bias used for confluence — regime-aware when present."""
        if self.trade_bias is not None:
            return self.trade_bias
        if self.macro_bias in {TrendDirection.UP, TrendDirection.DOWN}:
            return self.macro_bias
        if self.primary in {TrendDirection.UP, TrendDirection.DOWN}:
            return self.primary
        return TrendDirection.UNKNOWN


@dataclass(frozen=True, slots=True)
class TradeQualityFactor:
    code: str
    weight: int
    score: int  # 0-100 component
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "weight": self.weight,
            "score": self.score,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class TradeQualityScore:
    """0-100 composite: Trend · Liquidity · OB · FVG · Structure · Session · Spread."""

    total: int
    passed: bool  # total >= min_trade_quality_score
    band: str  # reject | tradable | high_confidence
    factors: tuple[TradeQualityFactor, ...] = ()

    @property
    def components(self) -> dict[str, int]:
        """Factor code → score for scalping overlays (momentum/volume aliases)."""
        from app.domain.institutional_trading.quality_components import (
            quality_components,
        )

        return quality_components(self)

    def to_dict(self) -> dict[str, Any]:
        from app.domain.institutional_trading.quality_components import (
            quality_components,
        )

        return {
            "total": self.total,
            "passed": self.passed,
            "band": self.band,
            "factors": [f.to_dict() for f in self.factors],
            "components": quality_components(self),
        }


@dataclass(frozen=True, slots=True)
class SessionFilterResult:
    session: MarketSession
    allowed: bool
    reason: str
    # Soft weighting — never an absolute reject by itself when allowed=True
    quality_score: int = 100
    risk_multiplier: Decimal = Decimal("1")
    stars: int = 5

    def to_dict(self) -> dict[str, Any]:
        return {
            "session": self.session.value,
            "allowed": self.allowed,
            "reason": self.reason,
            "quality_score": self.quality_score,
            "risk_multiplier": str(self.risk_multiplier),
            "stars": self.stars,
        }


@dataclass(frozen=True, slots=True)
class NewsProtectionStatus:
    enabled: bool
    blocked: bool
    reason: str
    events: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "blocked": self.blocked,
            "reason": self.reason,
            "events": list(self.events),
        }


@dataclass(frozen=True, slots=True)
class MarketAnalysisSnapshot:
    """Composite analysis snapshot for XAUUSD at one UTC instant."""

    symbol: str
    as_of: datetime
    config_version: str
    input_hash: str
    structure_by_tf: dict[str, StructureSnapshot]
    primary_structure: StructureSnapshot | None
    liquidity: LiquiditySnapshot | None
    order_blocks: OrderBlockSnapshot | None
    fair_value_gaps: FairValueGapSnapshot | None
    trend: TrendSnapshot
    session: SessionFilterResult
    news: NewsProtectionStatus
    trade_quality: TradeQualityScore
    spread: Decimal | None = None
    atr: Decimal | None = None
    # M5 scalp ATR for stop distance. ``atr`` remains the analysis/volatility ATR.
    entry_atr: Decimal | None = None
    # Entry-TF OHLC for EMA/RSI/candle PA — empty when unavailable (never invent).
    entry_opens: tuple[float, ...] = ()
    entry_highs: tuple[float, ...] = ()
    entry_lows: tuple[float, ...] = ()
    entry_closes: tuple[float, ...] = ()
    id: UUID = field(default_factory=uuid4)
    schema_version: str = "1.0.0"

    @property
    def timeframe_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self.structure_by_tf.keys()))

    def structure_for(self, tf: Timeframe | str) -> StructureSnapshot | None:
        key = tf.value if isinstance(tf, Timeframe) else str(tf)
        return self.structure_by_tf.get(key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "schema_version": self.schema_version,
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat(),
            "config_version": self.config_version,
            "input_hash": self.input_hash,
            "timeframes": list(self.timeframe_keys),
            "structure_by_tf": {
                k: v.to_dict() for k, v in self.structure_by_tf.items()
            },
            "primary_structure": (
                self.primary_structure.to_dict() if self.primary_structure else None
            ),
            "liquidity": self.liquidity.to_dict() if self.liquidity else None,
            "order_blocks": (
                self.order_blocks.to_dict() if self.order_blocks else None
            ),
            "fair_value_gaps": (
                self.fair_value_gaps.to_dict() if self.fair_value_gaps else None
            ),
            "trend": self.trend.to_dict(),
            "session": self.session.to_dict(),
            "news": self.news.to_dict(),
            "trade_quality": self.trade_quality.to_dict(),
            "spread": str(self.spread) if self.spread is not None else None,
            "atr": str(self.atr) if self.atr is not None else None,
            "entry_atr": str(self.entry_atr) if self.entry_atr is not None else None,
        }
