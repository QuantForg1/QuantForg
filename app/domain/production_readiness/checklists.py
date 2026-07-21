"""Pre/post-trade validation checklists — diagnostic only."""

from __future__ import annotations

from typing import Any

from app.domain.execution_intelligence.checklist import evaluate_checklist
from app.domain.execution_intelligence.post_trade import analyze_post_trades


def build_pre_trade_checklist(facts: dict[str, Any] | None) -> dict[str, Any]:
    if facts is None:
        return {
            "status": "unavailable",
            "message": "Pre-trade facts not supplied",
            "never_bypasses_risk": True,
            "never_bypasses_safety": True,
            "diagnostic_only": True,
        }

    def _opt_bool(key: str) -> bool | None:
        if key not in facts or facts[key] is None:
            return None
        return bool(facts[key])

    result = evaluate_checklist(
        broker_connected=_opt_bool("broker_connected"),
        market_open=_opt_bool("market_open"),
        risk_passed=_opt_bool("risk_passed"),
        margin_sufficient=_opt_bool("margin_sufficient"),
        strategy_signal_valid=_opt_bool("strategy_signal_valid"),
        execution_enabled=bool(facts.get("execution_enabled", False)),
    )
    # Explicit Risk/Safety gates — never bypass.
    risk_ok = _opt_bool("risk_engine_passed")
    safety_ok = _opt_bool("safety_engine_passed")
    extra_items = []
    for key, value in (
        ("risk_engine_passed", risk_ok),
        ("safety_engine_passed", safety_ok),
    ):
        if value is None:
            extra_items.append(
                {
                    "key": key,
                    "status": "unavailable",
                    "passed": None,
                    "reason": f"{key} unknown",
                }
            )
        else:
            extra_items.append(
                {
                    "key": key,
                    "status": "pass" if value else "fail",
                    "passed": value,
                    "reason": None if value else f"{key} failed",
                }
            )
            if not value:
                existing = list(result.get("blockers") or [])
                result["blockers"] = [*existing, f"{key} failed"]
                result["blocked"] = True
                result["ready_for_execution"] = False

    result["items"] = list(result.get("items") or []) + extra_items
    result["status"] = "available"
    result["never_bypasses_risk"] = True
    result["never_bypasses_safety"] = True
    result["diagnostic_only"] = True
    result["does_not_change_execution_architecture"] = True
    return result


def build_post_trade_checklist(
    trades: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if trades is None:
        return {
            "status": "unavailable",
            "message": "Post-trade rows not supplied",
            "diagnostic_only": True,
        }
    if not trades:
        return {
            "status": "empty",
            "message": "No recorded trades to validate",
            "items": [],
            "analyses": [],
            "diagnostic_only": True,
        }
    analyses = analyze_post_trades(trades)
    raw_items = analyses.get("items") if isinstance(analyses, dict) else None
    items: list[dict[str, Any]] = []
    for row in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(row, dict):
            continue
        st = str(row.get("status") or "unavailable")
        items.append(
            {
                "key": str(row.get("symbol") or row.get("ticket") or "trade"),
                "status": "pass" if st == "available" else st,
                "passed": st == "available",
                "reason": row.get("reason"),
                "analysis": row,
            }
        )
    fails = [i for i in items if i.get("status") == "fail"]
    return {
        "status": "available",
        "items": items,
        "analyses": analyses,
        "trade_count": len(trades),
        "failed_count": len(fails),
        "diagnostic_only": True,
        "message": "Post-trade validation from recorded fills only",
    }
