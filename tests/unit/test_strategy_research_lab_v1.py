"""Unit tests — QuantForg Strategy Research Lab V1."""

from __future__ import annotations

from decimal import Decimal

from app.domain.strategy_research_lab import StrategyResearchLab
from app.domain.strategy_research_lab.comparison import (
    StrategyRunMetrics,
    compare_strategy_runs,
)
from app.domain.strategy_research_lab.config import StrategyLabConfig
from app.domain.strategy_research_lab.scorecards import (
    ScorecardInput,
    build_strategy_scorecard,
)


def test_registry_lists_strategies() -> None:
    lab = StrategyResearchLab()
    registry = lab.registry.to_dict()
    assert registry["count"] > 0
    assert any(s["key"] == "trend_following" for s in registry["strategies"])


def test_replay_never_invents_bars() -> None:
    lab = StrategyResearchLab()
    empty = lab.replay.load(strategy_key="trend_following", bars=[])
    assert empty["total_bars"] == 0
    assert empty["affects_production_positions"] is False

    loaded = lab.replay.load(
        strategy_key="trend_following",
        bars=[
            {
                "time": "t1",
                "open": "1",
                "high": "2",
                "low": "0.5",
                "close": "1.5",
            }
        ],
    )
    assert loaded["total_bars"] == 1
    stepped = lab.replay.step()
    assert stepped["current"]["close"] == "1.5"


def test_comparison_from_supplied_metrics() -> None:
    out = compare_strategy_runs(
        (
            StrategyRunMetrics(
                "a", "1", Decimal("1.5"), Decimal("1.0"), Decimal("10"), 40
            ),
            StrategyRunMetrics(
                "b", "2", Decimal("0.9"), Decimal("0.2"), Decimal("30"), 10
            ),
        )
    )
    assert out["status"] == "available"
    assert out["leader"]["strategy_key"] == "a"


def test_scorecard_and_validation_report() -> None:
    lab = StrategyResearchLab()
    result = lab.validate(
        {
            "strategy_key": "trend_following",
            "profit_factor": "1.5",
            "sharpe": "0.8",
            "max_drawdown_pct": "10",
            "trade_count": 40,
            "win_rate": "55",
            "stability": "0.7",
        }
    )
    assert result["scorecard"]["passed"] is True
    assert result["report"]["passed"] is True
    assert result["never_submits_orders"] is True


def test_scorecard_unavailable_without_metrics() -> None:
    cfg = StrategyLabConfig()
    card = build_strategy_scorecard(
        cfg, ScorecardInput(strategy_key="x")
    )
    assert card.status == "unavailable"
    assert card.passed is False


def test_parameter_experiments_sandbox() -> None:
    lab = StrategyResearchLab()
    batch = lab.experiments.create_batch(
        strategy_key="trend_following",
        variants=[{"parameters": {"atr": 14}, "label": "base"}],
    )
    assert batch["production_defaults_untouched"] is True
    assert len(batch["variants"]) == 1


def test_version_history() -> None:
    lab = StrategyResearchLab()
    v = lab.versions.record(
        strategy_key="trend_following",
        version="1.0.0",
        parameters={"ema": 20},
        notes="lab",
    )
    assert v["deployed_to_production"] is False
    hist = lab.versions.list_versions("trend_following")
    assert len(hist) == 1


def test_promotion_workflow_and_operator_approval() -> None:
    lab = StrategyResearchLab()
    case = lab.open_promotion(
        {
            "strategy_key": "trend_following",
            "profit_factor": "1.5",
            "sharpe": "0.8",
            "max_drawdown_pct": "10",
            "trade_count": 40,
            "stability": "0.7",
            "validation_passed": True,
        }
    )
    assert case["state"] == "pending_approval"
    assert case["forwarded_to_live_execution"] is False

    decided = lab.approve(
        {
            "case_id": case["case_id"],
            "decision": "approve",
            "operator": "alice",
            "reason": "ok",
        }
    )
    assert decided is not None
    assert decided["state"] == "promoted"
    dash = lab.promotion.dashboard()
    assert dash["isolation"]["never_order_send"] is True


def test_config_hard_isolation() -> None:
    cfg = StrategyLabConfig(
        allows_broker_orders=True,  # type: ignore[arg-type]
        affects_production_positions=True,  # type: ignore[arg-type]
    )
    assert cfg.allows_broker_orders is False
    assert cfg.affects_production_positions is False


def test_service_status_capabilities() -> None:
    from app.application.services.strategy_research_lab import (
        StrategyResearchLabService,
    )

    svc = StrategyResearchLabService()
    status = svc.status()
    assert "strategy-research-lab" in str(status["version"])
    assert status["capabilities"]["strategy_registry"] is True
    assert status["capabilities"]["broker_order_submit"] is False
    assert status["capabilities"]["promotion_dashboard"] is True
