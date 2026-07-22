"""Daily operations checklist — WHY + RESOLUTION when items fail."""

from __future__ import annotations

from typing import Any

from app.domain.trading_operations_center.models import (
    CHECKLIST_LABELS,
    CHECKLIST_ORDER,
    CHECKLIST_RESOLVE,
)


def _truthy(raw: Any) -> bool | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "y", "connected", "open", "ready", "live", "ok"}:
        return True
    if text in {
        "0",
        "false",
        "no",
        "n",
        "disconnected",
        "closed",
        "blocked",
        "shadow",
        "canary",
        "disabled",
    }:
        return False
    return None


def _ops_live(facts: dict[str, Any]) -> tuple[bool | None, str]:
    explicit = _truthy(facts.get("ops_live"))
    if explicit is not None:
        return explicit, str(facts.get("ops_mode") or ("LIVE" if explicit else "—"))
    mode = str(facts.get("ops_mode") or "").strip().upper()
    if not mode:
        return None, "unknown"
    return mode == "LIVE", mode


def build_operations_checklist(facts: dict[str, Any] | None) -> dict[str, Any]:
    """Build readiness checklist. Never fabricates connectivity/mode facts."""
    src = dict(facts or {})
    items: list[dict[str, Any]] = []

    for key in CHECKLIST_ORDER:
        label = CHECKLIST_LABELS[key]
        if key == "ops_live":
            passed, value = _ops_live(src)
        elif key == "evidence_healthy":
            passed = _truthy(src.get("evidence_healthy"))
            value = str(
                src.get("evidence_status")
                or src.get("evidence_healthy")
                or "unknown"
            )
        else:
            passed = _truthy(src.get(key))
            value = str(src.get(key) if src.get(key) is not None else "unknown")

        if passed is None:
            item = {
                "key": key,
                "label": label,
                "passed": False,
                "value": value,
                "why": f"{label} status not supplied — never assumed healthy",
                "how_to_resolve": CHECKLIST_RESOLVE[key],
                "status": "unknown",
            }
        elif passed:
            item = {
                "key": key,
                "label": label,
                "passed": True,
                "value": value,
                "why": "",
                "how_to_resolve": "",
                "status": "pass",
            }
        else:
            item = {
                "key": key,
                "label": label,
                "passed": False,
                "value": value,
                "why": f"{label} failed (current: {value})",
                "how_to_resolve": CHECKLIST_RESOLVE[key],
                "status": "fail",
            }
        items.append(item)

    failed = [i for i in items if not i["passed"]]
    return {
        "status": "available",
        "all_passed": len(failed) == 0,
        "passed_count": sum(1 for i in items if i["passed"]),
        "total": len(items),
        "items": items,
        "failures": [
            {
                "key": i["key"],
                "label": i["label"],
                "why": i["why"],
                "how_to_resolve": i["how_to_resolve"],
                "value": i["value"],
            }
            for i in failed
        ],
        "note": "Checklist is advisory readiness — never bypasses Risk/Safety",
    }
