"""Strategy Comparison Dashboard — supplied run metrics only."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.research_validation_platform.util import dec, opt_int, reproducible_hash


def compare_strategies(
    runs: list[dict[str, Any]], *, max_comparisons: int = 20
) -> dict[str, Any]:
    if not runs:
        return {
            "status": "empty",
            "leader": None,
            "ranked": [],
            "reasons": ["No strategy runs supplied — never invents comparisons"],
            "input_hash": None,
            "reproducible": False,
            "affects_live_execution": False,
        }

    ranked: list[dict[str, Any]] = []
    for raw in runs[:max_comparisons]:
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("strategy_key") or "unknown")
        version = str(raw.get("version") or "unversioned")
        pf = dec(raw.get("profit_factor"))
        sharpe = dec(raw.get("sharpe"))
        dd = dec(raw.get("max_drawdown_pct"))
        trades = opt_int(raw.get("trade_count"))
        # Composite from supplied metrics only; missing → unavailable row.
        if pf is None and sharpe is None and dd is None and trades is None:
            ranked.append(
                {
                    "strategy_key": key,
                    "version": version,
                    "status": "unavailable",
                    "composite": None,
                    "reason": "No metrics supplied",
                }
            )
            continue
        composite = Decimal("0")
        parts = 0
        if pf is not None:
            composite += min(pf * Decimal("20"), Decimal("40"))
            parts += 1
        if sharpe is not None:
            composite += min(sharpe * Decimal("20"), Decimal("30"))
            parts += 1
        if dd is not None:
            composite += max(Decimal("30") - dd, Decimal("0"))
            parts += 1
        if trades is not None:
            composite += min(Decimal(trades) / Decimal("2"), Decimal("20"))
            parts += 1
        if parts:
            score = (composite / Decimal(parts)).quantize(Decimal("0.01"))
        else:
            score = None
        ranked.append(
            {
                "strategy_key": key,
                "version": version,
                "status": "available",
                "composite": str(score) if score is not None else None,
                "profit_factor": str(pf) if pf is not None else None,
                "sharpe": str(sharpe) if sharpe is not None else None,
                "max_drawdown_pct": str(dd) if dd is not None else None,
                "trade_count": trades,
            }
        )

    available = [
        r for r in ranked if r.get("status") == "available" and r.get("composite")
    ]
    available.sort(key=lambda r: Decimal(str(r["composite"])), reverse=True)
    leader = available[0] if available else None
    input_hash = reproducible_hash({"runs": ranked})
    return {
        "status": "available" if available else "unavailable",
        "leader": leader,
        "ranked": available + [r for r in ranked if r not in available],
        "reasons": [
            f"Compared {len(available)} scored runs from supplied metrics",
            "Never invents performance numbers",
            "Live execution pipeline unchanged",
        ],
        "input_hash": input_hash,
        "reproducible": True,
        "affects_live_execution": False,
    }
