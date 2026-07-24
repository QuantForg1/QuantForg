"""IRAP analytics — exposure, drawdown, VaR, correlations, stress, alerts."""

from __future__ import annotations

import statistics
from datetime import UTC, datetime
from typing import Any


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _f(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _perf(portfolio: dict[str, Any]) -> dict[str, Any]:
    sections = _as_dict(portfolio.get("sections"))
    return _as_dict(sections.get("performance") or portfolio.get("performance"))


def _risk(portfolio: dict[str, Any]) -> dict[str, Any]:
    sections = _as_dict(portfolio.get("sections"))
    return _as_dict(sections.get("risk") or portfolio.get("risk"))


def _behavior(portfolio: dict[str, Any]) -> dict[str, Any]:
    sections = _as_dict(portfolio.get("sections"))
    return _as_dict(sections.get("behavior") or portfolio.get("behavior"))


def _returns_from_trades(trades: list[Any]) -> list[float]:
    out: list[float] = []
    for t in trades:
        if not isinstance(t, dict):
            continue
        pnl = _f(t.get("pnl") or t.get("profit") or t.get("net_pnl"))
        if pnl is not None:
            out.append(pnl)
    return out


def _pctile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return round(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f), 4)


def build_core_metrics(ctx: dict[str, Any]) -> dict[str, Any]:
    portfolio = _as_dict(ctx.get("sources", {}).get("portfolio"))
    perf = _perf(portfolio)
    risk = _risk(portfolio)
    trades = _as_list(_as_dict(ctx.get("sources", {}).get("idw")).get("trades"))
    pnls = _returns_from_trades(trades)

    # Prefer portfolio analytics when present
    sharpe = _f(perf.get("sharpe_ratio"))
    sortino = _f(perf.get("sortino_ratio"))
    calmar = _f(perf.get("calmar_ratio"))
    max_dd = _f(risk.get("max_drawdown_pct") or portfolio.get("max_drawdown_pct"))
    pf = _f(perf.get("profit_factor"))
    expectancy = _f(perf.get("expectancy"))
    net = _f(perf.get("net_profit"))

    recovery = None
    if max_dd and max_dd > 0 and net is not None:
        recovery = round(net / max_dd, 4)

    # VaR / CVaR from trade PnL distribution (historical, 95%)
    var_95 = cvar_95 = None
    if pnls:
        losses = sorted(pnls)  # most negative first
        var_95 = _pctile(losses, 5)  # 5th percentile of PnL
        tail = [x for x in losses if var_95 is not None and x <= var_95]
        cvar_95 = round(statistics.mean(tail), 4) if tail else var_95

    # Risk of ruin proxy from win rate / payoff
    wr = _f(perf.get("win_rate_pct"))
    if wr is not None and wr > 1:
        wr = wr / 100.0
    avg_win = _f(perf.get("average_win"))
    avg_loss = _f(perf.get("average_loss"))
    risk_of_ruin = None
    if wr is not None and avg_win and avg_loss and avg_loss > 0:
        # Approximate Kelly-adjacent ruin proxy
        edge = wr * avg_win - (1 - wr) * avg_loss
        if edge <= 0:
            risk_of_ruin = round(min(99.0, 50.0 + abs(edge) * 2), 2)
        else:
            ratio = avg_loss / avg_win
            q = (1 - wr) / max(wr, 1e-9)
            # Classic ruin approx for unit bets
            if q >= 1:
                risk_of_ruin = round(min(99.0, 100.0 * (q ** 10)), 2)
            else:
                risk_of_ruin = round(max(0.1, 100.0 * (q ** 20) * ratio), 2)

    # Derive sharpe/sortino from pnls if missing
    if sharpe is None and len(pnls) >= 5:
        mu = statistics.mean(pnls)
        sd = statistics.pstdev(pnls)
        sharpe = round(mu / sd, 4) if sd > 0 else None
    if sortino is None and len(pnls) >= 5:
        mu = statistics.mean(pnls)
        downside = [x for x in pnls if x < 0]
        dsd = statistics.pstdev(downside) if len(downside) >= 2 else 0.0
        sortino = round(mu / dsd, 4) if dsd > 0 else None
    if calmar is None and max_dd and max_dd > 0 and net is not None:
        calmar = round((net / 100.0) / max_dd, 4)

    return {
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "maximum_drawdown": max_dd,
        "recovery_factor": recovery,
        "profit_factor": pf,
        "expectancy": expectancy,
        "value_at_risk": var_95,
        "conditional_var": cvar_95,
        "risk_of_ruin": risk_of_ruin,
        "sample_size": len(pnls) or int(_f(perf.get("trade_count")) or 0),
        "never_modifies_production": True,
    }


def build_exposure(ctx: dict[str, Any]) -> dict[str, Any]:
    portfolio = _as_dict(ctx.get("sources", {}).get("portfolio"))
    behavior = _behavior(portfolio)
    risk = _risk(portfolio)
    sessions = _as_dict(behavior.get("session_performance"))
    by_session = {}
    total = 0.0
    for name, body in sessions.items():
        if not isinstance(body, dict):
            continue
        count = _f(body.get("count") or body.get("trade_count")) or 0.0
        by_session[str(name)] = {
            "trade_count": count,
            "win_rate": _f(body.get("win_rate") or body.get("win_rate_pct")),
            "pnl": _f(body.get("total_pnl") or body.get("pnl")),
        }
        total += count

    symbols: dict[str, int] = {}
    for t in _as_list(_as_dict(ctx.get("sources", {}).get("idw")).get("trades")):
        if isinstance(t, dict):
            sym = str(t.get("symbol") or "unknown")
            symbols[sym] = symbols.get(sym, 0) + 1

    concentration = None
    if symbols:
        top = max(symbols.values())
        concentration = round(top / max(sum(symbols.values()), 1) * 100.0, 2)

    return {
        "by_session": by_session,
        "by_symbol": symbols,
        "session_trade_total": total,
        "symbol_concentration_pct": concentration,
        "avg_exposure_pct": _f(risk.get("avg_exposure_pct") or portfolio.get("exposure")),
        "never_modifies_production": True,
    }


def build_drawdown_analytics(ctx: dict[str, Any]) -> dict[str, Any]:
    portfolio = _as_dict(ctx.get("sources", {}).get("portfolio"))
    risk = _risk(portfolio)
    max_dd = _f(risk.get("max_drawdown_pct"))
    current_dd = _f(risk.get("current_drawdown_pct"))
    ulcer = _f(risk.get("ulcer_index"))
    return {
        "maximum_drawdown_pct": max_dd,
        "current_drawdown_pct": current_dd,
        "ulcer_index": ulcer,
        "drawdown_trend": (
            "increasing"
            if current_dd is not None and max_dd is not None and current_dd >= max_dd * 0.7
            else "stable"
        ),
        "never_modifies_production": True,
    }


def build_concentration(ctx: dict[str, Any], exposure: dict[str, Any]) -> dict[str, Any]:
    symbols = _as_dict(exposure.get("by_symbol"))
    sessions = _as_dict(exposure.get("by_session"))
    herfindahl = 0.0
    total = sum(float(v) for v in symbols.values()) or 1.0
    for v in symbols.values():
        share = float(v) / total
        herfindahl += share * share
    return {
        "symbol_hhi": round(herfindahl, 4),
        "symbol_concentration_pct": exposure.get("symbol_concentration_pct"),
        "session_count": len(sessions),
        "risk_concentration_flag": herfindahl >= 0.45
        or (_f(exposure.get("symbol_concentration_pct")) or 0) >= 60,
        "never_modifies_production": True,
    }


def build_capital_allocation(ctx: dict[str, Any], exposure: dict[str, Any]) -> dict[str, Any]:
    sessions = _as_dict(exposure.get("by_session"))
    rows = []
    for name, body in sessions.items():
        b = _as_dict(body)
        rows.append(
            {
                "bucket": name,
                "trade_count": b.get("trade_count"),
                "pnl": b.get("pnl"),
                "win_rate": b.get("win_rate"),
            }
        )
    rows.sort(key=lambda r: abs(_f(r.get("pnl")) or 0), reverse=True)
    return {
        "allocations": rows,
        "note": "Observational allocation by session — never modifies capital rules",
        "never_modifies_production": True,
    }


def build_risk_adjusted(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "sharpe_ratio": metrics.get("sharpe_ratio"),
        "sortino_ratio": metrics.get("sortino_ratio"),
        "calmar_ratio": metrics.get("calmar_ratio"),
        "recovery_factor": metrics.get("recovery_factor"),
        "profit_factor": metrics.get("profit_factor"),
        "expectancy": metrics.get("expectancy"),
        "never_modifies_production": True,
    }


def build_correlation(ctx: dict[str, Any]) -> dict[str, Any]:
    """Session/symbol co-occurrence correlation matrix (observational)."""
    trades = _as_list(_as_dict(ctx.get("sources", {}).get("idw")).get("trades"))
    sessions = _as_dict(
        _behavior(_as_dict(ctx.get("sources", {}).get("portfolio"))).get(
            "session_performance"
        )
    )
    labels = sorted({str(k) for k in sessions.keys()} | {"london", "tokyo", "new_york"})[
        :6
    ]
    # Build synthetic pairwise correlation from win-rate proximity when trade-level
    # session tags are sparse.
    rates = {}
    for lab in labels:
        body = _as_dict(sessions.get(lab))
        wr = _f(body.get("win_rate") or body.get("win_rate_pct"))
        if wr is not None and wr > 1:
            wr = wr / 100.0
        rates[lab] = wr if wr is not None else 0.5

    matrix: list[dict[str, Any]] = []
    for a in labels:
        row = {"session": a}
        for b in labels:
            if a == b:
                row[b] = 1.0
            else:
                # proximity of rates → pseudo-correlation in [-1,1]
                diff = abs((rates[a] or 0.5) - (rates[b] or 0.5))
                row[b] = round(max(-1.0, 1.0 - diff * 4.0), 3)
        matrix.append(row)

    # Symbol pairs from co-occurrence in short windows if available
    symbols = sorted(
        {
            str(t.get("symbol"))
            for t in trades
            if isinstance(t, dict) and t.get("symbol")
        }
    )[:5]
    return {
        "session_matrix": matrix,
        "symbols_observed": symbols,
        "method": "session_winrate_proximity",
        "never_modifies_production": True,
    }


def build_scenario_risk(ctx: dict[str, Any]) -> dict[str, Any]:
    sims = _as_list(_as_dict(ctx.get("sources", {}).get("ise")).get("simulations"))
    rows = []
    for s in sims[:15]:
        if not isinstance(s, dict):
            continue
        m = _as_dict(s.get("metrics"))
        rows.append(
            {
                "simulation_id": s.get("simulation_id"),
                "scenario": s.get("scenario") or s.get("mode"),
                "drawdown": m.get("drawdown"),
                "profit_factor": m.get("profit_factor"),
                "win_rate": m.get("win_rate"),
                "expectancy": m.get("expectancy"),
            }
        )
    rows.sort(key=lambda r: _f(r.get("drawdown")) or 0, reverse=True)
    return {
        "scenarios": rows,
        "worst_drawdown_scenario": rows[0] if rows else None,
        "never_modifies_production": True,
    }


def build_stress_loss(ctx: dict[str, Any], scenario_risk: dict[str, Any]) -> dict[str, Any]:
    rows = [
        r
        for r in _as_list(scenario_risk.get("scenarios"))
        if "stress" in str(r.get("scenario") or "").lower()
        or str(r.get("scenario") or "")
        in {
            "extreme_spread",
            "execution_delay",
            "volatility_spike",
            "low_liquidity",
            "gap",
            "rapid_trend",
            "rapid_reversal",
        }
    ]
    if not rows:
        rows = _as_list(scenario_risk.get("scenarios"))[:5]
    losses = [_f(r.get("drawdown")) for r in rows if _f(r.get("drawdown")) is not None]
    return {
        "stress_scenarios": rows,
        "average_stress_drawdown": round(statistics.mean(losses), 2) if losses else None,
        "max_stress_drawdown": round(max(losses), 2) if losses else None,
        "never_modifies_production": True,
    }


def build_tail_risk(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "value_at_risk": metrics.get("value_at_risk"),
        "conditional_var": metrics.get("conditional_var"),
        "risk_of_ruin": metrics.get("risk_of_ruin"),
        "tail_severity": (
            "elevated"
            if (_f(metrics.get("conditional_var")) or 0) < -50
            or (_f(metrics.get("risk_of_ruin")) or 0) > 25
            else "moderate"
        ),
        "never_modifies_production": True,
    }


def build_risk_trends(
    ctx: dict[str, Any],
    *,
    metrics: dict[str, Any],
    drawdown: dict[str, Any],
) -> dict[str, Any]:
    cvf = _as_dict(ctx.get("sources", {}).get("cvf"))
    eqs = _as_dict(ctx.get("sources", {}).get("eqs"))
    res = _as_dict(ctx.get("sources", {}).get("res"))
    return {
        "points": [
            {
                "period": "current",
                "maximum_drawdown": drawdown.get("maximum_drawdown_pct"),
                "sharpe": metrics.get("sharpe_ratio"),
                "var": metrics.get("value_at_risk"),
                "cvf_confidence": _as_dict(cvf.get("confidence")).get("confidence")
                or cvf.get("confidence"),
                "eqs_score": _as_dict(eqs.get("execution_score")).get(
                    "overall_execution_score"
                )
                or eqs.get("overall_score"),
                "res_score": _as_dict(res.get("reliability_score")).get(
                    "overall_reliability_score"
                )
                or res.get("reliability_score"),
            }
        ],
        "drawdown_trend": drawdown.get("drawdown_trend"),
        "never_modifies_production": True,
    }


def build_alerts(
    *,
    drawdown: dict[str, Any],
    concentration: dict[str, Any],
    exposure: dict[str, Any],
    capital: dict[str, Any],
    tail: dict[str, Any],
    metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if drawdown.get("drawdown_trend") == "increasing" or (
        _f(drawdown.get("maximum_drawdown_pct")) or 0
    ) >= 15:
        alerts.append(
            {
                "kind": "Increasing drawdown",
                "severity": "critical"
                if (_f(drawdown.get("maximum_drawdown_pct")) or 0) >= 20
                else "warning",
                "detail": f"Max DD={drawdown.get('maximum_drawdown_pct')}% trend={drawdown.get('drawdown_trend')}",
                "read_only": True,
            }
        )
    if concentration.get("risk_concentration_flag"):
        alerts.append(
            {
                "kind": "Risk concentration",
                "severity": "warning",
                "detail": f"HHI={concentration.get('symbol_hhi')} concentration={concentration.get('symbol_concentration_pct')}%",
                "read_only": True,
            }
        )
    sessions = _as_dict(exposure.get("by_session"))
    if sessions:
        counts = [_f(_as_dict(v).get("trade_count")) or 0 for v in sessions.values()]
        if counts and max(counts) > 0 and min(counts) / max(counts) < 0.25:
            alerts.append(
                {
                    "kind": "Exposure imbalance",
                    "severity": "warning",
                    "detail": "Session trade distribution highly skewed",
                    "read_only": True,
                }
            )
    alloc = _as_list(capital.get("allocations"))
    if alloc:
        pnls = [_f(a.get("pnl")) for a in alloc if _f(a.get("pnl")) is not None]
        if pnls and sum(1 for p in pnls if p and p < 0) >= max(1, len(pnls) // 2):
            alerts.append(
                {
                    "kind": "Capital inefficiency",
                    "severity": "warning",
                    "detail": "Multiple session buckets with negative PnL",
                    "read_only": True,
                }
            )
    if tail.get("tail_severity") == "elevated" or (
        _f(metrics.get("risk_of_ruin")) or 0
    ) > 30:
        alerts.append(
            {
                "kind": "Tail risk increase",
                "severity": "critical"
                if (_f(metrics.get("risk_of_ruin")) or 0) > 40
                else "warning",
                "detail": f"CVaR={tail.get('conditional_var')} RoR={metrics.get('risk_of_ruin')}",
                "read_only": True,
            }
        )
    for a in alerts:
        a["generated_at"] = datetime.now(UTC).isoformat()
        a["never_triggers_automation"] = True
    return alerts


def build_reports(
    *,
    metrics: dict[str, Any],
    exposure: dict[str, Any],
    drawdown: dict[str, Any],
    stress: dict[str, Any],
    alerts: list[dict[str, Any]],
    trends: dict[str, Any],
) -> dict[str, Any]:
    base = {
        "metrics": metrics,
        "exposure": exposure,
        "drawdown": drawdown,
        "stress": stress,
        "alerts": alerts,
        "trends": trends,
        "advisory_only": True,
    }
    return {
        "daily": {**base, "period": "daily", "title": "Daily Portfolio Risk Report"},
        "weekly": {**base, "period": "weekly", "title": "Weekly Portfolio Risk Report"},
        "monthly": {
            **base,
            "period": "monthly",
            "title": "Monthly Portfolio Risk Report",
        },
        "quarterly": {
            **base,
            "period": "quarterly",
            "title": "Quarterly Portfolio Risk Report",
        },
        "portfolio_risk_report": {
            **base,
            "title": "Portfolio Risk Report",
        },
        "strategy_risk_report": {
            "title": "Strategy Risk Report",
            "metrics": metrics,
            "drawdown": drawdown,
            "alerts": alerts,
        },
        "stress_risk_report": {
            "title": "Stress Risk Report",
            "stress": stress,
            "alerts": [a for a in alerts if "tail" in str(a.get("kind")).lower() or "drawdown" in str(a.get("kind")).lower()],
        },
        "generated_at": datetime.now(UTC).isoformat(),
    }
