"""Unit tests — Institutional AI Scalping v6.1 live execution hardening."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.application.services.ai_scalping_dashboard import build_ai_scalping_dashboard
from app.application.services.ai_scalping_mode import pme_config_for_scalping
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.execution_quality import (
    ExecutionQualityStore,
)
from app.domain.institutional_trading.ai_scalping.live_health import LiveHealthMonitor
from app.domain.institutional_trading.ai_scalping.post_trade_analytics import (
    compute_post_trade_analytics,
    get_post_trade_journal,
)
from app.domain.institutional_trading.ai_scalping.regime import classify_scalping_regime
from app.domain.institutional_trading.ai_scalping.regime_execution import (
    build_regime_execution_profile,
)
from app.domain.institutional_trading.ai_scalping.sizing import calculate_scalping_lots
from app.domain.institutional_trading.ai_scalping.slippage_protection import (
    measure_slippage,
)
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    assess_spread,
)


@pytest.mark.unit
def test_v61_version_preserves_v6_safety() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.version.startswith("ai-scalping-v6")
    assert cfg.risk_per_trade_pct <= Decimal("0.75")
    assert cfg.allow_martingale is False
    assert cfg.allow_grid is False
    assert cfg.min_expected_rr >= Decimal("1.3")
    assert cfg.self_protection_enabled is True
    assert cfg.slippage_protection_enabled is True


@pytest.mark.unit
def test_regime_profile_never_lowers_rr_or_extends_past_max() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    trending = classify_scalping_regime(
        alignment_score=80, atr_pct=Decimal("2.0"), bos=1, volume_expanding=True
    )
    profile = build_regime_execution_profile(
        trending, atr_pct=Decimal("2.0"), config=cfg
    )
    assert profile.volatility == "high"
    assert profile.min_expected_rr >= cfg.min_expected_rr
    assert profile.absolute_max_hold_minutes <= cfg.absolute_max_hold_minutes

    ranging = classify_scalping_regime(
        alignment_score=40, atr_pct=Decimal("0.2"), range_like=True
    )
    rp = build_regime_execution_profile(ranging, atr_pct=Decimal("0.2"), config=cfg)
    assert rp.volatility == "low"
    assert rp.min_expected_rr >= cfg.min_expected_rr
    assert rp.absolute_max_hold_minutes <= cfg.absolute_max_hold_minutes


@pytest.mark.unit
def test_spread_rejects_on_atr_pct() -> None:
    # Absolute max still works
    hard = assess_spread(Decimal("3.00"))
    assert hard.reject is True

    # ATR% gate: spread 1.0 with ATR 5 → 15% of ATR = 0.75 → reject
    atr_reject = assess_spread(Decimal("1.00"), atr=Decimal("5"))
    assert atr_reject.reject is True
    assert "ATR" in atr_reject.reason

    # Tight relative to ATR
    ok = assess_spread(Decimal("0.20"), atr=Decimal("5"))
    assert ok.reject is False


@pytest.mark.unit
def test_slippage_measurement() -> None:
    ok = measure_slippage(
        side="buy",
        requested_price=Decimal("2300"),
        filled_price=Decimal("2300.20"),
        max_slippage=Decimal("0.50"),
        latency_ms=12.5,
    )
    assert ok.exceeded is False
    assert ok.slippage == Decimal("0.20")

    bad = measure_slippage(
        side="buy",
        requested_price=Decimal("2300"),
        filled_price=Decimal("2301.00"),
        max_slippage=Decimal("0.50"),
    )
    assert bad.exceeded is True


@pytest.mark.unit
def test_vol_adjusted_sizing_never_raises_risk() -> None:
    base = calculate_scalping_lots(
        equity=Decimal("10000"),
        stop_distance=Decimal("5"),
        atr=Decimal("5"),
        risk_pct=Decimal("0.50"),
    )
    high = calculate_scalping_lots(
        equity=Decimal("10000"),
        stop_distance=Decimal("5"),
        atr=Decimal("10"),  # atr >= 1.5 * stop → high vol scale
        risk_pct=Decimal("0.50"),
    )
    assert base.valid and high.valid
    assert high.lots <= base.lots
    assert "+high_vol_scale" in high.method


@pytest.mark.unit
def test_execution_quality_rolling_stats() -> None:
    store = ExecutionQualityStore(window=50)
    store.record(outcome="success", latency_ms=10, slippage=0.1)
    store.record(outcome="reject", latency_ms=20, rejection_reason="spread")
    store.record(outcome="success", latency_ms=15, requote=True, partial_fill=True)
    snap = store.snapshot()
    assert snap["samples"] == 3
    assert snap["fill_rate"] == pytest.approx(66.67, rel=1e-2)
    assert snap["reject_rate"] == pytest.approx(33.33, rel=1e-2)
    assert snap["avg_latency_ms"] is not None


@pytest.mark.unit
def test_post_trade_mae_mfe_and_journal() -> None:
    analytics = compute_post_trade_analytics(
        ticket="1",
        direction="buy",
        entry=Decimal("2300"),
        exit_price=Decimal("2310"),
        stop_distance=Decimal("10"),
        mae_price=Decimal("2295"),
        mfe_price=Decimal("2315"),
        opened_at=datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
        closed_at=datetime(2026, 7, 20, 12, 8, tzinfo=UTC),
        spread=Decimal("0.2"),
        slippage=Decimal("0.1"),
        execution_latency_ms=18.0,
        pnl=Decimal("100"),
    )
    assert analytics.r_multiple == Decimal("1.0000")
    assert analytics.mae_r == Decimal("0.5000")
    assert analytics.mfe_r == Decimal("1.5000")
    assert analytics.holding_time_minutes == 8.0
    assert analytics.win is True

    journal = get_post_trade_journal()
    journal.record(analytics)
    perf = journal.performance_snapshot()
    assert perf["trades"] >= 1
    assert perf["average_r"] is not None


@pytest.mark.unit
def test_live_health_pauses_new_entries_only() -> None:
    mon = LiveHealthMonitor(
        reject_burst_threshold=3,
        reject_window_seconds=120,
        max_drawdown_pct=Decimal("3.0"),
    )
    mon.update_dependencies(gateway_ok=False)
    allowed, why = mon.allow_new_entries()
    assert allowed is False
    assert "gateway" in why or "Dependency" in why
    snap = mon.snapshot()
    assert snap["self_protection"]["existing_positions_managed"] is True

    mon.update_dependencies(gateway_ok=True, broker_ok=True, mt5_ok=True, oms_ok=True)
    mon.record_reject()
    mon.record_reject()
    mon.record_reject()
    allowed2, _ = mon.allow_new_entries()
    assert allowed2 is False

    mon.record_drawdown(Decimal("1.0"))
    # Still paused due to reject burst until window clears — force trim by age
    mon._rejects.clear()
    mon._protection.reasons = []
    mon._protection.new_entries_paused = False
    mon.update_dependencies(
        gateway_ok=True,
        broker_ok=True,
        mt5_ok=True,
        oms_ok=True,
        market_data_ok=True,
        latency_ms=50,
    )
    ok, _ = mon.allow_new_entries()
    assert ok is True


@pytest.mark.unit
def test_pme_and_dashboard_v61() -> None:
    pme = pme_config_for_scalping()
    assert "v6.1" in pme.config_version
    dash = build_ai_scalping_dashboard()
    assert dash["version"].startswith("ai-scalping-v6")
    assert "performance_metrics" in dash
    assert "execution_quality" in dash
    assert "live_health" in dash
    assert dash["safeguards"]["allow_martingale"] is False
    metrics = dash["performance_metrics"]
    for key in (
        "win_rate",
        "average_r",
        "profit_factor",
        "average_hold_time",
        "average_latency",
        "execution_success_rate",
    ):
        assert key in metrics
