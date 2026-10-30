"""Scalping analysis must use the active ITE configuration.

The shared quality evaluator stays. These tests lock the configuration that
reaches it, and they lock the owner gates that still run after a score.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.application.services.ai_scalping_mode import apply_trading_mode_to_runtime
from app.application.services.institutional_ite_runtime import InstitutionalIteRuntime
from app.application.services.institutional_multi_asset_scanner import (
    score_symbol_for_scan,
    score_universe_with_budget,
)
from app.application.services.ite_cycle_market_context import (
    IteCycleMarketContext,
    begin_cycle_market_snapshot,
    build_ite_cycle_market_context,
    end_cycle_market_snapshot,
)
from app.application.services.research_universe_scanner import (
    _score_one_research_symbol,
)
from app.domain.entities.mt5 import MT5AccountInfo
from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
    resolve_adaptive_thresholds,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    scalping_ite_config,
)
from app.domain.institutional_trading.ai_scalping.direction import DirectionDecision
from app.domain.institutional_trading.ai_scalping.quality_gates import (
    evaluate_quality_gates,
)
from app.domain.institutional_trading.ai_scalping.session_intelligence import (
    assess_session,
)
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    SpreadAssessment,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.operations.models import OpsExecutionMode
from app.domain.institutional_trading.owner_live_limits import (
    OWNER_MIN_REWARD_RISK,
    OWNER_MIN_TRADE_QUALITY,
    daily_loss_exceeded,
    evaluate_owner_entry,
    max_aggregate_risk_usd,
    max_planned_risk_usd,
)
from app.domain.institutional_trading.phase_a.kill_state import (
    DurableHaltController,
    HaltMode,
)
from app.domain.institutional_trading.phase_a.market_data_firewall import (
    evaluate_market_data_firewall,
)
from app.domain.institutional_trading.pipeline import InstitutionalAnalysisPipeline
from app.domain.institutional_trading.ports import MultiTimeframeBarStore
from app.domain.institutional_trading.runtime_policy import (
    reset_runtime_policy,
    use_runtime_policy,
)
from app.domain.institutional_trading.session_filter import SessionFilter
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe
from services.mt5_gateway.order_guard import (
    ClientOrderIdRegistry,
    OrderGuardRejected,
    enforce_order_guard,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _series(
    *,
    tf: Timeframe,
    n: int = 40,
    start: datetime,
    step_minutes: int,
) -> list[Candle]:
    out: list[Candle] = []
    price = 2300.0
    for i in range(n):
        open_time = start + timedelta(minutes=step_minutes * i)
        close_time = open_time + timedelta(minutes=step_minutes)
        drift = (i % 7) - 3
        o = price
        high = price + 1.5 + abs(drift) * 0.2
        low = price - 1.2 - abs(drift) * 0.1
        close = price + 0.4 * (1 if drift >= 0 else -1)
        out.append(
            Candle.create(
                symbol_code="XAUUSD",
                timeframe=tf,
                open_time=open_time,
                close_time=close_time,
                open=f"{o:.2f}",
                high=f"{high:.2f}",
                low=f"{low:.2f}",
                close=f"{close:.2f}",
                volume="1",
            )
        )
        price = float(close)
    return out


def _scalp_store(start: datetime) -> MultiTimeframeBarStore:
    store = MultiTimeframeBarStore()
    store.set_bars(Timeframe.H1, _series(tf=Timeframe.H1, start=start, step_minutes=60))
    store.set_bars(
        Timeframe.M15, _series(tf=Timeframe.M15, start=start, step_minutes=15)
    )
    store.set_bars(Timeframe.M5, _series(tf=Timeframe.M5, start=start, step_minutes=5))
    store.set_bars(Timeframe.M1, _series(tf=Timeframe.M1, start=start, step_minutes=1))
    return store


def _open_times(store: MultiTimeframeBarStore) -> dict[str, tuple[datetime, ...]]:
    return {
        tf.value: tuple(bar.open_time for bar in bars)
        for tf, bars in store.as_mapping().items()
    }


def _gates(trade_quality: int, expected_rr: Decimal = Decimal("2.0")):
    thresholds = resolve_adaptive_thresholds(
        atr=Decimal("5"), mid=Decimal("2400"), config=DEFAULT_AI_SCALPING_CONFIG
    )
    return evaluate_quality_gates(
        direction=DirectionDecision(
            direction=TradeDirection.BUY,
            buy_score=80,
            sell_score=20,
            reasons=("test",),
            structure_score=80,
            factors={},
        ),
        momentum=70,
        liquidity=70,
        structure_score=80,
        session=assess_session("london"),
        spread=SpreadAssessment(
            score=100, reject=False, confidence_penalty=0, reason="tight"
        ),
        atr_pct=Decimal("0.8"),
        confidence=90,
        trade_quality=trade_quality,
        expected_rr=expected_rr,
        thresholds=thresholds,
        config=DEFAULT_AI_SCALPING_CONFIG,
        pa_confluence=None,
    )


def _entry(**overrides: object) -> list[str]:
    payload: dict[str, object] = {
        "symbol": "XAUUSD",
        "side": "BUY",
        "volume": Decimal("0.01"),
        "entry": Decimal("100"),
        "stop_loss": Decimal("98"),
        "take_profit": Decimal("103.30"),
        "spread": Decimal("0.20"),
        "contract_size": Decimal("100"),
        "equity": Decimal("1000"),
        "now": datetime(2026, 10, 27, 14, 0, tzinfo=UTC),
        "commission": Decimal("0"),
    }
    payload.update(overrides)
    return evaluate_owner_entry(**payload)  # type: ignore[arg-type]


def _runtime(config: object) -> InstitutionalIteRuntime:
    runtime = InstitutionalIteRuntime(
        plane=MagicMock(),
        reliability=MagicMock(),
        probes=MagicMock(),
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=MagicMock(),
    )
    runtime.plane.mode = OpsExecutionMode.LIVE
    runtime.plane.auto_trading_run_state = "running"
    runtime.probes.last_health_payload = None
    runtime.probes.mt5_adapter = None
    runtime.position_management.engine._positions = {}
    runtime.decision_pipeline.config = config  # type: ignore[assignment]
    runtime.tick_health = lambda: {}  # type: ignore[method-assign]
    runtime._protect_open_positions = lambda **_k: None  # type: ignore[method-assign]
    return runtime


def _ready_adapter() -> MagicMock:
    adapter = MagicMock()
    adapter.client = SimpleNamespace(is_connected=True, session_mode="attached")
    adapter.list_symbols.return_value = [
        SimpleNamespace(code="XAUUSD_i", description="Gold", digits=3)
    ]

    def _bars(_symbol, tf, _start, count):
        base = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
        step = {
            Timeframe.H4: 240,
            Timeframe.H1: 60,
            Timeframe.M15: 15,
            Timeframe.M5: 5,
            Timeframe.M1: 1,
        }[tf]
        rows = []
        for i in range(count):
            open_time = base + timedelta(minutes=step * i)
            price = Decimal("2300") + Decimal(i)
            rows.append(
                SimpleNamespace(
                    symbol="XAUUSD",
                    timeframe=tf,
                    open_time=open_time,
                    open=price,
                    high=price + Decimal("1"),
                    low=price - Decimal("1"),
                    close=price + Decimal("0.4"),
                    tick_volume=10,
                    real_volume=Decimal("1"),
                )
            )
        return rows

    adapter.copy_rates_from_pos.side_effect = _bars
    adapter.latest_tick.return_value = SimpleNamespace(
        bid=Decimal("2300"),
        ask=Decimal("2300.30"),
        mid=Decimal("2300.15"),
        volume=Decimal("1"),
        timestamp=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
    )
    adapter.account_info.return_value = MT5AccountInfo(
        login=1,
        name="t",
        server="s",
        equity=Decimal("10000"),
        balance=Decimal("10000"),
        free_margin=Decimal("10000"),
    )
    adapter.list_positions.return_value = []
    adapter.history_deals = None
    return adapter


class _SpyAnalysis:
    seen: ClassVar[list[object]] = []
    bars: ClassVar[list[dict]] = []

    def __init__(self, config=DEFAULT_ITE_CONFIG) -> None:
        self.config = config
        _SpyAnalysis.seen.append(config)

    async def analyze_bars(self, bars_by_tf, **kwargs):
        _SpyAnalysis.bars.append(
            {
                tf.value: tuple(getattr(bar, "open_time", None) for bar in candles)
                for tf, candles in bars_by_tf.items()
            }
        )
        _SpyAnalysis.bars[-1]["as_of"] = kwargs.get("as_of")  # type: ignore[index]
        return SimpleNamespace(
            symbol="XAUUSD",
            atr=Decimal("1"),
            spread=Decimal("0.30"),
            session=SimpleNamespace(
                session=SimpleNamespace(value="london"), allowed=True
            ),
        )


@pytest.fixture
def quiet_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.institutional_trading.production_validation_mode.observe.begin_validation",
        lambda **_k: None,
    )
    monkeypatch.setattr(
        "app.domain.institutional_trading.production_validation_mode.observe.finalize",
        lambda **_k: None,
    )
    monkeypatch.setattr(
        "app.domain.institutional_trading.production_validation_mode.observe.stage",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "app.domain.institutional_trading.production_validation_mode.begin_validation",
        lambda **_k: None,
    )
    monkeypatch.setattr(
        "app.domain.institutional_trading.production_validation_mode.finalize",
        lambda **_k: None,
    )
    monkeypatch.setattr(
        "app.domain.institutional_trading.production_validation_mode.stage",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "app.application.services.auto_trading_continuity.ensure_auto_trading_running",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "app.application.services.telegram_dispatcher.notify_robot_started",
        lambda **_k: None,
    )
    monkeypatch.setattr(
        "app.application.services.telegram_dispatcher.notify_robot_stopped",
        lambda **_k: None,
    )


@pytest.mark.asyncio
async def test_scalping_config_reaches_the_analysis_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.domain.institutional_trading.ai_scalping.universe_discovery as ud

    monkeypatch.setattr(ud, "_CATALOGUE_CACHE", None)
    _SpyAnalysis.seen = []
    _SpyAnalysis.bars = []
    monkeypatch.setattr(
        "app.application.services.ite_cycle_market_context.InstitutionalTradingAnalysisService",
        _SpyAnalysis,
    )
    scalp = scalping_ite_config()
    ctx = await build_ite_cycle_market_context(_ready_adapter(), ite_config=scalp)
    assert ctx.ok is True
    assert _SpyAnalysis.seen == [scalp]
    assert ctx.diagnostics["analysis_trading_mode"] == "scalping"
    assert ctx.diagnostics["analysis_primary_timeframe"] == "M15"
    assert ctx.diagnostics["analysis_timeframes"] == ["H1", "M15", "M5", "M1"]
    assert ctx.diagnostics["analysis_requires_h4"] is False
    loaded = _SpyAnalysis.bars[0]
    for tf in ("H1", "M15", "M5", "M1"):
        stamps = loaded[tf]
        assert stamps == tuple(sorted(stamps))
        assert len(stamps) == len(set(stamps))
        assert stamps
    # Optional H4 bars may be fetched. They are not an analysis requirement.
    h4 = loaded.get("H4") or ()
    if h4:
        assert h4 == tuple(sorted(set(h4)))


@pytest.mark.asyncio
async def test_omitted_config_keeps_the_swing_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.domain.institutional_trading.ai_scalping.universe_discovery as ud

    monkeypatch.setattr(ud, "_CATALOGUE_CACHE", None)
    _SpyAnalysis.seen = []
    monkeypatch.setattr(
        "app.application.services.ite_cycle_market_context.InstitutionalTradingAnalysisService",
        _SpyAnalysis,
    )
    ctx = await build_ite_cycle_market_context(_ready_adapter())
    assert ctx.ok is True
    assert _SpyAnalysis.seen == [DEFAULT_ITE_CONFIG]
    assert ctx.diagnostics["analysis_trading_mode"] == "swing"
    assert ctx.diagnostics["analysis_primary_timeframe"] == "H1"
    assert "H4" in ctx.diagnostics["analysis_timeframes"]
    assert ctx.diagnostics["analysis_requires_h4"] is True


@pytest.mark.asyncio
async def test_same_cycle_does_not_reuse_a_different_strategy_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.domain.institutional_trading.ai_scalping.universe_discovery as ud

    monkeypatch.setattr(ud, "_CATALOGUE_CACHE", None)
    _SpyAnalysis.seen = []
    monkeypatch.setattr(
        "app.application.services.ite_cycle_market_context.InstitutionalTradingAnalysisService",
        _SpyAnalysis,
    )
    scalp = scalping_ite_config()
    begin_cycle_market_snapshot()
    try:
        swing = await build_ite_cycle_market_context(_ready_adapter())
        rebuilt = await build_ite_cycle_market_context(
            _ready_adapter(), ite_config=scalp
        )
        reused = await build_ite_cycle_market_context(
            _ready_adapter(), ite_config=scalping_ite_config()
        )
    finally:
        end_cycle_market_snapshot()
    assert swing.reused is False
    assert rebuilt.reused is False
    assert rebuilt.diagnostics["analysis_trading_mode"] == "scalping"
    assert reused.reused is True
    assert reused.diagnostics["analysis_trading_mode"] == "scalping"
    assert _SpyAnalysis.seen[0] is DEFAULT_ITE_CONFIG
    assert _SpyAnalysis.seen[1] is scalp
    assert len(_SpyAnalysis.seen) == 2


@pytest.mark.asyncio
async def test_scalping_analysis_does_not_require_h4() -> None:
    start = datetime(2026, 3, 10, 14, 0, tzinfo=UTC)
    store = _scalp_store(start)
    before = _open_times(store)
    as_of = datetime(2026, 3, 10, 14, 30, tzinfo=UTC)
    snap = await InstitutionalAnalysisPipeline(
        bars=store, config=scalping_ite_config()
    ).analyze(as_of=as_of, spread=Decimal("0.30"))
    after = _open_times(store)
    assert before == after
    assert set(snap.structure_by_tf.keys()) == {"H1", "M15", "M5", "M1"}
    assert "H4" not in snap.structure_by_tf
    assert snap.primary_structure is not None
    assert snap.primary_structure.timeframe is Timeframe.M15
    assert snap.primary_structure.as_of == as_of
    for stamps in before.values():
        assert stamps == tuple(sorted(set(stamps)))


@pytest.mark.asyncio
async def test_swing_analysis_keeps_h4_primary_h1() -> None:
    start = datetime(2026, 3, 10, 14, 0, tzinfo=UTC)
    store = MultiTimeframeBarStore()
    for tf, step in (
        (Timeframe.H4, 240),
        (Timeframe.H1, 60),
        (Timeframe.M15, 15),
        (Timeframe.M5, 5),
    ):
        store.set_bars(tf, _series(tf=tf, start=start, step_minutes=step))
    before = _open_times(store)
    as_of = datetime(2026, 3, 10, 14, 30, tzinfo=UTC)
    snap = await InstitutionalAnalysisPipeline(
        bars=store, config=DEFAULT_ITE_CONFIG
    ).analyze(as_of=as_of, spread=Decimal("0.30"))
    assert _open_times(store) == before
    assert set(snap.structure_by_tf.keys()) == {"H4", "H1", "M15", "M5"}
    assert snap.primary_structure.timeframe is Timeframe.H1
    assert DEFAULT_ITE_CONFIG.min_trade_quality_score == 80


@pytest.mark.asyncio
async def test_execute_now_passes_the_selected_config(
    monkeypatch: pytest.MonkeyPatch, quiet_validation: None
) -> None:
    scalp = scalping_ite_config()
    runtime = _runtime(scalp)
    seen: list[object] = []

    async def _pick() -> str:
        return "XAUUSD"

    async def _ctx(*_a, **kwargs):
        seen.append(kwargs.get("ite_config"))
        return IteCycleMarketContext(ok=False, reason="unit_stop")

    runtime._pick_executable_symbol_async = _pick  # type: ignore[method-assign]
    monkeypatch.setattr(
        "app.application.services.ite_cycle_market_context.build_ite_cycle_market_context",
        _ctx,
    )
    payload = await runtime.execute_now()
    assert seen == [scalp]
    assert payload["success"] is False


@pytest.mark.asyncio
async def test_execute_now_manage_only_passes_the_selected_config(
    monkeypatch: pytest.MonkeyPatch, quiet_validation: None
) -> None:
    scalp = scalping_ite_config()
    runtime = _runtime(scalp)
    seen: list[object] = []

    async def _pick() -> str:
        return ""

    async def _ctx(*_a, **kwargs):
        seen.append(kwargs.get("ite_config"))
        return IteCycleMarketContext(ok=False, reason="unit_stop")

    runtime._pick_executable_symbol_async = _pick  # type: ignore[method-assign]
    monkeypatch.setattr(
        "app.application.services.ite_cycle_market_context.build_ite_cycle_market_context",
        _ctx,
    )
    await runtime.execute_now()
    assert seen == [scalp]


@pytest.mark.asyncio
async def test_worker_cycle_passes_the_selected_config(
    monkeypatch: pytest.MonkeyPatch, quiet_validation: None
) -> None:
    scalp = scalping_ite_config()
    runtime = _runtime(scalp)
    runtime.interval_seconds = 1.0
    seen: list[object] = []

    async def _pick() -> str:
        return "XAUUSD"

    async def _ctx(*_a, **kwargs):
        seen.append(kwargs.get("ite_config"))
        runtime._stop.set()
        return IteCycleMarketContext(ok=False, reason="unit_stop")

    runtime._pick_executable_symbol_async = _pick  # type: ignore[method-assign]
    monkeypatch.setattr(
        "app.application.services.ite_cycle_market_context.build_ite_cycle_market_context",
        _ctx,
    )
    await runtime.run_forever()
    assert seen == [scalp]
    assert scalp.is_scalping()
    assert Timeframe.H4 not in scalp.analysis_timeframes()


@pytest.mark.asyncio
async def test_swing_worker_passes_the_swing_config(
    monkeypatch: pytest.MonkeyPatch, quiet_validation: None
) -> None:
    runtime = _runtime(DEFAULT_ITE_CONFIG)
    runtime.interval_seconds = 1.0
    seen: list[object] = []

    async def _pick() -> str:
        return "XAUUSD"

    async def _ctx(*_a, **kwargs):
        seen.append(kwargs.get("ite_config"))
        runtime._stop.set()
        return IteCycleMarketContext(ok=False, reason="unit_stop")

    runtime._pick_executable_symbol_async = _pick  # type: ignore[method-assign]
    monkeypatch.setattr(
        "app.application.services.ite_cycle_market_context.build_ite_cycle_market_context",
        _ctx,
    )
    await runtime.run_forever()
    assert seen == [DEFAULT_ITE_CONFIG]


@pytest.mark.asyncio
async def test_multi_asset_scan_uses_the_scalping_profile() -> None:
    seen: list[object] = []

    async def _ctx(*_a, **kwargs):
        seen.append(kwargs.get("ite_config"))
        return IteCycleMarketContext(ok=False, reason="unit_stop")

    import app.application.services.institutional_multi_asset_scanner as scanner

    original = scanner.build_ite_cycle_market_context
    scanner.build_ite_cycle_market_context = _ctx  # type: ignore[assignment]
    try:
        row = await score_symbol_for_scan(MagicMock(), "XAUUSD")
    finally:
        scanner.build_ite_cycle_market_context = original
    assert row["reject"] is True
    cfg = seen[0]
    assert cfg.is_scalping()
    assert cfg.primary_structure_tf is Timeframe.M15
    assert cfg.macro_bias_tf is Timeframe.H1
    assert cfg.entry_confirmation_tf is Timeframe.M5
    assert cfg.execution_management_tf is Timeframe.M1
    assert Timeframe.H4 not in cfg.analysis_timeframes()


@pytest.mark.asyncio
async def test_scan_budget_forwards_the_caller_config() -> None:
    scalp = scalping_ite_config()
    seen: list[object] = []

    async def _score(*_a, **kwargs):
        seen.append(kwargs.get("ite_config"))
        return {
            "symbol": "XAUUSD",
            "reject": True,
            "reject_reason": "unit_stop",
            "direction": "NONE",
            "ai_confidence": 0,
            "trade_quality": 0,
        }

    import app.application.services.institutional_multi_asset_scanner as scanner

    original = scanner.score_symbol_for_scan
    scanner.score_symbol_for_scan = _score  # type: ignore[assignment]
    try:
        rows, _stats = await score_universe_with_budget(
            MagicMock(),
            ["XAUUSD"],
            ite_config=scalp,
            budget_seconds=2,
            per_symbol_timeout=1,
            concurrency=1,
        )
    finally:
        scanner.score_symbol_for_scan = original
    assert rows
    assert seen == [scalp]


@pytest.mark.asyncio
async def test_research_scan_uses_scalping_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[object] = []

    async def _ctx(*_a, **kwargs):
        seen.append(kwargs.get("ite_config"))
        return IteCycleMarketContext(ok=False, reason="unit_stop")

    monkeypatch.setattr(
        "app.application.services.ite_cycle_market_context.build_ite_cycle_market_context",
        _ctx,
    )
    row = await _score_one_research_symbol(MagicMock(), "XAUUSD")
    assert row["forwarded_to_oms"] is False
    assert row["would_submit_order"] is False
    cfg = seen[0]
    assert cfg.is_scalping()
    assert Timeframe.H4 not in cfg.analysis_timeframes()
    assert cfg.primary_structure_tf is Timeframe.M15


def test_quality_below_70_is_still_rejected() -> None:
    assert OWNER_MIN_TRADE_QUALITY == 70
    gates = _gates(69)
    assert gates.passed is False
    assert any(
        r.startswith("OWNER_MIN_TRADE_QUALITY: trade quality 69 < 70")
        for r in gates.hard_rejects
    )


def test_quality_at_or_above_75_does_not_skip_later_gates() -> None:
    gates = _gates(75)
    assert gates.checks["owner_min_trade_quality"] is True
    low_rr = _gates(90, expected_rr=Decimal("0.50"))
    assert low_rr.checks["min_rr"] is False
    assert low_rr.passed is False
    assert any(r.startswith("OWNER_MIN_RR") for r in _entry(take_profit=Decimal("101")))
    assert any(r.startswith("OWNER_MAX_SPREAD") for r in _entry(spread=Decimal("0.46")))
    assert any(r.startswith("OWNER_MAX_LOT") for r in _entry(volume=Decimal("0.02")))
    assert any(r.startswith("OWNER_SL_REQUIRED") for r in _entry(stop_loss=None))
    assert any(r.startswith("OWNER_TP_REQUIRED") for r in _entry(take_profit=None))
    assert any(r.startswith("OWNER_GOLD_ONLY") for r in _entry(symbol="EURUSD"))
    assert any(
        r.startswith("OWNER_SL_RISK")
        for r in _entry(equity=Decimal("100"), stop_loss=Decimal("40"))
    )
    weekend = SessionFilter(
        config=scalping_ite_config(), prefer_utc_classifier=True
    ).evaluate(as_of=datetime(2026, 10, 31, 14, 0, tzinfo=UTC))
    assert weekend.allowed is False
    stale = evaluate_market_data_firewall(
        symbol="XAUUSD",
        bid=1.0,
        ask=1.1,
        quote_age_seconds=500,
        candles_ok=True,
    )
    assert stale.allow_new_entry is False
    assert stale.first_blocking_gate == "STALE_MARKET_DATA"
    missing = evaluate_market_data_firewall(
        symbol="XAUUSD",
        bid=None,
        ask=None,
        quote_age_seconds=0,
    )
    assert missing.allow_new_entry is False
    invalid = evaluate_market_data_firewall(
        symbol="XAUUSD",
        bid=2.0,
        ask=1.0,
        quote_age_seconds=1,
    )
    assert invalid.allow_new_entry is False
    incomplete = evaluate_market_data_firewall(
        symbol="XAUUSD",
        bid=1.0,
        ask=1.1,
        quote_age_seconds=1,
        candles_ok=False,
    )
    assert incomplete.allow_new_entry is False


def test_reward_risk_below_1_50_stays_rejected() -> None:
    assert Decimal("1.50") == OWNER_MIN_REWARD_RISK
    reasons = _entry(take_profit=Decimal("101.40"))
    assert any("1.50" in r for r in reasons)
    assert any(r.startswith("OWNER_MIN_RR") for r in reasons)
    cleared = _entry()
    assert not any(r.startswith("OWNER_MIN_RR") for r in cleared)


def test_loss_drawdown_lot_and_aggregate_caps_cannot_be_loosened() -> None:
    assert daily_loss_exceeded(daily_pnl=Decimal("-20"), base_now=Decimal("80"))
    assert (
        daily_loss_exceeded(daily_pnl=Decimal("-19"), base_now=Decimal("81")) is False
    )
    token = use_runtime_policy(
        {
            "max_drawdown_pct": "10",
            "max_planned_risk_pct": "50",
            "max_aggregate_open_risk_pct": "50",
            "max_lot": "1.00",
            "min_trade_quality": 10,
            "min_reward_risk": "0.50",
        }
    )
    try:
        reasons = _entry(
            equity=Decimal("80"),
            peak_equity=Decimal("100"),
        )
        assert any(r.startswith("OWNER_DRAWDOWN") for r in reasons)
        assert max_planned_risk_usd(Decimal("100")) == Decimal("14.00")
        assert max_aggregate_risk_usd(Decimal("100")) == Decimal("14.00")
    finally:
        reset_runtime_policy(token)
    halt = DurableHaltController()
    assert halt.new_entries_allowed() is True
    halt.set_mode(HaltMode.HALT_NEW_ENTRIES, actor="unit", reason="test")
    assert halt.new_entries_allowed() is False
    assert halt.oms_market_submit_allowed() is False
    with pytest.raises(OrderGuardRejected) as exc:
        enforce_order_guard(
            {
                "symbol": "EURUSD",
                "action": "buy",
                "volume": 0.02,
                "sl": 1.0,
                "tp": 2.0,
                "position": 0,
                "client_order_id": f"cid-{uuid4()}",
            },
            positions_lookup=lambda: [],
            equity=Decimal("1000"),
            quote={"bid": "100", "ask": "100.2"},
            registry=ClientOrderIdRegistry(),
        )
    assert exc.value.code == "GUARD_GOLD_ONLY"


def test_apply_trading_mode_selects_scalping_without_changing_the_floor() -> None:
    runtime = _runtime(DEFAULT_ITE_CONFIG)
    apply_trading_mode_to_runtime(runtime, mode="scalping")
    assert runtime.decision_pipeline.config.is_scalping()
    assert runtime.decision_pipeline.config.primary_structure_tf is Timeframe.M15
    assert Timeframe.H4 not in runtime.decision_pipeline.config.analysis_timeframes()
    assert OWNER_MIN_TRADE_QUALITY == 70
    assert DEFAULT_ITE_CONFIG.trading_mode == "swing"
    assert DEFAULT_ITE_CONFIG.min_trade_quality_score == 80
