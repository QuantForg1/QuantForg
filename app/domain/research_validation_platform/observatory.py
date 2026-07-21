"""Performance Observatory — supplied metrics dashboard only."""

from __future__ import annotations

from typing import Any

from app.domain.research_validation_platform.util import dec, opt_int, reproducible_hash


def build_observatory(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics")
    strategy_key = str(payload.get("strategy_key") or "unknown")
    version = str(payload.get("version") or "unversioned")

    if not isinstance(metrics, dict) or not metrics:
        return {
            "status": "unavailable",
            "strategy_key": strategy_key,
            "version": version,
            "panels": [],
            "reasons": [
                "No performance metrics supplied — never fabricates observatory data",
            ],
            "input_hash": None,
            "reproducible": False,
            "affects_live_execution": False,
        }

    panels: list[dict[str, Any]] = []
    for key, value in list(metrics.items())[:40]:
        d = dec(value)
        i = opt_int(value) if d is None else None
        if d is not None:
            display: object = str(d)
        elif i is not None:
            display = i
        else:
            display = str(value)
        panels.append(
            {
                "panel_id": str(key),
                "title": str(key).replace("_", " ").title(),
                "status": "available",
                "value": display,
                "invented": False,
            }
        )

    inputs = {
        "strategy_key": strategy_key,
        "version": version,
        "metrics": {p["panel_id"]: p["value"] for p in panels},
    }
    return {
        "status": "available",
        "strategy_key": strategy_key,
        "version": version,
        "panels": panels,
        "reasons": [
            f"{len(panels)} observatory panels from supplied metrics",
            "Observational only — not a profitability promise",
            "Live execution pipeline unchanged",
        ],
        "input_hash": reproducible_hash(inputs),
        "reproducible": True,
        "affects_live_execution": False,
        "promise_profitability": False,
    }
