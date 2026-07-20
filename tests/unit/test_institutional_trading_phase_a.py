"""Golden / unit tests for ITE Phase A analysis pipeline."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.fingerprint import compute_input_hash
from app.domain.institutional_trading.pipeline import InstitutionalAnalysisPipeline
from app.domain.institutional_trading.ports import MultiTimeframeBarStore
from app.domain.institutional_trading.session_filter import SessionFilter
from app.domain.institutional_trading.trend_engine import TrendEngine
from app.domain.market_context.enums import MarketSession
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import StructureRole, TrendDirection
from app.domain.market_structure.models import StructureSnapshot, TrendState
from app.domain.value_objects.identity import SymbolCode


def _make_series(
    *,
    tf: Timeframe,
    n: int = 40,
    start: datetime | None = None,
    base: float = 2300.0,
    step_minutes: int | None = None,
) -> list[Candle]:
    """Deterministic synthetic XAU path with enough bars for swings."""
    base_t = start or datetime(2026, 3, 10, 14, 0, tzinfo=UTC)  # London/NY overlap-ish
    minutes = (
        step_minutes
        or {
            Timeframe.M5: 5,
            Timeframe.M15: 15,
            Timeframe.H1: 60,
            Timeframe.H4: 240,
        }[tf]
    )
    out: list[Candle] = []
    price = base
    for i in range(n):
        open_time = base_t + timedelta(minutes=minutes * i)
        close_time = open_time + timedelta(minutes=minutes)
        # Gentle uptrend with mild swings
        drift = (i % 7) - 3
        o = price
        h = price + 1.5 + abs(drift) * 0.2
        low = price - 1.2 - abs(drift) * 0.1
        c = price + 0.4 * (1 if drift >= 0 else -1)
        out.append(
            Candle.create(
                symbol_code="XAUUSD",
                timeframe=tf,
                open_time=open_time,
                close_time=close_time,
                open=f"{o:.2f}",
                high=f"{h:.2f}",
                low=f"{low:.2f}",
                close=f"{c:.2f}",
                volume="1",
            )
        )
        price = float(c)
    return out


def _bundle() -> MultiTimeframeBarStore:
    store = MultiTimeframeBarStore()
    for tf in (Timeframe.H4, Timeframe.H1, Timeframe.M15, Timeframe.M5):
        store.set_bars(tf, _make_series(tf=tf))
    return store


@pytest.mark.unit
class TestITEPhaseAPipeline:
    @pytest.mark.asyncio
    async def test_pipeline_produces_composite_snapshot(self) -> None:
        store = _bundle()
        as_of = datetime(2026, 3, 10, 14, 30, tzinfo=UTC)
        pipe = InstitutionalAnalysisPipeline(bars=store, config=ITEConfig())
        snap = await pipe.analyze(as_of=as_of, spread=Decimal("0.30"))

        assert snap.symbol == "XAUUSD"
        assert snap.config_version == "ite-v1.0.0"
        assert snap.schema_version == "1.0.0"
        assert set(snap.structure_by_tf.keys()) == {"H4", "H1", "M15", "M5"}
        assert snap.primary_structure is not None
        assert snap.primary_structure.timeframe == Timeframe.H1
        assert snap.liquidity is not None
        assert snap.order_blocks is not None
        assert snap.fair_value_gaps is not None
        assert snap.trend.frames.keys() >= {"H4", "H1", "M15", "M5"}
        assert 0 <= snap.trade_quality.total <= 100
        assert snap.spread == Decimal("0.30")
        assert snap.input_hash
        assert "trend" in {f.code for f in snap.trade_quality.factors}
        assert "session" in {f.code for f in snap.trade_quality.factors}
        assert "spread" in {f.code for f in snap.trade_quality.factors}

    @pytest.mark.asyncio
    async def test_pipeline_is_deterministic(self) -> None:
        store = _bundle()
        as_of = datetime(2026, 3, 10, 14, 30, tzinfo=UTC)
        cfg = ITEConfig()
        a = await InstitutionalAnalysisPipeline(bars=store, config=cfg).analyze(
            as_of=as_of, spread=Decimal("0.30")
        )
        b = await InstitutionalAnalysisPipeline(bars=store, config=cfg).analyze(
            as_of=as_of, spread=Decimal("0.30")
        )
        assert a.input_hash == b.input_hash
        assert a.trend.alignment_score == b.trend.alignment_score
        assert a.trade_quality.total == b.trade_quality.total
        assert a.session.session == b.session.session

    def test_fingerprint_stable(self) -> None:
        store = _bundle()
        as_of = datetime(2026, 3, 10, 14, 30, tzinfo=UTC)
        h1 = compute_input_hash(
            symbol="XAUUSD",
            as_of=as_of,
            config_version="ite-v1.0.0",
            bars_by_tf=store.as_mapping(),
            spread="0.30",
        )
        h2 = compute_input_hash(
            symbol="XAUUSD",
            as_of=as_of,
            config_version="ite-v1.0.0",
            bars_by_tf=store.as_mapping(),
            spread="0.30",
        )
        assert h1 == h2

    def test_session_filter_rejects_tokyo(self) -> None:
        cfg = ITEConfig()
        result = SessionFilter(config=cfg).evaluate(
            as_of=datetime(2026, 3, 10, 3, 0, tzinfo=UTC),
            session=MarketSession.TOKYO,
        )
        assert result.allowed is False

    def test_session_filter_allows_overlap(self) -> None:
        cfg = ITEConfig()
        result = SessionFilter(config=cfg).evaluate(
            as_of=datetime(2026, 3, 10, 14, 0, tzinfo=UTC),
            session=MarketSession.LONDON_NY_OVERLAP,
        )
        assert result.allowed is True

    def test_trend_engine_hierarchy(self) -> None:
        cfg = ITEConfig()
        code = SymbolCode(value="XAUUSD")
        as_of = datetime(2026, 3, 10, tzinfo=UTC)

        def snap(tf: Timeframe, direction: TrendDirection) -> StructureSnapshot:
            return StructureSnapshot(
                symbol_code=code,
                timeframe=tf,
                as_of=as_of,
                swings=(),
                nodes=(),
                trend=TrendState(
                    symbol_code=code,
                    timeframe=tf,
                    direction=direction,
                    as_of=as_of,
                    last_structure_role=StructureRole.UNKNOWN,
                    swing_count=0,
                ),
                breaks_of_structure=(),
                changes_of_character=(),
            )

        by_tf = {
            Timeframe.H4: snap(Timeframe.H4, TrendDirection.UP),
            Timeframe.H1: snap(Timeframe.H1, TrendDirection.UP),
            Timeframe.M15: snap(Timeframe.M15, TrendDirection.UP),
            Timeframe.M5: snap(Timeframe.M5, TrendDirection.RANGE),
        }
        trend = TrendEngine(config=cfg).analyze(by_tf)
        assert trend.macro_bias == TrendDirection.UP
        assert trend.primary == TrendDirection.UP
        assert trend.aligned is True
        assert trend.alignment_score >= 70
