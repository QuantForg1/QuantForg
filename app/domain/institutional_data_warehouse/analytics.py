"""Read-only analytics queries over warehouse datasets."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.domain.institutional_data_warehouse.store import InstitutionalDataWarehouse


def _pnl(payload: dict[str, Any]) -> float | None:
    for key in ("net_pnl", "pnl", "profit", "netPl"):
        if payload.get(key) is not None:
            try:
                return float(payload[key])
            except (TypeError, ValueError):
                return None
    return None


def _bucket_performance(
    rows: list[dict[str, Any]],
    *,
    key_fn,
) -> dict[str, Any]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        pnl = _pnl(payload)
        if pnl is None:
            continue
        key = str(key_fn(row) or "unknown")
        buckets[key].append(pnl)
    out: dict[str, Any] = {}
    for key, pnls in buckets.items():
        n = len(pnls)
        wins = sum(1 for p in pnls if p > 0)
        out[key] = {
            "trades": n,
            "win_rate": round(wins / n, 4) if n else None,
            "net_pnl": round(sum(pnls), 4),
            "expectancy": round(sum(pnls) / n, 4) if n else None,
        }
    return out


def performance_by_strategy_version(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    rows = wh.list("trades", limit=10_000)
    return {
        "status": "available" if rows else "unavailable",
        "by_strategy_version": _bucket_performance(
            rows, key_fn=lambda r: r.get("strategy_version")
        ),
        "read_only": True,
    }


def performance_by_session(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    rows = wh.list("trades", limit=10_000)
    return {
        "status": "available" if rows else "unavailable",
        "by_session": _bucket_performance(rows, key_fn=lambda r: r.get("session")),
        "read_only": True,
    }


def performance_by_regime(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    rows = wh.list("trades", limit=10_000)

    def _regime(row: dict[str, Any]) -> str:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        return str(payload.get("regime") or payload.get("market_regime") or "unknown")

    return {
        "status": "available" if rows else "unavailable",
        "by_regime": _bucket_performance(rows, key_fn=_regime),
        "read_only": True,
    }


def no_trade_analysis(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    signal_rows = wh.list("signals", limit=10_000)
    replay_rows = wh.list("replay", limit=10_000)
    combined = signal_rows + replay_rows
    reasons: dict[str, int] = defaultdict(int)
    no_trade = 0
    for row in combined:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        decision = str(
            payload.get("decision") or payload.get("action") or ""
        ).upper()
        if decision != "NO_TRADE":
            continue
        no_trade += 1
        reason = str(
            payload.get("no_trade_reason")
            or payload.get("reason")
            or "unspecified"
        )
        reasons[reason] += 1
    return {
        "status": "available" if no_trade else "unavailable",
        "no_trade_count": no_trade,
        "reason_histogram": dict(reasons),
        "read_only": True,
        "note": "Analytics only — never fabricates avoided PnL",
    }


def governance_timeline(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    rows = wh.list("governance", limit=500)
    steps = [
        {
            "timestamp": r.get("timestamp"),
            "action": (r.get("payload") or {}).get("action"),
            "actor": (r.get("payload") or {}).get("actor"),
            "previous_state": (r.get("payload") or {}).get("previous_state"),
            "new_state": (r.get("payload") or {}).get("new_state"),
            "correlation_id": r.get("correlation_id"),
        }
        for r in rows
    ]
    return {
        "status": "available" if steps else "unavailable",
        "count": len(steps),
        "steps": steps,
        "read_only": True,
    }


def replay_coverage(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    replay = wh.list("replay", limit=10_000)
    market = wh.list("market", limit=10_000)
    target = 500
    return {
        "status": "available",
        "replay_records": len(replay),
        "market_bars": len(market),
        "coverage_ratio": round(min(1.0, len(replay) / target), 4),
        "target_replay_opportunities": target,
        "read_only": True,
        "note": "Coverage vs advisory threshold of 500 replay opportunities",
    }


def evidence_growth(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    evidence = wh.list("evidence", limit=10_000)
    by_env: dict[str, int] = defaultdict(int)
    for row in evidence:
        by_env[str(row.get("environment") or "unknown")] += 1
    return {
        "status": "available",
        "total": len(evidence),
        "by_environment": dict(by_env),
        "read_only": True,
    }


def risk_event_history(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    rows = wh.list("risk", limit=10_000) + wh.list("safety", limit=10_000)
    return {
        "status": "available" if rows else "unavailable",
        "count": len(rows),
        "events": [
            {
                "timestamp": r.get("timestamp"),
                "domain": r.get("domain"),
                "trade_id": r.get("trade_id"),
                "correlation_id": r.get("correlation_id"),
                "action": (r.get("payload") or {}).get("action"),
                "severity": (r.get("payload") or {}).get("severity"),
            }
            for r in rows[-200:]
        ],
        "read_only": True,
    }


def run_analytics(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    from app.domain.institutional_data_warehouse.dimensional import (
        historical_aggregation,
        rolling_statistics,
    )

    return {
        "performance_by_strategy_version": performance_by_strategy_version(wh),
        "performance_by_session": performance_by_session(wh),
        "performance_by_regime": performance_by_regime(wh),
        "no_trade_analysis": no_trade_analysis(wh),
        "governance_timeline": governance_timeline(wh),
        "replay_coverage": replay_coverage(wh),
        "evidence_growth": evidence_growth(wh),
        "risk_event_history": risk_event_history(wh),
        "historical_aggregation": historical_aggregation(wh, domain="trades", grain="day"),
        "rolling_statistics": rolling_statistics(wh, domain="trades", window=20),
        "read_only": True,
    }
