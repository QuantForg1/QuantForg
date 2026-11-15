"""Application facade — Phase 8 Quantitative Research Control."""

from __future__ import annotations

from typing import Any

from app.domain.quantitative_research_control import MODEL_VERSION, isolation_payload
from app.domain.quantitative_research_control.overview import (
    ai_hypothesize,
    backtest_overview,
    build_hub_summary,
    data_overview,
    leaderboard,
    montecarlo_overview,
    optimization_overview,
    paper_overview,
    robustness_overview,
    run_backtest_compose,
    run_montecarlo_compose,
    run_optimization_compose,
    run_walkforward_compose,
    strategy_templates,
    validate_strategy_spec,
    validation_pipeline,
    walkforward_overview,
)
from app.domain.quantitative_research_control.store import get_research_store


def health() -> dict[str, Any]:
    return {
        "ok": True,
        "model_version": MODEL_VERSION,
        "order_send": False,
        "never_auto_live_deploy": True,
        **isolation_payload(),
    }


def summary() -> dict[str, Any]:
    return build_hub_summary()


def list_projects() -> dict[str, Any]:
    rows = get_research_store().list_projects()
    return {"projects": rows, "count": len(rows), **isolation_payload()}


def get_project(project_id: str) -> dict[str, Any] | None:
    return get_research_store().get_project(project_id)


def create_project(**kwargs: Any) -> dict[str, Any]:
    return get_research_store().create_project(**kwargs)


def list_experiments() -> dict[str, Any]:
    rows = get_research_store().list_experiments()
    return {"experiments": rows, "count": len(rows), **isolation_payload()}


def create_experiment(**kwargs: Any) -> dict[str, Any]:
    return get_research_store().create_experiment(**kwargs)


def get_templates() -> dict[str, Any]:
    return strategy_templates()


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    return validate_strategy_spec(spec)


def hypothesize(payload: dict[str, Any]) -> dict[str, Any]:
    return ai_hypothesize(payload)


def get_data_overview(**kwargs: Any) -> dict[str, Any]:
    return data_overview(**kwargs)


def get_backtests_overview(**kwargs: Any) -> dict[str, Any]:
    return backtest_overview(**kwargs)


def run_backtest(payload: dict[str, Any]) -> dict[str, Any]:
    return run_backtest_compose(payload)


def get_walkforward_overview(**kwargs: Any) -> dict[str, Any]:
    return walkforward_overview(**kwargs)


def run_walkforward(payload: dict[str, Any]) -> dict[str, Any]:
    return run_walkforward_compose(payload)


def get_montecarlo_overview(**kwargs: Any) -> dict[str, Any]:
    return montecarlo_overview(**kwargs)


def run_montecarlo(payload: dict[str, Any]) -> dict[str, Any]:
    return run_montecarlo_compose(payload)


def get_robustness(**kwargs: Any) -> dict[str, Any]:
    return robustness_overview(**kwargs)


def get_optimization(**kwargs: Any) -> dict[str, Any]:
    return optimization_overview(**kwargs)


def run_optimization(payload: dict[str, Any]) -> dict[str, Any]:
    return run_optimization_compose(payload)


def get_leaderboard(**kwargs: Any) -> dict[str, Any]:
    return leaderboard(**kwargs)


def get_validation_pipeline(**kwargs: Any) -> dict[str, Any]:
    return validation_pipeline(**kwargs)


def list_approvals() -> dict[str, Any]:
    rows = get_research_store().list_approvals()
    return {
        "approvals": rows,
        "count": len(rows),
        "approved_is_not_live": True,
        **isolation_payload(),
    }


def create_approval(**kwargs: Any) -> dict[str, Any]:
    return get_research_store().create_approval(**kwargs)


def approval_action(approval_id: str, **kwargs: Any) -> dict[str, Any] | None:
    return get_research_store().act_on_approval(approval_id, **kwargs)


def get_paper(**kwargs: Any) -> dict[str, Any]:
    return paper_overview(**kwargs)


def audit_log(*, limit: int = 100) -> dict[str, Any]:
    rows = get_research_store().list_audit(limit=limit)
    redacted: list[dict[str, Any]] = []
    for row in rows:
        clean = dict(row)
        for k in list(clean.keys()):
            if any(s in k.lower() for s in ("password", "token", "secret", "api_key")):
                clean[k] = "[redacted]"
        redacted.append(clean)
    return {"events": redacted, "count": len(redacted), **isolation_payload()}
