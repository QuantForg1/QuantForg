"""Phase 8 — Quantitative Research Control (product facade).

Composes QSF, Quant Studio, Research Validation, backtests, walk-forward,
Monte Carlo, ISLM, Phase 6-7 intel. Research-only.

Never order_send. Never auto LIVE deploy. Never executes AI code in Production.
Distinct from historical Multi-account Phase 8 worker/dispatch track.
"""

from __future__ import annotations

from typing import Any

MODEL_VERSION = "phase8-research-1.0.0"

VALIDATION_STAGES: tuple[str, ...] = (
    "Research Draft",
    "Specification Validation",
    "Backtesting",
    "Walk-Forward Validation",
    "Monte Carlo Assessment",
    "Robustness Review",
    "Risk Review",
    "Human Approval",
    "Paper/Simulation Evaluation",
    "Production Strategy Approval",
)

VALIDATION_CLASSES: tuple[str, ...] = (
    "research",
    "backtested",
    "oos_validated",
    "simulation",
    "approved",
    "production_monitored",
)

STRATEGY_FAMILIES: tuple[str, ...] = (
    "trend_following",
    "mean_reversion",
    "momentum",
    "breakout",
    "volatility",
    "regime_aware",
    "multi_timeframe",
    "indicator_based",
    "rule_based",
    "template",
)

ISOLATION_FLAGS: dict[str, Any] = {
    "research_only": True,
    "advisory_only": True,
    "human_approval_required": True,
    "never_order_send": True,
    "never_auto_live_deploy": True,
    "never_auto_promote_to_production": True,
    "never_executes_arbitrary_code": True,
    "never_fabricates_ohlcv": True,
    "never_allocates_capital": True,
    "backtest_is_not_live": True,
    "approved_is_not_live": True,
    "paper_is_not_live": True,
    "optimization_is_not_live": True,
    "mutates_engines": False,
    "influences_trading": False,
    "preserves_weltrade_live_path": True,
}

MODULE_ROUTES: tuple[dict[str, str], ...] = (
    {"id": "quant_research", "path": "/quant-research", "label": "Quant Research"},
    {
        "id": "strategy_factory",
        "path": "/strategy-factory",
        "label": "Strategy Factory",
    },
    {"id": "research_data", "path": "/research-data", "label": "Research Data"},
    {
        "id": "strategy_backtesting",
        "path": "/strategy-backtesting",
        "label": "Strategy Backtesting",
    },
    {
        "id": "strategy_optimization",
        "path": "/strategy-optimization",
        "label": "Strategy Optimization",
    },
    {
        "id": "research_leaderboard",
        "path": "/research-leaderboard",
        "label": "Research Leaderboard",
    },
    {
        "id": "research_governance",
        "path": "/research-governance",
        "label": "Research Governance",
    },
)


def isolation_payload() -> dict[str, Any]:
    return {
        **ISOLATION_FLAGS,
        "model_version": MODEL_VERSION,
        "isolation": dict(ISOLATION_FLAGS),
        "order_send": False,
    }


def data_quality(
    *,
    source: str,
    as_of: str | None = None,
    stale: bool = False,
    missing_fields: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "as_of": as_of,
        "stale": stale,
        "missing_fields": list(missing_fields or []),
        "complete": not bool(missing_fields),
    }


__all__ = [
    "ISOLATION_FLAGS",
    "MODEL_VERSION",
    "MODULE_ROUTES",
    "STRATEGY_FAMILIES",
    "VALIDATION_CLASSES",
    "VALIDATION_STAGES",
    "data_quality",
    "isolation_payload",
]
