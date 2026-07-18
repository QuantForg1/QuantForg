"""Quant AI — portfolio & journal intelligence from real deal/history rows."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
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
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def analyze_portfolio_ai(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Win/loss, RR, expectancy, sessions, symbols — only from supplied rows."""
    if not trades:
        return {
            "status": "unavailable",
            "reason": "No closed trades / deals available",
            "data_source": "history_deals|paper_trades",
            "metrics": {},
            "autonomous_trading": False,
        }

    pnls = [
        _f(t.get("pnl") or t.get("profit") or t.get("realized_pnl")) for t in trades
    ]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    n = len(pnls)
    win_rate = len(wins) / n if n else None
    loss_rate = len(losses) / n if n else None
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    avg_rr = (avg_win / avg_loss) if avg_loss > 0 else None
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None
    expectancy = (
        (win_rate * avg_win - (1 - win_rate) * avg_loss)
        if win_rate is not None
        else None
    )

    # Drawdown from equity curve of cumulative pnl
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    by_symbol: dict[str, float] = defaultdict(float)
    by_hour: Counter[int] = Counter()
    by_dow: Counter[int] = Counter()
    hour_pnl: dict[int, float] = defaultdict(float)
    day_pnl: dict[int, float] = defaultdict(float)
    for t, p in zip(trades, pnls, strict=False):
        sym = str(t.get("symbol") or "UNK").upper()
        by_symbol[sym] += p
        ts = _parse_ts(t.get("closed_at") or t.get("time") or t.get("opened_at"))
        if ts:
            by_hour[ts.hour] += 1
            by_dow[ts.weekday()] += 1
            hour_pnl[ts.hour] += p
            day_pnl[ts.weekday()] += p

    best_symbols = sorted(by_symbol.items(), key=lambda x: x[1], reverse=True)[:5]
    worst_symbols = sorted(by_symbol.items(), key=lambda x: x[1])[:5]
    best_hours = sorted(hour_pnl.items(), key=lambda x: x[1], reverse=True)[:3]
    worst_hours = sorted(hour_pnl.items(), key=lambda x: x[1])[:3]
    best_days = sorted(day_pnl.items(), key=lambda x: x[1], reverse=True)[:3]
    worst_days = sorted(day_pnl.items(), key=lambda x: x[1])[:3]

    mistakes: list[str] = []
    if win_rate is not None and win_rate < 0.4 and (avg_rr or 0) < 1.2:
        mistakes.append(
            "Win rate below 40% with RR under 1.2 — edge not compensating losers"
        )
    if loss_rate is not None and loss_rate > 0.55:
        mistakes.append("Loss rate elevated — review entries and invalidation")
    if max_dd > 0 and gross_profit > 0 and max_dd > gross_profit * 0.5:
        mistakes.append("Drawdowns consume a large share of gross profit")
    if avg_rr is not None and avg_rr < 1.0:
        mistakes.append("Average win smaller than average loss — asymmetric payoff")
    if not mistakes:
        mistakes.append(
            "No systematic mistake pattern flagged from available trade sample"
        )

    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    return {
        "status": "available",
        "data_source": "history_deals|paper_trades",
        "sample_size": n,
        "metrics": {
            "win_rate": round(win_rate, 4) if win_rate is not None else None,
            "loss_rate": round(loss_rate, 4) if loss_rate is not None else None,
            "average_rr": round(avg_rr, 4) if avg_rr is not None else None,
            "profit_factor": (
                round(profit_factor, 4) if profit_factor is not None else None
            ),
            "expectancy": round(expectancy, 4) if expectancy is not None else None,
            "drawdown": round(max_dd, 4),
            "gross_profit": round(gross_profit, 4),
            "gross_loss": round(gross_loss, 4),
        },
        "best_symbols": [{"symbol": s, "pnl": round(p, 4)} for s, p in best_symbols],
        "worst_symbols": [{"symbol": s, "pnl": round(p, 4)} for s, p in worst_symbols],
        "best_sessions_hours": [
            {"hour_utc": h, "pnl": round(p, 4)} for h, p in best_hours
        ],
        "worst_sessions_hours": [
            {"hour_utc": h, "pnl": round(p, 4)} for h, p in worst_hours
        ],
        "most_profitable_days": [
            {"day": dow_names[d] if 0 <= d < 7 else str(d), "pnl": round(p, 4)}
            for d, p in best_days
        ],
        "least_profitable_days": [
            {"day": dow_names[d] if 0 <= d < 7 else str(d), "pnl": round(p, 4)}
            for d, p in worst_days
        ],
        "most_common_mistakes": mistakes,
        "why": {
            "summary": (
                f"Across {n} trades, win_rate="
                f"{round((win_rate or 0) * 100, 1)}%, expectancy="
                f"{round(expectancy or 0, 2)}"
            ),
            "supporting_factors": mistakes,
        },
        "autonomous_trading": False,
        "advisory_only": True,
    }


def review_trade(trade: dict[str, Any]) -> dict[str, Any]:
    """Per-trade AI review labels from observable fields only."""
    symbol = str(trade.get("symbol") or "").upper()
    if not symbol:
        return {
            "status": "unavailable",
            "reason": "Trade missing symbol",
            "autonomous_trading": False,
        }
    pnl = _f(trade.get("pnl") or trade.get("profit"))
    entry = trade.get("entry_price") or trade.get("open_price") or trade.get("price")
    exit_ = trade.get("exit_price") or trade.get("close_price")
    sl = trade.get("stop_loss") or trade.get("sl")
    trade.get("take_profit") or trade.get("tp")
    labels: list[str] = []
    reasons: list[str] = []

    if pnl > 0:
        labels.append("Positive outcome")
        reasons.append(f"Realized PnL {pnl}")
    elif pnl < 0:
        labels.append("Negative outcome")
        reasons.append(f"Realized PnL {pnl}")
    else:
        labels.append("Flat / breakeven")

    try:
        if entry is not None and exit_ is not None and sl is not None:
            e, x, s = float(entry), float(exit_), float(sl)
            risk = abs(e - s)
            reward = abs(x - e)
            if risk > 0 and reward / risk >= 2:
                labels.append("TP Excellent")
                reasons.append(f"Observed RR ≈ {reward / risk:.2f}")
            if risk > 0 and abs(e - s) / max(abs(e), 1e-9) < 0.0005:
                labels.append("SL Too Tight")
                reasons.append("Stop distance is very tight vs entry")
        if entry is not None and exit_ is not None:
            e, x = float(entry), float(exit_)
            if pnl < 0 and abs(x - e) > 0:
                labels.append("Late Exit")
                reasons.append("Loss realized after adverse excursion")
            if pnl > 0:
                labels.append("Good Entry")
                reasons.append("Entry followed by favorable exit")
    except (TypeError, ValueError):
        reasons.append("Price fields incomplete for RR diagnostics")

    risk_used = trade.get("margin_used") or trade.get("volume")
    if risk_used is not None:
        try:
            if float(risk_used) > 0 and pnl < 0:
                labels.append("Risk Too High")
                reasons.append("Loss size relative to position field warrants review")
        except (TypeError, ValueError):
            pass

    if not labels:
        labels.append("Insufficient fields for detailed review")

    return {
        "status": "available",
        "symbol": symbol,
        "side": str(trade.get("side") or "unknown"),
        "pnl": pnl,
        "labels": labels,
        "reasons": reasons,
        "why": {"summary": "; ".join(labels), "supporting_factors": reasons},
        "data_source": "trade_record",
        "autonomous_trading": False,
        "advisory_only": True,
    }
