"""Unit tests — Research Platform v10."""

from __future__ import annotations

import pytest

from app.domain.institutional_trading.research_platform.audit import AuditTrailStore
from app.domain.institutional_trading.research_platform.backtesting import (
    compute_metrics,
    run_backtest_suite,
)
from app.domain.institutional_trading.research_platform.config import (
    DEFAULT_RESEARCH_CONFIG,
)
from app.domain.institutional_trading.research_platform.experiments import (
    ExperimentStore,
)
from app.domain.institutional_trading.research_platform.optimization import (
    OptimizationStudio,
)
from app.domain.institutional_trading.research_platform.promotion import (
    PromotionWorkflow,
    next_stage,
)
from app.domain.institutional_trading.research_platform.reporting import (
    report_to_csv,
)


@pytest.mark.unit
def test_research_isolated_and_no_auto_promote() -> None:
    assert DEFAULT_RESEARCH_CONFIG.research_isolated_from_live is True
    assert DEFAULT_RESEARCH_CONFIG.auto_promote_to_production is False
    assert DEFAULT_RESEARCH_CONFIG.auto_apply_optimizations is False


@pytest.mark.unit
def test_experiment_lifecycle(tmp_path) -> None:
    store = ExperimentStore()
    store._path = tmp_path / "exp.json"
    exp = store.create(
        name="ATR study",
        description="test ATR mult",
        author="analyst",
        sample_size=100,
        success_criteria="PF > 1.2",
        status="Draft",
    )
    assert exp.status == "Draft"
    updated = store.set_status(exp.id, "Running")
    assert updated is not None and updated.status == "Running"
    store.attach_results(exp.id, {"win_rate": 55})
    assert store.summary()["by_status"]["Running"] >= 1


@pytest.mark.unit
def test_backtesting_metrics_and_suite() -> None:
    trades = [
        {"pnl": 10, "rr": 2, "win": True},
        {"pnl": -5, "rr": 1, "win": False},
        {"pnl": 8, "rr": 1.5, "win": True},
        {"pnl": -4, "rr": 1, "win": False},
        {"pnl": 12, "rr": 2.2, "win": True},
    ]
    m = compute_metrics(trades)
    assert m["trades"] == 5
    assert m["win_rate"] == 60.0
    assert m["max_consecutive_losses"] >= 1
    suite = run_backtest_suite(trades, strategy_id="unit_test", sync_live_compare=False)
    assert "historical" in suite
    assert "walk_forward" in suite
    assert "out_of_sample" in suite
    assert suite["affects_production"] is False


@pytest.mark.unit
def test_optimization_never_applied(tmp_path) -> None:
    studio = OptimizationStudio()
    studio._path = tmp_path / "opt.json"
    run = studio.record_run(
        author="quant",
        target="confidence_threshold",
        search_space={"confidence_threshold": [70, 75, 80]},
        candidates=[
            {"params": {"confidence_threshold": 70}, "metrics": {"win_rate": 50, "profit_factor": 1.1, "drawdown": 5, "sharpe": 0.5}},
            {"params": {"confidence_threshold": 80}, "metrics": {"win_rate": 58, "profit_factor": 1.4, "drawdown": 4, "sharpe": 0.8}},
        ],
    )
    assert run.applied is False
    assert run.best_params.get("confidence_threshold") == 80
    assert all(r["applied"] is False for r in studio.queue())


@pytest.mark.unit
def test_audit_trail_records_change(tmp_path) -> None:
    trail = AuditTrailStore()
    trail._path = tmp_path / "audit.jsonl"
    ev = trail.record(
        user="ops@quantforg.com",
        category="risk_settings",
        key="max_daily_loss_pct",
        previous_value="3.0",
        new_value="2.5",
        reason="tighten",
    )
    assert ev.previous_value == "3.0"
    assert trail.recent(limit=1)[0]["key"] == "max_daily_loss_pct"


@pytest.mark.unit
def test_audit_redacts_secrets(tmp_path) -> None:
    trail = AuditTrailStore()
    trail._path = tmp_path / "audit2.jsonl"
    ev = trail.record(
        user="ops",
        category="secrets",
        key="api_key",
        previous_value="super-secret",
        new_value="new-secret",
        reason="rotate",
    )
    assert ev.previous_value == "[redacted]"
    assert ev.new_value == "[redacted]"


@pytest.mark.unit
def test_promotion_requires_explicit_approval(tmp_path) -> None:
    assert next_stage("Development") == "Research"
    assert next_stage("Limited Live") == "Production"
    wf = PromotionWorkflow()
    wf._path = tmp_path / "promo.json"
    req = wf.request(
        artifact_type="model",
        artifact_id="m1",
        from_stage="Demo",
        requested_by="analyst",
        reason="promote after evidence",
    )
    assert req.status == "pending"
    assert req.to_stage == "Limited Live"
    decided = wf.decide(req.id, approved=True, approved_by="owner", reason="ok")
    assert decided is not None and decided.status == "approved"
    assert len(wf.pending()) == 0


@pytest.mark.unit
def test_report_csv_export() -> None:
    report = {
        "period": "daily",
        "sections": {"portfolio_performance": {"daily_return_pct": 0.5}},
    }
    csv_text = report_to_csv(report)
    assert "portfolio_performance" in csv_text
    assert "daily_return_pct" in csv_text


@pytest.mark.unit
def test_research_dashboard_shape() -> None:
    from app.application.services.research_platform import (
        build_research_platform_dashboard,
    )

    dash = build_research_platform_dashboard()
    assert dash["version"].startswith("research-platform-v10")
    assert dash["safeguards"]["auto_promote_to_production"] is False
    assert "guidance" in dash
    for key in (
        "active_experiments",
        "approved_models",
        "pending_reviews",
        "optimization_queue",
        "release_history",
        "audit_trail",
        "continuous_improvement",
    ):
        assert key in dash
