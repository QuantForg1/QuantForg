"""Strategy Intelligence Center — read-only post-trade intelligence.

Analyzes completed XAUUSD trades (MT5 deals paired into round-trips) and
optionally soft-joins Strategy Diagnostics context (MTF / Quality /
Confluence / ATR / spread).

Never modifies Strategy, Risk, Safety, OMS, Thresholds, or Auto Trading.
Never auto-optimizes. Advisory only.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from statistics import mean
from typing import Any

from app.domain.institutional_trading.session_filter import classify_session_utc
from app.domain.trading.gold_only import GOLD_SYMBOL
from app.domain.trading.xauusd_specs import CONTRACT_SIZE

ATR_STOP_MULT = Decimal("1.5")
ATR_HIGH_PCT = Decimal("1.5")
ATR_LOW_PCT = Decimal("0.4")
JOIN_WINDOW_SEC = 900
MIN_BUCKET = 2


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _i(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=UTC)
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def pair_deals_into_closed_trades(
    deals: list[dict[str, Any]],
    *,
    symbol: str = GOLD_SYMBOL,
) -> list[dict[str, Any]]:
    """Pair MT5 entry/exit deals by position_id into closed trades."""
    sym = symbol.upper()
    rows: list[dict[str, Any]] = []
    for raw in deals:
        d = _as_dict(raw)
        s = str(d.get("symbol") or "").upper()
        if s and s != sym:
            continue
        ticket = _i(d.get("ticket"))
        if not ticket:
            continue
        t = _parse_ts(d.get("time") or d.get("time_msc") or d.get("timestamp"))
        if t is None:
            continue
        rows.append(
            {
                "ticket": ticket,
                "position_id": _i(d.get("position_id")) or 0,
                "symbol": s or sym,
                "side": str(d.get("side") or "buy").lower(),
                "volume": _f(d.get("volume")) or 0.0,
                "price": _f(d.get("price")) or 0.0,
                "profit": _f(d.get("profit")) or 0.0,
                "commission": _f(d.get("commission")) or 0.0,
                "swap": _f(d.get("swap")) or 0.0,
                "deal_type": str(d.get("deal_type") or "").lower(),
                "time": t,
                "comment": str(d.get("comment") or ""),
                "magic": _i(d.get("magic")) or 0,
            }
        )
    rows.sort(key=lambda r: r["time"])

    by_pos: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r["position_id"] > 0:
            by_pos[int(r["position_id"])].append(r)

    closed: list[dict[str, Any]] = []
    for pos_id, group in by_pos.items():
        entries = [
            g
            for g in group
            if "in" in g["deal_type"] and "out" not in g["deal_type"]
        ]
        exits = [g for g in group if "out" in g["deal_type"]]
        if not entries:
            entries = [group[0]]
        if not exits and len(group) >= 2:
            exits = [group[-1]]
        if not entries or not exits:
            continue
        entry = entries[0]
        exit_d = exits[-1]
        net = sum(g["profit"] + g["commission"] + g["swap"] for g in group)
        hold_ms = max(
            0.0, (exit_d["time"] - entry["time"]).total_seconds() * 1000.0
        )
        closed.append(
            {
                "id": f"pos-{pos_id}",
                "position_id": pos_id,
                "symbol": entry["symbol"],
                "side": entry["side"],
                "volume": entry["volume"],
                "entry": entry["price"],
                "exit": exit_d["price"],
                "entry_time": entry["time"].isoformat(),
                "exit_time": exit_d["time"].isoformat(),
                "holding_time_sec": round(hold_ms / 1000.0, 1),
                "profit_loss": round(net, 2),
                "entry_ticket": entry["ticket"],
                "exit_ticket": exit_d["ticket"],
                "comment": entry.get("comment") or "",
                "status": "closed",
            }
        )
    closed.sort(key=lambda t: t["exit_time"], reverse=True)
    return closed


def classify_volatility_flags(
    *,
    atr: float | None,
    mid: float | None,
) -> dict[str, bool]:
    high = low = False
    if atr is not None and mid is not None and mid > 0 and atr > 0:
        pct = Decimal(str(atr)) / Decimal(str(mid)) * Decimal("100")
        high = pct >= ATR_HIGH_PCT
        low = pct <= ATR_LOW_PCT
    return {
        "high_volatility": high,
        "low_volatility": low,
        "normal_volatility": (not high and not low) if atr is not None else False,
    }


def classify_structure_flags(
    *,
    mtf_aligned: bool | None,
    mtf_score: int | None,
) -> dict[str, bool]:
    trending = bool(mtf_aligned) or (mtf_score is not None and mtf_score >= 70)
    known = mtf_score is not None or mtf_aligned is not None
    return {
        "trending": trending,
        "ranging": (not trending) if known else False,
    }


def _join_diagnostics(
    trade: dict[str, Any],
    cycles: list[dict[str, Any]],
) -> dict[str, Any]:
    entry_ts = _parse_ts(trade.get("entry_time"))
    if entry_ts is None or not cycles:
        return {}
    best = None
    best_score: float | None = None
    for c in cycles:
        cts = _parse_ts(c.get("recorded_at"))
        if cts is None:
            continue
        action = str(c.get("decision_action") or "").upper()
        executed = bool(c.get("executed") or c.get("forwarded_to_oms"))
        weight = 2 if (executed or action in {"BUY", "SELL"}) else 1
        delta = abs((cts - entry_ts).total_seconds())
        if delta > JOIN_WINDOW_SEC:
            continue
        score = delta - weight * 60
        if best_score is None or score < best_score:
            best_score = score
            best = c
    if best is None:
        return {}
    trend = _as_dict(best.get("trend"))
    quality = _as_dict(best.get("quality"))
    confluence = _as_dict(best.get("confluence"))
    sizing = _as_dict(best.get("sizing"))
    atr = _f(best.get("atr") or sizing.get("atr"))
    spread = _f(
        best.get("spread")
        or _as_dict(best.get("market_context_diagnostics")).get("spread")
    )
    return {
        "market_session": best.get("market_session"),
        "mtf_score": _i(trend.get("score")),
        "mtf_aligned": trend.get("aligned"),
        "quality": _i(quality.get("score")),
        "confluence": _i(confluence.get("total")),
        "atr": atr,
        "spread": spread,
        "stop_distance": _f(
            best.get("stop_distance") or sizing.get("stop_distance")
        ),
        "diagnostics_signal_id": best.get("signal_id"),
        "mid_price": _f(trade.get("entry")),
    }


def enrich_trade(
    trade: dict[str, Any],
    *,
    cycles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Attach session / regime / context fields to one closed trade."""
    row = dict(trade)
    join = _join_diagnostics(row, cycles or [])
    entry_ts = _parse_ts(row.get("entry_time"))
    session = join.get("market_session") or row.get("market_session")
    if not session and entry_ts is not None:
        session = classify_session_utc(entry_ts).value

    mtf = _i(join.get("mtf_score") if join else row.get("mtf_score"))
    if mtf is None:
        mtf = _i(row.get("mtf_score"))
    aligned = join.get("mtf_aligned") if join else row.get("mtf_aligned")
    quality = _i(join.get("quality") if join else row.get("quality"))
    if quality is None:
        quality = _i(row.get("quality"))
    confluence = _i(join.get("confluence") if join else row.get("confluence"))
    if confluence is None:
        confluence = _i(row.get("confluence"))
    atr = _f(join.get("atr") if join else row.get("atr"))
    if atr is None:
        atr = _f(row.get("atr"))
    spread = _f(join.get("spread") if join else row.get("spread"))
    if spread is None:
        spread = _f(row.get("spread"))
    mid = _f(join.get("mid_price") if join else row.get("entry"))
    stop = _f(join.get("stop_distance") if join else row.get("stop_distance"))
    if stop is None:
        stop = _f(row.get("stop_distance"))

    struct = classify_structure_flags(
        mtf_aligned=aligned if isinstance(aligned, bool) else None,
        mtf_score=mtf,
    )
    vol = classify_volatility_flags(atr=atr, mid=mid)

    if vol["high_volatility"]:
        regime = "high_volatility"
    elif vol["low_volatility"]:
        regime = "low_volatility"
    elif struct["trending"]:
        regime = "trending"
    elif struct["ranging"]:
        regime = "ranging"
    else:
        regime = "unknown"

    rr = _f(row.get("risk_reward"))
    pnl = _f(row.get("profit_loss")) or 0.0
    vol_lots = _f(row.get("volume")) or 0.0
    if rr is None and stop and stop > 0 and vol_lots > 0:
        dollar_risk = float(
            Decimal(str(vol_lots)) * Decimal(str(stop)) * CONTRACT_SIZE
        )
        if dollar_risk > 0:
            rr = round(pnl / dollar_risk, 3)
    elif rr is None and atr and atr > 0 and vol_lots > 0:
        stop_est = float(Decimal(str(atr)) * ATR_STOP_MULT)
        dollar_risk = float(
            Decimal(str(vol_lots)) * Decimal(str(stop_est)) * CONTRACT_SIZE
        )
        if dollar_risk > 0:
            rr = round(pnl / dollar_risk, 3)

    dow = entry_ts.strftime("%A") if entry_ts else row.get("day_of_week")

    row.update(
        {
            "market_session": session,
            "market_regime": regime,
            "trending": struct["trending"],
            "ranging": struct["ranging"],
            "high_volatility": vol["high_volatility"],
            "low_volatility": vol["low_volatility"],
            "mtf_score": mtf,
            "quality": quality,
            "confluence": confluence,
            "atr": atr,
            "spread": spread,
            "risk_reward": rr,
            "day_of_week": dow,
            "win": pnl > 0,
            "loss": pnl < 0,
            "context_joined": bool(join),
        }
    )
    return row


def _best_worst_bucket(
    trades: list[dict[str, Any]],
    key: str,
) -> tuple[str | None, str | None, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        k = t.get(key)
        if k is None or k == "" or k == "unknown":
            continue
        buckets[str(k)].append(t)
    stats: dict[str, Any] = {}
    for name, rows in buckets.items():
        if len(rows) < MIN_BUCKET:
            continue
        wins = sum(1 for r in rows if r.get("win"))
        pnls = [_f(r.get("profit_loss")) or 0.0 for r in rows]
        wr = wins / len(rows)
        stats[name] = {
            "count": len(rows),
            "wins": wins,
            "win_rate": round(wr * 100, 1),
            "avg_pnl": round(mean(pnls), 2) if pnls else 0.0,
            "total_pnl": round(sum(pnls), 2),
        }
    if not stats:
        return None, None, {}
    best = max(
        stats.items(),
        key=lambda kv: (kv[1]["win_rate"], kv[1]["avg_pnl"]),
    )[0]
    worst = min(
        stats.items(),
        key=lambda kv: (kv[1]["win_rate"], kv[1]["avg_pnl"]),
    )[0]
    return best, worst, stats


def _range_label(lo: float, hi: float) -> str:
    return f"{lo:.2f}–{hi:.2f}"


def _best_worst_numeric_range(
    trades: list[dict[str, Any]],
    field: str,
    *,
    bins: int = 4,
) -> tuple[str | None, str | None, dict[str, Any]]:
    vals = [(_f(t.get(field)), t) for t in trades]
    vals = [(v, t) for v, t in vals if v is not None]
    if len(vals) < MIN_BUCKET * 2:
        return None, None, {}
    numbers = sorted(v for v, _ in vals)
    lo, hi = numbers[0], numbers[-1]
    if hi <= lo:
        return None, None, {}
    width = (hi - lo) / bins
    bucket_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for v, t in vals:
        idx = min(bins - 1, int((v - lo) / width)) if width > 0 else 0
        a = lo + idx * width
        b = lo + (idx + 1) * width
        label = _range_label(a, b)
        bucket_rows[label].append(t)
    stats: dict[str, Any] = {}
    for label, rows in bucket_rows.items():
        if len(rows) < MIN_BUCKET:
            continue
        wins = sum(1 for r in rows if r.get("win"))
        pnls = [_f(r.get("profit_loss")) or 0.0 for r in rows]
        stats[label] = {
            "count": len(rows),
            "win_rate": round(100.0 * wins / len(rows), 1),
            "avg_pnl": round(mean(pnls), 2),
        }
    if not stats:
        return None, None, {}
    best = max(stats.items(), key=lambda kv: (kv[1]["win_rate"], kv[1]["avg_pnl"]))[0]
    worst = min(stats.items(), key=lambda kv: (kv[1]["win_rate"], kv[1]["avg_pnl"]))[0]
    return best, worst, stats


def discover_patterns(trades: list[dict[str, Any]]) -> dict[str, Any]:
    wins = [t for t in trades if t.get("win")]
    losses = [t for t in trades if t.get("loss")]

    def floors(rows: list[dict[str, Any]], field: str) -> float | None:
        xs = sorted(
            x
            for x in (_f(r.get(field)) for r in rows)
            if x is not None
        )
        if len(xs) < MIN_BUCKET:
            return None
        return round(_percentile(xs, 0.25) or xs[0], 1)

    def band(rows: list[dict[str, Any]], field: str) -> tuple[float, float] | None:
        xs = sorted(
            x
            for x in (_f(r.get(field)) for r in rows)
            if x is not None
        )
        if len(xs) < MIN_BUCKET:
            return None
        lo = _percentile(xs, 0.25)
        hi = _percentile(xs, 0.75)
        if lo is None or hi is None:
            return None
        return (round(lo, 2), round(hi, 2))

    win_cond: list[str] = []
    lose_cond: list[str] = []

    w_mtf = floors(wins, "mtf_score")
    w_q = floors(wins, "quality")
    w_c = floors(wins, "confluence")
    w_atr = band(wins, "atr")
    w_sp = band(wins, "spread")
    if w_mtf is not None:
        win_cond.append(f"MTF >= {w_mtf:.0f}")
    if w_q is not None:
        win_cond.append(f"Quality >= {w_q:.0f}")
    if w_c is not None:
        win_cond.append(f"Confluence >= {w_c:.0f}")
    if w_atr is not None:
        win_cond.append(f"ATR between {w_atr[0]} and {w_atr[1]}")
    if w_sp is not None:
        win_cond.append(f"Spread below {w_sp[1]}")

    range_share = (
        sum(1 for t in losses if t.get("ranging")) / len(losses) if losses else 0.0
    )
    if range_share >= 0.5 and losses:
        lose_cond.append("Range markets")
    l_atr = band(losses, "atr")
    if l_atr is not None:
        lose_cond.append(f"ATR above {l_atr[0]}")
    l_sp = band(losses, "spread")
    if l_sp is not None:
        lose_cond.append(f"Spread above {l_sp[0]}")

    return {
        "winning_trades_usually_occur_when": win_cond,
        "losing_trades_usually_occur_when": lose_cond,
        "winning_floors": {
            "mtf": w_mtf,
            "quality": w_q,
            "confluence": w_c,
            "atr_band": list(w_atr) if w_atr else None,
            "spread_below": w_sp[1] if w_sp else None,
        },
        "losing_flags": {
            "range_share_pct": round(range_share * 100, 1) if losses else None,
            "atr_band": list(l_atr) if l_atr else None,
            "spread_above": l_sp[0] if l_sp else None,
        },
        "sample_wins": len(wins),
        "sample_losses": len(losses),
    }


def _fmt_hold(sec: float) -> str:
    if sec < 60:
        return f"{sec:.0f}s"
    if sec < 3600:
        return f"{sec / 60:.1f} min"
    return f"{sec / 3600:.1f} hours"


def generate_intelligence(trades: list[dict[str, Any]]) -> dict[str, Any]:
    best_sess, worst_sess, sess_stats = _best_worst_bucket(trades, "market_session")
    best_dow, worst_dow, dow_stats = _best_worst_bucket(trades, "day_of_week")
    best_vol, worst_vol, vol_stats = _best_worst_bucket(trades, "market_regime")
    best_atr, worst_atr, atr_stats = _best_worst_numeric_range(trades, "atr")
    best_sp, worst_sp, sp_stats = _best_worst_numeric_range(trades, "spread")

    holds = [h for h in (_f(t.get("holding_time_sec")) for t in trades) if h is not None]
    win_rr = [
        x
        for x in (
            _f(t.get("risk_reward"))
            for t in trades
            if t.get("win")
        )
        if x is not None
    ]
    lose_rr = [
        x
        for x in (
            _f(t.get("risk_reward"))
            for t in trades
            if t.get("loss")
        )
        if x is not None
    ]

    return {
        "best_trading_session": best_sess,
        "worst_trading_session": worst_sess,
        "best_day_of_week": best_dow,
        "worst_day_of_week": worst_dow,
        "best_volatility_range": best_vol,
        "worst_volatility_range": worst_vol,
        "best_atr_range": best_atr,
        "worst_atr_range": worst_atr,
        "best_spread_range": best_sp,
        "worst_spread_range": worst_sp,
        "average_holding_time_sec": round(mean(holds), 1) if holds else None,
        "average_holding_time_display": (
            _fmt_hold(mean(holds)) if holds else None
        ),
        "average_winning_rr": round(mean(win_rr), 2) if win_rr else None,
        "average_losing_rr": round(mean(lose_rr), 2) if lose_rr else None,
        "bucket_stats": {
            "session": sess_stats,
            "day_of_week": dow_stats,
            "volatility_regime": vol_stats,
            "atr": atr_stats,
            "spread": sp_stats,
        },
    }


def score_current_market(
    *,
    current: dict[str, Any] | None,
    intelligence: dict[str, Any],
    patterns: dict[str, Any],
) -> dict[str, Any]:
    """0–100 Strategy Intelligence Score vs historically profitable conditions."""
    if not current:
        return {
            "score": None,
            "level": "YELLOW",
            "label": "Neutral",
            "reasons": ["No current market snapshot"],
            "insufficient_history": True,
        }

    floors = _as_dict(patterns.get("winning_floors"))
    points = 0
    max_points = 0
    reasons: list[str] = []

    def add(ok: bool | None, weight: int, detail: str) -> None:
        nonlocal points, max_points
        max_points += weight
        if ok is True:
            points += weight
            reasons.append(f"+ {detail}")
        elif ok is False:
            reasons.append(f"- {detail}")
        else:
            reasons.append(f". {detail} (unknown)")

    sess = str(current.get("market_session") or "")
    best_sess = intelligence.get("best_trading_session")
    if best_sess:
        add(sess == best_sess, 20, f"Session {sess or '-'} vs best {best_sess}")

    mtf = _i(current.get("mtf_score"))
    mtf_floor = _f(floors.get("mtf"))
    if mtf_floor is not None:
        add(
            mtf is not None and mtf >= mtf_floor,
            20,
            f"MTF {mtf if mtf is not None else '-'} >= {mtf_floor:.0f}",
        )

    q = _i(current.get("quality"))
    q_floor = _f(floors.get("quality"))
    if q_floor is not None:
        add(
            q is not None and q >= q_floor,
            20,
            f"Quality {q if q is not None else '-'} >= {q_floor:.0f}",
        )

    c = _i(current.get("confluence"))
    c_floor = _f(floors.get("confluence"))
    if c_floor is not None:
        add(
            c is not None and c >= c_floor,
            20,
            f"Confluence {c if c is not None else '-'} >= {c_floor:.0f}",
        )

    atr = _f(current.get("atr"))
    atr_band = floors.get("atr_band")
    if isinstance(atr_band, list) and len(atr_band) == 2:
        lo, hi = float(atr_band[0]), float(atr_band[1])
        add(
            atr is not None and lo <= atr <= hi,
            10,
            f"ATR {atr if atr is not None else '-'} in {lo}-{hi}",
        )

    spread = _f(current.get("spread"))
    sp_ceil = _f(floors.get("spread_below"))
    if sp_ceil is not None:
        add(
            spread is not None and spread <= sp_ceil,
            10,
            f"Spread {spread if spread is not None else '-'} <= {sp_ceil}",
        )

    if max_points == 0:
        return {
            "score": None,
            "level": "YELLOW",
            "label": "Neutral",
            "reasons": ["Insufficient enriched trade history for scoring"],
            "insufficient_history": True,
        }

    score = int(round(100.0 * points / max_points))
    if score >= 70:
        level, label = "GREEN", "Historically Favorable"
    elif score >= 40:
        level, label = "YELLOW", "Neutral"
    else:
        level, label = "RED", "Historically Unfavorable"

    return {
        "score": score,
        "level": level,
        "label": label,
        "reasons": reasons,
        "points": points,
        "max_points": max_points,
        "insufficient_history": False,
        "never_auto_optimizes": True,
    }


def current_market_from_cycle(cycle: dict[str, Any] | None) -> dict[str, Any] | None:
    if not cycle:
        return None
    trend = _as_dict(cycle.get("trend"))
    quality = _as_dict(cycle.get("quality"))
    confluence = _as_dict(cycle.get("confluence"))
    sizing = _as_dict(cycle.get("sizing"))
    return {
        "market_session": cycle.get("market_session"),
        "mtf_score": _i(trend.get("score")),
        "quality": _i(quality.get("score")),
        "confluence": _i(confluence.get("total")),
        "atr": _f(cycle.get("atr") or sizing.get("atr")),
        "spread": _f(
            cycle.get("spread")
            or _as_dict(cycle.get("market_context_diagnostics")).get("spread")
        ),
        "recorded_at": cycle.get("recorded_at"),
    }


def analyze_trades(
    closed_trades: list[dict[str, Any]],
    *,
    cycles: list[dict[str, Any]] | None = None,
    current_cycle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Core read-only analysis entrypoint (unit-testable without gateway)."""
    enriched = [enrich_trade(t, cycles=cycles) for t in closed_trades]
    intelligence = generate_intelligence(enriched)
    patterns = discover_patterns(enriched)
    current = current_market_from_cycle(current_cycle)
    score = score_current_market(
        current=current, intelligence=intelligence, patterns=patterns
    )
    wins = sum(1 for t in enriched if t.get("win"))
    losses = sum(1 for t in enriched if t.get("loss"))
    return {
        "schema_version": "1.0.0",
        "mode": "strategy_intelligence_center",
        "mutates_engines": False,
        "never_modifies_strategy_risk_safety_oms_thresholds_auto_trading": True,
        "never_auto_optimizes": True,
        "advisory_only": True,
        "trade_count": len(enriched),
        "wins": wins,
        "losses": losses,
        "trades": enriched[:100],
        "intelligence": intelligence,
        "patterns": patterns,
        "strategy_intelligence_score": score,
        "current_market": current,
    }


def _load_history_deals(days: int = 90) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    meta: dict[str, Any] = {"attempted": True, "ok": False, "days": days}
    deals: list[dict[str, Any]] = []

    def _normalize(rows: list[Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for r in rows:
            if hasattr(r, "to_dict"):
                out.append(dict(r.to_dict()))  # type: ignore[arg-type]
            elif isinstance(r, dict):
                out.append(r)
        return out

    try:
        from core.di.container import get_container

        adapter = getattr(get_container(), "mt5_adapter", None)
        if adapter is not None:
            date_to = datetime.now(UTC)
            date_from = date_to - timedelta(days=days)
            raw = adapter.history_deals(date_from=date_from, date_to=date_to)
            deals = _normalize(list(raw or []))
            meta["ok"] = True
            meta["via"] = "di_adapter"
            meta["raw_count"] = len(deals)
            return deals, meta
    except Exception as exc:  # noqa: BLE001
        meta["di_error"] = str(exc)[:200]

    try:
        import os
        from pathlib import Path

        from dotenv import load_dotenv

        load_dotenv(Path.cwd() / ".env")
        token = (os.getenv("MT5_GATEWAY_TOKEN") or "").strip()
        base = (
            os.getenv("MT5_GATEWAY_URL")
            or os.getenv("MT5_GATEWAY_BASE_URL")
            or "http://127.0.0.1:8765"
        )
        if token:
            from app.infrastructure.brokers.mt5.gateway_client import (
                GatewayMT5Client,
            )

            client = GatewayMT5Client(base_url=base, token=token)
            if client.adopt_existing_session():
                raw = client.history_deals(days=days)
                deals = _normalize(list(raw or []))
                meta["ok"] = True
                meta["via"] = "local_gateway"
                meta["raw_count"] = len(deals)
                return deals, meta
            meta["adopt_failed"] = True
    except Exception as exc:  # noqa: BLE001
        meta["gateway_error"] = str(exc)[:200]

    return deals, meta


def build_strategy_intelligence_center(
    *,
    days: int = 90,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ops payload: live deals + diagnostics soft-join (read-only)."""
    deals, deal_meta = _load_history_deals(days=days)
    closed = pair_deals_into_closed_trades(deals)

    cycles: list[dict[str, Any]] = []
    current_cycle: dict[str, Any] | None = None
    if diagnostics:
        cycles = list(diagnostics.get("cycles") or [])
        latest = cycles[0] if cycles else diagnostics.get("latest")
        current_cycle = latest if isinstance(latest, dict) else None
    else:
        try:
            from app.application.services.strategy_diagnostics import (
                get_strategy_diagnostics_store,
            )

            snap = get_strategy_diagnostics_store().snapshot(limit=100)
            cycles = list(snap.get("cycles") or [])
            current_cycle = cycles[0] if cycles else None
        except Exception:
            cycles = []
            current_cycle = None

    payload = analyze_trades(
        closed, cycles=cycles, current_cycle=current_cycle
    )
    payload["deal_source"] = deal_meta
    payload["diagnostics_cycles_joined"] = len(cycles)
    payload["observed_at"] = datetime.now(UTC).isoformat()

    # Soft-integrate Market Regime Intelligence (read-only; never influences execution).
    try:
        from app.application.services.market_regime_intelligence import (
            regime_summary_for_sic,
        )

        payload["market_regime_intelligence"] = regime_summary_for_sic(
            diagnostics=diagnostics
            or {"cycles": cycles, "latest": current_cycle},
            trades=list(payload.get("trades") or []),
        )
    except Exception:
        payload["market_regime_intelligence"] = {
            "advisory_only": True,
            "status": "unavailable",
        }

    return payload
