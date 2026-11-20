"""Customer catalog view.

Version rows come only from stored records. Performance lanes are never
combined, and a lane stays unavailable without a traceable record.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

PERFORMANCE_LANES = ("live", "demo", "backtest", "simulated", "unverified")

# Published records are added only when a real release is stored.
# An empty registry is unavailable history, not a generated version.
PUBLISHED_VERSIONS: tuple[dict[str, Any], ...] = ()


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def accept_version(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Keep a version only when identity and a real timestamp are present."""
    strategy_key = _text(raw.get("strategy_key"))
    version = _text(raw.get("version"))
    released_at = _text(raw.get("released_at"))
    if strategy_key is None or version is None or released_at is None:
        return None
    try:
        datetime.fromisoformat(released_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return {
        "strategy_key": strategy_key,
        "version": version,
        "released_at": released_at,
        "release_notes": _text(raw.get("release_notes")),
        "compatibility": _text(raw.get("compatibility")),
        "status": _text(raw.get("status")),
        "timeframe": _text(raw.get("timeframe")),
        "instrument": _text(raw.get("instrument")),
        "risk_characteristics": _text(raw.get("risk_characteristics")),
    }


def versions_for(
    strategy_key: str,
    records: tuple[dict[str, Any], ...] | list[dict[str, Any]] = PUBLISHED_VERSIONS,
) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    for raw in records:
        row = accept_version(raw)
        if row is not None and row["strategy_key"] == strategy_key:
            accepted.append(row)
    return accepted


def performance_lanes(evidence: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Classify evidence into separate lanes. Untraced rows are ignored."""
    lanes: dict[str, dict[str, Any]] = {
        lane: {"status": "unavailable", "records": []} for lane in PERFORMANCE_LANES
    }
    for raw in evidence or []:
        if not isinstance(raw, dict):
            continue
        lane = _text(raw.get("lane"))
        trace_id = _text(raw.get("trace_id"))
        strategy_key = _text(raw.get("strategy_key"))
        if lane not in lanes or trace_id is None or strategy_key is None:
            continue
        lanes[lane]["status"] = "available"
        lanes[lane]["records"].append(
            {
                "trace_id": trace_id,
                "strategy_key": strategy_key,
                "summary": _text(raw.get("summary")),
            }
        )
    return {"lanes": lanes, "combined": None}


def present_catalog(
    plugin: dict[str, Any],
    *,
    versions: tuple[dict[str, Any], ...] | list[dict[str, Any]] = PUBLISHED_VERSIONS,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Public catalog row. Sales, copy trading, and deployment stay off."""
    key = _text(plugin.get("key")) or ""
    history = versions_for(key, versions)
    own_evidence = [
        row
        for row in (evidence or [])
        if isinstance(row, dict) and _text(row.get("strategy_key")) == key
    ]
    current = history[-1] if history else None
    performance = performance_lanes(own_evidence)
    return {
        "key": key,
        "name": _text(plugin.get("name")) or key,
        "category": _text(plugin.get("category")) or "Unavailable",
        "description": _text(plugin.get("description")) or "Unavailable",
        "default_params": dict(plugin.get("default_params") or {}),
        "version": None if current is None else current["version"],
        "timeframe": None if current is None else current["timeframe"],
        "instrument": None if current is None else current["instrument"],
        "status": None if current is None else current["status"],
        "release_notes": None if current is None else current["release_notes"],
        "compatibility": None if current is None else current["compatibility"],
        "risk_characteristics": (
            None if current is None else current["risk_characteristics"]
        ),
        "versions": history,
        "performance": performance,
        "sales_enabled": False,
        "copy_trading_enabled": False,
        "automated_deployment_enabled": False,
    }
