"""EQS analytics — timelines, latency, slippage, fills, scores, alerts."""

from __future__ import annotations

import statistics
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.execution_quality_suite.models import TIMELINE_STAGES


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
    return round(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f), 3)


def _latency_stats(values: list[float]) -> dict[str, Any]:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return {
            "average": None,
            "median": None,
            "p95": None,
            "maximum": None,
            "minimum": None,
            "sample_size": 0,
        }
    return {
        "average": round(statistics.mean(vals), 3),
        "median": round(statistics.median(vals), 3),
        "p95": _pctile(vals, 95),
        "maximum": round(max(vals), 3),
        "minimum": round(min(vals), 3),
        "sample_size": len(vals),
    }


def _collect_orders(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    sources = _as_dict(ctx.get("sources"))
    orders: list[dict[str, Any]] = []

    for row in _as_list(sources.get("journal")):
        if isinstance(row, dict):
            orders.append({**row, "_origin": "journal"})

    idw = _as_dict(sources.get("idw"))
    for domain in ("execution", "oms", "trades"):
        for row in _as_list(idw.get(domain)):
            if isinstance(row, dict):
                orders.append({**row, "_origin": f"idw:{domain}"})

    diag = _as_dict(sources.get("diagnostics"))
    for cycle in _as_list(diag.get("cycles") or diag.get("items")):
        if isinstance(cycle, dict) and (
            cycle.get("forwarded_to_oms") or cycle.get("explain") or cycle.get("decision_action")
        ):
            orders.append({**cycle, "_origin": "diagnostics"})

    return orders


def build_execution_timelines(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    timelines: list[dict[str, Any]] = []
    for order in _collect_orders(ctx)[:80]:
        base_ts = (
            order.get("timestamp")
            or order.get("recorded_at")
            or order.get("created_at")
            or order.get("filled_at")
        )
        stages_raw = _as_list(order.get("stages"))
        stage_map: dict[str, Any] = {}
        for s in stages_raw:
            if isinstance(s, dict):
                name = str(s.get("stage") or s.get("name") or s.get("key") or "")
                stage_map[name.lower()] = s

        explain = _as_dict(order.get("explain") or order.get("live_execution_explain"))
        for s in _as_list(explain.get("stages")):
            if isinstance(s, dict):
                stage_map[str(s.get("key") or s.get("stage") or "").lower()] = s

        def _ts(key: str, fallback: Any = None) -> Any:
            s = stage_map.get(key)
            if isinstance(s, dict):
                return s.get("timestamp") or s.get("at") or fallback
            return fallback

        # Map institutional stages
        mapped = [
            ("Signal Created", _ts("signal", base_ts) or _ts("session", base_ts)),
            (
                "Strategy Approved",
                _ts("strategy")
                or _ts("mtf")
                or _ts("quality")
                or (_ts("confluence") if order.get("decision_action") else None),
            ),
            ("Risk Approved", _ts("risk")),
            ("Safety Approved", _ts("safety")),
            (
                "OMS Submitted",
                order.get("oms_submitted_at")
                or _ts("oms")
                or (base_ts if order.get("forwarded_to_oms") else None),
            ),
            (
                "Gateway Sent",
                order.get("gateway_sent_at")
                or _ts("gateway")
                or (base_ts if order.get("gateway") else None),
            ),
            (
                "Broker Received",
                order.get("broker_received_at")
                or _ts("broker")
                or (base_ts if order.get("broker") else None),
            ),
            (
                "Broker Filled",
                order.get("filled_at")
                or (
                    base_ts
                    if str(order.get("execution_result") or "").lower()
                    in {"filled", "success", "ok", "done"}
                    else None
                ),
            ),
            (
                "Trade Closed",
                order.get("closed_at") or order.get("trade_closed_at"),
            ),
        ]

        timeline = []
        for name, ts in mapped:
            timeline.append(
                {
                    "stage": name,
                    "timestamp": ts,
                    "present": ts is not None,
                    "evidence_ref": {
                        "origin": order.get("_origin"),
                        "order_id": order.get("order_id")
                        or order.get("journal_id")
                        or order.get("cycle_id")
                        or order.get("id"),
                    },
                }
            )

        oid = str(
            order.get("order_id")
            or order.get("journal_id")
            or order.get("cycle_id")
            or order.get("id")
            or uuid4()
        )
        timelines.append(
            {
                "order_id": oid,
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "result": order.get("execution_result") or order.get("decision_action"),
                "timeline": timeline,
                "stages_canonical": list(TIMELINE_STAGES),
                "evidence": {
                    "oms": order.get("_origin") == "idw:oms" or bool(order.get("oms_status")),
                    "gateway": bool(order.get("gateway")),
                    "broker": bool(order.get("broker")),
                    "origin": order.get("_origin"),
                },
            }
        )
    return timelines


def build_latency_analytics(ctx: dict[str, Any]) -> dict[str, Any]:
    sources = _as_dict(ctx.get("sources"))
    strategy: list[float] = []
    oms: list[float] = []
    gateway: list[float] = []
    broker: list[float] = []
    fill: list[float] = []
    total: list[float] = []

    for row in _as_list(sources.get("journal")):
        if not isinstance(row, dict):
            continue
        lat = _f(row.get("latency_ms"))
        gw = _f(row.get("gateway_latency_ms") or _as_dict(row.get("meta")).get("gateway_latency_ms"))
        br = _f(row.get("broker_latency_ms") or _as_dict(row.get("meta")).get("broker_latency_ms"))
        oms_l = _f(row.get("oms_latency_ms") or _as_dict(row.get("meta")).get("oms_latency_ms"))
        strat = _f(
            row.get("strategy_latency_ms")
            or _as_dict(row.get("meta")).get("strategy_latency_ms")
        )
        if lat is not None:
            total.append(lat)
            fill.append(lat)
        if gw is not None:
            gateway.append(gw)
        if br is not None:
            broker.append(br)
        if oms_l is not None:
            oms.append(oms_l)
        if strat is not None:
            strategy.append(strat)

    idw = _as_dict(sources.get("idw"))
    for domain, bucket in (
        ("oms", oms),
        ("gateway", gateway),
        ("broker", broker),
        ("execution", total),
    ):
        for row in _as_list(idw.get(domain)):
            if isinstance(row, dict):
                v = _f(row.get("latency_ms") or row.get("response_ms") or row.get("duration_ms"))
                if v is not None:
                    bucket.append(v)

    live = _as_dict(sources.get("live_metrics"))
    if _f(live.get("execution_latency_ms")) is not None:
        total.append(float(live["execution_latency_ms"]))
        fill.append(float(live["execution_latency_ms"]))
    if _f(live.get("gateway_latency_ms")) is not None:
        gateway.append(float(live["gateway_latency_ms"]))

    rc1 = _as_dict(sources.get("rc1"))
    if _f(rc1.get("avg_gateway_latency_ms")) is not None:
        gateway.append(float(rc1["avg_gateway_latency_ms"]))

    # If only total known, attribute portions for display (documented as estimated)
    if total and not strategy:
        strategy = [round(t * 0.15, 3) for t in total]
    if total and not oms:
        oms = [round(t * 0.2, 3) for t in total]
    if total and not broker:
        broker = [round(t * 0.25, 3) for t in total]
    if total and not gateway:
        gateway = [round(t * 0.25, 3) for t in total]

    return {
        "strategy_latency": _latency_stats(strategy),
        "oms_latency": _latency_stats(oms),
        "gateway_latency": _latency_stats(gateway),
        "broker_latency": _latency_stats(broker),
        "fill_latency": _latency_stats(fill),
        "total_execution_latency": _latency_stats(total),
        "units": "ms",
        "note": "Missing stage latencies may be proportionally estimated from total when only total is observed",
        "never_modifies_production": True,
    }


def build_slippage_analytics(ctx: dict[str, Any]) -> dict[str, Any]:
    slips: list[float] = []
    rows_out: list[dict[str, Any]] = []
    for order in _collect_orders(ctx):
        expected_entry = _f(
            order.get("expected_entry")
            or order.get("expected_price")
            or _as_dict(order.get("meta")).get("expected_entry")
        )
        actual_entry = _f(
            order.get("actual_entry")
            or order.get("price")
            or order.get("fill_price")
            or order.get("entry_price")
        )
        expected_exit = _f(
            order.get("expected_exit")
            or _as_dict(order.get("meta")).get("expected_exit")
        )
        actual_exit = _f(
            order.get("actual_exit")
            or order.get("exit_price")
            or order.get("close_price")
        )
        slip = _f(order.get("slippage"))
        if slip is None and expected_entry is not None and actual_entry is not None:
            slip = round(actual_entry - expected_entry, 6)
        if slip is not None:
            slips.append(slip)
        if any(v is not None for v in (expected_entry, actual_entry, slip)):
            rows_out.append(
                {
                    "order_id": order.get("order_id")
                    or order.get("journal_id")
                    or order.get("id"),
                    "expected_entry": expected_entry,
                    "actual_entry": actual_entry,
                    "expected_exit": expected_exit,
                    "actual_exit": actual_exit,
                    "slippage": slip,
                    "positive_slippage": slip if slip is not None and slip > 0 else 0,
                    "negative_slippage": slip if slip is not None and slip < 0 else 0,
                }
            )

    pos = [s for s in slips if s > 0]
    neg = [s for s in slips if s < 0]
    return {
        "rows": rows_out[:100],
        "average_slippage": round(statistics.mean(slips), 6) if slips else None,
        "worst_slippage": round(min(slips), 6) if slips else None,
        "best_slippage": round(max(slips), 6) if slips else None,
        "positive_slippage_avg": round(statistics.mean(pos), 6) if pos else None,
        "negative_slippage_avg": round(statistics.mean(neg), 6) if neg else None,
        "sample_size": len(slips),
        "never_modifies_production": True,
    }


def build_fill_quality(ctx: dict[str, Any]) -> dict[str, Any]:
    full = partial = rejected = expired = cancelled = 0
    for order in _collect_orders(ctx):
        result = str(
            order.get("execution_result")
            or order.get("status")
            or order.get("oms_status")
            or order.get("decision_action")
            or ""
        ).lower()
        fill_type = str(order.get("fill_type") or "").lower()
        if "partial" in result or fill_type == "partial":
            partial += 1
        elif any(k in result for k in ("reject", "fail", "denied")):
            rejected += 1
        elif "expir" in result:
            expired += 1
        elif "cancel" in result:
            cancelled += 1
        elif any(k in result for k in ("fill", "success", "done", "ok", "execute")):
            full += 1
        elif order.get("forwarded_to_oms") is False:
            rejected += 1

    live = _as_dict(_as_dict(ctx.get("sources")).get("live_metrics"))
    full = max(full, int(live.get("fills") or 0))
    rejected = max(rejected, int(live.get("rejects") or 0) + int(live.get("oms_failures") or 0))

    attempts = full + partial + rejected + expired + cancelled
    success_rate = round(((full + partial) / attempts) * 100.0, 2) if attempts else None
    return {
        "full_fills": full,
        "partial_fills": partial,
        "rejected_orders": rejected,
        "expired_orders": expired,
        "cancelled_orders": cancelled,
        "execution_success_rate": success_rate,
        "attempts": attempts,
        "never_modifies_production": True,
    }


def build_consistency(ctx: dict[str, Any], latency: dict[str, Any]) -> dict[str, Any]:
    def _stability(stats: dict[str, Any]) -> float | None:
        avg = _f(stats.get("average"))
        mx = _f(stats.get("maximum"))
        mn = _f(stats.get("minimum"))
        n = int(stats.get("sample_size") or 0)
        if not avg or n < 2 or mx is None or mn is None:
            return None
        spread = mx - mn
        # Lower spread relative to mean → higher stability (0-100)
        score = max(0.0, min(100.0, 100.0 - (spread / max(avg, 1.0)) * 25.0))
        return round(score, 1)

    lat_stab = _stability(_as_dict(latency.get("total_execution_latency")))
    gw = _stability(_as_dict(latency.get("gateway_latency")))
    oms = _stability(_as_dict(latency.get("oms_latency")))
    br = _stability(_as_dict(latency.get("broker_latency")))
    parts = [x for x in (lat_stab, gw, oms, br) if x is not None]
    exec_stab = round(statistics.mean(parts), 1) if parts else None
    return {
        "execution_stability": exec_stab,
        "latency_stability": lat_stab,
        "broker_consistency": br,
        "gateway_consistency": gw,
        "oms_consistency": oms,
        "never_modifies_production": True,
    }


def build_broker_health(ctx: dict[str, Any]) -> dict[str, Any]:
    sources = _as_dict(ctx.get("sources"))
    idw_broker = _as_list(_as_dict(sources.get("idw")).get("broker"))
    icc = _as_dict(sources.get("icc"))
    live = _as_dict(sources.get("live_metrics"))
    rc1 = _as_dict(sources.get("rc1"))

    failures = int(live.get("oms_failures") or 0)
    reconnects = 0
    latencies: list[float] = []
    for row in idw_broker:
        if not isinstance(row, dict):
            continue
        if "reconnect" in str(row.get("event") or row.get("type") or "").lower():
            reconnects += 1
        if "fail" in str(row.get("status") or row.get("event") or "").lower():
            failures += 1
        v = _f(row.get("latency_ms") or row.get("response_ms"))
        if v is not None:
            latencies.append(v)

    avg_resp = round(statistics.mean(latencies), 3) if latencies else _f(
        rc1.get("avg_broker_latency_ms") or live.get("execution_latency_ms")
    )
    uptime = _f(icc.get("broker_uptime_pct"))
    if uptime is None:
        sections = _as_dict(icc.get("sections"))
        uptime = _f(_as_dict(sections.get("system_status")).get("broker_uptime_pct"))
    if uptime is None:
        uptime = _f(_as_dict(icc.get("system_status")).get("broker_uptime_pct"))
    if uptime is None:
        # derive from failures
        uptime = max(0.0, min(100.0, 100.0 - failures * 2.5))

    health = round(
        max(
            0.0,
            min(
                100.0,
                (uptime or 0) * 0.5
                + (100.0 - min(failures * 5, 40)) * 0.3
                + (100.0 - min((avg_resp or 0) / 10.0, 40)) * 0.2,
            ),
        ),
        1,
    )
    return {
        "connection_uptime": uptime,
        "response_latency": avg_resp,
        "execution_failures": failures,
        "reconnect_count": reconnects,
        "health_score": health,
        "sample_broker_events": len(idw_broker),
        "never_modifies_production": True,
    }


def build_execution_score(
    *,
    latency: dict[str, Any],
    slippage: dict[str, Any],
    fills: dict[str, Any],
    consistency: dict[str, Any],
    broker: dict[str, Any],
) -> dict[str, Any]:
    total_lat = _as_dict(latency.get("total_execution_latency"))
    avg_lat = _f(total_lat.get("average"))
    # Latency score: faster is better (assume 500ms = 0, 0ms = 100)
    latency_score = (
        round(max(0.0, min(100.0, 100.0 - (avg_lat / 5.0))), 1)
        if avg_lat is not None
        else 50.0
    )

    avg_slip = _f(slippage.get("average_slippage"))
    abs_slip = abs(avg_slip) if avg_slip is not None else None
    slippage_score = (
        round(max(0.0, min(100.0, 100.0 - abs_slip * 50.0)), 1)
        if abs_slip is not None
        else 50.0
    )

    fill_score = _f(fills.get("execution_success_rate"))
    if fill_score is None:
        fill_score = 50.0

    consistency_score = _f(consistency.get("execution_stability")) or 50.0
    reliability_score = _f(broker.get("health_score")) or 50.0

    overall = round(
        latency_score * 0.25
        + slippage_score * 0.2
        + fill_score * 0.25
        + consistency_score * 0.15
        + reliability_score * 0.15,
        1,
    )
    return {
        "latency": latency_score,
        "slippage": slippage_score,
        "fill_quality": fill_score,
        "consistency": consistency_score,
        "reliability": reliability_score,
        "overall_execution_score": overall,
        "scale": "0-100",
        "never_modifies_production": True,
    }


def build_evidence_links(ctx: dict[str, Any]) -> dict[str, Any]:
    sources = _as_dict(ctx.get("sources"))
    idw = _as_dict(sources.get("idw"))
    qkg = _as_dict(sources.get("qkg"))
    return {
        "oms_events": _as_list(idw.get("oms"))[:20],
        "gateway_events": _as_list(idw.get("gateway"))[:20],
        "broker_events": _as_list(idw.get("broker"))[:20],
        "audit_trail": _as_list(sources.get("audit"))[:20],
        "knowledge_graph": {
            "stats": qkg.get("stats") or qkg,
            "relationships_hint": "Use /qkg/relationships/{node_id}",
        },
        "journal_sample": _as_list(sources.get("journal"))[:10],
        "never_modifies_production": True,
    }


def build_alerts(
    *,
    latency: dict[str, Any],
    slippage: dict[str, Any],
    fills: dict[str, Any],
    broker: dict[str, Any],
    consistency: dict[str, Any],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    avg_lat = _f(_as_dict(latency.get("total_execution_latency")).get("average"))
    p95 = _f(_as_dict(latency.get("total_execution_latency")).get("p95"))
    if avg_lat is not None and avg_lat > 250:
        alerts.append(
            {
                "kind": "High latency",
                "severity": "warning" if avg_lat < 500 else "critical",
                "detail": f"Average total execution latency {avg_lat}ms",
                "read_only": True,
            }
        )
    if p95 is not None and p95 > 800:
        alerts.append(
            {
                "kind": "High latency",
                "severity": "critical",
                "detail": f"P95 latency {p95}ms",
                "read_only": True,
            }
        )

    worst = _f(slippage.get("worst_slippage"))
    avg_slip = _f(slippage.get("average_slippage"))
    if worst is not None and abs(worst) > 0.5:
        alerts.append(
            {
                "kind": "Abnormal slippage",
                "severity": "warning",
                "detail": f"Worst slippage {worst}",
                "read_only": True,
            }
        )
    if avg_slip is not None and abs(avg_slip) > 0.2:
        alerts.append(
            {
                "kind": "Abnormal slippage",
                "severity": "warning",
                "detail": f"Average slippage {avg_slip}",
                "read_only": True,
            }
        )

    success = _f(fills.get("execution_success_rate"))
    if success is not None and success < 70:
        alerts.append(
            {
                "kind": "Execution degradation",
                "severity": "critical" if success < 50 else "warning",
                "detail": f"Success rate {success}%",
                "read_only": True,
            }
        )

    if int(broker.get("execution_failures") or 0) >= 3:
        alerts.append(
            {
                "kind": "Repeated broker failures",
                "severity": "critical",
                "detail": f"Failures={broker.get('execution_failures')}",
                "read_only": True,
            }
        )

    gw = _f(consistency.get("gateway_consistency"))
    if gw is not None and gw < 55:
        alerts.append(
            {
                "kind": "Gateway instability",
                "severity": "warning",
                "detail": f"Gateway consistency score {gw}",
                "read_only": True,
            }
        )

    for a in alerts:
        a["generated_at"] = datetime.now(UTC).isoformat()
        a["never_triggers_automation"] = True
    return alerts


def build_reports(
    *,
    latency: dict[str, Any],
    slippage: dict[str, Any],
    fills: dict[str, Any],
    broker: dict[str, Any],
    score: dict[str, Any],
    alerts: list[dict[str, Any]],
) -> dict[str, Any]:
    base = {
        "latency": latency,
        "slippage": slippage,
        "fill_quality": fills,
        "broker_health": broker,
        "execution_score": score,
        "alerts": alerts,
        "advisory_only": True,
    }
    return {
        "daily": {
            **base,
            "period": "daily",
            "title": "Daily Execution Quality Report",
        },
        "weekly": {
            **base,
            "period": "weekly",
            "title": "Weekly Execution Quality Report",
        },
        "monthly": {
            **base,
            "period": "monthly",
            "title": "Monthly Execution Quality Report",
        },
        "latency_report": {
            "title": "Latency Report",
            "latency": latency,
        },
        "slippage_report": {
            "title": "Slippage Report",
            "slippage": slippage,
        },
        "broker_report": {
            "title": "Broker Report",
            "broker_health": broker,
        },
        "generated_at": datetime.now(UTC).isoformat(),
    }
