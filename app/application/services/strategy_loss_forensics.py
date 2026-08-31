"""Matched-only loss forensics. Never infers expectancy from unmatched deals.

Sample-size labels are analytical only and never change trading gates.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean, median
from typing import Any

from app.application.services.strategy_forensic_ledger import (
    STRATEGY_MATCHED,
    UNMATCHED,
    _as_float,
    _as_str,
    _ticket,
    classify_closed_deal,
    list_signals,
    list_submissions,
)

ADVISORY_ONLY = True
INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
EARLY_SIGNAL = "EARLY_SIGNAL"
PRELIMINARY = "PRELIMINARY"
MEANINGFUL_RESEARCH = "MEANINGFUL_RESEARCH"
STRONGER_EVIDENCE = "STRONGER_EVIDENCE"
HIGHER_CONFIDENCE = "HIGHER_CONFIDENCE"
# Backward-compatible aliases (research labels only — never trading gates).
MEANINGFUL = MEANINGFUL_RESEARCH
OBSERVATIONAL = PRELIMINARY
ACTIONABLE_CANDIDATE = MEANINGFUL_RESEARCH
HIGH_CONFIDENCE_CANDIDATE = HIGHER_CONFIDENCE
UNKNOWN = "UNKNOWN"
SUSPECTED = "SUSPECTED"
PROVEN = "PROVEN"
LIKELY = "LIKELY"
POSSIBLE = "POSSIBLE"
REJECTED = "REJECTED"
DISCLAIMER = "Historical data does not guarantee future profitability."

LOSS_DIMENSIONS = (
    "A_DIRECTION",
    "B_BUY_VS_SELL",
    "C_SESSION",
    "D_REGIME",
    "E_OPPORTUNITY_BUCKET",
    "F_EDGE_BUCKET",
    "G_STRUCTURE",
    "H_LIQUIDITY",
    "I_OB",
    "J_FVG",
    "K_BOS",
    "L_CHOCH",
    "M_DISPLACEMENT",
    "N_MOMENTUM",
    "O_TIMING",
    "P_VOLATILITY",
    "Q_RR",
    "R_ENTRY_QUALITY",
    "S_MAE",
    "T_MFE",
    "U_HOLD_TIME",
    "V_EXIT_REASON",
    "W_SPREAD",
    "X_SLIPPAGE",
    "Y_EXECUTION_LATENCY",
    "Z_SETUP_FAMILY",
)

HYPOTHESES = (
    "A_BUY_BIAS",
    "B_SELL_BIAS",
    "C_BAD_ENTRIES",
    "D_LATE_ENTRIES",
    "E_STALE_ZONES",
    "F_WEAK_BOS_CHOCH",
    "G_FALSE_BREAKOUT",
    "H_RANGE_MARKET_ENTRIES",
    "I_NEWS_ENTRIES",
    "J_POOR_RR",
    "K_PREMATURE_TP",
    "L_OVERSIZED_SL",
    "M_EXCESSIVE_HOLDING_TIME",
    "N_REPEATED_ENTRIES",
    "O_COOLDOWN_FAILURE",
    "P_SPREAD_EXPANSION",
    "Q_SLIPPAGE",
    "R_EXECUTION_LATENCY",
    "S_M1_NOISE",
    "T_M5_NOISE",
    "U_M15_H1_CONTEXT_MISMATCH",
    "V_CONFLICTING_OB_FVG",
    "W_LIQUIDITY_SWEEP_FAILURE",
    "X_REGIME_TRANSITION",
    "Y_DUPLICATE_SETUP",
    "Z_EXIT_LOGIC",
)


LOSS_CONTRIBUTORS = (
    "direction",
    "entry_timing",
    "structure",
    "liquidity",
    "zone",
    "ob",
    "fvg",
    "displacement",
    "momentum",
    "timing",
    "volatility",
    "session",
    "regime",
    "rr",
    "spread",
    "slippage",
    "exit",
    "holding_time",
    "news",
    "execution",
)

CANONICAL_SESSIONS = (
    "sydney",
    "tokyo",
    "london",
    "london_ny_overlap",
    "new_york",
)
CANONICAL_REGIMES = (
    "TREND",
    "RANGE",
    "BREAKOUT",
    "REVERSAL",
    "NEWS_VOLATILITY",
    "LOW_VOLATILITY",
)


def sample_status(n: int) -> str:
    """Research labels only. Never a trading gate.

    Win-rate display still requires n>=10 so tiny samples cannot manufacture
    an 80–90% figure. n=1–9 is EARLY_SIGNAL; the numeric win rate stays hidden.
    """
    if n <= 0:
        return INSUFFICIENT_SAMPLE
    if n < 10:
        return EARLY_SIGNAL
    if n < 20:
        return PRELIMINARY
    if n < 50:
        return MEANINGFUL_RESEARCH
    if n < 100:
        return STRONGER_EVIDENCE
    return HIGHER_CONFIDENCE


def cause_strength(*, sample_size: int, contradicted: bool = False) -> str:
    """Loss-cause labels. Never PROVEN from n=0 or tiny samples."""
    n = int(sample_size or 0)
    if contradicted:
        return REJECTED
    if n < 20:
        return INSUFFICIENT_SAMPLE
    if n < 50:
        return POSSIBLE
    if n < 100:
        return LIKELY
    return PROVEN


def wilson_interval(wins: int, n: int, z: float = 1.96) -> dict[str, Any]:
    """Wilson score interval for a binomial win rate. Empty samples stay UNKNOWN."""
    if n <= 0:
        return {"low": UNKNOWN, "high": UNKNOWN, "n": 0}
    phat = wins / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (phat + z2 / (2.0 * n)) / denom
    margin = (z / denom) * ((phat * (1.0 - phat) / n) + (z2 / (4.0 * n * n))) ** 0.5
    return {
        "low": round(max(0.0, (center - margin) * 100.0), 2),
        "high": round(min(100.0, (center + margin) * 100.0), 2),
        "n": n,
    }


def format_win_rate(rate: Any, n: int, *, status: str | None = None) -> str:
    label = status or sample_status(n)
    if n < 10 or label == INSUFFICIENT_SAMPLE or rate in {None, UNKNOWN, ""}:
        return f"INSUFFICIENT SAMPLE n={n}"
    return f"{rate}% n={n}"


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _r_multiple(trade: dict[str, Any]) -> float | None:
    explicit = _as_float(trade.get("R_multiple") or trade.get("risk_reward"))
    if explicit is not None:
        return explicit
    return None


def _metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(trades)
    status = sample_status(n)
    empty = {
        "sample_size": n,
        "status": status,
        "TOTAL_TRADES": n,
        "BUY_TRADES": 0,
        "SELL_TRADES": 0,
        "WIN_RATE": UNKNOWN if n == 0 else None,
        "WIN_RATE_DISPLAY": f"INSUFFICIENT SAMPLE n={n}",
        "WIN_RATE_CI": {"low": UNKNOWN, "high": UNKNOWN, "n": n},
        "WIN_COUNT": 0,
        "LOSS_COUNT": 0,
        "LOSS_RATE": UNKNOWN if n == 0 else None,
        "EXPECTANCY": UNKNOWN if n == 0 else None,
        "PROFIT_FACTOR": UNKNOWN if n == 0 else None,
        "AVERAGE_WIN": UNKNOWN if n == 0 else None,
        "AVERAGE_LOSS": UNKNOWN if n == 0 else None,
        "AVERAGE_R": UNKNOWN if n == 0 else None,
        "MEDIAN_R": UNKNOWN if n == 0 else None,
        "MAX_DRAWDOWN": UNKNOWN if n == 0 else None,
        "MAX_CONSECUTIVE_LOSSES": UNKNOWN if n == 0 else None,
        "MAX_CONSECUTIVE_WINS": UNKNOWN if n == 0 else None,
        "MFE": UNKNOWN,
        "MAE": UNKNOWN,
        "AVERAGE_HOLD_TIME": UNKNOWN if n == 0 else None,
        "last_profitable_trade": UNKNOWN,
        "last_losing_trade": UNKNOWN,
        "last_profitable_day": UNKNOWN,
        "last_profitable_week": UNKNOWN,
        "last_profitable_session": UNKNOWN,
        "last_profitable_regime": UNKNOWN,
        "last_profitable_setup": UNKNOWN,
        "last_profitable_streak": UNKNOWN,
        "last_losing_streak": UNKNOWN,
        "expectancy_turned_negative_on": UNKNOWN,
        "best_winning_setup": UNKNOWN,
        "worst_losing_setup": UNKNOWN,
        "best_opportunity_bucket": UNKNOWN,
        "best_edge_bucket": UNKNOWN,
        "disclaimer": DISCLAIMER,
    }
    if n == 0:
        return empty

    pnls = [_as_float(t.get("net_pnl") if t.get("net_pnl") is not None else t.get("profit_loss")) or 0.0 for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    rs = [r for r in (_r_multiple(t) for t in trades) if r is not None]
    holds = [
        h
        for h in (_as_float(t.get("holding_time") or t.get("holding_time_sec")) for t in trades)
        if h is not None
    ]
    buy_n = sum(1 for t in trades if str(t.get("direction") or t.get("side") or "").upper() in {"BUY", "LONG"})
    sell_n = sum(1 for t in trades if str(t.get("direction") or t.get("side") or "").upper() in {"SELL", "SHORT"})
    win_n = len(wins)
    loss_n = len(losses)
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor: Any = UNKNOWN
    if gross_loss > 0:
        profit_factor = round(gross_win / gross_loss, 4)
    elif gross_win > 0:
        profit_factor = None
    else:
        profit_factor = 0.0

    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    streak_w = streak_l = max_w = max_l = 0
    last_win_idx: int | None = None
    last_loss_idx: int | None = None
    turn_neg: str | Any = UNKNOWN
    running_exp = 0.0
    for i, p in enumerate(pnls):
        equity += p
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
        if p > 0:
            streak_w += 1
            streak_l = 0
            max_w = max(max_w, streak_w)
            last_win_idx = i
        elif p < 0:
            streak_l += 1
            streak_w = 0
            max_l = max(max_l, streak_l)
            last_loss_idx = i
        running_exp = equity / (i + 1)
        if running_exp < 0 and turn_neg is UNKNOWN:
            ts = trades[i].get("exit_time") or trades[i].get("timestamp_utc")
            turn_neg = ts or UNKNOWN

    mfes = [v for v in (_as_float(t.get("MFE") or t.get("maximum_favorable_excursion")) for t in trades) if v is not None]
    maes = [v for v in (_as_float(t.get("MAE") or t.get("maximum_adverse_excursion")) for t in trades) if v is not None]

    def _trade_label(idx: int | None) -> Any:
        if idx is None:
            return UNKNOWN
        t = trades[idx]
        return {
            "ticket": t.get("ticket"),
            "exit_time": t.get("exit_time"),
            "net_pnl": t.get("net_pnl") if t.get("net_pnl") is not None else t.get("profit_loss"),
            "direction": t.get("direction") or t.get("side"),
            "setup_state": t.get("setup_state"),
        }

    last_win = trades[last_win_idx] if last_win_idx is not None else None
    win_rate = round(100.0 * win_n / n, 2)
    ci = wilson_interval(win_n, n)
    last_week = UNKNOWN
    if last_win and last_win.get("exit_time"):
        ts = _parse_ts(last_win.get("exit_time"))
        if ts is not None:
            iso = ts.isocalendar()
            last_week = f"{iso.year}-W{iso.week:02d}"
    result = {
        "sample_size": n,
        "status": status,
        "TOTAL_TRADES": n,
        "BUY_TRADES": buy_n,
        "SELL_TRADES": sell_n,
        "WIN_RATE": win_rate,
        "WIN_RATE_DISPLAY": format_win_rate(win_rate, n, status=status),
        "WIN_RATE_CI": ci,
        "WIN_COUNT": win_n,
        "LOSS_COUNT": loss_n,
        "LOSS_RATE": round(100.0 * loss_n / n, 2),
        "EXPECTANCY": round(mean(pnls), 4),
        "PROFIT_FACTOR": profit_factor if profit_factor is not None else UNKNOWN,
        "AVERAGE_WIN": round(mean(wins), 4) if wins else UNKNOWN,
        "AVERAGE_LOSS": round(mean(losses), 4) if losses else UNKNOWN,
        "AVERAGE_R": round(mean(rs), 4) if rs else UNKNOWN,
        "MEDIAN_R": round(median(rs), 4) if rs else UNKNOWN,
        "MAX_DRAWDOWN": round(max_dd, 4),
        "MAX_CONSECUTIVE_LOSSES": max_l,
        "MAX_CONSECUTIVE_WINS": max_w,
        "MFE": round(mean(mfes), 4) if mfes else UNKNOWN,
        "MAE": round(mean(maes), 4) if maes else UNKNOWN,
        "AVERAGE_HOLD_TIME": round(mean(holds), 1) if holds else UNKNOWN,
        "last_profitable_trade": _trade_label(last_win_idx),
        "last_losing_trade": _trade_label(last_loss_idx),
        "last_profitable_day": (
            str(last_win.get("exit_time") or "")[:10] if last_win else UNKNOWN
        ),
        "last_profitable_week": last_week,
        "last_profitable_session": (last_win or {}).get("session") or UNKNOWN,
        "last_profitable_regime": (last_win or {}).get("regime") or UNKNOWN,
        "last_profitable_setup": (last_win or {}).get("setup_state") or UNKNOWN,
        "last_profitable_streak": max_w if max_w else UNKNOWN,
        "last_losing_streak": max_l if last_loss_idx is not None else UNKNOWN,
        "expectancy_turned_negative_on": turn_neg,
        "best_winning_setup": UNKNOWN,
        "worst_losing_setup": UNKNOWN,
        "best_opportunity_bucket": UNKNOWN,
        "best_edge_bucket": UNKNOWN,
        "disclaimer": DISCLAIMER,
        "high_win_rate_without_expectancy_is_not_success": True,
    }
    if n < 10:
        result["WIN_RATE"] = UNKNOWN
        result["LOSS_RATE"] = UNKNOWN
        result["WIN_RATE_DISPLAY"] = format_win_rate(UNKNOWN, n, status=status)
    if profit_factor is None:
        result["PROFIT_FACTOR"] = UNKNOWN
        result["profit_factor_note"] = "undefined_no_losses"
    return result


def _canonical_session(raw: Any) -> str | None:
    t = str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not t:
        return None
    if t in {"sydney", "aest"}:
        return "sydney"
    if t in {"tokyo", "asia", "asia_tokyo", "tyo"}:
        return "tokyo"
    if t in {
        "london_ny_overlap",
        "overlap",
        "london_new_york",
        "london_ny",
        "ny_london",
        "london/ny",
        "london_ny_open",
    }:
        return "london_ny_overlap"
    if t in {"london", "ldn", "uk", "london_open"}:
        return "london"
    if t in {"new_york", "ny", "newyork", "us", "ny_open"}:
        return "new_york"
    return None


def _canonical_regime(raw: Any) -> str | None:
    t = str(raw or "").strip().upper().replace(" ", "_").replace("-", "_")
    if not t:
        return None
    if "NEWS" in t:
        return "NEWS_VOLATILITY"
    if "LOW" in t and "VOL" in t:
        return "LOW_VOLATILITY"
    if "BREAK" in t:
        return "BREAKOUT"
    if "REVERS" in t or "CHOCH" in t:
        return "REVERSAL"
    if "RANGE" in t:
        return "RANGE"
    if "TREND" in t:
        return "TREND"
    return None


def _filled_segments(
    trades: list[dict[str, Any]],
    key: str,
    canonical: tuple[str, ...],
    canonicalize,
) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in canonical}
    extras: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        raw = t.get(key)
        label = canonicalize(raw)
        if label in buckets:
            buckets[label].append(t)
        elif label:
            extras[label].append(t)
        elif _as_str(raw):
            extras[str(raw)].append(t)
    out = {
        name: {**_metrics(rows), "key": key, "bucket": name}
        for name, rows in buckets.items()
    }
    for name, rows in extras.items():
        out[name] = {**_metrics(rows), "key": key, "bucket": name}
    return out


def _segment(trades: list[dict[str, Any]], key: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        label = _as_str(t.get(key))
        if not label:
            continue
        buckets[label].append(t)
    return {
        name: {
            **_metrics(rows),
            "key": key,
            "bucket": name,
        }
        for name, rows in sorted(buckets.items())
    }


def _bucket_numeric(trades: list[dict[str, Any]], field: str, edges: list[tuple[str, float | None, float | None]]) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        v = _as_float(t.get(field))
        if v is None:
            continue
        for name, lo, hi in edges:
            if lo is not None and v < lo:
                continue
            if hi is not None and v >= hi:
                continue
            buckets[name].append(t)
            break
    return {name: _metrics(rows) for name, rows in buckets.items()}


def hypothesis_report(matched: list[dict[str, Any]]) -> dict[str, Any]:
    """Each letter is independent. Never auto-patches trading."""
    n = len(matched)
    status = sample_status(n)
    out: dict[str, Any] = {}
    for name in HYPOTHESES:
        if n < 10:
            verdict = INSUFFICIENT_SAMPLE
        elif n < 20:
            verdict = SUSPECTED
        else:
            verdict = "NOT_PROVEN"
        evidence = "No STRATEGY_MATCHED closed trades." if n == 0 else f"n={n}"
        out[name] = {
            "verdict": verdict,
            "sample_size": n,
            "status": status,
            "evidence": evidence,
            "auto_changes_trading": False,
        }
    if n >= 20:
        buy = [t for t in matched if str(t.get("direction") or "").upper() in {"BUY", "LONG"}]
        sell = [t for t in matched if str(t.get("direction") or "").upper() in {"SELL", "SHORT"}]
        buy_exp = mean([_as_float(t.get("net_pnl")) or 0.0 for t in buy]) if buy else None
        sell_exp = mean([_as_float(t.get("net_pnl")) or 0.0 for t in sell]) if sell else None
        if buy_exp is not None and sell_exp is not None:
            if buy_exp < 0 <= sell_exp:
                out["A_BUY_BIAS"]["verdict"] = SUSPECTED if n < 50 else "NOT_PROVEN"
                out["A_BUY_BIAS"]["evidence"] = f"buy_expectancy={buy_exp:.4f} sell_expectancy={sell_exp:.4f}"
            elif sell_exp < 0 <= buy_exp:
                out["B_SELL_BIAS"]["verdict"] = SUSPECTED if n < 50 else "NOT_PROVEN"
                out["B_SELL_BIAS"]["evidence"] = f"buy_expectancy={buy_exp:.4f} sell_expectancy={sell_exp:.4f}"
            else:
                out["A_BUY_BIAS"]["verdict"] = "CONTRADICTED_BY_DATA" if buy_exp >= 0 else "NOT_PROVEN"
                out["B_SELL_BIAS"]["verdict"] = "CONTRADICTED_BY_DATA" if sell_exp >= 0 else "NOT_PROVEN"
    return out


def classify_loss_contributors(matched: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-factor labels. One or two losing trades are never PROVEN."""
    n = len(matched)
    pnls = [
        _as_float(t.get("net_pnl") if t.get("net_pnl") is not None else t.get("profit_loss")) or 0.0
        for t in matched
    ]
    losses = [t for t, p in zip(matched, pnls, strict=False) if p < 0]
    loss_n = len(losses)
    rs = [r for r in (_r_multiple(t) for t in matched) if r is not None]
    if n < 10 or loss_n < 3:
        classification = INSUFFICIENT_SAMPLE
    elif n < 50:
        classification = SUSPECTED
    else:
        classification = UNKNOWN
    out: dict[str, Any] = {}
    for name in LOSS_CONTRIBUTORS:
        out[name] = {
            "factor": name,
            "sample_size": n,
            "loss_count": loss_n,
            "loss_rate": UNKNOWN if n < 10 else round(100.0 * loss_n / n, 2),
            "average_R": UNKNOWN if not rs else round(mean(rs), 4),
            "expectancy": UNKNOWN if n < 10 else round(mean(pnls), 4) if pnls else UNKNOWN,
            "confidence": sample_status(n),
            "classification": classification,
            "verdict": classification,
            "status": sample_status(n),
            "never_from_single_trade": True,
            "never_proven_from_one_or_two_trades": True,
        }
    return {
        "contributors": out,
        "proven_loss_cause": INSUFFICIENT_SAMPLE if n < 50 else "NOT_PROVEN",
        "strength": cause_strength(sample_size=n),
        "never_proven_below_n_50": True,
        "disclaimer": DISCLAIMER,
    }


def classify_exit_path(trade: dict[str, Any]) -> dict[str, Any]:
    """Separate gave-back-MFE losses from immediate adverse moves. Advisory only."""
    pnl = _as_float(trade.get("net_pnl") if trade.get("net_pnl") is not None else trade.get("profit_loss"))
    mae = _as_float(trade.get("MAE") or trade.get("maximum_adverse_excursion"))
    mfe = _as_float(trade.get("MFE") or trade.get("maximum_favorable_excursion"))
    if pnl is None:
        return {
            "exit_class": UNKNOWN,
            "mae": mae,
            "mfe": mfe,
            "hypothesis": INSUFFICIENT_SAMPLE,
        }
    if pnl >= 0:
        return {"exit_class": "WINNER", "mae": mae, "mfe": mfe, "hypothesis": None}
    if mfe is None and mae is None:
        return {
            "exit_class": UNKNOWN,
            "mae": mae,
            "mfe": mfe,
            "hypothesis": "no_mae_mfe_path",
        }
    if mfe is not None and mfe > 0:
        return {
            "exit_class": "GAVE_BACK_MFE",
            "mae": mae,
            "mfe": mfe,
            "hypothesis": "exit_optimization_candidate",
            "auto_changes_exits": False,
        }
    return {
        "exit_class": "IMMEDIATE_ADVERSE",
        "mae": mae,
        "mfe": mfe,
        "hypothesis": "entry_or_direction",
        "auto_changes_exits": False,
    }


def attach_close_fields(deal: dict[str, Any], join: dict[str, Any]) -> dict[str, Any]:
    signal = join.get("signal") if isinstance(join.get("signal"), dict) else {}
    sub = join.get("submission") if isinstance(join.get("submission"), dict) else {}
    features = sub.get("setup_features") if isinstance(sub.get("setup_features"), dict) else {}
    src = {**features, **signal, **deal}
    return {
        "ticket": join.get("ticket") or _ticket(deal.get("ticket") or deal.get("entry_ticket")),
        "signal_id": join.get("signal_id"),
        "decision_hash": join.get("decision_hash"),
        "request_id": join.get("request_id"),
        "entry_time": deal.get("entry_time"),
        "exit_time": deal.get("exit_time"),
        "entry_price": deal.get("entry") or deal.get("entry_price"),
        "exit_price": deal.get("exit") or deal.get("exit_price"),
        "direction": str(deal.get("side") or deal.get("direction") or src.get("direction") or "").upper(),
        "volume": deal.get("volume"),
        "gross_pnl": _as_float(deal.get("gross_pnl") or deal.get("profit_loss")),
        "net_pnl": _as_float(deal.get("net_pnl") or deal.get("profit_loss")),
        "commission": _as_float(deal.get("commission")),
        "swap": _as_float(deal.get("swap")),
        "R_multiple": _r_multiple(deal) or _as_float(src.get("rr")),
        "MFE": _as_float(deal.get("MFE") or deal.get("maximum_favorable_excursion")),
        "MAE": _as_float(deal.get("MAE") or deal.get("maximum_adverse_excursion")),
        "maximum_adverse_excursion": _as_float(deal.get("MAE") or deal.get("maximum_adverse_excursion")),
        "maximum_favorable_excursion": _as_float(deal.get("MFE") or deal.get("maximum_favorable_excursion")),
        "holding_time": _as_float(deal.get("holding_time_sec") or deal.get("holding_time")),
        "exit_reason": _as_str(deal.get("exit_reason") or deal.get("comment")),
        "session": _canonical_session(src.get("market_session") or deal.get("market_session"))
        or src.get("market_session")
        or deal.get("market_session"),
        "regime": _canonical_regime(src.get("market_regime") or deal.get("market_regime"))
        or src.get("market_regime")
        or deal.get("market_regime"),
        "setup_state": src.get("setup_state"),
        "buy_families": src.get("buy_families") or [],
        "sell_families": src.get("sell_families") or [],
        "opportunity_score": src.get("opportunity_score"),
        "directional_edge": src.get("directional_edge"),
        "order_id": sub.get("order_id") or deal.get("order_id") or deal.get("order"),
        "deal_id": deal.get("deal_id") or deal.get("deal") or sub.get("deal_id"),
        "slippage": _as_float(deal.get("slippage")),
        "spread": _as_float(src.get("spread") or deal.get("spread")),
        "decision_snapshot": dict(
            sub.get("decision_snapshot")
            or signal.get("decision_snapshot")
            or {}
        ),
        "original_setup_features": dict(features),
        "exit_class": classify_exit_path(
            {
                "net_pnl": _as_float(deal.get("net_pnl") or deal.get("profit_loss")),
                "MAE": _as_float(deal.get("MAE") or deal.get("maximum_adverse_excursion")),
                "MFE": _as_float(deal.get("MFE") or deal.get("maximum_favorable_excursion")),
            }
        ),
        "classification": STRATEGY_MATCHED,
    }


def build_loss_forensics(
    *,
    deals: list[dict[str, Any]] | None = None,
    closed_trades: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Scientific strategy stats from STRATEGY_MATCHED rows only."""
    submissions = list_submissions()
    signals = list_signals()
    unmatched: list[dict[str, Any]] = []
    matched: list[dict[str, Any]] = []
    source = closed_trades if closed_trades is not None else deals or []
    for deal in source:
        join = classify_closed_deal(deal, submissions=submissions, signals=signals)
        if join.get("classification") == STRATEGY_MATCHED:
            matched.append(attach_close_fields(deal, join))
        else:
            unmatched.append(
                {
                    "classification": UNMATCHED,
                    "ticket": join.get("ticket") or deal.get("ticket") or deal.get("entry_ticket"),
                    "reason": join.get("reason"),
                    "excluded_from_strategy_statistics": True,
                }
            )

    overall = _metrics(matched)
    buy = [t for t in matched if str(t.get("direction") or "").upper() in {"BUY", "LONG"}]
    sell = [t for t in matched if str(t.get("direction") or "").upper() in {"SELL", "SHORT"}]
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "never_uses_unmatched_broker_activity": True,
        "never_manufactures_fills": True,
        "opportunity_threshold": 70,
        "edge_margin": 5,
        "matched_count": len(matched),
        "unmatched_count": len(unmatched),
        "overall": overall,
        "BUY_EXPECTANCY": _metrics(buy),
        "SELL_EXPECTANCY": _metrics(sell),
        "SESSION_EXPECTANCY": _filled_segments(
            matched, "session", CANONICAL_SESSIONS, _canonical_session
        ),
        "REGIME_EXPECTANCY": _filled_segments(
            matched, "regime", CANONICAL_REGIMES, _canonical_regime
        ),
        "segments": {
            "direction": _segment(matched, "direction"),
            "setup_state": _segment(matched, "setup_state"),
            "opportunity_bucket": _bucket_numeric(
                matched,
                "opportunity_score",
                [("<70", None, 70), ("70-74", 70, 75), ("75-79", 75, 80), ("80+", 80, None)],
            ),
            "edge_bucket": _bucket_numeric(
                matched,
                "directional_edge",
                [("<5", None, 5), ("5-7", 5, 8), ("8+", 8, None)],
            ),
        },
        "hypotheses": hypothesis_report(matched),
        "loss_contributors": classify_loss_contributors(matched),
        "loss_dimensions": {
            key: {
                "dimension": key,
                "sample_size": len(matched),
                "classification": cause_strength(sample_size=len(matched)),
                "status": sample_status(len(matched)),
                "never_from_n_zero": True,
            }
            for key in LOSS_DIMENSIONS
        },
        "exit_paths": {
            label: sum(
                1
                for t in matched
                if str((t.get("exit_class") or {}).get("exit_class") or "") == label
            )
            for label in ("WINNER", "GAVE_BACK_MFE", "IMMEDIATE_ADVERSE", UNKNOWN)
        },
        "unmatched_preview": unmatched[:50],
        "matched_preview": matched[:50],
        "first_proven_loss_cause": (
            INSUFFICIENT_SAMPLE
            if len(matched) < 50
            else "NOT_PROVEN"
        ),
        "disclaimer": DISCLAIMER,
        "code_defect_proven": False,
        "trading_change_justified": False,
    }
