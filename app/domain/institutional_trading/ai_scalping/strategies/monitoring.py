"""Strategy-level performance monitoring for the SOE.

Aggregates StrategyStatsBook + health classification. Never fabricates
broker P&L. Rejected-signal tallies come from evaluation counters.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_trading.ai_scalping.strategies.live_eligibility import (
    eligibility_snapshot,
)
from app.domain.institutional_trading.ai_scalping.strategies.orchestrator import (
    ORCHESTRATION_VERSION,
    catalog_participation_policy,
)
from app.domain.institutional_trading.ai_scalping.strategies.registry import (
    ALL_STRATEGIES,
)
from app.domain.institutional_trading.ai_scalping.strategies.stats import (
    StrategyStatsBook,
    get_strategy_stats_book,
)
from app.domain.institutional_trading.ai_scalping.strategies.validation_status import (
    influence_weight_for_strategy,
    strategy_health_snapshot,
)


def build_strategy_performance_monitor(
    book: StrategyStatsBook | None = None,
) -> dict[str, Any]:
    """Durable-ish monitoring snapshot for ops / regression assertions."""
    stats_book = book or get_strategy_stats_book()
    snap = stats_book.snapshot()
    boosts = dict(snap.get("live_rank_boosts") or {})
    health = strategy_health_snapshot(snap)

    strategies: list[dict[str, Any]] = []
    deteriorating: list[str] = []
    for definition in ALL_STRATEGIES:
        sid = definition.strategy_id
        row = next(
            (
                r
                for r in (snap.get("strategies") or [])
                if str(r.get("strategy_id")) == sid
            ),
            None,
        )
        h = health.get(sid) or {"status": "insufficient_sample"}
        weight = influence_weight_for_strategy(
            strategy_id=sid,
            live_rank_boost=float(boosts.get(sid, 0.0)),
            health_row=h if isinstance(h, dict) else None,
        )
        if str(h.get("status")) == "deteriorating":
            deteriorating.append(sid)
        closed = int(h.get("closed_trades") or 0) if isinstance(h, dict) else 0
        strategies.append(
            {
                "strategy_id": sid,
                "name": definition.name,
                "scans": int((row or {}).get("scans") or 0),
                "eligible": int((row or {}).get("eligible") or 0),
                "accepted": int((row or {}).get("accepted") or 0),
                "rejected": int((row or {}).get("rejected") or 0),
                "wins": int((row or {}).get("wins") or 0),
                "losses": int((row or {}).get("losses") or 0),
                "closed_trades": closed,
                "win_rate": (row or {}).get("win_rate"),
                "profit_factor": (row or {}).get("profit_factor"),
                "expectancy": h.get("expectancy") if isinstance(h, dict) else None,
                "running_pnl": (row or {}).get("running_pnl"),
                "max_drawdown": (row or {}).get("max_drawdown"),
                "gross_profit": (row or {}).get("gross_profit"),
                "gross_loss": (row or {}).get("gross_loss"),
                "live_rank_boost": boosts.get(sid, 0.0),
                "influence_weight": weight,
                "health": h,
                "net_after_costs_note": (
                    "Net after spread/commission requires broker deal history; "
                    "StrategyStatsBook stores realized pnl when closed outcomes "
                    "are recorded — not a substitute for MT5 /history."
                ),
            }
        )

    live_safe = not deteriorating and all(
        int(s.get("accepted") or 0) == 0
        or s.get("health", {}).get("status")
        in {"healthy", "insufficient_sample", "unknown", "watch"}
        for s in strategies
    )

    eligibility = eligibility_snapshot()
    return {
        "as_of": datetime.now(UTC).isoformat(),
        "orchestration_version": ORCHESTRATION_VERSION,
        "strategies": strategies,
        "deteriorating_strategy_ids": deteriorating,
        "flags": (
            [f"deteriorating:{sid}" for sid in deteriorating]
            if deteriorating
            else ["no_deteriorating_flags"]
        ),
        "participation_policy": catalog_participation_policy(),
        "eligibility_registry": eligibility,
        "collaboration": {
            "mode": "live_pack_plus_advisory_votes",
            "oms_winners": "live_executable_profiles_only",
            "advisory_sources": [
                "score_factor_advisory",
                "strategy_engine_plugin",
                "institutional_alpha",
                "m1_micro",
            ],
            "prefer_no_trade_on_weak_or_conflict": True,
        },
        "live_execution_authorization": {
            "soe_influence_safe": live_safe,
            "auto_authorize_live": False,
            "live_operating_objective": True,
            "permanent_shadow_not_required": True,
            "note": (
                "LIVE is the operating objective when owner gates are enabled. "
                "SOE never auto-authorizes capital. Risk, OMS, MT5, "
                "EXECUTION_ENABLED, and ops LIVE mode remain fail-closed. "
                "Insufficient sample ≠ proven edge. Broker P&L is authoritative."
            ),
        },
        "disclaimer": "Historical data does not guarantee future profitability.",
    }
