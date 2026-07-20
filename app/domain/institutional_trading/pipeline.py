"""Analysis pipeline orchestrator — Structure → Liquidity → OB → FVG → Trend.

Produces :class:`MarketAnalysisSnapshot` for XAUUSD. Never trades (ADR-0010).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.fair_value_gap.engine import FairValueGapEngine
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.fingerprint import compute_input_hash
from app.domain.institutional_trading.models import MarketAnalysisSnapshot
from app.domain.institutional_trading.news_protection import NewsProtection
from app.domain.institutional_trading.ports import (
    MultiTimeframeBarStore,
    SnapshotLiquidityPort,
    SnapshotOrderBlockPort,
    SnapshotStructurePort,
    SwingFromBarsPort,
)
from app.domain.institutional_trading.session_filter import SessionFilter
from app.domain.institutional_trading.trade_quality import TradeQualityEvaluator
from app.domain.institutional_trading.trend_engine import TrendEngine
from app.domain.liquidity.engine import LiquidityEngine
from app.domain.market_context.engine import MarketContextEngine
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.engine import MarketStructureEngine
from app.domain.market_structure.structure_analyzer import StructureAnalyzer
from app.domain.market_structure.swing_detector import SwingDetector
from app.domain.market_structure.trend_classifier import TrendClassifier
from app.domain.order_block.engine import OrderBlockEngine
from app.domain.trading.gold_only import GOLD_SYMBOL, resolve_trading_symbol
from app.domain.value_objects.identity import SymbolCode


def build_default_context_engine() -> MarketContextEngine:
    """Wire FX session defaults for session filtering."""
    from app.domain.market_context.liquidity_resolver import LiquidityProfileResolver
    from app.domain.market_context.market_clock import MarketClock
    from app.domain.market_context.session_resolver import SessionResolver
    from app.domain.market_context.trading_calendar import TradingCalendarService
    from app.domain.market_context.volatility_resolver import VolatilityProfileResolver
    from app.infrastructure.market_context.default_fx_ports import (
        DefaultFxSessionPort,
        DefaultLiquidityProfilePort,
        DefaultVolatilityProfilePort,
        SystemClockPort,
        WeekendCalendarPort,
    )

    clock = MarketClock(clock=SystemClockPort())
    return MarketContextEngine(
        clock=clock,
        sessions=SessionResolver(sessions=DefaultFxSessionPort(), clock=clock),
        calendar=TradingCalendarService(calendar=WeekendCalendarPort(), clock=clock),
        liquidity=LiquidityProfileResolver(profiles=DefaultLiquidityProfilePort()),
        volatility=VolatilityProfileResolver(profiles=DefaultVolatilityProfilePort()),
    )


@dataclass
class InstitutionalAnalysisPipeline:
    """Run the ADR-0007 ordered analysis pipeline for ITE v1."""

    bars: MultiTimeframeBarStore
    config: ITEConfig = field(default_factory=lambda: DEFAULT_ITE_CONFIG)
    context_engine: MarketContextEngine | None = None
    news: NewsProtection | None = None

    async def analyze(
        self,
        *,
        as_of: datetime | None = None,
        spread: Decimal | None = None,
        symbol: str | None = None,
    ) -> MarketAnalysisSnapshot:
        cfg = self.config
        code_str = resolve_trading_symbol(symbol or cfg.symbol)
        if code_str != GOLD_SYMBOL and cfg.symbol == GOLD_SYMBOL:
            # Engine is gold-only by policy unless multi-symbol is enabled upstream
            code_str = resolve_trading_symbol(None)
        code = SymbolCode(value=code_str)
        moment = as_of or datetime.now(UTC)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)

        structure_port = SnapshotStructurePort()
        swings = SwingDetector()
        trends = TrendClassifier()
        analyzer = StructureAnalyzer()

        structure_by_tf: dict[Timeframe, object] = {}
        for tf in cfg.analysis_timeframes():
            engine = MarketStructureEngine(
                prices=self.bars,
                swings=swings,
                trends=trends,
                analyzer=analyzer,
                swing_left=cfg.swing_left,
                swing_right=cfg.swing_right,
                candle_limit=cfg.candle_limit,
            )
            result = await engine.analyze(code, tf, as_of=moment)
            structure_port.put(result.snapshot)
            structure_by_tf[tf] = result.snapshot

        primary_tf = cfg.primary_structure_tf
        primary = structure_by_tf.get(primary_tf)

        swing_port = SwingFromBarsPort(
            prices=self.bars,
            detector=swings,
            left=cfg.swing_left,
            right=cfg.swing_right,
        )
        liquidity_engine = LiquidityEngine(
            prices=self.bars,
            swings=swing_port,
            structure=structure_port,
            swing_left=cfg.swing_left,
            swing_right=cfg.swing_right,
            candle_limit=cfg.candle_limit,
        )
        liq_result = await liquidity_engine.analyze(code, primary_tf, as_of=moment)
        liq_port = SnapshotLiquidityPort(snapshot=liq_result.snapshot)

        ob_engine = OrderBlockEngine(
            prices=self.bars,
            structure=structure_port,
            liquidity=liq_port,
            candle_limit=cfg.candle_limit,
        )
        ob_result = await ob_engine.analyze(code, primary_tf, as_of=moment)
        ob_port = SnapshotOrderBlockPort(snapshot=ob_result.snapshot)

        fvg_engine = FairValueGapEngine(
            prices=self.bars,
            structure=structure_port,
            order_blocks=ob_port,
            candle_limit=cfg.candle_limit,
        )
        fvg_result = await fvg_engine.analyze(code, primary_tf, as_of=moment)

        typed_structure = {
            tf: snap  # type: ignore[misc]
            for tf, snap in structure_by_tf.items()
        }
        trend = TrendEngine(config=cfg).analyze(typed_structure)  # type: ignore[arg-type]

        # Prefer deterministic UTC classifier (no tzdata / DST variance in v1)
        session = SessionFilter(
            config=cfg,
            context_engine=None,
            prefer_utc_classifier=True,
        ).evaluate(as_of=moment)
        news = (self.news or NewsProtection(config=cfg)).evaluate(as_of=moment)

        quality = TradeQualityEvaluator(config=cfg).evaluate(
            trend=trend,
            structure=primary,  # type: ignore[arg-type]
            liquidity=liq_result.snapshot,
            order_blocks=ob_result.snapshot,
            fvgs=fvg_result.snapshot,
            session=session,
            spread=spread,
        )

        input_hash = compute_input_hash(
            symbol=code_str,
            as_of=moment,
            config_version=cfg.config_version,
            bars_by_tf=self.bars.as_mapping(),
            spread=str(spread) if spread is not None else None,
        )

        return MarketAnalysisSnapshot(
            symbol=code_str,
            as_of=moment,
            config_version=cfg.config_version,
            input_hash=input_hash,
            structure_by_tf={tf.value: s for tf, s in typed_structure.items()},  # type: ignore[misc]
            primary_structure=primary,  # type: ignore[arg-type]
            liquidity=liq_result.snapshot,
            order_blocks=ob_result.snapshot,
            fair_value_gaps=fvg_result.snapshot,
            trend=trend,
            session=session,
            news=news,
            trade_quality=quality,
            spread=spread,
        )
