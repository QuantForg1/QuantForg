"""Institutional Period Reports (AI v8) — D/W/M/Q/Y from REAL trades only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


def _iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def _f(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _period_bounds(now: datetime) -> dict[str, tuple[datetime, datetime]]:
    start_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_week = start_day - timedelta(days=start_day.weekday())
    start_month = start_day.replace(day=1)
    q_month = ((start_day.month - 1) // 3) * 3 + 1
    start_quarter = start_day.replace(month=q_month, day=1)
    start_year = start_day.replace(month=1, day=1)
    return {
        "daily": (start_day, now),
        "weekly": (start_week, now),
        "monthly": (start_month, now),
        "quarterly": (start_quarter, now),
        "yearly": (start_year, now),
    }


def _rollup(rows: list[Any]) -> dict[str, Any]:
    n = len(rows)
    wins = sum(1 for r in rows if getattr(r, "win", False))
    pnls = [_f(getattr(r, "pnl", None)) for r in rows]
    pnls_f = [p for p in pnls if p is not None]
    gross_p = sum(p for p in pnls_f if p > 0)
    gross_l = abs(sum(p for p in pnls_f if p < 0))
    return {
        "trades": n,
        "wins": wins,
        "losses": n - wins,
        "win_rate": round(wins / n, 4) if n else None,
        "net_pnl": round(sum(pnls_f), 4) if pnls_f else None,
        "profit_factor": (
            round(gross_p / gross_l, 4) if gross_l > 0 else None
        ),
        "fabricated": False,
    }


def build_institutional_period_reports() -> dict[str, Any]:
    rows: list[Any] = []
    try:
        from app.domain.institutional_trading.ai_scalping.learning import (
            get_scalping_learning_store,
        )

        store = get_scalping_learning_store()
        with store._lock:
            rows = list(store._records)
    except Exception:
        rows = []

    now = datetime.now(UTC)
    bounds = _period_bounds(now)
    reports: dict[str, Any] = {}
    for name, (start, end) in bounds.items():
        selected = []
        for r in rows:
            dt = _parse(str(getattr(r, "closed_at", "") or ""))
            if dt is None:
                continue
            if start <= dt <= end:
                selected.append(r)
        reports[name] = _rollup(selected)

    # Attach KPI snapshot when available (shared evidence)
    kpis: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.institutional_performance_kpis import (  # noqa: E501
            build_institutional_performance_kpis,
        )

        kpis = build_institutional_performance_kpis()
    except Exception:
        kpis = {}

    return {
        "as_of": _iso(),
        "periods": reports,
        "kpis_all_time": {
            "expectancy": kpis.get("expectancy"),
            "sharpe": kpis.get("sharpe"),
            "institutional_score": kpis.get("institutional_score"),
            "trades": kpis.get("trades"),
        },
        "fabricated": False,
        "source": "real_completed_trades_only",
        "observe_only": True,
        "auto_applies": False,
    }
