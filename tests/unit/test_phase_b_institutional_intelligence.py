"""Phase B institutional performance / execution intelligence — observe-only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.institutional_trading.phase_a.plane import reset_phase_a_plane_for_tests
from app.domain.institutional_trading.phase_b.execution_intel import (
    ExecutionIntelStore,
    score_execution,
)
from app.domain.institutional_trading.phase_b.explain_journal import ExplainJournal
from app.domain.institutional_trading.phase_b.live_vs_research import (
    LiveVsResearchStore,
    classify_parity,
)
from app.domain.institutional_trading.phase_b.mae_mfe import LiveMaeMfeTracker
from app.domain.institutional_trading.phase_b.model_monitor_prep import (
    ModelMonitorPrepStore,
)
from app.domain.institutional_trading.phase_b.plane import (
    get_phase_b_plane,
    reset_phase_b_plane_for_tests,
)
from app.domain.institutional_trading.phase_b.portfolio_incremental import (
    evaluate_incremental_risk,
)
from app.domain.institutional_trading.phase_b.post_trade_review import (
    build_post_trade_review,
)
from app.domain.institutional_trading.phase_b.regime_align import (
    OperationalRegime,
    map_to_operational_regime,
)
from app.domain.institutional_trading.phase_b.research_integrity_prep import (
    ResearchIntegrityPrepStore,
)
from app.domain.institutional_trading.phase_b.small_account_observe import (
    observe_small_account_xau_block,
)
from app.domain.institutional_trading.phase_b.strategy_matrix import StrategyMatrixStore


@pytest.fixture(autouse=True)
def _reset_planes() -> None:
    reset_phase_a_plane_for_tests()
    reset_phase_b_plane_for_tests()
    yield
    reset_phase_b_plane_for_tests()
    reset_phase_a_plane_for_tests()


# --- B.1 MAE/MFE -----------------------------------------------------------


def test_mae_mfe_profitable_long() -> None:
    t = LiveMaeMfeTracker()
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    rec = t.observe_entry(
        trade_id="t1",
        symbol="EURUSD",
        strategy="momentum",
        direction="buy",
        entry_price=1.1000,
        initial_stop=1.0990,
        initial_target=1.1030,
        entry_timestamp=t0.isoformat(),
    )
    assert rec.risk_distance == pytest.approx(0.001)
    t.observe_mark("t1", mark_price=1.0995, now=t0 + timedelta(seconds=10))
    t.observe_mark("t1", mark_price=1.1020, now=t0 + timedelta(seconds=30))
    closed = t.observe_close(
        "t1", exit_price=1.1015, exit_reason="tp", now=t0 + timedelta(seconds=60)
    )
    assert closed is not None
    assert closed.closed is True
    assert closed.final_mae_r == pytest.approx(0.5)
    assert closed.final_mfe_r == pytest.approx(2.0)
    assert closed.realized_r == pytest.approx(1.5)
    assert closed.holding_time_s == pytest.approx(60.0)
    # Open book must not retain closed trade
    assert "t1" not in t.open


def test_mae_mfe_losing_short() -> None:
    t = LiveMaeMfeTracker()
    t.observe_entry(
        trade_id="t2",
        symbol="GBPUSD",
        direction="sell",
        entry_price=1.2500,
        initial_stop=1.2510,
    )
    t.observe_mark("t2", mark_price=1.2505)
    closed = t.observe_close("t2", exit_price=1.2508, exit_reason="sl")
    assert closed is not None
    assert closed.realized_r is not None and closed.realized_r < 0
    assert closed.final_mae_r is not None and closed.final_mae_r > 0


def test_mae_mfe_partial_and_be_and_trail_marks() -> None:
    """Partial / BE / trail are mark updates only — no SL mutation."""
    t = LiveMaeMfeTracker()
    t.observe_entry(
        trade_id="t3",
        symbol="XAUUSD",
        direction="buy",
        entry_price=2000.0,
        initial_stop=1990.0,
    )
    # Adverse then favorable (simulate trail)
    t.observe_mark("t3", mark_price=1995.0)
    t.observe_mark("t3", mark_price=2010.0)
    # BE-like mark near entry
    t.observe_mark("t3", mark_price=2000.5)
    rec = t.open["t3"]
    assert rec.mae_r == pytest.approx(0.5)
    assert rec.mfe_r == pytest.approx(1.0)
    # Still open — no fabricated final values
    assert rec.closed is False
    assert rec.final_mae_r is None
    assert rec.final_mfe_r is None


def test_mae_mfe_missing_quote_marked_incomplete() -> None:
    t = LiveMaeMfeTracker()
    t.observe_entry(
        trade_id="t4",
        symbol="EURUSD",
        direction="buy",
        entry_price=1.1,
        initial_stop=1.09,
    )
    rec = t.observe_mark("t4", mark_price=None)
    assert rec is not None
    assert rec.telemetry_complete is False
    assert rec.incomplete_reason == "missing_quote"


def test_mae_mfe_interrupted_telemetry_no_fabricated_final() -> None:
    t = LiveMaeMfeTracker()
    t.observe_entry(
        trade_id="t5",
        symbol="EURUSD",
        direction="buy",
        entry_price=1.1,
        initial_stop=None,  # incomplete risk
    )
    closed = t.observe_close("t5", exit_price=1.11, exit_reason="manual")
    assert closed is not None
    assert closed.telemetry_complete is False
    assert closed.final_mae_r is None or closed.risk_distance is None


# --- B.2 Portfolio incremental ---------------------------------------------


def test_incremental_isolated_allow() -> None:
    v = evaluate_incremental_risk(
        current_open_risk=1.0,
        new_trade_risk=1.0,
        max_portfolio_risk=10.0,
        symbol="EURUSD",
        existing_symbols=(),
    )
    assert v.decision == "ALLOW"
    assert v.projected_total_risk == pytest.approx(2.0)
    assert "USD" in v.currency_factor_exposure


def test_incremental_correlated_usd_surface() -> None:
    v = evaluate_incremental_risk(
        current_open_risk=3.0,
        new_trade_risk=1.0,
        max_portfolio_risk=20.0,
        correlation_score=0.8,
        symbol="GBPUSD",
        existing_symbols=("EURUSD", "AUDUSD"),
    )
    assert v.currency_factor_exposure.get("USD", 0) >= 3
    assert v.correlation_penalty == pytest.approx(0.8)
    assert v.projected_total_risk is not None
    assert v.projected_total_risk > 4.0  # penalty inflate


def test_incremental_same_symbol_reduce() -> None:
    v = evaluate_incremental_risk(
        current_open_risk=1.0,
        new_trade_risk=1.0,
        max_portfolio_risk=20.0,
        symbol="EURUSD",
        existing_symbols=("EURUSD",),
    )
    assert v.decision == "REDUCE"
    assert v.first_blocking_gate == "SAME_SYMBOL_EXPOSURE"


def test_incremental_over_limit_block() -> None:
    v = evaluate_incremental_risk(
        current_open_risk=9.0,
        new_trade_risk=2.0,
        max_portfolio_risk=10.0,
        symbol="USDJPY",
    )
    assert v.decision == "BLOCK"
    assert v.first_blocking_gate == "PROJECTED_PORTFOLIO_RISK_CEILING"


def test_incremental_hard_blocked_preserves_gate() -> None:
    v = evaluate_incremental_risk(
        hard_blocked=True,
        hard_block_reason="CORRELATED_EXPOSURE_LIMIT",
        symbol="EURUSD",
    )
    assert v.decision == "BLOCK"
    assert v.first_blocking_gate == "CORRELATED_EXPOSURE_LIMIT"


# --- B.3 Execution quality -------------------------------------------------


def test_execution_normal_and_degraded() -> None:
    ok, deg = score_execution(
        slippage=0.1, latency_ms=200, spread=0.2, outcome="success"
    )
    assert ok is not None and ok > 80
    assert deg is False
    bad, deg2 = score_execution(
        slippage=2.0, latency_ms=3000, spread=2.0, outcome="success"
    )
    assert bad is not None and bad < 55
    assert deg2 is True


def test_execution_store_reject_and_ambiguous() -> None:
    store = ExecutionIntelStore()
    store.record(symbol="EURUSD", outcome="reject", broker_retcode=10006)
    store.record(symbol="EURUSD", outcome="ambiguous", fill_latency_ms=5000)
    snap = store.snapshot()
    assert snap["policy_change"] is False
    assert snap["degradation_events"] >= 2


# --- B.4 Regime ------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("strong_trend", OperationalRegime.TRENDING),
        ("range", OperationalRegime.RANGING),
        ("breakout", OperationalRegime.BREAKOUT),
        ("expansion", OperationalRegime.HIGH_VOLATILITY),
        ("compression", OperationalRegime.LOW_VOLATILITY),
        ("liquidity_stress", OperationalRegime.LIQUIDITY_STRESS),
        ("", OperationalRegime.TRANSITION),
    ],
)
def test_regime_map(raw: str, expected: OperationalRegime) -> None:
    op, _ = map_to_operational_regime(raw)
    assert op is expected


# --- B.5 Strategy matrix ---------------------------------------------------


def test_matrix_insufficient_sample_not_best() -> None:
    m = StrategyMatrixStore(min_sample=20)
    for _ in range(3):
        m.record(
            strategy="scalp",
            symbol="EURUSD",
            regime="TRENDING",
            direction="BUY",
            realized_r=2.0,
            win=True,
        )
    snap = m.snapshot()
    cell = snap["cells"][0]
    assert cell["sample_status"] == "INSUFFICIENT_SAMPLE"
    assert cell["expectancy"] is None
    assert cell["win_rate"] is None


def test_matrix_ok_after_min_sample() -> None:
    m = StrategyMatrixStore(min_sample=5)
    for i in range(5):
        m.record(
            strategy="scalp",
            symbol="EURUSD",
            regime="RANGING",
            direction="BUY",
            realized_r=1.0 if i % 2 == 0 else -0.5,
            win=i % 2 == 0,
            mae_r=0.3,
            mfe_r=1.2,
        )
    cell = m.snapshot()["cells"][0]
    assert cell["sample_status"] == "OK"
    assert cell["trade_count"] == 5
    assert cell["expectancy"] is not None


# --- B.6 Live vs research --------------------------------------------------


def test_parity_insufficient_and_states() -> None:
    assert (
        classify_parity(
            research={"trade_count": 100, "avg_R": 1.0},
            live={"trade_count": 3, "avg_R": 2.0},
            min_sample=20,
        )
        == "INSUFFICIENT_SAMPLE"
    )
    assert (
        classify_parity(
            research={"trade_count": 30, "avg_R": 1.0},
            live={"trade_count": 30, "avg_R": 1.1},
            min_sample=20,
        )
        == "LIVE_OUTPERFORMING"
    )
    assert (
        classify_parity(
            research={"trade_count": 30, "avg_R": 1.0},
            live={"trade_count": 30, "avg_R": 0.8},
            min_sample=20,
        )
        == "LIVE_DEGRADING"
    )
    store = LiveVsResearchStore(min_sample=20)
    store.record_research(strategy="s", realized_r=1.0, win=True)
    store.record_live(strategy="s", realized_r=0.5, win=True)
    assert store.snapshot()["comparisons"][0]["state"] == "INSUFFICIENT_SAMPLE"
    assert store.snapshot()["auto_disable"] is False


# --- B.7 Explain journal ---------------------------------------------------


def test_explain_journal_blocked_and_allowed() -> None:
    j = ExplainJournal()
    blocked = j.record(
        symbol="EURUSD",
        strategy="momentum",
        control_state="BLOCK",
        first_blocking_gate="STALE_MARKET_DATA",
        why_signalled="momentum + trend",
        why_ranked="score 91, rank 1/36",
    )
    assert blocked.why_blocked == "STALE_MARKET_DATA"
    assert blocked.why_allowed is None
    allowed = j.record(
        symbol="GBPUSD",
        strategy="momentum",
        control_state="ALLOW",
        first_blocking_gate="UNKNOWN_REASON",
    )
    assert allowed.why_allowed == "all controls passed"
    assert allowed.why_blocked is None
    unknown = j.record(control_state="HALT")
    assert unknown.why_blocked == "UNKNOWN_REASON"
    assert "WHY_SIGNALLED" in unknown.to_dict()


# --- B.8 Post-trade --------------------------------------------------------


def test_post_trade_review_deterministic() -> None:
    a = build_post_trade_review(
        trade_id="1",
        symbol="EURUSD",
        realized_r=1.2,
        mae_r=0.4,
        mfe_r=1.5,
        slippage=0.1,
        exit_reason="tp",
    )
    b = build_post_trade_review(
        trade_id="1",
        symbol="EURUSD",
        realized_r=1.2,
        mae_r=0.4,
        mfe_r=1.5,
        slippage=0.1,
        exit_reason="tp",
        timestamp=a.timestamp,
    )
    assert a.to_dict() == b.to_dict()
    assert a.outcome == "WIN"


# --- B.10 Small account ----------------------------------------------------


def test_small_account_xau_block_surface() -> None:
    snap = observe_small_account_xau_block(
        equity=100.0,
        symbol="XAUUSD_i",
        min_lot_risk_pct=12.0,
        hard_max_risk_pct=5.0,
        blocked_by_min_lot=True,
    )
    assert snap["blocked"] is True
    assert snap["force_trade"] is False
    assert snap["risk_ceiling_preserved"] is True
    assert snap["continue_ranking_other_symbols"] is True
    assert snap["why_blocked"]


# --- B.11 / B.12 Prep stores -----------------------------------------------


def test_research_and_model_prep_no_live_switches() -> None:
    r = ResearchIntegrityPrepStore()
    r.register_trial(
        trial_id="t1",
        strategy="scalp",
        sample_count=50,
        oos_windows=3,
        walk_forward_windows=2,
        parameter_set={"k": 1},
    )
    rs = r.snapshot()
    assert rs["deflated_sharpe_in_live"] is False
    assert rs["pbo_in_live"] is False
    m = ModelMonitorPrepStore()
    m.observe(confidence=0.8, quality=70, signal="BUY", realized_r=0.5)
    ms = m.snapshot()
    assert ms["retrain_in_phase_b"] is False
    assert ms["calibration"] == "PENDING_PHASE_C"


# --- B.13 Integrity / Phase A authority ------------------------------------


def test_phase_b_telemetry_failure_does_not_alter_phase_a() -> None:
    from app.domain.institutional_trading.phase_a import get_phase_a_plane

    pa = get_phase_a_plane()
    before = pa.halt.mode.value
    pb = get_phase_b_plane()
    # Interrupted / duplicate close is a no-op
    assert pb.mae_mfe.observe_close("missing") is None
    pb.mae_mfe.observe_entry(
        trade_id="dup",
        symbol="EURUSD",
        direction="buy",
        entry_price=1.1,
        initial_stop=1.09,
    )
    pb.mae_mfe.observe_close("dup", exit_price=1.11)
    pb.mae_mfe.observe_close("dup", exit_price=1.12)  # duplicate post-trade
    assert pa.halt.mode.value == before
    snap = pb.snapshot()
    assert snap["policy_changes"] is False
    assert snap["mode"] == "OBSERVE_ONLY"


def test_plane_snapshot_structure() -> None:
    pb = get_phase_b_plane()
    pb.observe_regime("strong_trend")
    pb.observe_incremental_risk(
        current_open_risk=1.0, new_trade_risk=1.0, max_portfolio_risk=10.0
    )
    snap = pb.snapshot()
    assert snap["phase"] == "B"
    assert snap["portfolio"] is not None
    assert snap["regime"]["operational_regime"] == "TRENDING"
    assert snap["mae_mfe"] is not None
