"""Phase 8 Quantitative Research Control — unit gates."""

from __future__ import annotations

from app.domain.quantitative_research_control import (
    ISOLATION_FLAGS,
    MODEL_VERSION,
    VALIDATION_STAGES,
)
from app.domain.quantitative_research_control.overview import (
    ai_hypothesize,
    backtest_overview,
    leaderboard,
    optimization_overview,
    run_backtest_compose,
    validate_strategy_spec,
    walkforward_overview,
)
from app.domain.quantitative_research_control.store import (
    reset_research_store_for_tests,
)


def setup_function() -> None:
    reset_research_store_for_tests()


def test_isolation_flags() -> None:
    assert MODEL_VERSION.startswith("phase8-research-")
    assert ISOLATION_FLAGS["research_only"] is True
    assert ISOLATION_FLAGS["never_order_send"] is True
    assert ISOLATION_FLAGS["never_auto_live_deploy"] is True
    assert ISOLATION_FLAGS["never_executes_arbitrary_code"] is True
    assert ISOLATION_FLAGS["never_fabricates_ohlcv"] is True
    assert ISOLATION_FLAGS["backtest_is_not_live"] is True
    assert ISOLATION_FLAGS["approved_is_not_live"] is True
    assert ISOLATION_FLAGS["paper_is_not_live"] is True
    assert len(VALIDATION_STAGES) == 10


def test_incomplete_spec_rejected() -> None:
    out = validate_strategy_spec({"name": "x"})
    assert out["valid"] is False
    assert "entry_rules" in out["missing_fields"]
    assert out["never_executes_arbitrary_code"] is True


def test_ai_hypothesis_not_live_no_profit_claim() -> None:
    out = ai_hypothesize({"family": "trend_following", "symbol": "XAUUSD"})
    assert out["research_artifact"] is True
    assert out["never_auto_live"] is True
    assert out["profitability_claimed"] is False
    assert out["never_order_send"] is True
    assert out.get("order_send") is False


def test_backtest_not_live_not_fabricated() -> None:
    overview = backtest_overview()
    assert overview["backtest_is_not_live"] is True
    assert overview["fabricated"] is False
    assert overview["never_order_send"] is True
    run = run_backtest_compose(
        {"symbol": "XAUUSD", "timeframe": "H1", "actor": "tester"}
    )
    assert run["fabricated"] is False
    assert run["backtest_is_not_live"] is True
    assert run.get("experiment_id")
    assert "order_send" not in str(run.get("actions") or [])


def test_walkforward_holdout_honesty() -> None:
    out = walkforward_overview()
    labels = out.get("labels") or {}
    assert labels.get("holdout") or labels.get("out_of_sample")
    rules = out.get("rules") or {}
    assert rules.get("test_data_not_used_to_tune_before_validation") is True
    assert out["fabricated"] is False


def test_optimization_never_auto_deploy() -> None:
    out = optimization_overview()
    rules = out.get("rules") or {}
    assert rules.get("never_auto_deploy_optimized_params") is True
    assert rules.get("holdout_reserved") is True
    assert out["optimization_is_not_live"] is True


def test_leaderboard_never_profit_only() -> None:
    out = leaderboard(
        rows=[
            {
                "name": "A",
                "profit": 1000,
                "sharpe": 0.1,
                "sample_size": 5,
                "validation_class": "research",
            },
            {
                "name": "B",
                "profit": 10,
                "sharpe": 1.5,
                "sample_size": 100,
                "validation_class": "oos_validated",
            },
        ]
    )
    assert out["never_profit_only"] is True
    rows = out.get("rows") or []
    assert rows
    assert rows[0]["name"] == "B"


def test_approval_material_change_invalidates() -> None:
    store = reset_research_store_for_tests()
    appr = store.create_approval(
        strategy_id="s1",
        strategy_version="1.0.0",
        bound_params={
            "strategy_id": "s1",
            "strategy_version": "1.0.0",
            "parameters_hash": "abc",
            "symbol": "XAUUSD",
        },
        stage="Human Approval",
        actor="owner",
    )
    bad = store.act_on_approval(
        appr["id"],
        action="Approve",
        actor="owner",
        current_params={
            "strategy_id": "s1",
            "strategy_version": "1.0.0",
            "parameters_hash": "CHANGED",
            "symbol": "XAUUSD",
        },
    )
    assert bad is not None
    assert bad.get("ok") is False
    assert bad.get("error") == "material_change"
    assert bad.get("approved_is_not_live") is True


def test_approved_is_not_live() -> None:
    store = reset_research_store_for_tests()
    appr = store.create_approval(
        strategy_id="s1",
        strategy_version="1.0.0",
        bound_params={
            "strategy_id": "s1",
            "strategy_version": "1.0.0",
            "parameters_hash": "abc",
            "symbol": "XAUUSD",
        },
        stage="Human Approval",
        actor="owner",
    )
    ok = store.act_on_approval(
        appr["id"],
        action="Approve",
        actor="owner",
        current_params={
            "strategy_id": "s1",
            "strategy_version": "1.0.0",
            "parameters_hash": "abc",
            "symbol": "XAUUSD",
        },
    )
    assert ok is not None
    assert ok.get("ok") is True
    assert ok.get("status") == "Approved"
    assert ok.get("approved_is_not_live") is True
    assert ok.get("never_auto_live_deploy") is True


def test_never_order_send_in_service_health() -> None:
    from app.application.services import quantitative_research_control as qrc

    h = qrc.health()
    assert h["order_send"] is False
    assert h["never_order_send"] is True
    assert h["never_auto_live_deploy"] is True
