"""Research Platform executive dashboard — v10."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.research_platform import (
    DEFAULT_RESEARCH_CONFIG,
    get_audit_trail,
    get_continuous_improvement,
    get_experiment_store,
    get_model_registry,
    get_optimization_studio,
    get_promotion_workflow,
    get_reporting_store,
    get_research_workspace,
)
from app.domain.institutional_trading.research_platform.docs_gen import (
    document_experiment,
    document_model_change,
    document_optimization,
)
from core.logging import get_logger

logger = get_logger(__name__)


def build_research_platform_dashboard() -> dict[str, Any]:
    experiments = get_experiment_store()
    models = get_model_registry()
    opt = get_optimization_studio()
    promo = get_promotion_workflow()
    reports = get_reporting_store()
    workspace = get_research_workspace()
    audit = get_audit_trail()

    exp_summary = experiments.summary()
    pending_models = len(models.list(approval="pending"))
    approved_models = models.approved()
    opt_queue = opt.queue()
    pending_reviews = promo.pending()

    symbol_rankings: dict[str, Any] = {}
    weight_mult: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.performance_lab import (
            build_symbol_rankings,
        )

        symbol_rankings = build_symbol_rankings()
    except Exception:
        pass
    try:
        from app.domain.institutional_trading.ai_validation import get_weight_optimizer

        weight_mult = get_weight_optimizer().snapshot().get("multipliers") or {}
    except Exception:
        pass

    insights = get_continuous_improvement().generate(
        {
            "experiments_by_status": exp_summary.get("by_status"),
            "symbol_rankings": symbol_rankings,
            "optimization_queue": opt_queue,
            "models_pending": pending_models,
            "weight_multipliers": weight_mult,
        }
    )

    # Auto docs for latest artifacts
    docs: list[dict[str, str]] = []
    for e in experiments.list()[:3]:
        docs.append({"type": "experiment", "markdown": document_experiment(e)})
    for m in approved_models[:2]:
        docs.append({"type": "model", "markdown": document_model_change(m)})
    for r in opt_queue[:2]:
        docs.append({"type": "optimization", "markdown": document_optimization(r)})

    strategy_rankings = []
    try:
        from app.domain.institutional_trading.ai_validation import (
            get_strategy_performance_store,
        )

        by = get_strategy_performance_store().snapshot().get("by_strategy") or {}
        for name, m in by.items():
            strategy_rankings.append({"strategy": name, **(m if isinstance(m, dict) else {})})
        strategy_rankings.sort(
            key=lambda x: (x.get("profit_factor") is not None, x.get("profit_factor") or 0),
            reverse=True,
        )
    except Exception:
        logger.exception("strategy_rankings_failed")

    return {
        "version": DEFAULT_RESEARCH_CONFIG.version,
        "config": DEFAULT_RESEARCH_CONFIG.to_dict(),
        "guidance": {
            "message": (
                "Before Production promotion: run demo or low-risk live for 2–4 weeks and review "
                "win rate, profit factor, drawdown, Sharpe, average RR, execution latency, "
                "slippage, and AI calibration."
            ),
            "min_days": DEFAULT_RESEARCH_CONFIG.min_recommended_live_days,
            "recommended_days": DEFAULT_RESEARCH_CONFIG.recommended_live_days,
        },
        "active_experiments": experiments.list(status="Running"),
        "experiments_summary": exp_summary,
        "research_variants": workspace.list()[:20],
        "approved_models": approved_models,
        "pending_models": models.list(approval="pending"),
        "pending_reviews": pending_reviews,
        "research_results": [
            e for e in experiments.list(status="Completed")[:20]
        ],
        "strategy_rankings": strategy_rankings,
        "optimization_queue": opt_queue,
        "release_history": promo.history(limit=30),
        "reports": reports.recent(limit=10),
        "audit_trail": audit.recent(limit=40),
        "continuous_improvement": [i.to_dict() for i in insights],
        "generated_docs": docs,
        "safeguards": {
            "auto_promote_to_production": False,
            "auto_apply_optimizations": False,
            "research_isolated_from_live": True,
        },
    }
