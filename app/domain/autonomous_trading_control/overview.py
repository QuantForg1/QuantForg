"""Read-only overview builders for Phase 7 Autonomous Trading Control."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.autonomous_trading_control import (
    MODULE_ROUTES,
    data_quality,
    isolation_payload,
)
from app.domain.autonomous_trading_control.store import get_autonomy_store


def _now() -> str:
    return datetime.now(UTC).isoformat()


def build_hub_summary() -> dict[str, Any]:
    store = get_autonomy_store()
    mode = store.get_mode()
    decisions = store.list_decisions(limit=50)
    blocked = sum(
        1
        for d in decisions
        if d.get("outcome") in {"EXECUTION_BLOCKED", "REJECTED", "NO_TRADE"}
    )
    return {
        "ok": True,
        "modules": list(MODULE_ROUTES),
        "mode": mode.get("mode"),
        "pending_approvals": store.pending_approval_count(),
        "recent_decisions": len(decisions),
        "blocked_or_no_trade": blocked,
        "links": {
            "phase5_operations": "/operations",
            "phase6_intelligence": "/intelligence-center",
            "live_trading_control": "/admin/live-trading",
            "auto_trading": "/auto-trading",
        },
        "phase7_live_dispatch": False,
        "data_quality": data_quality(
            source="phase7.hub",
            as_of=_now(),
        ),
        **isolation_payload(),
    }


def build_ops_overview(
    *,
    robot_status: dict[str, Any] | None = None,
    live_trading: dict[str, Any] | None = None,
    auto_trade: dict[str, Any] | None = None,
    broker: dict[str, Any] | None = None,
) -> dict[str, Any]:
    store = get_autonomy_store()
    return {
        "ok": True,
        "autonomy_mode": store.get_mode().get("mode"),
        "active_decisions": store.list_decisions(limit=10),
        "pending_approvals": store.pending_approval_count(),
        "robot_status": robot_status or {"status": "unavailable"},
        "live_trading": live_trading or {"status": "unavailable"},
        "auto_trade": auto_trade or {"status": "unavailable"},
        "broker": broker or {"status": "unavailable"},
        "phase7_live_dispatch": False,
        "data_quality": data_quality(source="phase7.ops", as_of=_now()),
        **isolation_payload(),
    }


def build_orders_lifecycle(
    *,
    attempts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = [r for r in (attempts or []) if isinstance(r, dict)]
    # Pass through known lifecycle fields only — never invent fills.
    cleaned: list[dict[str, Any]] = []
    for row in rows[:50]:
        cleaned.append(
            {
                "id": row.get("id")
                or row.get("attempt_id")
                or row.get("correlation_id"),
                "status": row.get("status") or row.get("state"),
                "symbol": row.get("symbol"),
                "side": row.get("side") or row.get("direction"),
                "volume": row.get("volume") or row.get("lots"),
                "correlation_id": row.get("correlation_id"),
                "broker_response": row.get("broker_response")
                or row.get("reject_reason"),
                "updated_at": row.get("updated_at") or row.get("created_at"),
            }
        )
    return {
        "ok": True,
        "orders": cleaned,
        "count": len(cleaned),
        "empty": not cleaned,
        "fabricated": False,
        "note": "read_only_journal_compose",
        "never_resend_uncertain": True,
        "data_quality": data_quality(
            source="phase7.orders_lifecycle",
            as_of=_now(),
            missing_fields=([] if cleaned else ["execution_attempts"]),
        ),
        **isolation_payload(),
    }


def build_trade_intelligence(
    *,
    trades: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = [r for r in (trades or []) if isinstance(r, dict)]
    analyzed: list[dict[str, Any]] = []
    for row in rows[:40]:
        confirmed = bool(
            row.get("confirmed")
            or row.get("filled")
            or str(row.get("status") or "").lower() in {"filled", "closed", "done"}
        )
        if not confirmed:
            analyzed.append(
                {
                    "id": row.get("id"),
                    "classification": "Data incomplete",
                    "note": "unconfirmed_order_not_classified_as_completed_trade",
                    "execution_quality_separated": True,
                }
            )
            continue
        pnl = row.get("realized_pnl")
        classification = "Data incomplete"
        if isinstance(pnl, (int, float)):
            if pnl > 0:
                classification = "Successful"
            elif pnl < 0:
                classification = "Unsuccessful"
            else:
                classification = "Breakeven"
        if row.get("execution_issue"):
            classification = "Execution issue"
        if row.get("risk_intervention"):
            classification = "Risk intervention"
        analyzed.append(
            {
                "id": row.get("id"),
                "symbol": row.get("symbol"),
                "planned_entry": row.get("planned_entry"),
                "actual_entry": row.get("actual_entry") or row.get("fill_price"),
                "planned_sl": row.get("planned_sl") or row.get("stop_loss"),
                "actual_sl": row.get("actual_sl"),
                "planned_tp": row.get("planned_tp") or row.get("take_profit"),
                "actual_tp": row.get("actual_tp"),
                "slippage": row.get("slippage"),
                "latency_ms": row.get("latency_ms"),
                "realized_pnl": pnl,
                "regime": row.get("regime"),
                "strategy": row.get("strategy"),
                "exit_reason": row.get("exit_reason"),
                "classification": classification,
                "execution_quality_separated": True,
            }
        )
    return {
        "ok": True,
        "trades": analyzed,
        "count": len(analyzed),
        "empty": not analyzed,
        "fabricated": False,
        "data_quality": data_quality(
            source="phase7.trade_intelligence",
            as_of=_now(),
            missing_fields=([] if analyzed else ["confirmed_trades"]),
        ),
        **isolation_payload(),
    }


def build_feedback_overview(
    *,
    evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ev = evaluation if isinstance(evaluation, dict) else {}
    return {
        "ok": True,
        "historical_evaluation": ev.get("historical") or {"status": "unavailable"},
        "model_version_comparison": ev.get("versions") or {"status": "unavailable"},
        "calibration": ev.get("calibration") or {"status": "unavailable"},
        "drift": ev.get("drift") or {"status": "unavailable"},
        "degradation_alerts": ev.get("alerts") or [],
        "rules": {
            "no_auto_model_change_to_live": True,
            "training_separated_from_production_execution": True,
            "never_train_on_fabricated_records": True,
        },
        "data_quality": data_quality(
            source="phase7.feedback",
            as_of=_now(),
            missing_fields=([] if ev else ["evaluation_sources"]),
        ),
        **isolation_payload(),
    }
