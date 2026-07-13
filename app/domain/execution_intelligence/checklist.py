"""Pre-trade checklist — deterministic blockers from supplied facts only."""

from __future__ import annotations

from typing import Any


def evaluate_checklist(
    *,
    broker_connected: bool | None,
    market_open: bool | None,
    risk_passed: bool | None,
    margin_sufficient: bool | None,
    strategy_signal_valid: bool | None,
    execution_enabled: bool,
) -> dict[str, Any]:
    """Return checklist with explicit unavailable when fact is unknown."""

    def _item(
        key: str, value: bool | None, block_when_false: bool = True
    ) -> dict[str, Any]:
        if value is None:
            return {
                "key": key,
                "status": "unavailable",
                "passed": None,
                "reason": f"{key} unknown — no invented value",
            }
        passed = bool(value)
        status = "pass" if passed else ("fail" if block_when_false else "warn")
        reason = None
        if not passed:
            reason = f"{key} failed"
        return {"key": key, "status": status, "passed": passed, "reason": reason}

    items = [
        _item("broker_connected", broker_connected),
        _item("market_open", market_open),
        _item("risk_passed", risk_passed),
        _item("margin_sufficient", margin_sufficient),
        _item("strategy_signal_valid", strategy_signal_valid),
        {
            "key": "execution_enabled",
            "status": "pass" if execution_enabled else "fail",
            "passed": execution_enabled,
            "reason": (
                None
                if execution_enabled
                else "EXECUTION_ENABLED=false — live submit blocked (unchanged)"
            ),
        },
    ]

    blockers = [
        i["reason"]
        for i in items
        if i["status"] == "fail" and i.get("reason")
    ]
    unknowns = [i["key"] for i in items if i["status"] == "unavailable"]
    ready = len(blockers) == 0 and len(unknowns) == 0

    return {
        "ready_for_execution": ready,
        "blocked": len(blockers) > 0,
        "blockers": blockers,
        "unknown_facts": unknowns,
        "items": items,
        "autonomous_trading": False,
        "note": (
            "Checklist is diagnostic only — does not enable EXECUTION_ENABLED "
            "or place orders"
        ),
    }
