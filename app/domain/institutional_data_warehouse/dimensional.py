"""Dimensional models — star schema over warehouse event copies."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.domain.institutional_data_warehouse.store import InstitutionalDataWarehouse


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    p = row.get("payload")
    return p if isinstance(p, dict) else {}


def build_dimensions(wh: InstitutionalDataWarehouse) -> dict[str, list[dict[str, Any]]]:
    dim_time: dict[str, dict[str, Any]] = {}
    dim_session: dict[str, dict[str, Any]] = {}
    dim_strategy: dict[str, dict[str, Any]] = {}
    dim_regime: dict[str, dict[str, Any]] = {}
    dim_instrument: dict[str, dict[str, Any]] = {}

    for domain in (
        "trades",
        "signals",
        "execution",
        "risk",
        "research",
        "portfolio",
        "diagnostics",
        "regimes",
        "opportunity",
    ):
        try:
            rows = wh.list(domain, limit=10_000)  # type: ignore[arg-type]
        except ValueError:
            continue
        for row in rows:
            day = row.get("trading_day") or (
                str(row.get("timestamp") or "")[:10] or None
            )
            if day:
                dim_time[str(day)] = {
                    "time_key": str(day),
                    "trading_day": str(day),
                    "year": str(day)[:4],
                    "month": str(day)[:7],
                }
            sess = row.get("session")
            if sess:
                dim_session[str(sess)] = {"session_key": str(sess), "session": str(sess)}
            strat = row.get("strategy_version")
            if strat:
                dim_strategy[str(strat)] = {
                    "strategy_key": str(strat),
                    "strategy_version": str(strat),
                }
            regime = _payload(row).get("regime") or _payload(row).get("market_regime")
            if regime:
                dim_regime[str(regime)] = {
                    "regime_key": str(regime),
                    "regime": str(regime),
                }
            sym = row.get("symbol") or "XAUUSD"
            dim_instrument[str(sym)] = {
                "instrument_key": str(sym),
                "symbol": str(sym),
            }

    return {
        "dim_time": list(dim_time.values()),
        "dim_session": list(dim_session.values()),
        "dim_strategy": list(dim_strategy.values()),
        "dim_regime": list(dim_regime.values()),
        "dim_instrument": list(dim_instrument.values()),
    }


def build_facts(wh: InstitutionalDataWarehouse) -> dict[str, list[dict[str, Any]]]:
    def _map(
        domain: str,
        *,
        fact_name: str,
        extra: Any = None,
    ) -> list[dict[str, Any]]:
        try:
            rows = wh.list(domain, limit=10_000)  # type: ignore[arg-type]
        except ValueError:
            return []
        out: list[dict[str, Any]] = []
        for row in rows:
            payload = _payload(row)
            fact = {
                "fact": fact_name,
                "uuid": row.get("uuid") or row.get("warehouse_id"),
                "timestamp": row.get("timestamp"),
                "trading_day": row.get("trading_day"),
                "session_key": row.get("session"),
                "strategy_key": row.get("strategy_version"),
                "instrument_key": row.get("symbol"),
                "regime_key": payload.get("regime") or payload.get("market_regime"),
                "correlation_id": row.get("correlation_id"),
                "environment": row.get("environment"),
                "source": row.get("source"),
            }
            if extra:
                fact.update(extra(row, payload))
            out.append(fact)
        return out

    return {
        "fact_trades": _map(
            "trades",
            fact_name="fact_trades",
            extra=lambda r, p: {
                "pnl": p.get("net_pnl") or p.get("pnl"),
                "trade_id": r.get("trade_id"),
            },
        ),
        "fact_signals": _map(
            "signals",
            fact_name="fact_signals",
            extra=lambda r, p: {
                "decision": p.get("decision") or p.get("action"),
            },
        ),
        "fact_executions": _map(
            "execution",
            fact_name="fact_executions",
            extra=lambda r, p: {
                "retcode": p.get("retcode"),
                "oms_status": p.get("oms_status"),
            },
        ),
        "fact_research": _map(
            "research",
            fact_name="fact_research",
            extra=lambda r, p: {
                "experiment_id": p.get("uuid") or p.get("experiment_id"),
                "verdict": p.get("verdict"),
            },
        ),
        "fact_portfolio": _map(
            "portfolio",
            fact_name="fact_portfolio",
            extra=lambda r, p: {
                "net_profit": p.get("net_profit") or p.get("net_pnl"),
            },
        ),
        "fact_risk": _map(
            "risk",
            fact_name="fact_risk",
            extra=lambda r, p: {
                "action": p.get("action"),
                "severity": p.get("severity"),
            },
        ),
        "fact_diagnostics": _map(
            "diagnostics",
            fact_name="fact_diagnostics",
            extra=lambda r, p: {
                "cycle_id": p.get("cycle_id") or p.get("id"),
            },
        ),
    }


def build_dimensional_model(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    facts = build_facts(wh)
    dims = build_dimensions(wh)
    return {
        "status": "available",
        "facts": {k: {"count": len(v), "sample": v[:5]} for k, v in facts.items()},
        "dimensions": {k: {"count": len(v), "rows": v[:50]} for k, v in dims.items()},
        "fact_rows": {k: len(v) for k, v in facts.items()},
        "dimension_rows": {k: len(v) for k, v in dims.items()},
        "read_only": True,
        "star_schema": True,
    }


def historical_aggregation(
    wh: InstitutionalDataWarehouse,
    *,
    domain: str = "trades",
    grain: str = "day",
) -> dict[str, Any]:
    try:
        rows = wh.list(domain, limit=10_000)  # type: ignore[arg-type]
    except ValueError:
        return {"status": "unavailable", "reason": "unknown_domain", "read_only": True}

    buckets: dict[str, int] = defaultdict(int)
    for row in rows:
        ts = str(row.get("timestamp") or row.get("trading_day") or "")
        if grain == "month":
            key = ts[:7] if len(ts) >= 7 else "unknown"
        elif grain == "hour":
            key = ts[:13] if len(ts) >= 13 else "unknown"
        else:
            key = ts[:10] if len(ts) >= 10 else str(row.get("trading_day") or "unknown")
        buckets[key] += 1

    series = [{"bucket": k, "count": buckets[k]} for k in sorted(buckets)]
    return {
        "status": "available",
        "domain": domain,
        "grain": grain,
        "series": series,
        "read_only": True,
    }


def rolling_statistics(
    wh: InstitutionalDataWarehouse,
    *,
    domain: str = "trades",
    window: int = 20,
) -> dict[str, Any]:
    try:
        rows = wh.list(domain, limit=10_000)  # type: ignore[arg-type]
    except ValueError:
        return {"status": "unavailable", "reason": "unknown_domain", "read_only": True}

    pnls: list[float] = []
    for row in rows:
        payload = _payload(row)
        for key in ("net_pnl", "pnl", "profit", "net_profit"):
            if payload.get(key) is not None:
                try:
                    pnls.append(float(payload[key]))
                    break
                except (TypeError, ValueError):
                    continue

    w = max(2, min(int(window), 200))
    rolling: list[dict[str, Any]] = []
    for i in range(len(pnls)):
        if i + 1 < w:
            continue
        chunk = pnls[i + 1 - w : i + 1]
        mean = sum(chunk) / w
        wins = sum(1 for x in chunk if x > 0)
        rolling.append(
            {
                "index": i,
                "window": w,
                "mean_pnl": round(mean, 4),
                "win_rate": round(wins / w, 4),
                "sum_pnl": round(sum(chunk), 4),
            }
        )
    return {
        "status": "available" if rolling else "unavailable",
        "domain": domain,
        "window": w,
        "points": rolling[-100:],
        "read_only": True,
    }
