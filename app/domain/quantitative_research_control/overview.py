"""Read-only overview builders for Phase 8 Quantitative Research Control."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.quantitative_research_control import (
    MODEL_VERSION,
    MODULE_ROUTES,
    STRATEGY_FAMILIES,
    VALIDATION_CLASSES,
    VALIDATION_STAGES,
    data_quality,
    isolation_payload,
)
from app.domain.quantitative_research_control.store import get_research_store


def _now() -> str:
    return datetime.now(UTC).isoformat()


def build_hub_summary() -> dict[str, Any]:
    store = get_research_store()
    return {
        "ok": True,
        "modules": list(MODULE_ROUTES),
        "projects": len(store.list_projects(limit=200)),
        "experiments": len(store.list_experiments(limit=200)),
        "pending_reviews": store.pending_review_count(),
        "links": {
            "qsf": "/quantforg-strategy-factory",
            "strategy_lifecycle": "/strategy-lifecycle",
            "strategy_analytics": "/strategy-analytics",
            "phase7_autonomy": "/autonomous-trading",
            "flagship_research": "/research",
        },
        "data_quality": data_quality(source="phase8.hub", as_of=_now()),
        **isolation_payload(),
    }


def strategy_templates() -> dict[str, Any]:
    required = [
        "name",
        "description",
        "instrument_compatibility",
        "timeframe",
        "entry_rules",
        "exit_rules",
        "stop_loss_rules",
        "take_profit_rules",
        "position_sizing",
        "risk_constraints",
        "parameter_definitions",
        "required_market_data",
    ]
    templates = [
        {
            "family": fam,
            "required_fields": required,
            "status": "research_template",
            "executable_code_allowed": False,
        }
        for fam in STRATEGY_FAMILIES
    ]
    return {
        "ok": True,
        "templates": templates,
        "validator": {
            "rejects_incomplete_specs": True,
            "never_executes_arbitrary_code": True,
        },
        **isolation_payload(),
    }


def validate_strategy_spec(spec: dict[str, Any]) -> dict[str, Any]:
    required = [
        "name",
        "entry_rules",
        "exit_rules",
        "stop_loss_rules",
        "take_profit_rules",
        "position_sizing",
        "risk_constraints",
    ]
    missing = [f for f in required if not spec.get(f)]
    return {
        "ok": len(missing) == 0,
        "valid": len(missing) == 0,
        "missing_fields": missing,
        "never_executes_arbitrary_code": True,
        "research_artifact_until_approved": True,
        **isolation_payload(),
    }


def ai_hypothesize(payload: dict[str, Any]) -> dict[str, Any]:
    """Advisory hypothesis artifact — never claims profitability, never LIVE."""
    store = get_research_store()
    family = str(payload.get("family") or "rule_based")
    symbol = str(payload.get("symbol") or "XAUUSD")
    hyp = {
        "id": f"hyp-{uuid4().hex[:12]}",
        "hypothesis": (
            payload.get("hypothesis")
            or f"Explore {family} behavior on {symbol} under documented regimes"
        ),
        "market_rationale": payload.get("market_rationale")
        or "Regime and structure evidence must be supplied by research data",
        "entry_logic": payload.get("entry_logic") or ["research_placeholder_entry"],
        "exit_logic": payload.get("exit_logic") or ["research_placeholder_exit"],
        "risk_assumptions": payload.get("risk_assumptions")
        or ["hard_risk_limits_take_priority"],
        "parameter_ranges": payload.get("parameter_ranges") or {},
        "expected_market_conditions": payload.get("expected_market_conditions")
        or ["unspecified"],
        "known_limitations": [
            "Not tested",
            "Not a profitability claim",
            "Research artifact only",
            "Never auto LIVE",
        ],
        "validation_plan": [
            "Specification validation",
            "Backtest with disclosed costs",
            "Walk-forward OOS",
            "Monte Carlo assumptions stated",
            "Robustness review",
            "Human approval",
        ],
        "family": family,
        "symbol": symbol,
        "profitability_claimed": False,
        "never_auto_live": True,
        "research_artifact": True,
    }
    return store.put_hypothesis(hyp)


def data_overview(
    *,
    idw: dict[str, Any] | None = None,
    qcdm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    missing: list[str] = []
    if not idw:
        missing.append("idw")
    if not qcdm:
        missing.append("qcdm")
    return {
        "ok": True,
        "idw": idw or {"status": "unavailable"},
        "qcdm": qcdm or {"status": "unavailable"},
        "rules": {
            "never_fabricates_ohlcv": True,
            "synthetic_must_be_labeled": True,
            "block_on_critical_missing": True,
            "preserve_source_attribution": True,
        },
        "data_quality": data_quality(
            source="phase8.research_data",
            as_of=_now(),
            missing_fields=missing,
        ),
        **isolation_payload(),
    }


def backtest_overview(
    *,
    result: dict[str, Any] | None = None,
    assumptions: list[str] | None = None,
) -> dict[str, Any]:
    metrics = result.get("metrics") if isinstance(result, dict) else None
    clean: dict[str, Any] = {}
    if isinstance(metrics, dict):
        for k in (
            "net_profit",
            "gross_profit",
            "gross_loss",
            "win_rate",
            "profit_factor",
            "expectancy",
            "max_drawdown",
            "sharpe",
            "sortino",
            "trade_count",
        ):
            if k in metrics and isinstance(metrics[k], (int, float)):
                clean[k] = metrics[k]
    return {
        "ok": True,
        "metrics": clean,
        "empty": not clean,
        "fabricated": False,
        "assumptions": list(
            assumptions
            or [
                "Backtest is not guaranteed future performance",
                "Costs/slippage must be disclosed when applied",
            ]
        ),
        "engine_version": (
            (result or {}).get("engine_version") if isinstance(result, dict) else None
        )
        or MODEL_VERSION,
        "backtest_is_not_live": True,
        "data_quality": data_quality(
            source="phase8.backtests",
            as_of=_now(),
            missing_fields=([] if clean else ["backtest_metrics"]),
        ),
        **isolation_payload(),
    }


def walkforward_overview(
    *,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "result": result or {"status": "unavailable"},
        "labels": {
            "in_sample": "training",
            "out_of_sample": "validation",
            "holdout": "final_holdout_not_for_tuning",
        },
        "rules": {
            "test_data_not_used_to_tune_before_validation": True,
            "distinguish_train_validation_holdout": True,
        },
        "fabricated": False,
        **isolation_payload(),
    }


def montecarlo_overview(
    *,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "result": result or {"status": "unavailable"},
        "assumptions_required": True,
        "not_guaranteed_future_probabilities": True,
        "fabricated": False,
        **isolation_payload(),
    }


def robustness_overview(
    *,
    findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = [r for r in (findings or []) if isinstance(r, dict)]
    return {
        "ok": True,
        "findings": rows,
        "empty": not rows,
        "rules": {
            "no_stat_claim_without_assumptions": True,
            "insufficient_sample_flagged": True,
        },
        **isolation_payload(),
    }


def optimization_overview(
    *,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "result": result or {"status": "unavailable"},
        "rules": {
            "optimize_on_training_only": True,
            "holdout_reserved": True,
            "never_auto_deploy_optimized_params": True,
            "show_tradeoffs_not_only_best_profit": True,
        },
        "optimization_is_not_live": True,
        **isolation_payload(),
    }


def leaderboard(
    *,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cleaned: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        vclass = str(row.get("validation_class") or "research")
        if vclass not in VALIDATION_CLASSES:
            vclass = "research"
        cleaned.append(
            {
                "strategy_id": row.get("strategy_id") or row.get("id"),
                "name": row.get("name"),
                "validation_class": vclass,
                "net_performance": row.get("net_performance"),
                "risk_adjusted": row.get("risk_adjusted") or row.get("sharpe"),
                "drawdown": row.get("drawdown") or row.get("max_drawdown"),
                "expectancy": row.get("expectancy"),
                "profit_factor": row.get("profit_factor"),
                "sample_size": row.get("sample_size") or row.get("trade_count"),
                "oos_robustness": row.get("oos_robustness"),
            }
        )
    # Prefer risk-adjusted then sample size — never profit alone.
    cleaned.sort(
        key=lambda r: (
            (
                float(r["risk_adjusted"])
                if isinstance(r.get("risk_adjusted"), (int, float))
                else -1e9
            ),
            (
                float(r["sample_size"])
                if isinstance(r.get("sample_size"), (int, float))
                else 0
            ),
        ),
        reverse=True,
    )
    return {
        "ok": True,
        "rows": cleaned,
        "count": len(cleaned),
        "ranking": "risk_adjusted_then_sample_size",
        "never_profit_only": True,
        "validation_classes": list(VALIDATION_CLASSES),
        **isolation_payload(),
    }


def validation_pipeline(
    *,
    qsf: dict[str, Any] | None = None,
    islm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stages = [
        {
            "stage": name,
            "status": "pending",
            "evidence": None,
            "backtest_pass_is_not_approval": True,
        }
        for name in VALIDATION_STAGES
    ]
    return {
        "ok": True,
        "stages": stages,
        "qsf": qsf or {"status": "unavailable"},
        "islm": islm or {"status": "unavailable"},
        "rules": {
            "successful_backtest_not_automatic_approval": True,
            "only_approved_versions_for_execution_consideration": True,
            "material_param_change_invalidates_approval": True,
        },
        **isolation_payload(),
    }


def paper_overview(*, paper: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "paper": paper or {"status": "unavailable"},
        "rules": {
            "paper_is_not_live": True,
            "never_send_real_orders_from_research": True,
            "simulated_records_not_real_trades": True,
        },
        "links": {
            "paper": "/paper",
            "qptcm": "/quantforg-paper-trading",
        },
        **isolation_payload(),
    }


def run_backtest_compose(payload: dict[str, Any]) -> dict[str, Any]:
    """Record experiment + return honest unavailable/metrics-passthrough result."""
    store = get_research_store()
    exp = store.create_experiment(
        project_id=payload.get("project_id"),
        strategy_id=payload.get("strategy_id"),
        strategy_version=payload.get("strategy_version"),
        config={
            "data_window": payload.get("data_window"),
            "parameters": payload.get("parameters") or {},
            "costs": payload.get("costs") or {},
            "engine_version": MODEL_VERSION,
            "assumptions": [
                "Compose facade — metrics only when supplied by existing engines",
                "Backtest is not LIVE",
            ],
            "symbol": payload.get("symbol"),
            "timeframe": payload.get("timeframe"),
        },
        actor=str(payload.get("actor") or "user"),
    )
    raw_metrics = payload.get("metrics")
    supplied: dict[str, Any] = (
        dict(raw_metrics) if isinstance(raw_metrics, dict) else {}
    )
    # Never invent metrics.
    clean: dict[str, Any] = {}
    for k in (
        "net_profit",
        "win_rate",
        "profit_factor",
        "max_drawdown",
        "sharpe",
        "trade_count",
    ):
        val = supplied.get(k)
        if isinstance(val, (int, float)):
            clean[k] = val
    return {
        "ok": True,
        "experiment_id": exp["id"],
        "metrics": clean,
        "empty": not clean,
        "fabricated": False,
        "status": "recorded" if clean else "awaiting_engine_metrics",
        "backtest_is_not_live": True,
        "assumptions": exp["config_snapshot"]["assumptions"],
        **isolation_payload(),
    }


def run_walkforward_compose(payload: dict[str, Any]) -> dict[str, Any]:
    raw_folds = payload.get("folds")
    folds: list[Any] = list(raw_folds) if isinstance(raw_folds, list) else []
    return {
        "ok": True,
        "folds": folds[:50],
        "empty": not folds,
        "fabricated": False,
        "labels": {"train": "IS", "test": "OOS", "holdout": "holdout"},
        **isolation_payload(),
    }


def run_montecarlo_compose(payload: dict[str, Any]) -> dict[str, Any]:
    iterations = payload.get("iterations")
    seed = payload.get("seed")
    if not isinstance(iterations, int) or iterations <= 0:
        return {
            "ok": False,
            "blocked": True,
            "reason": "iterations_required",
            "fabricated": False,
            **isolation_payload(),
        }
    # Passthrough distribution only when provided — never invent.
    dist = (
        payload.get("distribution")
        if isinstance(payload.get("distribution"), dict)
        else {}
    )
    return {
        "ok": True,
        "iterations": iterations,
        "seed": seed,
        "distribution": dist,
        "empty": not dist,
        "fabricated": False,
        "not_guaranteed_future_probabilities": True,
        "assumptions": payload.get("assumptions") or ["caller_supplied_or_unavailable"],
        **isolation_payload(),
    }


def run_optimization_compose(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "method": payload.get("method") or "grid",
        "candidates": (
            payload.get("candidates")
            if isinstance(payload.get("candidates"), list)
            else []
        ),
        "training_window": payload.get("training_window"),
        "holdout_window": payload.get("holdout_window"),
        "rules": {
            "holdout_not_used_for_selection": True,
            "never_auto_deploy": True,
        },
        "optimization_is_not_live": True,
        "fabricated": False,
        **isolation_payload(),
    }
