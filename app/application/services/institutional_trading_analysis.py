"""Application service — run ITE Phase A analysis for XAUUSD."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.models import MarketAnalysisSnapshot
from app.domain.institutional_trading.pipeline import InstitutionalAnalysisPipeline
from app.domain.institutional_trading.ports import MultiTimeframeBarStore
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe


@dataclass
class InstitutionalTradingAnalysisService:
    """Load bars into the pipeline and return a composite snapshot.

    Does not submit orders. Preserves the existing OMS boundary.
    """

    config: ITEConfig = field(default_factory=lambda: DEFAULT_ITE_CONFIG)

    async def analyze_bars(
        self,
        bars_by_tf: dict[Timeframe, list[Candle]],
        *,
        as_of: datetime | None = None,
        spread: Decimal | None = None,
    ) -> MarketAnalysisSnapshot:
        store = MultiTimeframeBarStore()
        for tf, candles in bars_by_tf.items():
            store.set_bars(tf, candles)
        pipeline = InstitutionalAnalysisPipeline(bars=store, config=self.config)
        return await pipeline.analyze(as_of=as_of, spread=spread)
