"""Strategy-level performance monitoring for the SOE.

Aggregates StrategyStatsBook + health classification. Never fabricates
broker P&L. Rejected-signal tallies come from evaluation counters.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_trading.ai_scalping.strategies.cycle_activity import (
    snapshot_cycle_activity,
)
from app.domain.institutional_trading.ai_scalping.strategies.live_eligibility import (
    eligibility_snapshot,
    live_executable_ids,
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


def _m1_status_block() -> dict[str, Any]:
    try:
        from app.domain.institutional_trading.m1_micro.config import (
            m1_live_submit_enabled,
            m1_micro_enabled,
        )

        micro = bool(m1_micro_enabled())
        live = bool(m1_live_submit_enabled())
    except Exception as exc:
        return {
            "m1_micro_enabled": None,
            "m1_live_submit": None,
            "status": "ERROR",
            "error": str(exc)[:200],
            "recommendation": "Inspect M1 config module",
        }
    if not micro:
        status = "DISABLED"
        recommendation = (
            "M1 module off (deployment flag and/or policy). Keep separate from "
            "five-pack SOE. Phase-2 matched expectancy was negative — do not "
            "enable LIVE submit without new evidence."
        )
    elif not live:
        status = "DISABLED"
        recommendation = (
            "M1 analysis may run but LIVE submit is off. Recommended while "
            "matched expectancy remains negative."
        )
    else:
        status = "ACTIVE_AND_EVALUATING"
        recommendation = (
            "m1_live_submit is ON. Phase-2 matched broker expectancy was "
            "negative — owner should confirm Admin Off unless new evidence "
            "supports LIVE. Flags were not silently changed."
        )
    return {
        "m1_micro_enabled": micro,
        "m1_live_submit": live,
        "status": status,
        "recommendation": recommendation,
        "owner_controlled": True,
        "auto_changed": False,
    }


def build_robot_health_monitor(
    book: StrategyStatsBook | None = None,
) -> dict[str, Any]:
    """Operational truth for LIVE robot health — process-local + durable stats.

    Never fabricates profitability. Never authorizes LIVE. Per-strategy status
    uses the Phase-3 vocabulary when cycle activity is present; otherwise
    falls back to registry + stats (never claims ACTIVE without evidence).
    """
    performance = build_strategy_performance_monitor(book=book)
    activity = snapshot_cycle_activity()
    activity_rows = dict(activity.get("strategies") or {})
    live_ids = set(live_executable_ids())

    strategies: list[dict[str, Any]] = []
    for definition in ALL_STRATEGIES:
        sid = definition.strategy_id
        perf: dict[str, Any] = next(
            (s for s in performance["strategies"] if s.get("strategy_id") == sid),
            {},
        )
        act = activity_rows.get(sid) or {}
        if sid not in live_ids:
            status = "DISABLED"
        elif activity.get("last_error") and not act:
            status = "ERROR"
        elif act.get("status"):
            status = str(act["status"])
        elif int(perf.get("scans") or 0) > 0:
            status = "ACTIVE_NO_VALID_SETUP"
        else:
            status = "DATA_UNAVAILABLE"
        strategies.append(
            {
                "strategy_id": sid,
                "name": definition.name,
                "tier": "live_executable" if sid in live_ids else "registry",
                "operational_status": status,
                "last_evaluated_at": act.get("last_evaluated_at"),
                "last_direction": act.get("direction"),
                "last_quality": act.get("quality"),
                "last_confidence": act.get("confidence"),
                "last_reject_reason": act.get("reject_reason"),
                "scans": perf.get("scans"),
                "accepted": perf.get("accepted"),
                "rejected": perf.get("rejected"),
                "closed_trades": perf.get("closed_trades"),
                "expectancy": perf.get("expectancy"),
                "profit_factor": perf.get("profit_factor"),
                "win_rate": perf.get("win_rate"),
                "running_pnl": perf.get("running_pnl"),
                "health": perf.get("health"),
                "influence_weight": perf.get("influence_weight"),
            }
        )

    quote_age = activity.get("last_quote_age_seconds")
    data_fresh = quote_age is None or (
        isinstance(quote_age, (int, float)) and float(quote_age) <= 8.0
    )

    return {
        "as_of": datetime.now(UTC).isoformat(),
        "orchestration_version": ORCHESTRATION_VERSION,
        "robot": {
            "last_cycle_at": activity.get("last_cycle_at"),
            "last_market_data_at": activity.get("last_market_data_at"),
            "last_quote_age_seconds": quote_age,
            "market_data_fresh": data_fresh,
            "last_soe_decision": activity.get("last_soe_decision"),
            "last_soe_reasons": activity.get("last_soe_reasons"),
            "last_selected_strategy_id": activity.get("last_selected_strategy_id"),
            "last_symbol": activity.get("last_symbol"),
            "last_regime": activity.get("last_regime"),
            "cycles_observed": activity.get("cycles_observed"),
            "last_error": activity.get("last_error"),
            "process_local": True,
        },
        "opportunity_intelligence": {
            "last_atr_pct": activity.get("last_atr_pct"),
            "last_net_reward_risk": activity.get("last_net_reward_risk"),
            "last_trade_quality": activity.get("last_trade_quality"),
            "last_regime": activity.get("last_regime"),
            "owner_min_net_rr": 0.50,
            "owner_preferred_rr": 0.50,
            "owner_min_quality": 70,
            "note": (
                "Phase-6: surfaces last-cycle ATR%/net RR/quality for reject "
                "forensics. Does not authorize LIVE or fabricate profitability."
            ),
        },
        "strategies": strategies,
        "m1": _m1_status_block(),
        "performance": {
            "deteriorating_strategy_ids": performance.get("deteriorating_strategy_ids"),
            "flags": performance.get("flags"),
        },
        "eligibility_registry": performance.get("eligibility_registry"),
        "collaboration": performance.get("collaboration"),
        "live_execution_authorization": performance.get("live_execution_authorization"),
        "risk_policy_defaults": {
            "max_concurrent_positions": 1,
            "minimum_net_reward_risk": "0.50",
            "preferred_reward_risk": "0.50",
            "minimum_trade_quality": 70,
            "max_lot": "0.01",
            "daily_loss_halt_percent": "48",
            "weekly_loss_halt_percent": "0 (off)",
            "overall_drawdown_halt_percent": "0 (off)",
            "note": (
                "Owner floor: experimental_promoted cannot lower the "
                "active net RR floor below 0.50. 20% per-trade and 48% daily "
                "halt are aggressive. Broker constraints still bind."
            ),
        },
        "disclaimer": (
            "Operational status is evidence-based. Registry membership alone "
            "never implies ACTIVE. Broker P&L is authoritative for "
            "profitability. Historical data does not guarantee future results."
        ),
        "mutates_engines": False,
        "advisory_only": True,
        "auto_authorize_live": False,
    }
