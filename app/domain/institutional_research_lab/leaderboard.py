"""IRL leaderboard ranking — research experiments only."""

from __future__ import annotations

from typing import Any


def _n(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def composite_score(exp: dict[str, Any]) -> float:
    stats = exp.get("statistics") or {}
    sig = exp.get("significance") or {}
    pf = _n(stats.get("profit_factor"))
    expct = _n(stats.get("expectancy"))
    dd = _n(stats.get("maximum_drawdown_pct"), 50.0)
    consistency = _n(sig.get("consistency_score"), 50.0)
    stability = _n(sig.get("stability_score"), 50.0)
    # Normalize loosely
    pf_s = max(0.0, min(100.0, pf * 30.0))
    exp_s = max(0.0, min(100.0, 50.0 + expct * 5.0))
    dd_s = max(0.0, min(100.0, 100.0 - dd * 4.0))
    return round((pf_s * 0.3 + exp_s * 0.25 + dd_s * 0.2 + consistency * 0.15 + stability * 0.1), 2)


def build_leaderboard(
    experiments: list[dict[str, Any]],
    *,
    rank_by: str = "composite",
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for exp in experiments:
        if not exp.get("statistics"):
            continue
        stats = exp["statistics"]
        sig = exp.get("significance") or {}
        rows.append(
            {
                "uuid": exp.get("uuid"),
                "name": exp.get("name"),
                "author": exp.get("author"),
                "status": exp.get("status"),
                "verdict": exp.get("verdict"),
                "profit_factor": stats.get("profit_factor"),
                "expectancy": stats.get("expectancy"),
                "maximum_drawdown_pct": stats.get("maximum_drawdown_pct"),
                "consistency_score": sig.get("consistency_score"),
                "composite_score": composite_score(exp),
                "updated_at": exp.get("updated_at"),
            }
        )

    key_map = {
        "profit_factor": lambda r: _n(r.get("profit_factor")),
        "expectancy": lambda r: _n(r.get("expectancy")),
        "drawdown": lambda r: -_n(r.get("maximum_drawdown_pct"), 999.0),
        "consistency": lambda r: _n(r.get("consistency_score")),
        "composite": lambda r: _n(r.get("composite_score")),
    }
    key_fn = key_map.get(rank_by, key_map["composite"])
    rows.sort(key=key_fn, reverse=True)
    for i, row in enumerate(rows[:limit], start=1):
        row["rank"] = i
    return rows[:limit]
