"""Historical trends over 24h / 7d / 30d / 90d / 1y — evidence only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.continuous_improvement.models import TREND_WINDOWS
from app.domain.continuous_improvement.persistence import utc_iso

_WINDOW_DELTA = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
    "1y": timedelta(days=365),
}


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _bucket_history(history: list[dict[str, Any]], *, window: str) -> dict[str, Any]:
    delta = _WINDOW_DELTA.get(window)
    if not delta:
        return {"window": window, "points": [], "sample_count": 0}
    now = datetime.now(UTC)
    cutoff = now - delta
    points: list[dict[str, Any]] = []
    for snap in history:
        if not isinstance(snap, dict):
            continue
        ts = _parse_ts(snap.get("as_of"))
        if ts is None or ts < cutoff:
            continue
        tc = snap.get("target_count") or 1
        ok = snap.get("ok_count") or 0
        try:
            ratio = round(100.0 * float(ok) / float(tc), 2)
        except (TypeError, ValueError):
            ratio = None
        points.append(
            {
                "as_of": snap.get("as_of"),
                "overall": snap.get("overall"),
                "ok_ratio_percent": ratio,
            }
        )
    avg = None
    ratios = [
        p["ok_ratio_percent"]
        for p in points
        if isinstance(p.get("ok_ratio_percent"), (int, float))
    ]
    if ratios:
        avg = round(sum(ratios) / len(ratios), 2)
    return {
        "window": window,
        "sample_count": len(points),
        "avg_ok_ratio_percent": avg,
        "points": points[-60:],
        "fabricated": False,
    }


def build_historical_trends(
    *,
    validation: dict[str, Any],
    trading: dict[str, Any],
) -> dict[str, Any]:
    history = list(validation.get("history") or [])
    # Prefer fuller history from store
    try:
        from app.domain.continuous_improvement.continuous_validation import (
            list_validation_history,
        )

        history = list_validation_history(limit=2000)
    except Exception:  # noqa: S110
        pass

    windows = {w: _bucket_history(history, window=w) for w in TREND_WINDOWS}

    # Period trading evidence (AI period reports) — null when absent
    period_trading: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.ai_scalping import (
            institutional_period_reports as period_mod,
        )

        build_institutional_period_reports = (
            period_mod.build_institutional_period_reports
        )

        pack = build_institutional_period_reports() or {}
        period_trading = {
            "periods": pack.get("periods") or pack,
            "fabricated": bool(pack.get("fabricated")),
            "observe_only": True,
        }
    except Exception:
        period_trading = {"periods": {}, "fabricated": False}

    return {
        "as_of": utc_iso(),
        "validation_trends": windows,
        "trading_snapshot": {
            "win_rate": trading.get("win_rate"),
            "profit_factor": trading.get("profit_factor"),
            "expectancy": trading.get("expectancy"),
            "measured_count": trading.get("measured_count"),
        },
        "period_trading": period_trading,
        "windows": list(TREND_WINDOWS),
        "fabricated": False,
        "observe_only": True,
        "note": "Empty windows mean insufficient history — never fabricated",
    }
