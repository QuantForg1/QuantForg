"""Application facade — Institutional Research Lab (IRL).

Isolated from production trading. Read-only toward production systems.
"""

from __future__ import annotations

from typing import Any

from app.domain.institutional_research_lab import get_irl
from app.domain.institutional_research_lab.models import ResearchVerdict
from app.domain.institutional_research_lab.replay import production_baseline_metrics


def build_irl_dashboard() -> dict[str, Any]:
    lab = get_irl()
    payload = lab.dashboard()
    payload.update(
        {
            "schema_version": "1.0.0",
            "advisory_only": True,
            "mutates_engines": False,
            "never_modifies_strategy_risk_safety_oms_execution_auto_trading_thresholds": True,
        }
    )
    return payload


def irl_create_experiment(
    *,
    name: str,
    description: str = "",
    author: str = "researcher",
    candidate_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return get_irl().create_experiment(
        name=name,
        description=description,
        author=author,
        candidate_params=candidate_params,
    )


def irl_list_experiments(*, limit: int = 100) -> dict[str, Any]:
    rows = get_irl().list_experiments(limit=limit)
    return {"experiments": rows, "count": len(rows), "isolation": get_irl().isolation}


def irl_get_experiment(experiment_id: str) -> dict[str, Any] | None:
    return get_irl().get_experiment(experiment_id)


def irl_update_experiment(experiment_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    return get_irl().update_experiment(experiment_id, updates)


def irl_run_replay(
    *,
    experiment_id: str,
    window: str = "90d",
    custom_start: str | None = None,
    custom_end: str | None = None,
    bars: list[dict[str, Any]] | None = None,
    author: str = "researcher",
    use_live_portfolio_baseline: bool = False,
) -> dict[str, Any]:
    baseline = None
    if use_live_portfolio_baseline:
        # Optional READ-ONLY snapshot from portfolio analytics — never writes.
        try:
            from app.application.services.institutional_portfolio_analytics import (
                analyze_portfolio,
            )

            snap = analyze_portfolio([], starting_equity=10_000.0, include_reports=False)
            perf = (snap.get("sections") or {}).get("performance") or {}
            risk = (snap.get("sections") or {}).get("risk") or {}
            baseline = {
                "label": "Production analytics snapshot (read-only)",
                "profit_factor": perf.get("profit_factor") or production_baseline_metrics()["profit_factor"],
                "expectancy": perf.get("expectancy") or production_baseline_metrics()["expectancy"],
                "win_rate": perf.get("win_rate_pct") or production_baseline_metrics()["win_rate"],
                "maximum_drawdown_pct": risk.get("max_drawdown_pct")
                or production_baseline_metrics()["maximum_drawdown_pct"],
                "total_trades": perf.get("trade_count") or 0,
                "source": "portfolio_analytics_read_only",
                "not_live_production_write": True,
            }
        except Exception:  # noqa: BLE001
            baseline = production_baseline_metrics()

    return get_irl().queue_and_run_replay(
        experiment_id=experiment_id,
        window=window,
        custom_start=custom_start,
        custom_end=custom_end,
        bars=bars,
        production_baseline=baseline,
        author=author,
    )


def irl_leaderboard(*, rank_by: str = "composite", limit: int = 50) -> dict[str, Any]:
    return get_irl().leaderboard(rank_by=rank_by, limit=limit)


def irl_list_jobs(*, limit: int = 50, experiment_id: str | None = None) -> dict[str, Any]:
    rows = get_irl().list_jobs(limit=limit, experiment_id=experiment_id)
    return {"jobs": rows, "count": len(rows)}


def irl_list_reports(*, limit: int = 50) -> dict[str, Any]:
    rows = get_irl().list_reports(limit=limit)
    return {"reports": rows, "count": len(rows)}


def irl_add_note(experiment_id: str, *, author: str, body: str) -> dict[str, Any]:
    return get_irl().add_note(experiment_id, author=author, body=body)


def irl_archive(experiment_id: str) -> dict[str, Any] | None:
    return get_irl().archive_experiment(experiment_id)


def irl_set_verdict(experiment_id: str, verdict: str) -> dict[str, Any] | None:
    allowed = {v.value for v in ResearchVerdict}
    if verdict not in allowed:
        raise ValueError("invalid_verdict")
    return get_irl().mark_verdict(experiment_id, verdict)


def irl_benchmark_view() -> dict[str, Any]:
    """Aggregate latest completed experiment benchmarks."""
    experiments = [
        e
        for e in get_irl().list_experiments(limit=100)
        if e.get("benchmark")
    ]
    return {
        "experiments": [
            {
                "uuid": e["uuid"],
                "name": e["name"],
                "verdict": e.get("verdict"),
                "benchmark": e.get("benchmark"),
                "statistics": e.get("statistics"),
            }
            for e in experiments[:30]
        ],
        "production_baseline": production_baseline_metrics(),
        "isolation": get_irl().isolation,
    }
