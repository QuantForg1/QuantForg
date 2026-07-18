"""Research Lab — strategy comparison & ranking from supplied metrics only."""

from __future__ import annotations

from typing import Any


def _f(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


COMPARE_KEYS = (
    "win_rate",
    "profit_factor",
    "sharpe_ratio",
    "sortino_ratio",
    "max_drawdown_pct",
    "expectancy",
    "average_r",
    "trade_count",
)


def compare_strategies(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Side-by-side comparison; missing metrics stay null — never invented."""
    if not rows:
        return {
            "status": "unavailable",
            "reason": "No strategy research results to compare",
            "items": [],
        }

    items: list[dict[str, Any]] = []
    for row in rows:
        metrics = dict(row.get("metrics") or {})
        items.append(
            {
                "strategy_key": row.get("strategy_key"),
                "name": row.get("name"),
                "run_id": row.get("run_id"),
                "win_rate": _f(metrics.get("win_rate")),
                "profit_factor": _f(metrics.get("profit_factor")),
                "sharpe_ratio": _f(metrics.get("sharpe_ratio")),
                "sortino_ratio": _f(metrics.get("sortino_ratio")),
                "max_drawdown_pct": _f(metrics.get("max_drawdown_pct")),
                "expectancy": _f(metrics.get("expectancy")),
                "average_rr": _f(metrics.get("average_r") or metrics.get("average_rr")),
                "trade_count": _f(metrics.get("trade_count")),
                "exposure": row.get("exposure"),
                "correlation": row.get("correlation"),
                "stability": _f((row.get("stability") or {}).get("stability_score")),
                "regime_fit": row.get("regime_fit"),
            }
        )

    def _rank(key: str, *, reverse: bool = True) -> list[str]:
        scored = [
            (it["strategy_key"], it.get(key)) for it in items if it.get(key) is not None
        ]
        scored.sort(key=lambda x: float(x[1] or 0), reverse=reverse)
        return [str(k) for k, _ in scored]

    return {
        "status": "available",
        "items": items,
        "rankings": {
            "by_sharpe": _rank("sharpe_ratio"),
            "by_profit_factor": _rank("profit_factor"),
            "by_drawdown_asc": _rank("max_drawdown_pct", reverse=False),
            "by_expectancy": _rank("expectancy"),
        },
        "data_source": "research_runs|backtest_metrics",
        "advisory_only": True,
    }


def pick_dashboard_leaders(comparison: dict[str, Any]) -> dict[str, Any]:
    items = list(comparison.get("items") or [])
    if not items:
        return {
            "best": None,
            "worst": None,
            "candidate": None,
            "confidence": None,
            "stability": None,
            "market_suitability": None,
        }

    def score(it: dict[str, Any]) -> float:
        s = 0.0
        if it.get("sharpe_ratio") is not None:
            s += float(it["sharpe_ratio"]) * 20
        if it.get("profit_factor") is not None:
            s += float(it["profit_factor"]) * 10
        if it.get("max_drawdown_pct") is not None:
            s -= float(it["max_drawdown_pct"]) * 0.5
        if it.get("stability") is not None:
            s += float(it["stability"]) * 15
        return s

    ranked = sorted(items, key=score, reverse=True)
    best = ranked[0]
    worst = ranked[-1]
    candidate = best if score(best) > 5 else None
    return {
        "best": best,
        "worst": worst,
        "candidate": candidate,
        "confidence": round(min(95.0, max(5.0, score(best) + 40)), 1) if best else None,
        "stability": best.get("stability") if best else None,
        "market_suitability": best.get("regime_fit") if best else None,
    }
