"""IRL benchmark — compare candidate research stats to production baseline."""

from __future__ import annotations

from typing import Any


def _pct_diff(candidate: float | None, production: float | None) -> float | None:
    if candidate is None or production is None:
        return None
    if abs(production) < 1e-12:
        return None
    return round((candidate - production) / abs(production) * 100.0, 2)


def _abs_diff(candidate: float | None, production: float | None) -> float | None:
    if candidate is None or production is None:
        return None
    return round(candidate - production, 4)


def benchmark_against_production(
    candidate: dict[str, Any],
    production: dict[str, Any],
) -> dict[str, Any]:
    keys = (
        ("profit_factor", "profit_factor"),
        ("expectancy", "expectancy"),
        ("win_rate", "win_rate"),
        ("maximum_drawdown_pct", "maximum_drawdown_pct"),
        ("total_trades", "total_trades"),
    )
    rows: list[dict[str, Any]] = []
    for label, key in keys:
        prod = production.get(key)
        cand = candidate.get(key)
        # Drawdown: lower is better — invert difference sign for "improvement"
        if key == "maximum_drawdown_pct":
            diff_pct = _pct_diff(prod, cand)  # reduction vs production
            diff_abs = _abs_diff(cand, prod)
        else:
            diff_pct = _pct_diff(cand if isinstance(cand, (int, float)) else None, prod if isinstance(prod, (int, float)) else None)
            diff_abs = _abs_diff(
                float(cand) if isinstance(cand, (int, float)) else None,
                float(prod) if isinstance(prod, (int, float)) else None,
            )
        rows.append(
            {
                "metric": label,
                "production": prod,
                "candidate": cand,
                "difference_abs": diff_abs,
                "difference_pct": diff_pct,
            }
        )

    return {
        "production_label": production.get("label", "Production"),
        "candidate_label": "Candidate",
        "rows": rows,
        "profit_factor_difference_pct": next(
            (r["difference_pct"] for r in rows if r["metric"] == "profit_factor"), None
        ),
        "expectancy_difference": next(
            (r["difference_abs"] for r in rows if r["metric"] == "expectancy"), None
        ),
        "win_rate_difference": next(
            (r["difference_abs"] for r in rows if r["metric"] == "win_rate"), None
        ),
        "drawdown_difference": next(
            (r["difference_abs"] for r in rows if r["metric"] == "maximum_drawdown_pct"), None
        ),
        "trade_count_difference": next(
            (r["difference_abs"] for r in rows if r["metric"] == "total_trades"), None
        ),
        "advisory_only": True,
        "never_auto_promotes": True,
    }
