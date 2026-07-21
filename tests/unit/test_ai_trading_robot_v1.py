"""Unit tests — QuantForg AI Trading Robot V1."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.domain.ai_trading_robot.config import RobotV1Config
from app.domain.ai_trading_robot.dynamic_sizing import compute_dynamic_size
from app.domain.ai_trading_robot.filters import (
    NewsEventView,
    evaluate_consecutive_losses,
    evaluate_daily_drawdown,
    evaluate_news_filter,
    evaluate_spread_filter,
)
from app.domain.ai_trading_robot.invariants import (
    assert_no_forbidden_technique,
    reject_averaging_into_loss,
    risk_must_decrease_after_drawdown,
)
from app.domain.ai_trading_robot.journal_intelligence import (
    JournalTradeView,
    analyze_journal,
)
from app.domain.ai_trading_robot.orchestrator import (
    RobotEvaluateInput,
    RobotV1Orchestrator,
)
from app.domain.ai_trading_robot.strategy_health import (
    compute_strategy_performance,
    score_strategy_health,
)


def test_forbidden_techniques_blocked() -> None:
    assert not assert_no_forbidden_technique("martingale").ok
    assert not assert_no_forbidden_technique("grid_recovery").ok
    assert not assert_no_forbidden_technique("average_losing").ok
    assert assert_no_forbidden_technique("smc_bos").ok


def test_risk_decreases_after_drawdown_and_losses() -> None:
    base = Decimal("1.00")
    reduced = risk_must_decrease_after_drawdown(
        base_risk_pct=base,
        current_drawdown_pct=Decimal("2.0"),
        consecutive_losses=2,
        reduction_per_loss=Decimal("0.25"),
        reduction_per_dd_pct=Decimal("0.10"),
        floor_pct=Decimal("0.25"),
    )
    assert reduced < base
    assert reduced == Decimal("0.30")  # 1 - 0.5 - 0.2 = 0.30


def test_never_increase_risk_above_base() -> None:
    out = risk_must_decrease_after_drawdown(
        base_risk_pct=Decimal("1.00"),
        current_drawdown_pct=Decimal("-5"),
        consecutive_losses=-1,
    )
    assert out <= Decimal("1.00")


def test_reject_add_to_loser() -> None:
    check = reject_averaging_into_loss(
        open_side="buy",
        proposed_side="buy",
        open_unrealized_pnl=Decimal("-50"),
    )
    assert not check.ok


def test_dynamic_sizing_reduces_after_losses() -> None:
    cfg = RobotV1Config()
    base = compute_dynamic_size(
        config=cfg,
        equity=Decimal("10000"),
        stop_distance=Decimal("10"),
        current_drawdown_pct=Decimal("0"),
        consecutive_losses=0,
    )
    reduced = compute_dynamic_size(
        config=cfg,
        equity=Decimal("10000"),
        stop_distance=Decimal("10"),
        current_drawdown_pct=Decimal("2"),
        consecutive_losses=3,
    )
    assert reduced.risk_pct < base.risk_pct
    assert reduced.reduced is True
    assert reduced.approved_lots <= base.approved_lots


def test_daily_dd_and_loss_streak_filters() -> None:
    cfg = RobotV1Config(max_daily_drawdown_pct=Decimal("3"), max_consecutive_losses=3)
    assert not evaluate_daily_drawdown(
        cfg, daily_drawdown_pct=Decimal("3.5")
    ).passed
    assert not evaluate_consecutive_losses(
        cfg, consecutive_losses=3, cooldown_active=False
    ).passed
    assert evaluate_consecutive_losses(
        cfg, consecutive_losses=1, cooldown_active=False
    ).passed


def test_spread_filter_fail_closed() -> None:
    cfg = RobotV1Config()
    assert not evaluate_spread_filter(cfg, spread=None).passed
    assert evaluate_spread_filter(cfg, spread=Decimal("0.50")).passed


def test_news_filter_architecture_with_feed() -> None:
    cfg = RobotV1Config(news_filter_enabled=True)
    now = datetime(2026, 7, 21, 14, 0, tzinfo=UTC)

    class _Cal:
        def events_near(self, *, as_of, minutes_before, minutes_after):
            return [
                NewsEventView(
                    code="NFP",
                    title="Non-Farm Payrolls",
                    scheduled_at=now,
                    impact="high",
                )
            ]

    blocked = evaluate_news_filter(cfg, as_of=now, calendar=_Cal())
    assert not blocked.passed
    open_ok = evaluate_news_filter(cfg, as_of=now, calendar=None)
    assert open_ok.passed


def test_strategy_health_auto_pause() -> None:
    cfg = RobotV1Config(auto_pause_health_below=Decimal("35"))
    perf = compute_strategy_performance(
        strategy_id="smc",
        closed_pnls=[Decimal("-10")] * 12,
    )
    health = score_strategy_health(cfg, perf)
    assert health.auto_pause is True
    assert health.status == "pause"


def test_journal_intelligence() -> None:
    intel = analyze_journal(
        [
            JournalTradeView("XAUUSD", "buy", Decimal("20"), session="london"),
            JournalTradeView("XAUUSD", "sell", Decimal("-30"), session="tokyo"),
        ]
    )
    assert intel.trade_count == 2
    assert intel.best_session == "london"


def test_orchestrator_fail_closed_without_risk_safety() -> None:
    robot = RobotV1Orchestrator()
    result = robot.evaluate(
        RobotEvaluateInput(
            side="buy",
            spread=Decimal("0.40"),
            atr=Decimal("8"),
            price=Decimal("4000"),
            equity=Decimal("10000"),
            stop_distance=Decimal("5"),
            confluence=Decimal("80"),
            trade_quality=Decimal("75"),
            structure_bias_aligned=True,
            as_of=datetime(2026, 7, 21, 14, 30, tzinfo=UTC),  # London/NY overlap
            risk_engine_passed=None,
            safety_engine_passed=None,
        )
    )
    assert result.allow_entry is False
    assert any(s.name == "risk_engine" and not s.passed for s in result.pipeline)
    assert any(s.name == "safety_engine" and not s.passed for s in result.pipeline)
    assert result.capabilities["martingale"] is False


def test_orchestrator_allows_only_when_risk_safety_pass() -> None:
    robot = RobotV1Orchestrator()
    result = robot.evaluate(
        RobotEvaluateInput(
            side="buy",
            spread=Decimal("0.40"),
            atr=Decimal("8"),
            price=Decimal("4000"),
            equity=Decimal("10000"),
            stop_distance=Decimal("5"),
            confluence=Decimal("80"),
            trade_quality=Decimal("75"),
            structure_bias_aligned=True,
            as_of=datetime(2026, 7, 21, 14, 30, tzinfo=UTC),
            risk_engine_passed=True,
            safety_engine_passed=True,
        )
    )
    assert result.allow_entry is True
    assert result.sizing.approved_lots > 0
    assert result.pipeline[-1].passed is False  # execution never claimed


def test_orchestrator_blocks_martingale_technique() -> None:
    robot = RobotV1Orchestrator()
    result = robot.evaluate(
        RobotEvaluateInput(
            side="buy",
            technique="martingale",
            spread=Decimal("0.40"),
            atr=Decimal("8"),
            price=Decimal("4000"),
            risk_engine_passed=True,
            safety_engine_passed=True,
            as_of=datetime(2026, 7, 21, 14, 30, tzinfo=UTC),
        )
    )
    assert result.allow_entry is False


def test_config_hard_locks_forbidden_flags() -> None:
    cfg = RobotV1Config(
        allow_martingale=True,  # type: ignore[arg-type]
        allow_grid=True,  # type: ignore[arg-type]
        allow_average_losers=True,  # type: ignore[arg-type]
    )
    assert cfg.allow_martingale is False
    assert cfg.allow_grid is False
    assert cfg.allow_average_losers is False


def test_service_status_and_evaluate() -> None:
    from app.application.services.ai_trading_robot import AiTradingRobotService

    svc = AiTradingRobotService()
    status = svc.status()
    assert status["version"].startswith("ai-robot")
    assert status["capabilities"]["dynamic_position_sizing"] is True
    out = svc.evaluate(
        {
            "side": "buy",
            "spread": "0.4",
            "atr": "8",
            "price": "4000",
            "equity": "10000",
            "stop_distance": "5",
            "confluence": "80",
            "trade_quality": "70",
            "risk_engine_passed": True,
            "safety_engine_passed": True,
        }
    )
    assert "pipeline" in out
    assert out["capabilities"]["grid"] is False
