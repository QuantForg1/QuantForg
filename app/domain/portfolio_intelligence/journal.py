"""Trade journal analytics from real deal / trade rows only."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any


def _session(hour_utc: int) -> str:
    if 0 <= hour_utc < 7:
        return "asia"
    if 7 <= hour_utc < 12:
        return "london"
    if 12 <= hour_utc < 17:
        return "new_york_overlap"
    if 17 <= hour_utc < 21:
        return "new_york"
    return "off_hours"


def _parse_time(raw: str | datetime | None) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def analyze_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze closed-trade style rows: profit, symbol, side, times."""
    if not trades:
        return {
            "status": "unavailable",
            "reason": "No historical trades/deals available",
            "data_source": "history_deals|paper_trades",
            "metrics": {},
            "rankings": {},
        }

    wins = 0
    losses = 0
    by_symbol: dict[str, list[float]] = defaultdict(list)
    by_session: dict[str, list[float]] = defaultdict(list)
    hold_hours: list[float] = []
    rr_samples: list[float] = []

    for t in trades:
        pnl = float(t.get("profit") or t.get("pnl") or 0.0)
        symbol = str(t.get("symbol") or "UNK").upper()
        by_symbol[symbol].append(pnl)
        ts = _parse_time(t.get("time") or t.get("closed_at") or t.get("opened_at"))
        if ts is not None:
            by_session[_session(ts.utctimetuple().tm_hour)].append(pnl)
        opened = _parse_time(t.get("opened_at"))
        closed = _parse_time(t.get("closed_at") or t.get("time"))
        if opened and closed and closed >= opened:
            hold_hours.append((closed - opened).total_seconds() / 3600.0)
        risk = t.get("risk") or t.get("stop_distance_pnl")
        reward = t.get("reward")
        if risk is not None and reward is not None:
            try:
                r = float(risk)
                if r != 0:
                    rr_samples.append(float(reward) / abs(r))
            except (TypeError, ValueError):
                pass
        if pnl > 0:
            wins += 1
        elif pnl < 0:
            losses += 1

    total = wins + losses
    symbol_net = {s: sum(v) for s, v in by_symbol.items()}
    session_net = {s: sum(v) for s, v in by_session.items()}
    best_symbols = sorted(symbol_net.items(), key=lambda x: x[1], reverse=True)[:5]
    worst_symbols = sorted(symbol_net.items(), key=lambda x: x[1])[:5]
    best_sessions = sorted(session_net.items(), key=lambda x: x[1], reverse=True)
    worst_sessions = sorted(session_net.items(), key=lambda x: x[1])

    avg_hold = sum(hold_hours) / len(hold_hours) if hold_hours else None
    avg_rr = sum(rr_samples) / len(rr_samples) if rr_samples else None

    return {
        "status": "available",
        "data_source": "history_deals|paper_trades",
        "trade_count": len(trades),
        "metrics": {
            "win_rate": round(wins / total, 4) if total else None,
            "loss_rate": round(losses / total, 4) if total else None,
            "average_hold_hours": (
                round(avg_hold, 4) if avg_hold is not None else None
            ),
            "average_rr": round(avg_rr, 4) if avg_rr is not None else None,
            "hold_time_sample_size": len(hold_hours),
            "rr_sample_size": len(rr_samples),
            "rr_note": (
                None
                if rr_samples
                else "Average RR unavailable — trades lack risk/reward fields"
            ),
        },
        "rankings": {
            "best_symbols": [
                {"symbol": s, "net_pnl": round(v, 4)} for s, v in best_symbols
            ],
            "worst_symbols": [
                {"symbol": s, "net_pnl": round(v, 4)} for s, v in worst_symbols
            ],
            "best_sessions": [
                {"session": s, "net_pnl": round(v, 4)} for s, v in best_sessions
            ],
            "worst_sessions": [
                {"session": s, "net_pnl": round(v, 4)} for s, v in worst_sessions
            ],
        },
    }
