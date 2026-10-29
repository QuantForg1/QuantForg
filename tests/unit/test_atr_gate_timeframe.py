"""Entry-timeframe ATR for percentage gates. Stop ATR stays on its own series."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
    resolve_adaptive_thresholds,
)
from app.domain.institutional_trading.ai_scalping.session_intelligence import (
    assess_session,
)
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    SpreadAssessment,
    assess_spread,
)
from app.domain.institutional_trading.ai_scalping.volatility_gate_v2 import (
    evaluate_volatility_gate_v2,
)
from app.domain.institutional_trading.atr import (
    atr_for_timeframe,
    bar_is_time_aligned,
    score_gate_atr,
)
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe

_ROOT = Path(__file__).resolve().parents[2]
_LIVE_CALLERS = (
    "app/application/services/institutional_decision_pipeline.py",
    "app/application/services/institutional_multi_asset_scanner.py",
    "app/application/services/research_universe_scanner.py",
)


def _bar(
    timeframe: Timeframe,
    open_time: datetime,
    *,
    low: str,
    high: str,
    close: str,
) -> Candle:
    return Candle.create(
        symbol_code="XAUUSD",
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + timeframe.duration,
        open=close,
        high=high,
        low=low,
        close=close,
        volume="1",
    )


def _flat(
    timeframe: Timeframe,
    start: datetime,
    count: int,
    *,
    half_range: str,
    base: str = "4000",
) -> list[Candle]:
    half = Decimal(half_range)
    price = Decimal(base)
    bars: list[Candle] = []
    opened = start
    for _ in range(count):
        bars.append(
            _bar(
                timeframe,
                opened,
                low=str(price - half),
                high=str(price + half),
                close=str(price),
            )
        )
        opened += timeframe.duration
    return bars


def _vol(atr: Decimal, mid: Decimal) -> bool:
    resolved = resolve_adaptive_thresholds(atr, mid, symbol="XAUUSD")
    decision = evaluate_volatility_gate_v2(
        atr_pct=resolved.atr_pct,
        thresholds=resolved,
        trade_quality=90,
        confidence=90,
        structure_score=90,
        liquidity=90,
        momentum=90,
        mtf_alignment=90,
        session=assess_session("london"),
        spread=SpreadAssessment(
            score=100,
            confidence_penalty=0,
            reject=False,
            reason="tight",
        ),
        market_regime="strong_trend",
        symbol="XAUUSD",
    )
    return decision.passed


@pytest.mark.unit
def test_score_gate_atr_ignores_the_m1_stop_series() -> None:
    snapshot = SimpleNamespace(
        atr=Decimal("4.80"),
        entry_atr=Decimal("1.90"),
        stop_atr=Decimal("1.90"),
    )
    assert score_gate_atr(snapshot) == Decimal("4.80")
    missing = SimpleNamespace(
        atr=None, entry_atr=Decimal("1.90"), stop_atr=Decimal("1.90")
    )
    assert score_gate_atr(missing) is None
    zero = SimpleNamespace(atr=Decimal("0"), stop_atr=Decimal("1.90"))
    assert score_gate_atr(zero) is None


@pytest.mark.unit
def test_atr_percent_and_spread_cap_use_price_units() -> None:
    mid = Decimal("4000")
    gate = Decimal("4.80")
    stop = Decimal("1.90")
    assert (gate / mid) * Decimal("100") == Decimal("0.12")
    assert (stop / mid) * Decimal("100") == Decimal("0.0475")
    # 15% of 4.80 = 0.72. 15% of 1.90 = 0.285. Absolute class ceiling is wider.
    wide = assess_spread(Decimal("0.450"), atr=gate, symbol="XAUUSD-GATE-TF")
    tight = assess_spread(Decimal("0.450"), atr=stop, symbol="XAUUSD-GATE-TF-STOP")
    assert wide.reject is False
    assert tight.reject is True
    assert "15" in tight.reason


@pytest.mark.unit
def test_volatility_regimes_follow_the_entry_series() -> None:
    mid = Decimal("4000")
    # M5-scale 0.12% is the normal band: the 0.20 floor does not apply.
    assert _vol(Decimal("4.80"), mid) is True
    # M15-scale 0.18% is also normal and passes.
    assert _vol(Decimal("7.20"), mid) is True
    # High band still passes. The compression floor is low-band only.
    assert _vol(Decimal("16"), mid) is True
    # M1-scale 0.0475% is below the 0.08 hard minimum.
    assert _vol(Decimal("1.90"), mid) is False


@pytest.mark.unit
def test_closed_bars_drop_a_forming_bar_and_reject_a_stale_series() -> None:
    start = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)
    closed = _flat(Timeframe.M5, start, 16, half_range="2")
    as_of = closed[-1].close_time
    fresh = atr_for_timeframe(closed, as_of=as_of, timeframe=Timeframe.M5)
    assert fresh == Decimal("4.00000000")
    forming = _bar(
        Timeframe.M5,
        as_of,
        low="3900",
        high="4100",
        close="4000",
    )
    assert forming.close_time > as_of
    assert (
        atr_for_timeframe([*closed, forming], as_of=as_of, timeframe=Timeframe.M5)
        == fresh
    )
    stale_as_of = as_of + timedelta(minutes=11)
    assert atr_for_timeframe(closed, as_of=stale_as_of, timeframe=Timeframe.M5) is None


@pytest.mark.unit
def test_misaligned_bars_do_not_enter_the_atr() -> None:
    start = datetime(2026, 6, 2, 12, 1, tzinfo=UTC)
    bars = _flat(Timeframe.M5, start, 16, half_range="2")
    assert bar_is_time_aligned(bars[0], Timeframe.M5) is False
    as_of = bars[-1].close_time
    assert atr_for_timeframe(bars, as_of=as_of, timeframe=Timeframe.M5) is None


@pytest.mark.unit
def test_broker_clock_lead_drops_the_unproven_newest_bar() -> None:
    start = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)
    bars = _flat(Timeframe.M5, start, 16, half_range="2")
    # Decision clock is two hours behind the candle stamps.
    as_of = bars[-1].close_time - timedelta(hours=2)
    assert atr_for_timeframe(bars, as_of=as_of, timeframe=Timeframe.M5) == Decimal(
        "4.00000000"
    )
    wide = _bar(
        Timeframe.M5,
        bars[-1].open_time + Timeframe.M5.duration,
        low="3900",
        high="4100",
        close="4000",
    )
    assert atr_for_timeframe(
        [*bars, wide], as_of=as_of, timeframe=Timeframe.M5
    ) == Decimal("4.00000000")
    shifted = _flat(Timeframe.M5, start + timedelta(minutes=1), 16, half_range="2")
    assert (
        atr_for_timeframe(
            shifted,
            as_of=shifted[-1].close_time - timedelta(hours=2),
            timeframe=Timeframe.M5,
        )
        is None
    )


@pytest.mark.unit
def test_m5_gate_atr_and_m1_stop_atr_stay_on_separate_series() -> None:
    start = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)
    m5 = _flat(Timeframe.M5, start, 16, half_range="2")
    m1 = _flat(Timeframe.M1, start, 80, half_range="0.5")
    as_of = m5[-1].close_time
    gate = atr_for_timeframe(m5, as_of=as_of, timeframe=Timeframe.M5)
    stop = atr_for_timeframe(m1, as_of=as_of, timeframe=Timeframe.M1)
    assert gate == Decimal("4.00000000")
    assert stop == Decimal("1.00000000")
    assert gate != stop


@pytest.mark.unit
def test_missing_analysis_atr_fails_the_volatility_gate() -> None:
    resolved = resolve_adaptive_thresholds(None, Decimal("4000"), symbol="XAUUSD")
    assert resolved.atr_pct is None
    decision = evaluate_volatility_gate_v2(
        atr_pct=resolved.atr_pct,
        thresholds=resolved,
        trade_quality=90,
        confidence=90,
        structure_score=90,
        liquidity=90,
        momentum=90,
        mtf_alignment=90,
        session=assess_session("london"),
        spread=SpreadAssessment(
            score=100,
            confidence_penalty=0,
            reject=False,
            reason="tight",
        ),
        market_regime="strong_trend",
        symbol="XAUUSD",
    )
    assert decision.passed is False
    assert "atr_pct_missing" in decision.strength_failures
    # The percentage cap is not evaluated without an ATR. The absolute ceiling
    # still applies, and the volatility gate is what fails closed.
    skipped = assess_spread(Decimal("0.20"), atr=None, symbol="XAUUSD-MISSING-ATR")
    assert skipped.reject is False


@pytest.mark.unit
def test_scan_row_keeps_gate_atr_after_quote_context_attaches_the_stop_series() -> None:
    from app.application.services.institutional_multi_asset_scanner import (
        _quote_fields_from_context,
        publish_scored_atr_fields,
    )

    snapshot = SimpleNamespace(
        atr=Decimal("4.80"),
        stop_atr=Decimal("1.90"),
        entry_atr=Decimal("1.90"),
    )
    account = SimpleNamespace(
        atr=Decimal("1.90"),
        bid=None,
        ask=None,
        mid_price=None,
        quote_age_seconds=0,
    )
    ctx = SimpleNamespace(spread=Decimal("0.40"), diagnostics={}, market_data_live=True)
    payload = {"atr_pct": "0.1200"}
    payload.update(_quote_fields_from_context(ctx, account))
    assert payload["atr"] == "1.90"
    publish_scored_atr_fields(payload, snapshot)
    assert payload["atr"] == "4.80"
    assert payload["gate_atr"] == "4.80"
    assert payload["stop_atr"] == "1.90"
    assert payload["atr_pct"] == "0.1200"


@pytest.mark.unit
def test_missing_gate_atr_is_not_filled_from_the_stop_series() -> None:
    from app.application.services.institutional_multi_asset_scanner import (
        publish_scored_atr_fields,
    )

    payload = {"atr": "1.90"}
    publish_scored_atr_fields(
        payload,
        SimpleNamespace(atr=None, stop_atr=Decimal("1.90")),
    )
    assert payload["atr"] is None
    assert payload["gate_atr"] is None
    assert payload["stop_atr"] == "1.90"


def test_live_scorers_pass_snapshot_atr_into_the_percentage_gates() -> None:
    for relative in _LIVE_CALLERS:
        text = (_ROOT / relative).read_text(encoding="utf-8")
        assert "score_gate_atr(" in text
        assert "score_gate_atr(snapshot, account.atr)" not in text
        assert 'score_gate_atr(snapshot, item.get("atr"))' not in text
    decision = (
        _ROOT / "app/application/services/institutional_decision_pipeline.py"
    ).read_text(encoding="utf-8")
    assert "gate_atr=gate_atr" in decision
    assert "atr=gate_atr if self.config.is_scalping() else account.atr" in decision
    pipeline = (_ROOT / "app/domain/institutional_trading/pipeline.py").read_text(
        encoding="utf-8"
    )
    assert pipeline.count("atr_for_timeframe(") >= 2
    scanner = (
        _ROOT / "app/application/services/institutional_multi_asset_scanner.py"
    ).read_text(encoding="utf-8")
    update_at = scanner.index("payload.update(_quote_fields_from_context")
    restore_at = scanner.index("publish_scored_atr_fields(payload, snapshot)")
    assert restore_at > update_at
