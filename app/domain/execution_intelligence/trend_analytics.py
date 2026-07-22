"""Trend-only risk / session / regime analytics from supplied closed trades.

Never invents PnL. Never mixes regimes. Advisory / reporting only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


def _f(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def _pnl(t: dict[str, Any]) -> float:
    for key in ("net_pnl", "pnl", "profit", "netPl"):
        if t.get(key) is not None:
            return _f(t.get(key))
    return 0.0


def _r_multiple(t: dict[str, Any]) -> float | None:
    if t.get("r_multiple") is not None:
        return _f(t.get("r_multiple"))
    risk = t.get("risk_amount") or t.get("initial_risk")
    pnl = _pnl(t)
    if risk is not None and abs(_f(risk)) > 1e-12:
        return pnl / abs(_f(risk))
    return None


def _bucket_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "status": "empty",
            "trade_count": 0,
            "win_rate": None,
            "expectancy": None,
            "profit_factor": None,
            "avg_duration_seconds": None,
        }
    wins = [t for t in trades if _pnl(t) > 0]
    losses = [t for t in trades if _pnl(t) < 0]
    gross_win = sum(_pnl(t) for t in wins)
    gross_loss = abs(sum(_pnl(t) for t in losses))
    n = len(trades)
    win_rate = len(wins) / n if n else None
    avg_win = gross_win / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0
    expectancy = (
        (win_rate * avg_win - (1.0 - win_rate) * avg_loss)
        if win_rate is not None
        else None
    )
    pf = (gross_win / gross_loss) if gross_loss > 0 else None
    durations: list[float] = []
    for t in trades:
        start = _parse_ts(
            t.get("opened_at") or t.get("entry_at") or t.get("created_at")
        )
        end = _parse_ts(
            t.get("closed_at") or t.get("filled_at") or t.get("completed_at")
        )
        if start and end and end >= start:
            durations.append((end - start).total_seconds())
    return {
        "status": "available",
        "trade_count": n,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "expectancy": round(expectancy, 6) if expectancy is not None else None,
        "profit_factor": round(pf, 4) if pf is not None else None,
        "avg_duration_seconds": (
            round(sum(durations) / len(durations), 2) if durations else None
        ),
    }


def compute_risk_trends(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Daily / weekly / monthly drawdown + streaks + R stats (trend report)."""
    if not trades:
        return {
            "status": "unavailable",
            "reason": "No closed trades supplied",
            "trends": {},
        }

    ordered = sorted(
        trades,
        key=lambda t: _parse_ts(t.get("closed_at") or t.get("created_at"))
        or datetime.min.replace(tzinfo=UTC),
    )
    equity = 0.0
    peak = 0.0
    curve: list[tuple[datetime, float, float]] = []
    for t in ordered:
        ts = _parse_ts(t.get("closed_at") or t.get("created_at")) or datetime.now(UTC)
        equity += _pnl(t)
        peak = max(peak, equity)
        dd = ((peak - equity) / peak * 100.0) if peak > 0 else 0.0
        curve.append((ts, equity, dd))

    now = datetime.now(UTC)

    def _max_dd_since(delta: timedelta) -> float | None:
        cutoff = now - delta
        window = [dd for ts, _eq, dd in curve if ts >= cutoff]
        return round(max(window), 4) if window else None

    pnls = [_pnl(t) for t in ordered]
    cur_w = cur_l = max_w = max_l = 0
    for p in pnls:
        if p > 0:
            cur_w += 1
            cur_l = 0
            max_w = max(max_w, cur_w)
        elif p < 0:
            cur_l += 1
            cur_w = 0
            max_l = max(max_l, cur_l)
        else:
            cur_w = cur_l = 0

    rs = [r for r in (_r_multiple(t) for t in ordered) if r is not None]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p < 0]

    return {
        "status": "available",
        "report_type": "trend_only",
        "trends": {
            "daily_drawdown_pct": _max_dd_since(timedelta(days=1)),
            "weekly_drawdown_pct": _max_dd_since(timedelta(days=7)),
            "monthly_drawdown_pct": _max_dd_since(timedelta(days=30)),
            "consecutive_wins_max": max_w,
            "consecutive_losses_max": max_l,
            "consecutive_wins_current": cur_w,
            "consecutive_losses_current": cur_l,
            "average_r": round(sum(rs) / len(rs), 4) if rs else None,
            "largest_winner": round(max(winners), 4) if winners else None,
            "largest_loser": round(min(losers), 4) if losers else None,
            "trade_count": len(ordered),
        },
        "note": "Trend report only — not a trading signal",
    }


def compute_session_analytics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-session performance; sessions never mixed."""
    from app.domain.institutional_trading.session_filter import classify_session_utc

    buckets: dict[str, list[dict[str, Any]]] = {
        "sydney": [],
        "tokyo": [],
        "london": [],
        "new_york": [],
        "london_ny_overlap": [],
        "off_hours": [],
    }
    for t in trades:
        label = str(t.get("session") or t.get("market_session") or "").lower()
        if label not in buckets:
            ts = _parse_ts(
                t.get("opened_at") or t.get("closed_at") or t.get("created_at")
            )
            label = classify_session_utc(ts).value if ts else "off_hours"
        if label not in buckets:
            label = "off_hours"
        buckets[label].append(t)

    return {
        "status": "available" if trades else "unavailable",
        "overall": _bucket_stats(trades),
        "sessions": {k: _bucket_stats(v) for k, v in buckets.items()},
        "note": "Sessions evaluated separately — never mixed",
    }


def compute_regime_analytics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-regime performance; regimes never mixed."""
    regimes = ("trend", "range", "high_volatility", "low_volatility", "news")
    buckets: dict[str, list[dict[str, Any]]] = {r: [] for r in regimes}
    unlabeled = 0
    for t in trades:
        raw = str(t.get("regime") or t.get("market_regime") or "").lower().strip()
        aliases = {
            "trending": "trend",
            "ranging": "range",
            "hv": "high_volatility",
            "high_vol": "high_volatility",
            "lv": "low_volatility",
            "low_vol": "low_volatility",
            "news_driven": "news",
        }
        key = aliases.get(raw, raw)
        if key in buckets:
            buckets[key].append(t)
        else:
            unlabeled += 1

    return {
        "status": "available" if trades else "unavailable",
        "regimes": {k: _bucket_stats(v) for k, v in buckets.items()},
        "unlabeled_trades": unlabeled,
        "note": "Regimes evaluated separately — never mixed; unlabeled excluded",
    }
