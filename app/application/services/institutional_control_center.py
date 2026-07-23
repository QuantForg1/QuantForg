"""Institutional Control Center (ICC) — read-only executive operational cockpit.

Aggregates institutional subsystems into one command center.
NEVER modifies Strategy, Risk, Safety, OMS, Gateway, Auto Trading,
Thresholds, Research Lab, or Data Warehouse. NEVER influences trading.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any, Literal

HealthStatus = Literal["PASS", "WARNING", "FAIL"]

GOLD = "XAUUSD"

ARCHITECTURE_NODES: list[dict[str, Any]] = [
    {
        "id": "trading_core",
        "label": "Trading Core",
        "href": "/auto-trading",
        "group": "Trading Core",
    },
    {
        "id": "risk",
        "label": "Risk Engine",
        "href": "/auto-trading",
        "group": "Trading Core",
    },
    {
        "id": "safety",
        "label": "Safety Engine",
        "href": "/auto-trading",
        "group": "Trading Core",
    },
    {
        "id": "oms",
        "label": "OMS",
        "href": "/ops",
        "group": "Trading Core",
    },
    {
        "id": "gateway",
        "label": "Gateway / Broker",
        "href": "/broker",
        "group": "Infrastructure",
    },
    {
        "id": "governance",
        "label": "Governance",
        "href": "/audit-governance",
        "group": "Governance",
    },
    {
        "id": "research",
        "label": "Research Lab",
        "href": "/institutional-research-lab",
        "group": "Research",
    },
    {
        "id": "observability",
        "label": "Observability",
        "href": "/institutional-observability",
        "group": "Observability",
    },
    {
        "id": "analytics_sic",
        "label": "Strategy Intelligence",
        "href": "/strategy-intelligence-center",
        "group": "Analytics",
    },
    {
        "id": "analytics_mri",
        "label": "Market Regime",
        "href": "/market-regime-intelligence",
        "group": "Analytics",
    },
    {
        "id": "analytics_opp",
        "label": "Opportunity Timeline",
        "href": "/opportunity-timeline",
        "group": "Analytics",
    },
    {
        "id": "analytics_pa",
        "label": "Portfolio Analytics",
        "href": "/portfolio-analytics",
        "group": "Analytics",
    },
    {
        "id": "prr",
        "label": "Production Readiness",
        "href": "/production-readiness-review",
        "group": "Analytics",
    },
    {
        "id": "idw",
        "label": "Data Warehouse",
        "href": "/institutional-data-warehouse",
        "group": "Data Warehouse",
    },
    {
        "id": "infra_health",
        "label": "Services Health",
        "href": "/ops",
        "group": "Infrastructure",
    },
]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _status(ok: bool | None, *, warn: bool = False) -> HealthStatus:
    if ok is True:
        return "PASS"
    if warn or ok is None:
        return "WARNING"
    return "FAIL"


def _safe(fn, default: Any = None) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001 — advisory aggregation
        return default


def _subsystem(name: str, status: HealthStatus, detail: str, *, href: str | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "href": href,
    }


def section_system_status() -> dict[str, Any]:
    subs: list[dict[str, Any]] = []

    # Trading / control plane
    plane = _safe(lambda: __import__(
        "app.domain.institutional_trading.operations.control_plane",
        fromlist=["get_control_plane"],
    ).get_control_plane())
    if plane is not None:
        mode = getattr(getattr(plane, "mode", None), "value", str(getattr(plane, "mode", "?")))
        kill = bool(getattr(plane, "kill_switch_armed", False))
        subs.append(
            _subsystem(
                "Trading Engine",
                "WARNING" if kill else "PASS",
                f"ops_mode={mode} kill={kill}",
                href="/auto-trading",
            )
        )
        risk_ok = not bool(getattr(plane, "daily_loss_exceeded", False))
        subs.append(
            _subsystem(
                "Risk Engine",
                _status(risk_ok),
                "daily_loss_ok" if risk_ok else "daily_loss_exceeded",
                href="/auto-trading",
            )
        )
        subs.append(
            _subsystem(
                "Safety Engine",
                "WARNING" if kill else "PASS",
                "kill_armed" if kill else "safety_clear",
                href="/auto-trading",
            )
        )
        oms_allowed = bool(_safe(lambda: plane.oms_orders_allowed(), False))
        subs.append(
            _subsystem(
                "OMS",
                _status(oms_allowed, warn=not oms_allowed),
                "orders_allowed" if oms_allowed else "orders_blocked",
                href="/ops",
            )
        )
    else:
        for name in ("Trading Engine", "Risk Engine", "Safety Engine", "OMS"):
            subs.append(_subsystem(name, "WARNING", "control plane unavailable"))

    # Gateway / broker via auto trading facts
    facts_pack = _safe(
        lambda: __import__(
            "app.application.services.auto_trading_status",
            fromlist=["build_status_facts"],
        ).build_status_facts(
            __import__(
                "app.domain.institutional_trading.operations.control_plane",
                fromlist=["get_control_plane"],
            ).get_control_plane()
        )
    )
    gw = False
    br = False
    if isinstance(facts_pack, tuple) and facts_pack:
        live_facts = facts_pack[0]
        gw = bool(getattr(live_facts, "gateway_connected", False))
        br = bool(getattr(live_facts, "broker_connected", False) or getattr(live_facts, "mt5_connected", False))
        meta = facts_pack[1] if len(facts_pack) > 1 and isinstance(facts_pack[1], dict) else {}
        gw = gw or bool(meta.get("gateway_connected") or meta.get("gateway_ok"))
        br = br or bool(meta.get("broker_connected") or meta.get("mt5_connected"))
    elif isinstance(facts_pack, dict):
        gw = bool(facts_pack.get("gateway_connected") or facts_pack.get("gateway_ok"))
        br = bool(facts_pack.get("broker_connected") or facts_pack.get("mt5_connected"))
    if facts_pack is not None:
        subs.append(
            _subsystem(
                "Gateway",
                _status(gw, warn=not gw),
                "reachable" if gw else "unreachable",
                href="/broker",
            )
        )
        subs.append(
            _subsystem(
                "Broker",
                _status(br, warn=not br),
                "connected" if br else "disconnected",
                href="/broker",
            )
        )
    else:
        settings = _safe(
            lambda: __import__("core.config.settings", fromlist=["get_settings"]).get_settings()
        )
        has_url = bool(getattr(settings, "mt5_gateway_base_url", None)) if settings else False
        subs.append(
            _subsystem(
                "Gateway",
                _status(None if not has_url else True, warn=True),
                "settings probe",
                href="/broker",
            )
        )
        subs.append(_subsystem("Broker", "WARNING", "status unread", href="/broker"))

    # Scheduler / ITE runtime
    rt = _safe(
        lambda: __import__(
            "app.application.services.institutional_ite_runtime",
            fromlist=["get_ite_runtime"],
        ).get_ite_runtime()
    )
    if rt is not None and callable(getattr(rt, "snapshot", None)):
        snap = _safe(rt.snapshot, {})
        cycles = (snap or {}).get("cycle_count") or (snap or {}).get("cycles")
        subs.append(
            _subsystem(
                "Scheduler",
                "PASS",
                f"ite_runtime cycles={cycles}",
                href="/ops",
            )
        )
    else:
        subs.append(_subsystem("Scheduler", "WARNING", "ITE runtime not observable", href="/ops"))

    # Replay
    replay_ok = _safe(
        lambda: __import__(
            "app.domain.replay_evidence_lab.evidence_store",
            fromlist=["get_evidence_database"],
        ).get_evidence_database()
        is not None
    )
    subs.append(
        _subsystem(
            "Replay Engine",
            _status(True if replay_ok else None, warn=not replay_ok),
            "evidence store available" if replay_ok else "unavailable",
            href="/replay-evidence-lab",
        )
    )

    # Research Lab
    irl = _safe(
        lambda: __import__(
            "app.domain.institutional_research_lab",
            fromlist=["get_irl"],
        ).get_irl().dashboard()
    )
    if isinstance(irl, dict):
        counts = irl.get("counts") or {}
        subs.append(
            _subsystem(
                "Research Lab",
                "PASS",
                f"experiments={counts.get('experiments', 0)}",
                href="/institutional-research-lab",
            )
        )
    else:
        subs.append(
            _subsystem("Research Lab", "WARNING", "IRL unread", href="/institutional-research-lab")
        )

    # Data Warehouse
    inv = _safe(
        lambda: __import__(
            "app.domain.institutional_data_warehouse.store",
            fromlist=["get_warehouse"],
        ).get_warehouse().inventory()
    )
    if isinstance(inv, dict):
        total = int(inv.get("total_records") or 0)
        subs.append(
            _subsystem(
                "Data Warehouse",
                "PASS" if total >= 0 else "WARNING",
                f"records={total}",
                href="/institutional-data-warehouse",
            )
        )
    else:
        subs.append(
            _subsystem(
                "Data Warehouse",
                "WARNING",
                "warehouse unread",
                href="/institutional-data-warehouse",
            )
        )

    pass_n = sum(1 for s in subs if s["status"] == "PASS")
    warn_n = sum(1 for s in subs if s["status"] == "WARNING")
    fail_n = sum(1 for s in subs if s["status"] == "FAIL")
    overall: HealthStatus = "PASS"
    if fail_n:
        overall = "FAIL"
    elif warn_n:
        overall = "WARNING"

    return {
        "subsystems": subs,
        "counts": {"pass": pass_n, "warning": warn_n, "fail": fail_n, "total": len(subs)},
        "overall": overall,
    }


def section_live_trading() -> dict[str, Any]:
    out: dict[str, Any] = {
        "symbol": GOLD,
        "session": None,
        "market_regime": None,
        "mtf_score": None,
        "quality": None,
        "confluence": None,
        "risk_status": None,
        "safety_status": None,
        "execution_decision": None,
        "last_evaluation": None,
        "last_trade": None,
    }

    # Session from domain helper if available
    out["session"] = _safe(
        lambda: __import__(
            "app.domain.institutional_trading.session_filter",
            fromlist=["classify_session_utc"],
        ).classify_session_utc(datetime.now(UTC)).value
    )

    regime = _safe(
        lambda: __import__(
            "app.application.services.market_regime_intelligence",
            fromlist=["build_market_regime_intelligence"],
        ).build_market_regime_intelligence(limit=20)
    )
    if isinstance(regime, dict):
        current = regime.get("current") if isinstance(regime.get("current"), dict) else {}
        out["market_regime"] = current.get("current_regime") or current.get("regime")

    # Diagnostics latest cycle
    diag = _safe(
        lambda: __import__(
            "app.application.services.strategy_diagnostics",
            fromlist=["get_strategy_diagnostics_store"],
        ).get_strategy_diagnostics_store().snapshot(limit=5)
    )
    if isinstance(diag, dict):
        cycles = list(diag.get("cycles") or [])
        if cycles:
            c = cycles[0] if isinstance(cycles[0], dict) else {}
            out["last_evaluation"] = c.get("observed_at") or c.get("timestamp") or c.get("at")
            out["mtf_score"] = c.get("mtf_score") or (c.get("mtf") or {}).get("score")
            out["quality"] = c.get("quality_score") or (c.get("quality") or {}).get("score")
            out["confluence"] = c.get("confluence_score") or (c.get("confluence") or {}).get("score")
            out["execution_decision"] = (
                c.get("decision")
                or c.get("execution_decision")
                or c.get("action")
                or c.get("outcome")
            )
            out["risk_status"] = c.get("risk_status") or (c.get("risk") or {}).get("status")
            out["safety_status"] = c.get("safety_status") or (c.get("safety") or {}).get("status")

    plane = _safe(
        lambda: __import__(
            "app.domain.institutional_trading.operations.control_plane",
            fromlist=["get_control_plane"],
        ).get_control_plane()
    )
    if plane is not None:
        if out["risk_status"] is None:
            out["risk_status"] = (
                "FAIL" if getattr(plane, "daily_loss_exceeded", False) else "PASS"
            )
        if out["safety_status"] is None:
            out["safety_status"] = (
                "FAIL" if getattr(plane, "kill_switch_armed", False) else "PASS"
            )

    # Last trade from portfolio analytics trades sample
    pa = _safe(
        lambda: __import__(
            "app.application.services.institutional_portfolio_analytics",
            fromlist=["build_institutional_portfolio_analytics"],
        ).build_institutional_portfolio_analytics(days=30)
    )
    if isinstance(pa, dict):
        trades = pa.get("trades") or pa.get("closed_trades") or []
        if trades and isinstance(trades[0], dict):
            t = trades[0]
            out["last_trade"] = {
                "id": t.get("id") or t.get("trade_id"),
                "pnl": t.get("profit_loss") or t.get("pnl"),
                "exit_time": t.get("exit_time") or t.get("timestamp"),
            }

    return out


def section_portfolio() -> dict[str, Any]:
    pa = _safe(
        lambda: __import__(
            "app.application.services.institutional_portfolio_analytics",
            fromlist=["build_institutional_portfolio_analytics"],
        ).build_institutional_portfolio_analytics(days=90)
    )
    if not isinstance(pa, dict):
        return {
            "balance": None,
            "equity": None,
            "floating_pnl": None,
            "closed_pnl": None,
            "drawdown": None,
            "health_score": None,
            "available": False,
        }
    sections = pa.get("sections") if isinstance(pa.get("sections"), dict) else {}
    dash = sections.get("dashboard") if isinstance(sections.get("dashboard"), dict) else {}
    risk = sections.get("risk") if isinstance(sections.get("risk"), dict) else {}
    health = sections.get("health_score") if isinstance(sections.get("health_score"), dict) else {}
    return {
        "balance": dash.get("balance"),
        "equity": dash.get("equity"),
        "floating_pnl": dash.get("floating_pnl"),
        "closed_pnl": dash.get("closed_pnl"),
        "drawdown": risk.get("current_drawdown_pct") or risk.get("max_drawdown_pct"),
        "health_score": health.get("score"),
        "health_status": health.get("status"),
        "available": True,
    }


def section_research() -> dict[str, Any]:
    lab = _safe(
        lambda: __import__(
            "app.domain.institutional_research_lab",
            fromlist=["get_irl"],
        ).get_irl()
    )
    if lab is None:
        return {
            "running_experiments": 0,
            "completed_experiments": 0,
            "leaderboard_top5": [],
            "latest_benchmark": None,
            "promotion_queue": [],
            "available": False,
        }
    dash = _safe(lab.dashboard, {}) or {}
    counts = dash.get("counts") if isinstance(dash, dict) else {}
    board = _safe(lambda: lab.leaderboard(rank_by="composite", limit=5), {}) or {}
    bench = _safe(
        lambda: __import__(
            "app.application.services.institutional_research_lab",
            fromlist=["irl_benchmark_view"],
        ).irl_benchmark_view(),
        {},
    )
    experiments = _safe(lambda: lab.list_experiments(limit=50), []) or []
    promotion_queue = [
        {
            "uuid": e.get("uuid"),
            "name": e.get("name"),
            "verdict": e.get("verdict"),
        }
        for e in experiments
        if e.get("verdict") == "Research Passed"
    ][:10]
    latest_benchmark = None
    if isinstance(bench, dict):
        rows = bench.get("experiments") or []
        if rows:
            latest_benchmark = rows[0]
    return {
        "running_experiments": (counts or {}).get("running", 0),
        "completed_experiments": (counts or {}).get("completed", 0),
        "leaderboard_top5": (board or {}).get("rows") or [],
        "latest_benchmark": latest_benchmark,
        "promotion_queue": promotion_queue,
        "note": "Promotion continues via governance — ICC never promotes",
        "available": True,
    }


def section_analytics() -> dict[str, Any]:
    links = [
        {
            "id": "strategy_intelligence",
            "label": "Strategy Intelligence",
            "href": "/strategy-intelligence-center",
            "status": "PASS",
        },
        {
            "id": "market_regime",
            "label": "Market Regime Intelligence",
            "href": "/market-regime-intelligence",
            "status": "PASS",
        },
        {
            "id": "opportunity_timeline",
            "label": "Opportunity Timeline",
            "href": "/opportunity-timeline",
            "status": "PASS",
        },
        {
            "id": "portfolio_analytics",
            "label": "Portfolio Analytics",
            "href": "/portfolio-analytics",
            "status": "PASS",
        },
        {
            "id": "production_readiness",
            "label": "Production Readiness",
            "href": "/production-readiness-review",
            "status": "PASS",
        },
    ]
    prr = _safe(
        lambda: __import__(
            "app.application.services.institutional_production_readiness_review",
            fromlist=["build_institutional_production_readiness_review"],
        ).build_institutional_production_readiness_review(write_report=False)
    )
    prr_summary = None
    if isinstance(prr, dict):
        prr_summary = {
            "score": prr.get("overall_production_readiness_score"),
            "recommendation": prr.get("recommendation"),
        }
        for link in links:
            if link["id"] == "production_readiness":
                link["status"] = (
                    "PASS"
                    if (prr.get("overall_production_readiness_score") or 0) >= 65
                    else "WARNING"
                )
    return {"desks": links, "production_readiness": prr_summary}


def section_data_warehouse() -> dict[str, Any]:
    wh = _safe(
        lambda: __import__(
            "app.domain.institutional_data_warehouse.store",
            fromlist=["get_warehouse"],
        ).get_warehouse()
    )
    if wh is None:
        return {"available": False}
    inv = _safe(wh.inventory, {}) or {}
    storage = _safe(wh.storage_stats, {}) or {}
    flow = _safe(lambda: wh.event_flow(limit=20), []) or []
    dq = _safe(
        lambda: __import__(
            "app.domain.institutional_data_warehouse.quality_monitor",
            fromlist=["run_data_quality_monitor"],
        ).run_data_quality_monitor(wh),
        {},
    ) or {}
    recent = flow[-5:] if flow else []
    event_rate = None
    if len(recent) >= 2:
        event_rate = sum(int(x.get("records") or 0) for x in recent)
    return {
        "available": True,
        "event_rate": event_rate,
        "events_stored": inv.get("total_records"),
        "storage_health": "PASS" if (storage.get("approx_mb") or 0) < 512 else "WARNING",
        "integrity_score": dq.get("integrity_score"),
        "latency": dq.get("latency_seconds_avg"),
        "missing_events": dq.get("missing_events"),
        "duplicate_events": dq.get("duplicates"),
        "approx_mb": storage.get("approx_mb"),
    }


def section_alerts() -> dict[str, Any]:
    alerts: list[dict[str, Any]] = []
    # Control plane / kill / daily loss synthetic active alerts
    plane = _safe(
        lambda: __import__(
            "app.domain.institutional_trading.operations.control_plane",
            fromlist=["get_control_plane"],
        ).get_control_plane()
    )
    if plane is not None:
        if getattr(plane, "kill_switch_armed", False):
            alerts.append(
                {
                    "id": "kill-armed",
                    "category": "Safety",
                    "severity": "Critical",
                    "message": "Kill switch armed",
                    "active": True,
                }
            )
        if getattr(plane, "daily_loss_exceeded", False):
            alerts.append(
                {
                    "id": "daily-loss",
                    "category": "Risk",
                    "severity": "High",
                    "message": "Daily loss limit exceeded",
                    "active": True,
                }
            )

    dq = section_data_warehouse()
    if dq.get("available") and (dq.get("integrity_score") is not None) and float(dq["integrity_score"]) < 55:
        alerts.append(
            {
                "id": "idw-integrity",
                "category": "Data",
                "severity": "Medium",
                "message": f"Warehouse integrity {dq['integrity_score']}",
                "active": True,
            }
        )
    if dq.get("duplicate_events"):
        alerts.append(
            {
                "id": "idw-dupes",
                "category": "Data",
                "severity": "Low",
                "message": f"Duplicate events={dq.get('duplicate_events')}",
                "active": True,
            }
        )

    research = section_research()
    if research.get("available") and int(research.get("running_experiments") or 0) > 0:
        alerts.append(
            {
                "id": "research-running",
                "category": "Research",
                "severity": "Low",
                "message": f"{research['running_experiments']} research experiment(s) running",
                "active": True,
            }
        )

    # Optional plane alerts list
    plane_alerts = _safe(lambda: plane.list_alerts(active_only=True) if plane and hasattr(plane, "list_alerts") else None)
    if isinstance(plane_alerts, list):
        for a in plane_alerts[:20]:
            if isinstance(a, dict):
                alerts.append(
                    {
                        "id": str(a.get("id") or a.get("alert_id") or len(alerts)),
                        "category": str(a.get("category") or "Infrastructure"),
                        "severity": str(a.get("severity") or "Medium"),
                        "message": str(a.get("message") or a.get("detail") or "alert"),
                        "active": True,
                    }
                )

    # Keep active only
    alerts = [a for a in alerts if a.get("active")]
    return {"alerts": alerts, "count": len(alerts)}


def section_operational_timeline() -> dict[str, Any]:
    events: list[dict[str, Any]] = []

    diag = _safe(
        lambda: __import__(
            "app.application.services.strategy_diagnostics",
            fromlist=["get_strategy_diagnostics_store"],
        ).get_strategy_diagnostics_store().snapshot(limit=15)
    )
    if isinstance(diag, dict):
        for c in list(diag.get("cycles") or [])[:10]:
            if not isinstance(c, dict):
                continue
            ts = c.get("observed_at") or c.get("timestamp") or c.get("at") or _now()
            events.append(
                {
                    "timestamp": ts,
                    "kind": "Scheduler Cycle",
                    "detail": str(c.get("decision") or c.get("outcome") or "cycle"),
                }
            )
            if c.get("signal") or c.get("signal_generated"):
                events.append({"timestamp": ts, "kind": "Signal Generated", "detail": "signal"})
            risk = str(c.get("risk_status") or (c.get("risk") or {}).get("status") or "")
            if risk.upper() in {"PASS", "OK", "APPROVED"}:
                events.append({"timestamp": ts, "kind": "Risk PASS", "detail": risk})
            safety = str(c.get("safety_status") or (c.get("safety") or {}).get("status") or "")
            if safety.upper() in {"PASS", "OK", "APPROVED"}:
                events.append({"timestamp": ts, "kind": "Safety PASS", "detail": safety})

    # Warehouse ingest flow
    flow = _safe(
        lambda: __import__(
            "app.domain.institutional_data_warehouse.store",
            fromlist=["get_warehouse"],
        ).get_warehouse().event_flow(limit=10),
        [],
    ) or []
    for row in flow:
        events.append(
            {
                "timestamp": row.get("at"),
                "kind": "Data Warehouse Ingest",
                "detail": f"{row.get('domain')} +{row.get('records')}",
            }
        )

    # Research jobs
    jobs = _safe(
        lambda: __import__(
            "app.domain.institutional_research_lab",
            fromlist=["get_irl"],
        ).get_irl().list_jobs(limit=5),
        [],
    ) or []
    for j in jobs:
        kind = "Research Completed" if j.get("status") == "Completed" else "Research Job"
        events.append(
            {
                "timestamp": j.get("completed_at") or j.get("created_at"),
                "kind": kind,
                "detail": f"job={j.get('job_id')} window={j.get('window')}",
            }
        )

    events = [e for e in events if e.get("timestamp")]
    events.sort(key=lambda e: str(e.get("timestamp")), reverse=True)
    return {"events": events[:40], "count": len(events[:40])}


def section_executive_kpis(
    *,
    system: dict[str, Any],
    portfolio: dict[str, Any],
    research: dict[str, Any],
    warehouse: dict[str, Any],
    analytics: dict[str, Any],
) -> dict[str, Any]:
    sys_counts = system.get("counts") or {}
    total = max(int(sys_counts.get("total") or 1), 1)
    pass_n = int(sys_counts.get("pass") or 0)
    platform_health = round(100.0 * pass_n / total, 1)

    trading_readiness = 70.0
    if system.get("overall") == "PASS":
        trading_readiness = 88.0
    elif system.get("overall") == "FAIL":
        trading_readiness = 35.0

    stability = platform_health
    research_progress = 40.0
    if research.get("available"):
        completed = int(research.get("completed_experiments") or 0)
        research_progress = min(100.0, 30.0 + completed * 10.0 + len(research.get("leaderboard_top5") or []) * 5.0)

    data_integrity = float(warehouse.get("integrity_score") or 50.0)
    availability = 90.0 if system.get("overall") != "FAIL" else 55.0

    prr = (analytics.get("production_readiness") or {})
    if prr.get("score") is not None:
        trading_readiness = round((trading_readiness + float(prr["score"])) / 2.0, 1)

    health = portfolio.get("health_score")
    if health is not None:
        platform_health = round((platform_health + float(health)) / 2.0, 1)

    return {
        "overall_platform_health": platform_health,
        "trading_readiness": trading_readiness,
        "operational_stability": stability,
        "research_progress": round(research_progress, 1),
        "data_integrity": round(data_integrity, 1),
        "system_availability": availability,
    }


def section_architecture() -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for node in ARCHITECTURE_NODES:
        groups.setdefault(str(node["group"]), []).append(node)
    return {
        "nodes": ARCHITECTURE_NODES,
        "groups": groups,
        "clickable": True,
        "read_only": True,
    }


def build_institutional_control_center() -> dict[str, Any]:
    """Compose full ICC payload — read-only aggregation only."""
    t0 = time.perf_counter()
    system = section_system_status()
    live = section_live_trading()
    portfolio = section_portfolio()
    research = section_research()
    analytics = section_analytics()
    warehouse = section_data_warehouse()
    alerts = section_alerts()
    timeline = section_operational_timeline()
    kpis = section_executive_kpis(
        system=system,
        portfolio=portfolio,
        research=research,
        warehouse=warehouse,
        analytics=analytics,
    )
    architecture = section_architecture()
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    return {
        "schema_version": "1.0.0",
        "mode": "institutional_control_center",
        "mutates_engines": False,
        "influences_trading": False,
        "analytics_only": True,
        "advisory_only": True,
        "never_modifies_strategy_risk_safety_oms_gateway_auto_trading_thresholds_research_warehouse": True,
        "observed_at": _now(),
        "elapsed_ms": elapsed_ms,
        "symbol": GOLD,
        "sections": {
            "system_status": system,
            "live_trading": live,
            "portfolio": portfolio,
            "research": research,
            "analytics": analytics,
            "data_warehouse": warehouse,
            "alerts": alerts,
            "operational_timeline": timeline,
            "executive_kpis": kpis,
            "architecture": architecture,
        },
        "executive_kpis": kpis,
        "system_overall": system.get("overall"),
    }
