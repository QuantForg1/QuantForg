"""Pattern Intelligence (AI v8) — discover best/worst regimes from REAL trades.

Never modifies production strategy. Intelligence only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _f(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _bucket_stats(rows: list[Any], key_fn) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = key_fn(r)
        if not key:
            continue
        b = buckets.setdefault(key, {"trades": 0, "wins": 0, "pnl": 0.0})
        b["trades"] += 1
        if getattr(r, "win", False):
            b["wins"] += 1
        pnl = _f(getattr(r, "pnl", None))
        if pnl is not None:
            b["pnl"] += pnl
    for b in buckets.values():
        n = int(b["trades"])
        b["win_rate"] = round(b["wins"] / n, 4) if n else None
        b["avg_pnl"] = round(b["pnl"] / n, 4) if n else None
    return buckets


def _best_worst(
    buckets: dict[str, dict[str, Any]], *, min_n: int = 2
) -> tuple[str | None, str | None]:
    scored: list[tuple[str, float, int]] = []
    for k, s in buckets.items():
        n = int(s.get("trades") or 0)
        if n < min_n:
            continue
        wr = float(s.get("win_rate") or 0)
        scored.append((k, wr, n))
    if not scored:
        return None, None
    scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return scored[0][0], scored[-1][0]


def _range_bucket(
    value: float | None, edges: list[tuple[float, float, str]]
) -> str | None:
    if value is None:
        return None
    for lo, hi, label in edges:
        if lo <= value < hi:
            return label
    return edges[-1][2] if edges else None


def build_pattern_intelligence() -> dict[str, Any]:
    """Discover best/worst patterns from learning store — observe only."""
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

    by_regime = _bucket_stats(
        rows, lambda r: str(getattr(r, "regime", "") or "") or None
    )
    by_session = _bucket_stats(
        rows, lambda r: str(getattr(r, "session", "") or "") or None
    )
    by_symbol = _bucket_stats(
        rows, lambda r: str(getattr(r, "symbol", "") or "").upper() or None
    )

    def _weekday(r: Any) -> str | None:
        raw = str(getattr(r, "closed_at", "") or "")
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.strftime("%A")
        except Exception:
            return None

    by_weekday = _bucket_stats(rows, _weekday)

    vol_edges = [
        (0.0, 0.2, "compression"),
        (0.2, 0.6, "normal_low"),
        (0.6, 1.5, "normal"),
        (1.5, 3.0, "elevated"),
        (3.0, 100.0, "extreme"),
    ]
    by_vol = _bucket_stats(
        rows,
        lambda r: _range_bucket(_f(getattr(r, "atr_pct", None)), vol_edges),
    )
    q_edges = [
        (0, 70, "q_<70"),
        (70, 80, "q_70_80"),
        (80, 88, "q_80_88"),
        (88, 95, "q_88_95"),
        (95, 101, "q_95_plus"),
    ]
    by_quality = _bucket_stats(
        rows,
        lambda r: _range_bucket(float(getattr(r, "quality", 0) or 0), q_edges),
    )
    c_edges = [
        (0, 70, "c_<70"),
        (70, 80, "c_70_80"),
        (80, 88, "c_80_88"),
        (88, 95, "c_88_95"),
        (95, 101, "c_95_plus"),
    ]
    by_confidence = _bucket_stats(
        rows,
        lambda r: _range_bucket(float(getattr(r, "confidence", 0) or 0), c_edges),
    )
    hold_edges = [
        (0, 5, "hold_<5m"),
        (5, 15, "hold_5_15m"),
        (15, 45, "hold_15_45m"),
        (45, 120, "hold_45_120m"),
        (120, 1e9, "hold_>120m"),
    ]
    by_hold = _bucket_stats(
        rows,
        lambda r: _range_bucket(
            _f(getattr(r, "holding_time_minutes", None)), hold_edges
        ),
    )

    best_regime, worst_regime = _best_worst(by_regime)
    best_session, worst_session = _best_worst(by_session)
    best_symbol, worst_symbol = _best_worst(by_symbol)
    best_weekday, worst_weekday = _best_worst(by_weekday)
    best_vol, worst_vol = _best_worst(by_vol)
    best_q, worst_q = _best_worst(by_quality)
    best_c, worst_c = _best_worst(by_confidence)
    best_hold, worst_hold = _best_worst(by_hold)

    return {
        "as_of": _iso(),
        "trades": len(rows),
        "best_market_regimes": best_regime,
        "worst_market_regimes": worst_regime,
        "best_sessions": best_session,
        "worst_sessions": worst_session,
        "best_weekdays": best_weekday,
        "worst_weekdays": worst_weekday,
        "best_symbols": best_symbol,
        "worst_symbols": worst_symbol,
        "best_volatility_ranges": best_vol,
        "worst_volatility_ranges": worst_vol,
        "best_quality_ranges": best_q,
        "worst_quality_ranges": worst_q,
        "best_confidence_ranges": best_c,
        "worst_confidence_ranges": worst_c,
        "best_holding_times": best_hold,
        "worst_holding_times": worst_hold,
        "buckets": {
            "regime": by_regime,
            "session": by_session,
            "symbol": by_symbol,
            "weekday": by_weekday,
            "volatility": by_vol,
            "quality": by_quality,
            "confidence": by_confidence,
            "holding": by_hold,
        },
        "modifies_strategy": False,
        "auto_applies": False,
        "fabricated": False,
        "source": "real_completed_trades_only",
        "observe_only": True,
    }
