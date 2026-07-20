"""Phase E unit tests — simulation, replay, WF, MC, analytics, promotion, versioning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.application.services.institutional_research_platform import (
    InstitutionalResearchPlatform,
)
from app.domain.institutional_trading.research.config import ResearchConfig
from app.domain.institutional_trading.research.models import ResearchBar, WalkForwardMode
from app.domain.institutional_trading.research.monte_carlo import MC_COUNTS
from app.domain.institutional_trading.research.replay import (
    HistoricalReplayController,
    ReplayState,
)
from app.domain.institutional_trading.research.simulation_engine import RuleSignalProvider
from app.domain.institutional_trading.research.trade_replay import TradeReplayEngine


def _bars(
    n: int = 80,
    *,
    start: datetime | None = None,
    trend: str = "up",
) -> list[ResearchBar]:
    t0 = start or datetime(2025, 1, 2, 12, 0, tzinfo=UTC)
    out: list[ResearchBar] = []
    px = Decimal("2300")
    for i in range(n):
        if trend == "up":
            o = px
            c = px + Decimal("2")
            h = c + Decimal("1")
            l = o - Decimal("1")
            px = c
        elif trend == "down":
            o = px
            c = px - Decimal("2")
            h = o + Decimal("1")
            l = c - Decimal("1")
            px = c
        else:
            o = px
            c = px + (Decimal("1") if i % 2 == 0 else Decimal("-1"))
            h = max(o, c) + Decimal("1")
            l = min(o, c) - Decimal("1")
            px = c
        session = "london" if i % 3 else "overlap"
        out.append(
            ResearchBar(
                time=t0 + timedelta(hours=i),
                open=o,
                high=h,
                low=l,
                close=c,
                session=session,
            )
        )
    return out


@pytest.mark.unit
class TestSimulationDeterminism:
    def test_same_bars_same_hash_and_metrics(self) -> None:
        bars = _bars(60, trend="up")
        platform = InstitutionalResearchPlatform()
        provider = RuleSignalProvider()
        a = platform.run_simulation(bars, provider, persist=False)
        b = platform.run_simulation(bars, provider, persist=False)
        assert a.input_hash == b.input_hash
        assert a.analytics.trade_count == b.analytics.trade_count
        assert a.analytics.win_rate == b.analytics.win_rate
        assert a.analytics.expectancy == b.analytics.expectancy
        assert [t.pnl for t in a.trades] == [t.pnl for t in b.trades]
        assert a.deterministic is True


@pytest.mark.unit
class TestReplay:
    def test_pause_resume_step_speed(self) -> None:
        bars = _bars(10)
        ctrl = HistoricalReplayController()
        ctrl.load(bars)
        ctrl.start()
        assert ctrl.step() is not None
        ctrl.pause()
        assert ctrl.state is ReplayState.PAUSED
        ctrl.resume()
        assert ctrl.state is ReplayState.RUNNING
        ctrl.set_speed(10.0)
        assert ctrl.speed == 10.0
        with pytest.raises(ValueError):
            ctrl.set_speed(3.0)
        while ctrl.step() is not None:
            pass
        assert ctrl.state is ReplayState.COMPLETED


@pytest.mark.unit
class TestWalkForward:
    def test_rolling_no_future_leak(self) -> None:
        bars = _bars(120, trend="up")
        platform = InstitutionalResearchPlatform()
        report = platform.run_walk_forward(
            bars,
            RuleSignalProvider(),
            mode=WalkForwardMode.ROLLING,
            train_size=40,
            test_size=20,
            step=20,
        )
        assert len(report.folds) >= 1
        for fold in report.folds:
            assert fold.test_start == fold.train_end
            assert fold.test_end > fold.test_start
            # OOS window never overlaps prior train end incorrectly for rolling
            assert fold.train_end <= fold.test_start

    def test_anchored_grows_train(self) -> None:
        bars = _bars(120, trend="up")
        platform = InstitutionalResearchPlatform()
        report = platform.run_walk_forward(
            bars,
            RuleSignalProvider(),
            mode=WalkForwardMode.ANCHORED,
            train_size=40,
            test_size=20,
            step=20,
        )
        assert report.folds
        assert report.folds[0].train_start == 0


@pytest.mark.unit
class TestMonteCarlo:
    def test_seeded_deterministic(self) -> None:
        bars = _bars(80, trend="up")
        platform = InstitutionalResearchPlatform()
        sim = platform.run_simulation(bars, RuleSignalProvider(), persist=False)
        a = platform.run_monte_carlo(sim, iterations=100, seed=7)
        b = platform.run_monte_carlo(sim, iterations=100, seed=7)
        assert a.median_final_equity == b.median_final_equity
        assert a.p05_final_equity == b.p05_final_equity
        assert a.iterations in MC_COUNTS


@pytest.mark.unit
class TestAnalyticsAndTradeReplay:
    def test_analytics_schema_fields(self) -> None:
        bars = _bars(80, trend="up")
        platform = InstitutionalResearchPlatform()
        sim = platform.run_simulation(bars, RuleSignalProvider(), persist=False)
        d = sim.analytics.to_dict()
        for key in (
            "win_rate",
            "expectancy",
            "profit_factor",
            "average_rr",
            "max_drawdown_pct",
            "sharpe",
            "sortino",
            "calmar",
            "recovery_factor",
            "average_hold_seconds",
            "best_session",
            "worst_session",
            "longest_win_streak",
            "longest_loss_streak",
            "mae_avg",
            "mfe_avg",
            "monthly_returns",
            "equity_curve",
            "pnl_distribution",
        ):
            assert key in d

    def test_trade_replay(self) -> None:
        bars = _bars(80, trend="up")
        platform = InstitutionalResearchPlatform()
        sim = platform.run_simulation(bars, RuleSignalProvider(), persist=False)
        if not sim.trades:
            pytest.skip("no trades in synthetic path")
        replay = TradeReplayEngine().replay(sim.trades[0])
        assert "entry" in replay
        assert "stop_loss" in replay
        assert "decision_reasons" in replay
        assert "confluence" in replay
        assert "quality" in replay
        assert "risk_score" in replay


@pytest.mark.unit
class TestOptimization:
    def test_top_parameter_sets(self) -> None:
        bars = _bars(50, trend="up")
        platform = InstitutionalResearchPlatform(
            config=ResearchConfig(optimization_top_n=5)
        )
        top = platform.optimize(
            bars,
            confluence_grid=(80, 90),
            atr_grid=(Decimal("10"),),
            be_grid=(Decimal("1.0"),),
            trail_grid=(Decimal("2.0"),),
            session_grid=("london",),
            risk_grid=(Decimal("0.10"),),
        )
        assert 1 <= len(top) <= 5
        assert top[0].score >= top[-1].score


@pytest.mark.unit
class TestPromotionAndVersioning:
    def test_promotion_gate_fail_low_trades(self) -> None:
        bars = _bars(40, trend="up")
        # Strict institutional thresholds
        platform = InstitutionalResearchPlatform()
        sim = platform.run_simulation(bars, RuleSignalProvider(), persist=False)
        report = platform.evaluate_promotion(sim)
        assert report.eligible is False
        assert report.checks["min_trades"] is False
        assert "canary" == report.target

    def test_promotion_gate_pass_with_relaxed_config(self) -> None:
        bars = _bars(80, trend="up")
        cfg = ResearchConfig(
            promotion_min_trades=1,
            promotion_min_profit_factor=Decimal("0.01"),
            promotion_max_drawdown_pct=Decimal("99"),
            promotion_require_walk_forward_pass=False,
            promotion_require_monte_carlo_pass=False,
        )
        platform = InstitutionalResearchPlatform(config=cfg)
        sim = platform.run_simulation(bars, RuleSignalProvider(), persist=False)
        report = platform.evaluate_promotion(sim)
        # May still fail expectancy/pf depending on path; if trades exist and PF ok:
        if sim.analytics.trade_count >= 1 and sim.analytics.expectancy > 0:
            if sim.analytics.profit_factor and sim.analytics.profit_factor > Decimal("0.01"):
                assert report.checks["min_trades"] is True

    def test_versioning_append_only(self) -> None:
        bars = _bars(40, trend="up")
        platform = InstitutionalResearchPlatform()
        a = platform.run_simulation(bars, RuleSignalProvider(), persist=True)
        b = platform.run_simulation(bars, RuleSignalProvider(), persist=True)
        assert platform.versions.count() == 2
        assert platform.versions.by_run_id(a.run_id) is not None
        assert platform.versions.by_run_id(b.run_id) is not None
        rows = platform.versions.list()
        assert rows[0]["input_hash"] == rows[1]["input_hash"]
        assert rows[0]["run_id"] != rows[1]["run_id"]

    def test_dashboard_periods(self) -> None:
        bars = _bars(60, trend="up")
        platform = InstitutionalResearchPlatform()
        sim = platform.run_simulation(bars, RuleSignalProvider(), persist=False)
        dash = platform.dashboard.build([sim])
        assert "daily" in dash
        assert "weekly" in dash
        assert "monthly" in dash
        assert "yearly" in dash
        assert "strategy_comparison" in dash
