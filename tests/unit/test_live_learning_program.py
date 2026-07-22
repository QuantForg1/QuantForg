"""Unit tests — Live Learning Program."""

from __future__ import annotations

from app.domain.live_learning_program import (
    LiveLearningProgram,
    LlpConfig,
    LlpInput,
)
from app.domain.trading.gold_only import GOLD_SYMBOL


def _trades(n: int) -> list[dict]:
    sessions = ["london", "new_york", "asia", "tokyo"]
    rows = []
    for i in range(n):
        rows.append(
            {
                "id": f"t{i}",
                "entry_context": "setup",
                "exit_context": "target",
                "market_regime": "trend",
                "session": sessions[i % 4],
                "spread": 0.2,
                "volatility": "normal",
                "liquidity": "deep",
                "risk_usage": 0.4,
                "decision_explanation": "approved",
                "execution_latency": 50,
                "result": -5 if i % 3 == 0 else 10,
                "predicted_confidence": 60,
                "win": i % 3 != 0,
                "day_type": "trend",
                "period": "week_a" if i < n // 2 else "week_b",
            }
        )
    return rows


def test_hard_locks_evidence_only() -> None:
    status = LiveLearningProgram().status()
    assert status["symbol"] == GOLD_SYMBOL
    assert status["allow_order_send"] is False
    assert status["allow_auto_tune_parameters"] is False
    assert status["allow_auto_promote_strategies"] is False
    caps = status["capabilities"]
    assert caps["evidence_only"] is True
    assert caps["never_modify_execution_pipeline"] is True
    assert len(status["modules"]) == 10


def test_policies_cannot_unlock() -> None:
    cfg = LlpConfig().update(
        {
            "allow_order_send": True,
            "allow_auto_tune_parameters": True,
            "allow_auto_promote_strategies": True,
        }
    )
    assert cfg.allow_order_send is False
    assert cfg.allow_auto_tune_parameters is False
    assert cfg.allow_auto_promote_strategies is False


def test_empty_observations() -> None:
    out = LiveLearningProgram().evaluate(LlpInput())
    assert out["modules"]["live_observation_collector"]["status"] == "empty"
    assert out["never_order_send"] is True
    assert out["auto_tune_parameters"] is False


def test_full_learning_cycle() -> None:
    out = LiveLearningProgram().evaluate(
        LlpInput(
            completed_trades=_trades(40),
            replay_results={
                "expectancy": 4,
                "win_rate": 58,
                "profit_factor": 1.4,
                "drawdown": 3,
                "trade_count": 40,
                "avg_latency_ms": 5,
            },
            paper_results={
                "expectancy": 3,
                "win_rate": 55,
                "profit_factor": 1.3,
                "drawdown": 3.5,
                "trade_count": 36,
                "avg_latency_ms": 30,
            },
            live_results={
                "expectancy": 2,
                "win_rate": 50,
                "profit_factor": 1.1,
                "drawdown": 5,
                "trade_count": 40,
                "avg_latency_ms": 90,
            },
            operator_feedback=[
                {"tag": "good_setup", "note": "ok", "operator": "a"},
                {"tag": "research_idea", "note": "idea", "operator": "b"},
            ],
            edge_score_series=[
                {"period": "W1", "horizon": "weekly", "edge_score": 50},
                {"period": "W2", "horizon": "weekly", "edge_score": 55},
            ],
            journal_entries=[
                {"day_type": "trend_days", "session": "london"},
                {"day_type": "news_days", "session": "new_york"},
            ],
        )
    )
    assert out["evidence_only"] is True
    assert out["modifies_execution_pipeline"] is False
    assert out["auto_promote_strategies"] is False
    assert out["modules"]["live_observation_collector"]["details"][
        "immutable"
    ] is True
    assert out["modules"]["operator_feedback"]["details"][
        "changes_production"
    ] is False
    assert out["modules"]["research_recommendations"]["details"][
        "recommends_live_changes"
    ] is False
    assert out["modules"]["learning_dashboard"]["status"] == "available"
    assert out["learning_summary"]["observation_count"] == 40
    assert isinstance(out["learning_summary"]["research_backlog"], list)
    assert len(out["learning_summary"]["research_backlog"]) >= 1


def test_feedback_never_auto_applies() -> None:
    out = LiveLearningProgram().evaluate(
        LlpInput(
            operator_feedback=[
                {"tag": "bad_setup", "note": "x"},
                {"tag": "invalid_tag", "note": "ignored"},
            ]
        )
    )
    fb = out["modules"]["operator_feedback"]
    assert fb["details"]["never_auto_applies"] is True
    assert fb["details"]["by_tag"]["bad_setup"] == 1
    assert fb["details"]["by_tag"]["good_setup"] == 0
