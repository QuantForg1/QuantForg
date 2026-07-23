"""Institutional Portfolio Analytics — read-only MT5 portfolio intelligence.

Analyzes closed XAUUSD trades paired from MT5 deals and optional SIC enrichment.
Never modifies Strategy, Risk, Safety, OMS, Execution, Auto Trading, or Thresholds.
"""

from __future__ import annotations

import csv
import io
import math
import statistics
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from app.application.services.strategy_intelligence_center import (
    GOLD_SYMBOL,
    enrich_trade,
    pair_deals_into_closed_trades,
)
from app.domain.institutional_trading.session_filter import classify_session_utc

DEFAULT_STARTING_EQUITY = 10_000.0
MIN_BUCKET = 2
ROLLING_WINDOW = 20
ReportPeriod = Literal["daily", "weekly", "monthly", "quarterly", "yearly"]

__all__ = [
    "DEFAULT_STARTING_EQUITY",
    "ReportPeriod",
    "analyze_portfolio",
    "analytics_to_csv",
    "analytics_to_pdf_bytes",
    "build_institutional_portfolio_analytics",
    "build_report",
]


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _safe_div(num: float | None, den: float | None, *, default: float | None = None) -> float | None:
    if num is None or den is None or abs(den) < 1e-12:
        return default
    return num / den


def _chrono_trades(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return trades sorted by exit time ascending."""
    keyed: list[tuple[datetime, dict[str, Any]]] = []
    for t in trades:
        ts = _parse_ts(t.get("exit_time") or t.get("entry_time"))
        if ts is None:
            continue
        keyed.append((ts, t))
    keyed.sort(key=lambda kv: kv[0])
    return [t for _, t in keyed]


def _normalize_rows(rows: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        if hasattr(r, "to_dict"):
            out.append(dict(r.to_dict()))  # type: ignore[arg-type]
        elif isinstance(r, dict):
            out.append(r)
    return out


def _account_to_dict(info: Any) -> dict[str, Any]:
    if info is None:
        return {}
    if hasattr(info, "to_dict"):
        raw = info.to_dict()
        return raw if isinstance(raw, dict) else {}
    if isinstance(info, dict):
        return info
    return {}


def _load_deals_and_account(
    days: int = 365,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Load MT5 deals + account snapshot via DI adapter or local gateway."""
    meta: dict[str, Any] = {"attempted": True, "ok": False, "days": days}
    deals: list[dict[str, Any]] = []
    account: dict[str, Any] = {}

    try:
        from core.di.container import get_container

        adapter = getattr(get_container(), "mt5_adapter", None)
        if adapter is not None:
            date_to = datetime.now(UTC)
            date_from = date_to - timedelta(days=days)
            raw = adapter.history_deals(date_from=date_from, date_to=date_to)
            deals = _normalize_rows(list(raw or []))
            meta["ok"] = True
            meta["via"] = "di_adapter"
            meta["raw_count"] = len(deals)
            try:
                account = _account_to_dict(adapter.account_info())
                meta["account_loaded"] = bool(account)
            except Exception as exc:  # noqa: BLE001
                meta["account_error"] = str(exc)[:200]
            return deals, account, meta
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
            from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client

            client = GatewayMT5Client(base_url=base, token=token)
            if client.adopt_existing_session():
                raw = client.history_deals(days=days)
                deals = _normalize_rows(list(raw or []))
                meta["ok"] = True
                meta["via"] = "local_gateway"
                meta["raw_count"] = len(deals)
                try:
                    account = _account_to_dict(client.account_info())
                    meta["account_loaded"] = bool(account)
                except Exception as exc:  # noqa: BLE001
                    meta["account_error"] = str(exc)[:200]
                return deals, account, meta
            meta["adopt_failed"] = True
    except Exception as exc:  # noqa: BLE001
        meta["gateway_error"] = str(exc)[:200]

    return deals, account, meta


def _equity_path(
    trades: list[dict[str, Any]],
    *,
    starting_equity: float,
) -> dict[str, Any]:
    """Build equity/balance/drawdown curves and risk metrics from closed trades."""
    ordered = _chrono_trades(trades)
    pnls = [_f(t.get("profit_loss")) or 0.0 for t in ordered]
    equity_points: list[float] = [starting_equity]
    balance_points: list[float] = [starting_equity]
    profit_points: list[float] = [0.0]
    drawdown_abs: list[float] = [0.0]
    drawdown_pct: list[float] = [0.0]
    recovery_pct: list[float] = [0.0]
    per_trade_returns: list[float] = []
    timestamps: list[str | None] = [None]

    equity = starting_equity
    peak = starting_equity
    trough = starting_equity
    cum_profit = 0.0
    max_dd_abs = 0.0
    max_dd_pct = 0.0
    dd_samples: list[float] = []
    recovery_bars = 0
    max_recovery_bars = 0
    in_recovery = False

    for idx, pnl in enumerate(pnls):
        prev_equity = equity
        equity += pnl
        cum_profit += pnl
        ret = _safe_div(pnl, prev_equity, default=0.0) or 0.0
        per_trade_returns.append(round(ret, 6))

        peak = max(peak, equity)
        trough = min(trough, equity)
        dd_a = peak - equity
        dd_p = _safe_div(dd_a, peak, default=0.0) or 0.0
        max_dd_abs = max(max_dd_abs, dd_a)
        max_dd_pct = max(max_dd_pct, dd_p * 100.0)
        dd_samples.append(dd_p * 100.0)

        if dd_a > 1e-9:
            in_recovery = True
            recovery_bars += 1
            max_recovery_bars = max(max_recovery_bars, recovery_bars)
        else:
            in_recovery = False
            recovery_bars = 0

        rec = _safe_div(equity - trough, peak - trough, default=1.0) if peak > trough else 1.0
        exit_ts = ordered[idx].get("exit_time")
        equity_points.append(round(equity, 2))
        balance_points.append(round(equity, 2))
        profit_points.append(round(cum_profit, 2))
        drawdown_abs.append(round(dd_a, 2))
        drawdown_pct.append(round(dd_p * 100.0, 4))
        recovery_pct.append(round((rec or 0.0) * 100.0, 2))
        timestamps.append(str(exit_ts) if exit_ts else None)

    current_dd_abs = drawdown_abs[-1] if drawdown_abs else 0.0
    current_dd_pct = drawdown_pct[-1] if drawdown_pct else 0.0
    avg_dd_pct = round(statistics.mean(dd_samples), 4) if dd_samples else 0.0
    net_profit = cum_profit
    recovery_factor = _safe_div(net_profit, max_dd_abs, default=None)
    if recovery_factor is not None:
        recovery_factor = round(recovery_factor, 4)

    ulcer = None
    if dd_samples:
        ulcer = round(math.sqrt(sum(d * d for d in dd_samples) / len(dd_samples)), 4)

    return {
        "starting_equity": round(starting_equity, 2),
        "ending_equity": round(equity, 2),
        "high_water_mark": round(peak, 2),
        "low_water_mark": round(trough, 2),
        "net_profit": round(net_profit, 2),
        "equity_curve": equity_points,
        "balance_curve": balance_points,
        "profit_curve": profit_points,
        "drawdown_abs_curve": drawdown_abs,
        "drawdown_pct_curve": drawdown_pct,
        "recovery_pct_curve": recovery_pct,
        "timestamps": timestamps,
        "per_trade_returns": per_trade_returns,
        "max_drawdown_abs": round(max_dd_abs, 2),
        "max_drawdown_pct": round(max_dd_pct, 4),
        "current_drawdown_abs": round(current_dd_abs, 2),
        "current_drawdown_pct": round(current_dd_pct, 4),
        "average_drawdown_pct": avg_dd_pct,
        "max_recovery_bars": max_recovery_bars,
        "recovery_factor": recovery_factor,
        "ulcer_index": ulcer,
        "trade_count": len(ordered),
    }


def _pnls(trades: list[dict[str, Any]]) -> list[float]:
    return [_f(t.get("profit_loss")) or 0.0 for t in trades]


def _wins_losses(trades: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    wins = [t for t in trades if (_f(t.get("profit_loss")) or 0.0) > 0]
    losses = [t for t in trades if (_f(t.get("profit_loss")) or 0.0) < 0]
    return wins, losses


def _period_pnl(trades: list[dict[str, Any]], *, since: datetime) -> float:
    total = 0.0
    for t in trades:
        ts = _parse_ts(t.get("exit_time"))
        if ts is None or ts < since:
            continue
        total += _f(t.get("profit_loss")) or 0.0
    return round(total, 2)


def _return_pct(pnl: float, base: float) -> float | None:
    if base <= 0:
        return None
    return round(pnl / base * 100.0, 4)


def _sharpe(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    mu = statistics.mean(returns)
    sd = statistics.pstdev(returns)
    if sd < 1e-12:
        return None
    return round(mu / sd * math.sqrt(len(returns)), 4)


def _sortino(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    mu = statistics.mean(returns)
    downs = [r for r in returns if r < 0]
    if not downs:
        return None
    dd = statistics.pstdev(downs)
    if dd < 1e-12:
        return None
    return round(mu / dd * math.sqrt(len(returns)), 4)


def _risk_of_ruin(
    *,
    win_rate: float | None,
    payoff: float | None,
    trades: int,
) -> float | None:
    """Simplified Bernoulli ruin estimate for fixed fractional outcomes."""
    if win_rate is None or payoff is None or trades < 1:
        return None
    p = win_rate
    q = 1.0 - p
    if payoff <= 0:
        return 1.0 if q > 0 else None
    edge = p * payoff - q
    if edge <= 0:
        return round(min(1.0, 0.5 + (0.5 - p) * 0.8), 4)
    decay = ((q / p) * (1.0 / payoff)) ** trades if payoff > 0 else 1.0
    return round(min(1.0, max(0.0, decay)), 4)


def _bucket_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"count": 0, "wins": 0, "win_rate": None, "total_pnl": 0.0, "avg_pnl": 0.0}
    wins = sum(1 for r in rows if (_f(r.get("profit_loss")) or 0.0) > 0)
    pnls = _pnls(rows)
    return {
        "count": len(rows),
        "wins": wins,
        "win_rate": round(wins / len(rows) * 100.0, 2),
        "total_pnl": round(sum(pnls), 2),
        "avg_pnl": round(statistics.mean(pnls), 2) if pnls else 0.0,
    }


def _best_worst_bucket(buckets: dict[str, dict[str, Any]]) -> tuple[str | None, str | None]:
    eligible = {k: v for k, v in buckets.items() if v.get("count", 0) >= MIN_BUCKET}
    if not eligible:
        return None, None
    best = max(eligible.items(), key=lambda kv: (kv[1].get("total_pnl", 0.0), kv[1].get("win_rate") or 0))[0]
    worst = min(eligible.items(), key=lambda kv: (kv[1].get("total_pnl", 0.0), kv[1].get("win_rate") or 0))[0]
    return best, worst


def section_dashboard(
    trades: list[dict[str, Any]],
    *,
    account: dict[str, Any] | None,
    equity_path: dict[str, Any],
    starting_equity: float,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    balance = _f(account.get("balance") if account else None)
    equity = _f(account.get("equity") if account else None)
    floating = _f(account.get("profit") if account else None)
    if equity is None:
        equity = equity_path.get("ending_equity")
    if balance is None:
        balance = equity_path.get("ending_equity")
    if floating is None and equity is not None and balance is not None:
        floating = round(equity - balance, 2)

    base = balance or starting_equity
    pnls = _pnls(trades)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    net_profit = sum(pnls)

    return {
        "balance": balance,
        "equity": equity,
        "high_water_mark": equity_path.get("high_water_mark"),
        "low_water_mark": equity_path.get("low_water_mark"),
        "floating_pnl": floating,
        "closed_pnl": round(net_profit, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "net_profit": round(net_profit, 2),
        "return_today_pct": _return_pct(_period_pnl(trades, since=now.replace(hour=0, minute=0, second=0, microsecond=0)), base or starting_equity),
        "return_week_pct": _return_pct(_period_pnl(trades, since=now - timedelta(days=7)), base or starting_equity),
        "return_month_pct": _return_pct(_period_pnl(trades, since=now - timedelta(days=30)), base or starting_equity),
        "return_year_pct": _return_pct(_period_pnl(trades, since=now - timedelta(days=365)), base or starting_equity),
        "trade_count": len(trades),
    }


def section_risk(
    trades: list[dict[str, Any]],
    *,
    equity_path: dict[str, Any],
    starting_equity: float,
) -> dict[str, Any]:
    wins, losses = _wins_losses(trades)
    win_rate = _safe_div(len(wins), len(trades))
    avg_win = _safe_div(sum(_pnls(wins)), len(wins))
    avg_loss = _safe_div(abs(sum(_pnls(losses))), len(losses))
    payoff = _safe_div(avg_win, avg_loss)
    net = equity_path.get("net_profit") or 0.0
    max_dd_pct = equity_path.get("max_drawdown_pct") or 0.0
    capital_efficiency = _safe_div(net, starting_equity)
    if capital_efficiency is not None:
        capital_efficiency = round(capital_efficiency * 100.0, 4)

    return {
        "max_drawdown_pct": equity_path.get("max_drawdown_pct"),
        "max_drawdown_abs": equity_path.get("max_drawdown_abs"),
        "current_drawdown_pct": equity_path.get("current_drawdown_pct"),
        "current_drawdown_abs": equity_path.get("current_drawdown_abs"),
        "average_drawdown_pct": equity_path.get("average_drawdown_pct"),
        "recovery_factor": equity_path.get("recovery_factor"),
        "recovery_time_trades": equity_path.get("max_recovery_bars"),
        "max_recovery_trades": equity_path.get("max_recovery_bars"),
        "ulcer_index": equity_path.get("ulcer_index"),
        "risk_of_ruin_estimate": _risk_of_ruin(
            win_rate=win_rate,
            payoff=payoff,
            trades=len(trades),
        ),
        "capital_efficiency_pct": capital_efficiency,
        "capital_efficiency": capital_efficiency,
    }


def section_performance(
    trades: list[dict[str, Any]],
    *,
    equity_path: dict[str, Any],
    starting_equity: float,
) -> dict[str, Any]:
    wins, losses = _wins_losses(trades)
    pnls = _pnls(trades)
    n = len(trades)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    net = sum(pnls)
    win_rate = _safe_div(len(wins), n)
    avg_win = _safe_div(gross_profit, len(wins))
    avg_loss = _safe_div(gross_loss, len(losses))
    pf = _safe_div(gross_profit, gross_loss) if gross_loss > 0 else None
    expectancy = None
    if win_rate is not None and avg_win is not None and avg_loss is not None:
        expectancy = win_rate * avg_win - (1.0 - win_rate) * avg_loss
    elif win_rate is not None and avg_win is not None and not losses:
        expectancy = win_rate * avg_win
    payoff = _safe_div(avg_win, avg_loss)
    rs = [_f(t.get("risk_reward")) for t in trades if _f(t.get("risk_reward")) is not None]
    avg_r = round(statistics.mean(rs), 4) if rs else None
    returns = equity_path.get("per_trade_returns") or []
    sharpe = _sharpe(returns)
    sortino = _sortino(returns)
    max_dd_pct = equity_path.get("max_drawdown_pct") or 0.0
    calmar = None
    if max_dd_pct > 0 and starting_equity > 0:
        ann_return = net / starting_equity * 100.0
        calmar = round(ann_return / max_dd_pct, 4)

    largest_win = max((p for p in pnls if p > 0), default=None)
    largest_loss = min((p for p in pnls if p < 0), default=None)

    loss_rate = _safe_div(len(losses), n)
    return {
        "trade_count": n,
        "wins": len(wins),
        "losses": len(losses),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": round(win_rate * 100.0, 2) if win_rate is not None else None,
        "loss_rate_pct": round(loss_rate * 100.0, 2) if loss_rate is not None else None,
        "average_win": round(avg_win, 2) if avg_win is not None else None,
        "average_loss": round(avg_loss, 2) if avg_loss is not None else None,
        "largest_win": round(largest_win, 2) if largest_win is not None else None,
        "largest_loss": round(largest_loss, 2) if largest_loss is not None else None,
        "average_r": avg_r,
        "average_r_multiple": avg_r,
        "profit_factor": round(pf, 4) if pf is not None else None,
        "expectancy": round(expectancy, 4) if expectancy is not None else None,
        "payoff_ratio": round(payoff, 4) if payoff is not None else None,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "net_profit": round(net, 2),
    }


def section_behavior(trades: list[dict[str, Any]]) -> dict[str, Any]:
    holds = [_f(t.get("holding_time_sec")) for t in trades if _f(t.get("holding_time_sec")) is not None]
    spreads = [_f(t.get("spread")) for t in trades if _f(t.get("spread")) is not None]
    atrs = [_f(t.get("atr")) for t in trades if _f(t.get("atr")) is not None]

    session_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        session = t.get("market_session")
        if not session:
            entry_ts = _parse_ts(t.get("entry_time"))
            if entry_ts is not None:
                session = classify_session_utc(entry_ts).value
        session_buckets[str(session or "unknown")].append(t)

    session_stats = {k: _bucket_stats(v) for k, v in session_buckets.items()}

    dates: set[str] = set()
    weeks: set[str] = set()
    for t in trades:
        ts = _parse_ts(t.get("exit_time"))
        if ts is None:
            continue
        dates.add(ts.date().isoformat())
        weeks.add(f"{ts.isocalendar().year}-W{ts.isocalendar().week:02d}")

    span_days = max(len(dates), 1)
    span_weeks = max(len(weeks), 1)

    tpd = round(len(trades) / span_days, 3)
    tpw = round(len(trades) / span_weeks, 3)
    if tpd >= 3:
        trading_frequency = "high"
    elif tpd >= 1:
        trading_frequency = "moderate"
    elif tpd > 0:
        trading_frequency = "low"
    else:
        trading_frequency = "none"

    return {
        "average_holding_time_sec": round(statistics.mean(holds), 1) if holds else None,
        "median_holding_time_sec": round(statistics.median(holds), 1) if holds else None,
        "best_holding_time_sec": round(min(holds), 1) if holds else None,
        "worst_holding_time_sec": round(max(holds), 1) if holds else None,
        "trades_per_day": tpd,
        "trades_per_week": tpw,
        "average_trades_per_day": tpd,
        "average_trades_per_week": tpw,
        "trading_frequency": trading_frequency,
        "active_days": len(dates),
        "active_weeks": len(weeks),
        "session_performance": session_stats,
        "average_session_performance": session_stats,
        "average_spread_at_entry": round(statistics.mean(spreads), 4) if spreads else None,
        "average_atr_at_entry": round(statistics.mean(atrs), 4) if atrs else None,
    }


def _time_bucket_key(ts: datetime, kind: str) -> str:
    if kind == "hour":
        return f"{ts.hour:02d}:00 UTC"
    if kind == "dow":
        return ts.strftime("%A")
    if kind == "week":
        return f"{ts.isocalendar().year}-W{ts.isocalendar().week:02d}"
    if kind == "month":
        return ts.strftime("%Y-%m")
    if kind == "quarter":
        return f"{ts.year}-Q{(ts.month - 1) // 3 + 1}"
    if kind == "year":
        return str(ts.year)
    return ts.isoformat()


def section_time(trades: list[dict[str, Any]]) -> dict[str, Any]:
    kinds = ("hour", "dow", "week", "month", "quarter", "year")
    out: dict[str, Any] = {}
    for kind in kinds:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for t in trades:
            ts = _parse_ts(t.get("exit_time") or t.get("entry_time"))
            if ts is None:
                continue
            buckets[_time_bucket_key(ts, kind)].append(t)
        stats = {k: _bucket_stats(v) for k, v in buckets.items()}
        best, worst = _best_worst_bucket(stats)
        out[kind] = {
            "buckets": stats,
            "best": best,
            "worst": worst,
        }
    return out


def _rolling_metric(
    trades: list[dict[str, Any]],
    *,
    window: int,
    metric: str,
) -> list[float | None]:
    ordered = _chrono_trades(trades)
    out: list[float | None] = []
    for i in range(len(ordered)):
        if i + 1 < window:
            out.append(None)
            continue
        slice_rows = ordered[i + 1 - window : i + 1]
        wins, losses = _wins_losses(slice_rows)
        pnls = _pnls(slice_rows)
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        if metric == "win_rate":
            out.append(round(len(wins) / window * 100.0, 2))
        elif metric == "profit_factor":
            pf = _safe_div(gross_profit, gross_loss) if gross_loss > 0 else None
            out.append(round(pf, 4) if pf is not None else None)
        elif metric == "expectancy":
            wr = len(wins) / window
            aw = _safe_div(gross_profit, len(wins)) or 0.0
            al = _safe_div(gross_loss, len(losses)) or 0.0
            exp = wr * aw - (1.0 - wr) * al if losses else wr * aw
            out.append(round(exp, 4))
        else:
            out.append(None)
    return out


def section_equity_analytics(
    trades: list[dict[str, Any]],
    *,
    equity_path: dict[str, Any],
    window: int = ROLLING_WINDOW,
) -> dict[str, Any]:
    return {
        "equity_curve": equity_path.get("equity_curve"),
        "balance_curve": equity_path.get("balance_curve"),
        "drawdown_pct_curve": equity_path.get("drawdown_pct_curve"),
        "profit_curve": equity_path.get("profit_curve"),
        "recovery_pct_curve": equity_path.get("recovery_pct_curve"),
        "timestamps": equity_path.get("timestamps"),
        "rolling_window": window,
        "rolling_win_rate": _rolling_metric(trades, window=window, metric="win_rate"),
        "rolling_profit_factor": _rolling_metric(trades, window=window, metric="profit_factor"),
        "rolling_expectancy": _rolling_metric(trades, window=window, metric="expectancy"),
    }


def _score_component(value: float | None, *, good: float, warn: float, higher_is_better: bool = True) -> float:
    if value is None:
        return 50.0
    if higher_is_better:
        if value >= good:
            return 100.0
        if value >= warn:
            return 70.0
        return max(0.0, 40.0 + (value / warn) * 30.0) if warn > 0 else 40.0
    if value <= good:
        return 100.0
    if value <= warn:
        return 70.0
    return max(0.0, 100.0 - (value - warn) * 2.0)


def section_health_score(
    *,
    dashboard: dict[str, Any],
    risk: dict[str, Any],
    performance: dict[str, Any],
    behavior: dict[str, Any],
    equity_path: dict[str, Any],
    source_meta: dict[str, Any],
) -> dict[str, Any]:
    components = {
        "execution_reliability": _score_component(
            performance.get("win_rate_pct"),
            good=55.0,
            warn=45.0,
        ),
        "risk_discipline": _score_component(
            risk.get("max_drawdown_pct"),
            good=8.0,
            warn=15.0,
            higher_is_better=False,
        ),
        "strategy_consistency": _score_component(
            performance.get("profit_factor"),
            good=1.5,
            warn=1.0,
        ),
        "portfolio_stability": _score_component(
            100.0 - (risk.get("ulcer_index") or 50.0),
            good=85.0,
            warn=70.0,
        ),
        "operational_reliability": 100.0 if source_meta.get("ok") else 55.0,
        "market_adaptation": _score_component(
            performance.get("expectancy"),
            good=5.0,
            warn=0.0,
        ),
        "analytics_integrity": 100.0 if equity_path.get("trade_count", 0) >= MIN_BUCKET else 60.0,
    }
    if behavior.get("session_performance"):
        sessions = behavior["session_performance"]
        if isinstance(sessions, dict) and sessions:
            avg_wr = statistics.mean(
                s.get("win_rate") or 0.0 for s in sessions.values() if s.get("count", 0) >= MIN_BUCKET
            ) if any(s.get("count", 0) >= MIN_BUCKET for s in sessions.values()) else 50.0
            components["market_adaptation"] = round(
                (components["market_adaptation"] + _score_component(avg_wr, good=55.0, warn=45.0)) / 2.0,
                1,
            )

    overall = round(statistics.mean(components.values()), 1)
    if overall >= 75:
        status = "GREEN"
        label = "Healthy"
    elif overall >= 55:
        status = "YELLOW"
        label = "Monitor"
    else:
        status = "RED"
        label = "Attention Required"

    return {
        "score": overall,
        "status": status,
        "label": label,
        "components": {k: round(v, 1) for k, v in components.items()},
        "summary": f"{label} — composite {overall}/100",
        "balance": dashboard.get("balance"),
        "equity": dashboard.get("equity"),
    }


def _infer_starting_equity(
    *,
    account: dict[str, Any] | None,
    trades: list[dict[str, Any]],
    explicit: float | None,
) -> tuple[float, dict[str, Any]]:
    notes: list[str] = []
    if explicit is not None and explicit > 0:
        return explicit, {"method": "explicit", "notes": notes}

    balance = _f(account.get("balance") if account else None)
    net = sum(_pnls(trades))
    if balance is not None:
        inferred = balance - net
        if inferred > 0:
            return round(inferred, 2), {"method": "balance_minus_closed_pnl", "notes": notes}

    notes.append(f"starting_equity_seeded_{DEFAULT_STARTING_EQUITY}")
    return DEFAULT_STARTING_EQUITY, {"method": "default_seed", "notes": notes}


def analyze_portfolio(
    closed_trades: list[dict[str, Any]],
    *,
    account: dict[str, Any] | None = None,
    starting_equity: float | None = None,
    source_meta: dict[str, Any] | None = None,
    strategy_id: str = "production",
    include_reports: bool = True,
) -> dict[str, Any]:
    """Core read-only portfolio analysis (unit-testable without gateway)."""
    trades = list(closed_trades)
    meta = dict(source_meta or {})
    seed, seed_info = _infer_starting_equity(
        account=account,
        trades=trades,
        explicit=starting_equity,
    )
    eq_path = _equity_path(trades, starting_equity=seed)
    dashboard = section_dashboard(trades, account=account, equity_path=eq_path, starting_equity=seed)
    risk = section_risk(trades, equity_path=eq_path, starting_equity=seed)
    performance = section_performance(trades, equity_path=eq_path, starting_equity=seed)
    behavior = section_behavior(trades)
    time_section = section_time(trades)
    equity_analytics = section_equity_analytics(trades, equity_path=eq_path)
    health = section_health_score(
        dashboard=dashboard,
        risk=risk,
        performance=performance,
        behavior=behavior,
        equity_path=eq_path,
        source_meta=meta,
    )

    report_seed: dict[str, Any] = {
        "closed_trades": trades,
        "trades": trades,
        "account": account or {},
        "starting_equity": seed,
        "source": meta,
        "strategy_id": strategy_id,
    }
    reports: dict[str, Any] = {}
    if include_reports:
        reports = {
            period: build_report(report_seed, period=period)  # type: ignore[arg-type]
            for period in ("daily", "weekly", "monthly", "quarterly", "yearly")
        }

    return {
        "schema_version": "1.0.0",
        "mode": "institutional_portfolio_analytics",
        "strategy_id": strategy_id,
        "symbol": GOLD_SYMBOL,
        "mutates_engines": False,
        "analytics_only": True,
        "never_modifies_strategy_risk_safety_oms_execution_auto_trading_thresholds": True,
        "observed_at": datetime.now(UTC).isoformat(),
        "starting_equity": seed,
        "starting_equity_inference": seed_info,
        "account": account or {},
        "source": meta,
        "trade_count": len(trades),
        "sections": {
            "dashboard": dashboard,
            "risk": risk,
            "performance": performance,
            "behavior": behavior,
            "time": time_section,
            "equity_analytics": equity_analytics,
            "health_score": health,
        },
        "equity_path": eq_path,
        "reports": reports,
    }


def _filter_trades_since(trades: list[dict[str, Any]], since: datetime) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in trades:
        ts = _parse_ts(t.get("exit_time") or t.get("entry_time"))
        if ts is not None and ts >= since:
            out.append(t)
    return out


def build_report(
    payload: dict[str, Any],
    *,
    period: ReportPeriod = "monthly",
) -> dict[str, Any]:
    """Slice portfolio analytics into daily/weekly/monthly/quarterly/yearly views."""
    now = datetime.now(UTC)
    windows: dict[ReportPeriod, timedelta] = {
        "daily": timedelta(days=1),
        "weekly": timedelta(days=7),
        "monthly": timedelta(days=30),
        "quarterly": timedelta(days=91),
        "yearly": timedelta(days=365),
    }
    since = now - windows[period]
    all_trades = payload.get("trades") or []
    if not all_trades and payload.get("trade_count"):
        all_trades = payload.get("closed_trades") or []
    subset = _filter_trades_since(all_trades, since)
    account = payload.get("account") if isinstance(payload.get("account"), dict) else None
    starting = payload.get("starting_equity")
    seed = float(starting) if starting is not None else None
    analysis = analyze_portfolio(
        subset,
        account=account,
        starting_equity=seed,
        source_meta=payload.get("source") if isinstance(payload.get("source"), dict) else {},
        strategy_id=str(payload.get("strategy_id") or "production"),
        include_reports=False,
    )
    sections = analysis.get("sections") if isinstance(analysis.get("sections"), dict) else {}
    health = sections.get("health_score") if isinstance(sections.get("health_score"), dict) else {}
    perf = sections.get("performance") if isinstance(sections.get("performance"), dict) else {}
    dash = sections.get("dashboard") if isinstance(sections.get("dashboard"), dict) else {}
    net = perf.get("net_profit", dash.get("net_profit", 0))
    wr = perf.get("win_rate_pct")
    wr_text = f"{wr}%" if wr is not None else "—"
    risk = sections.get("risk") if isinstance(sections.get("risk"), dict) else {}
    behavior = sections.get("behavior") if isinstance(sections.get("behavior"), dict) else {}
    time_sec = sections.get("time") if isinstance(sections.get("time"), dict) else {}
    executive_summary = (
        f"{health.get('label', 'Portfolio')} — {len(subset)} trades in {period} window; "
        f"net P/L {net}; win rate {wr_text}."
    )
    recommendations: list[str] = []
    status = str(health.get("status") or "YELLOW")
    if status == "RED":
        recommendations.append("Attention required — review drawdown, expectancy, and session concentration.")
    elif status == "YELLOW":
        recommendations.append("Monitor — track recovery factor and rolling win rate before expanding risk.")
    else:
        recommendations.append("Healthy — maintain current risk discipline; continue read-only surveillance.")
    if (risk.get("max_drawdown_pct") or 0) > 15:
        recommendations.append("Max drawdown elevated — keep position sizing conservative.")
    if (perf.get("profit_factor") or 0) < 1.0 and len(subset) >= 5:
        recommendations.append("Profit factor below 1.0 in window — investigate losing clusters by hour/weekday.")

    best_hour = (time_sec.get("hour") or {}).get("best") if isinstance(time_sec.get("hour"), dict) else None
    worst_hour = (time_sec.get("hour") or {}).get("worst") if isinstance(time_sec.get("hour"), dict) else None

    return {
        "period": period,
        "window_start": since.isoformat(),
        "window_end": now.isoformat(),
        "trade_count": len(subset),
        "executive_summary": executive_summary,
        "performance_summary": {
            "net_profit": net,
            "win_rate_pct": wr,
            "profit_factor": perf.get("profit_factor"),
            "expectancy": perf.get("expectancy"),
            "sharpe_ratio": perf.get("sharpe_ratio"),
            "trade_count": len(subset),
        },
        "risk_summary": {
            "max_drawdown_pct": risk.get("max_drawdown_pct"),
            "current_drawdown_pct": risk.get("current_drawdown_pct"),
            "recovery_factor": risk.get("recovery_factor"),
            "ulcer_index": risk.get("ulcer_index"),
            "risk_of_ruin_estimate": risk.get("risk_of_ruin_estimate"),
            "health_score": health.get("score"),
            "health_status": status,
        },
        "market_summary": {
            "best_hour": best_hour,
            "worst_hour": worst_hour,
            "session_performance": behavior.get("session_performance"),
            "average_spread_at_entry": behavior.get("average_spread_at_entry"),
            "average_atr_at_entry": behavior.get("average_atr_at_entry"),
        },
        "strategy_summary": {
            "strategy_id": analysis.get("strategy_id"),
            "symbol": analysis.get("symbol"),
            "analytics_only": True,
            "mutates_engines": False,
            "trading_frequency": behavior.get("trading_frequency"),
            "average_r_multiple": perf.get("average_r_multiple"),
        },
        "recommendations": recommendations,
        "operational_notes": [
            "Read-only portfolio analytics — does not modify strategy, risk, safety, OMS, execution, auto trading, or thresholds.",
            f"Deal window trades analyzed: {len(subset)}.",
            f"Health: {health.get('summary') or status}.",
        ],
        "analysis": analysis,
    }


def build_institutional_portfolio_analytics(
    *,
    days: int = 365,
    strategy_id: str = "production",
) -> dict[str, Any]:
    """Ops entry: load MT5 deals, pair XAUUSD trades, enrich, analyze."""
    deals, account, deal_meta = _load_deals_and_account(days=days)
    closed = pair_deals_into_closed_trades(deals, symbol=GOLD_SYMBOL)

    cycles: list[dict[str, Any]] = []
    try:
        from app.application.services.strategy_diagnostics import get_strategy_diagnostics_store

        snap = get_strategy_diagnostics_store().snapshot(limit=100)
        cycles = list(snap.get("cycles") or [])
    except Exception:
        cycles = []

    enriched = [enrich_trade(t, cycles=cycles) for t in closed]
    payload = analyze_portfolio(
        enriched,
        account=account or None,
        source_meta=deal_meta,
        strategy_id=strategy_id,
    )
    payload["closed_trades"] = enriched
    payload["trades"] = enriched[:100]
    payload["deal_source"] = deal_meta
    payload["diagnostics_cycles_joined"] = len(cycles)
    payload["params"] = {"days": days}
    payload["benchmark_ready"] = True
    payload["supports_candidate_strategies"] = True
    return payload


def report_to_markdown(payload: dict[str, Any]) -> str:
    sections = payload.get("sections") or {}
    dash = sections.get("dashboard") or {}
    risk = sections.get("risk") or {}
    perf = sections.get("performance") or {}
    health = sections.get("health_score") or {}
    lines = [
        "# Institutional Portfolio Analytics",
        "",
        f"- Observed: `{payload.get('observed_at')}`",
        f"- Strategy: `{payload.get('strategy_id')}` · Symbol: `{payload.get('symbol')}`",
        "- Read-only analytics — engines unchanged",
        f"- Trades: **{payload.get('trade_count', 0)}**",
        "",
        "## Dashboard",
        "",
        f"- Balance: **{dash.get('balance')}** · Equity: **{dash.get('equity')}**",
        f"- HWM: **{dash.get('high_water_mark')}** · LWM: **{dash.get('low_water_mark')}**",
        f"- Net P/L: **{dash.get('net_profit')}** (closed **{dash.get('closed_pnl')}**)",
        "",
        "## Risk",
        "",
        f"- Max DD: **{risk.get('max_drawdown_pct')}%** · Current DD: **{risk.get('current_drawdown_pct')}%**",
        f"- Recovery factor: **{risk.get('recovery_factor')}** · Ulcer: **{risk.get('ulcer_index')}**",
        "",
        "## Performance",
        "",
        f"- Win rate: **{perf.get('win_rate_pct')}%** · PF: **{perf.get('profit_factor')}**",
        f"- Expectancy: **{perf.get('expectancy')}** · Sharpe: **{perf.get('sharpe_ratio')}**",
        "",
        "## Health",
        "",
        f"- Score: **{health.get('score')}** · Status: **{health.get('status')}** ({health.get('label')})",
        "",
    ]
    return "\n".join(lines)


def analytics_to_csv(payload: dict[str, Any]) -> str:
    """Flatten key metrics to CSV."""
    sections = payload.get("sections") or {}
    rows: list[dict[str, Any]] = []
    for section_name, section in sections.items():
        if not isinstance(section, dict):
            continue
        if section_name == "time":
            for bucket_kind, bucket_data in section.items():
                if not isinstance(bucket_data, dict):
                    continue
                for bucket, stats in (bucket_data.get("buckets") or {}).items():
                    rows.append(
                        {
                            "section": section_name,
                            "bucket_kind": bucket_kind,
                            "bucket": bucket,
                            **stats,
                        }
                    )
        elif section_name == "health_score":
            rows.append(
                {
                    "section": section_name,
                    "metric": "overall",
                    "value": section.get("score"),
                    "status": section.get("status"),
                }
            )
            for comp, val in (section.get("components") or {}).items():
                rows.append(
                    {
                        "section": section_name,
                        "metric": comp,
                        "value": val,
                        "status": section.get("status"),
                    }
                )
        else:
            for metric, value in section.items():
                if isinstance(value, (dict, list)):
                    continue
                rows.append(
                    {
                        "section": section_name,
                        "metric": metric,
                        "value": value,
                    }
                )

    fields = ["section", "bucket_kind", "bucket", "metric", "value", "status", "count", "win_rate", "total_pnl"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def analytics_to_pdf_bytes(payload: dict[str, Any]) -> bytes:
    """Minimal multi-line PDF 1.4 — Helvetica Type1, no external deps."""
    md = report_to_markdown(payload)
    lines: list[str] = []
    for raw in md.splitlines():
        line = raw.replace("**", "").replace("`", "").replace("#", "").strip()
        if line:
            lines.append(line[:110])
        if len(lines) >= 55:
            break
    if not lines:
        lines = ["Institutional Portfolio Analytics", "No data"]

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    y = 780
    content = ["BT", "/F1 9 Tf", "12 TL"]
    for line in lines:
        content.append(f"1 0 0 1 40 {y} Tm ({esc(line)}) Tj")
        y -= 12
        if y < 40:
            break
    content.append("ET")
    stream = "\n".join(content)
    objects = [
        "1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj",
        "2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj",
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj",
        f"4 0 obj<< /Length {len(stream)} >>stream\n{stream}\nendstream endobj",
        "5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj",
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf.encode("latin-1", errors="replace")))
        pdf += obj + "\n"
    xref = len(pdf.encode("latin-1", errors="replace"))
    pdf += f"xref\n0 {len(objects) + 1}\n"
    pdf += "0000000000 65535 f \n"
    for i in range(1, len(offsets)):
        pdf += f"{offsets[i]:010d} 00000 n \n"
    pdf += f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
    pdf += f"startxref\n{xref}\n%%EOF"
    return pdf.encode("latin-1", errors="replace")
