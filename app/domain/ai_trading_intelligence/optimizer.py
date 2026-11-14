"""Strategy optimization orchestrator — never auto-deploys to LIVE."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    strategy_id: str
    as_of: datetime
    backtest: dict[str, Any] | None
    walk_forward: dict[str, Any] | None
    out_of_sample: dict[str, Any] | None
    robustness: dict[str, Any] | None
    metrics: dict[str, Any]
    live_deploy_allowed: bool
    live_deploy_reason: str
    methodology: dict[str, Any] = field(default_factory=dict)


def run_optimization_orchestrator(
    *,
    strategy_id: str,
    backtest_summary: dict[str, Any] | None = None,
    walk_forward_summary: dict[str, Any] | None = None,
    out_of_sample_summary: dict[str, Any] | None = None,
    robustness_summary: dict[str, Any] | None = None,
    owner_promotion_approved: bool = False,
) -> OptimizationResult:
    """Assemble optimization evidence from existing BT/WF engine outputs.

    ``live_deploy_allowed`` stays False unless an *external* owner promotion
    flag is explicitly true — Phase 4 never writes trading_runtime_config.
    """
    metrics: dict[str, Any] = {}
    for src in (
        backtest_summary,
        walk_forward_summary,
        out_of_sample_summary,
        robustness_summary,
    ):
        if not isinstance(src, dict):
            continue
        for key in (
            "profit_factor",
            "expectancy",
            "max_drawdown",
            "max_drawdown_pct",
            "win_rate",
            "net_profit",
            "sharpe",
            "trades",
        ):
            if key in src and key not in metrics:
                metrics[key] = src[key]

    # Soft numeric coercion for common fields
    for key in list(metrics.keys()):
        try:
            metrics[key] = str(Decimal(str(metrics[key])))
        except Exception:
            metrics[key] = str(metrics[key])

    deploy = False
    reason = "phase4_forbids_auto_live_deploy"
    if owner_promotion_approved:
        # Still false — promotion must go through existing ITE/threshold APIs.
        deploy = False
        reason = (
            "owner_promotion_flag_seen_but_ati_never_auto_applies_"
            "use_existing_promotion_apis"
        )

    return OptimizationResult(
        strategy_id=strategy_id,
        as_of=datetime.now(UTC),
        backtest=backtest_summary,
        walk_forward=walk_forward_summary,
        out_of_sample=out_of_sample_summary,
        robustness=robustness_summary,
        metrics=metrics,
        live_deploy_allowed=deploy,
        live_deploy_reason=reason,
        methodology={
            "engines": "wrap_existing_backtest_walkforward_summaries",
            "look_ahead": "inherits_source_engine_guards",
            "auto_live_deploy": False,
            "order_send": False,
        },
    )
