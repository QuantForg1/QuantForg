"""NOC Command Center aggregator — observe-only production telemetry.

Never mutates strategy, risk, safety, OMS, gateway, or MT5.
Never fabricates metrics. Missing data → null / empty / elegant gaps.
Never returns tokens, secrets, or credentials.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

_SECRET_PARTS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "secrets",
        "token",
        "apikey",
        "authorization",
        "credential",
        "credentials",
        "bearer",
    }
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _is_secret_key(key: str) -> bool:
    """True for credential-bearing field names only."""
    parts = [p for p in str(key).lower().replace("-", "_").split("_") if p]
    if not parts:
        return False
    # Allow operational boolean/meta flags that mention secrets without carrying them.
    joined = "_".join(parts)
    if joined.startswith("never_") or joined.startswith("no_"):
        return False
    if parts[0] in {"flags", "has"} and any(p.startswith("expose") for p in parts):
        return False
    if "api" in parts and "key" in parts:
        return True
    if "private" in parts and "key" in parts:
        return True
    return any(p in _SECRET_PARTS for p in parts)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if _is_secret_key(str(k)):
                out[str(k)] = "[redacted]"
            else:
                out[str(k)] = _redact(v)
        return out
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _tone(ok: bool | None, *, warn: bool = False) -> str:
    if ok is True:
        return "healthy"
    if warn:
        return "warning"
    if ok is False:
        return "critical"
    return "unknown"


def _safe_call(label: str, fn: Any, default: Any = None) -> Any:
    try:
        return fn()
    except Exception:
        logger.exception("noc_collect_failed", section=label)
        return default


def _git_commit() -> str | None:
    try:
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )

        cc = get_control_plane().control_center()
        commit = cc.get("git_commit")
        return str(commit) if commit else None
    except Exception:
        return None


def _header(*, settings: Any) -> dict[str, Any]:
    env = str(
        getattr(settings, "environment", None)
        or getattr(settings, "app_env", None)
        or "unknown"
    )
    version = str(getattr(settings, "app_version", None) or "unknown")
    return {
        "title": "QuantForg Command Center",
        "live": True,
        "environment": env,
        "version": version,
        "commit_sha": _git_commit(),
        "deployment_time": None,  # filled by Railway meta only when known; never invent
        "railway_status": "unknown",
        "as_of": _now(),
        "observe_only": True,
    }


def _health_cards(
    *,
    _plane: Any,
    settings: Any,
    auto: Any,
    services: dict[str, Any],
    pvm: dict[str, Any],
) -> list[dict[str, Any]]:
    facts = getattr(auto, "facts", None)
    exec_state = getattr(auto, "execution_state", None) or {}
    live = getattr(auto, "live", None) or {}

    gw = bool(getattr(facts, "gateway_connected", False)) if facts else False
    broker = bool(getattr(facts, "broker_connected", False)) if facts else False
    mkt = bool(getattr(facts, "market_data_live", False)) if facts else False
    exec_on = bool(getattr(settings, "execution_enabled", False))
    mt5_at = bool(getattr(facts, "mt5_autotrading_enabled", False)) if facts else False
    run_state = str(exec_state.get("auto_trading_run_state") or "off")

    svc_list = services.get("services") if isinstance(services, dict) else None
    svc_by_name: dict[str, dict[str, Any]] = {}
    if isinstance(svc_list, list):
        for row in svc_list:
            if isinstance(row, dict) and row.get("name"):
                svc_by_name[str(row["name"]).lower()] = row

    def _svc(name: str) -> dict[str, Any]:
        return svc_by_name.get(name.lower()) or {}

    def card(
        key: str,
        *,
        ok: bool | None,
        warn: bool = False,
        heartbeat: Any = None,
        latency_ms: Any = None,
        detail: str = "",
    ) -> dict[str, Any]:
        return {
            "key": key,
            "label": key,
            "status": _tone(ok, warn=warn),
            "last_heartbeat": heartbeat,
            "latency_ms": latency_ms,
            "detail": detail or None,
        }

    ai_action = None
    if isinstance(pvm.get("last_validation"), dict):
        ai_action = pvm["last_validation"].get("ai_action")
    ai_ok: bool | None = None
    ai_warn = False
    if ai_action:
        action_u = str(ai_action).upper()
        if action_u in {"BUY", "SELL"}:
            ai_ok = True
        elif action_u == "NO_TRADE":
            ai_ok = True
            ai_warn = True
        elif action_u in {"WATCH", "UNKNOWN"}:
            ai_warn = True

    oms_status = str(pvm.get("oms_status") or "").upper()
    oms_ok = (
        True
        if oms_status in {"PASS", "OK", "HEALTHY"}
        else False if oms_status in {"FAIL", "CRITICAL"} else None
    )

    return [
        card(
            "AI Engine",
            ok=ai_ok,
            warn=ai_warn or ai_ok is None,
            detail=f"last_signal={ai_action or '—'}",
            heartbeat=pvm.get("last_validation_id"),
        ),
        card(
            "Gateway",
            ok=gw,
            heartbeat=_svc("gateway").get("heartbeat_at")
            or live.get("gateway_checked_at"),
            latency_ms=_svc("gateway").get("latency_ms")
            or live.get("gateway_latency_ms"),
            detail=_svc("gateway").get("last_error") or "",
        ),
        card(
            "OMS",
            ok=oms_ok if oms_ok is not None else gw,
            warn=oms_status in {"UNKNOWN", "REACHED"},
            detail=f"status={oms_status or 'UNKNOWN'}",
            latency_ms=_svc("oms").get("latency_ms"),
            heartbeat=_svc("oms").get("heartbeat_at"),
        ),
        card(
            "MT5",
            ok=broker,
            heartbeat=_svc("mt5").get("heartbeat_at") or live.get("mt5_checked_at"),
            latency_ms=_svc("mt5").get("latency_ms") or live.get("mt5_latency_ms"),
            detail=_svc("mt5").get("last_error") or "",
        ),
        card(
            "Broker",
            ok=broker,
            detail="connected" if broker else "disconnected",
            latency_ms=live.get("broker_latency_ms"),
        ),
        card(
            "Railway",
            ok=True if mkt or gw else None,
            warn=not (mkt or gw),
            detail="API process alive (NOC probe)",
            heartbeat=_now(),
        ),
        card(
            "Execution Enabled",
            ok=exec_on,
            detail="EXECUTION_ENABLED" if exec_on else "EXECUTION_ENABLED=false",
        ),
        card(
            "AutoTrading",
            ok=run_state == "running"
            and bool(getattr(auto, "safety", None) and auto.safety.allowed),
            warn=run_state == "running"
            and not (getattr(auto, "safety", None) and auto.safety.allowed),
            detail=f"run_state={run_state} mt5_autotrading={mt5_at}",
        ),
    ]


# Display labels for NOC (observe-only); underlying stage keys remain PVM values.
_PIPELINE_DISPLAY: dict[str, str] = {
    "Context": "Context Builder",
    "AI": "AI Decision",
    "Risk": "Risk Engine",
    "Position Open": "Position",
}


def _pipeline_from_pvm(pvm: dict[str, Any]) -> dict[str, Any]:
    from app.domain.institutional_trading.production_validation_mode.models import (
        PIPELINE_ORDER,
    )

    last = _as_dict(pvm.get("last_validation"))
    raw_pipeline = last.get("pipeline")
    pipeline: list[Any] = list(raw_pipeline) if isinstance(raw_pipeline, list) else []
    by_stage: dict[str, dict[str, Any]] = {}
    for row in pipeline:
        if not isinstance(row, dict):
            continue
        key = str(row.get("stage") or "")
        if not key:
            continue
        status = str(row.get("status") or "PENDING").upper()
        mapped = {
            "PASS": "PASS",
            "FAIL": "FAIL",
            "PENDING": "WAITING",
            "SKIP": "WAITING",
            "RUNNING": "RUNNING",
        }.get(status, status)
        by_stage[key] = {
            "stage": _PIPELINE_DISPLAY.get(key, key),
            "stage_key": key,
            "status": mapped,
            "timestamp": row.get("timestamp"),
            "latency_ms": row.get("latency_ms"),
            "reason": row.get("reason") or None,
        }

    # Full pipeline always; missing stages → WAITING.
    nodes: list[dict[str, Any]] = []
    for stage in PIPELINE_ORDER:
        key = stage.value
        if key in by_stage:
            nodes.append(by_stage[key])
        else:
            nodes.append(
                {
                    "stage": _PIPELINE_DISPLAY.get(key, key),
                    "stage_key": key,
                    "status": "WAITING",
                    "timestamp": None,
                    "latency_ms": None,
                    "reason": None,
                }
            )
    return {
        "validation_id": last.get("validation_id") or pvm.get("last_validation_id"),
        "final_result": last.get("final_result"),
        "first_blocker": last.get("first_blocker") or pvm.get("current_blocker"),
        "nodes": nodes,
        "as_of": last.get("timestamp") or pvm.get("as_of"),
    }


def _ai_engine(*, diagnostics: dict[str, Any], pvm: dict[str, Any]) -> dict[str, Any]:
    latest = _as_dict(diagnostics.get("latest"))
    last = _as_dict(pvm.get("last_validation"))
    thresholds = _as_dict(diagnostics.get("thresholds"))
    reasons: list[str] = []
    for key in ("decision_reasons", "reasons", "no_trade_reasons"):
        raw = latest.get(key) or last.get(key)
        if isinstance(raw, list):
            reasons.extend(str(r) for r in raw if str(r).strip())
    # de-dupe preserve order
    seen: set[str] = set()
    unique_reasons: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            unique_reasons.append(r)
    for r in last.get("no_trade_reasons") or []:
        s = str(r)
        if s and s not in seen:
            seen.add(s)
            unique_reasons.append(s)

    return {
        "current_session": pvm.get("current_session") or latest.get("session") or "—",
        "symbol": last.get("symbol") or latest.get("symbol") or "—",
        "decision": last.get("ai_action") or latest.get("decision_action") or "—",
        "quality_score": (
            last.get("quality_score")
            if last.get("quality_score") is not None
            else latest.get("quality")
        ),
        "threshold": thresholds.get("required_quality"),
        "confidence": (
            last.get("ai_confidence")
            if last.get("ai_confidence") is not None
            else latest.get("confidence")
        ),
        "confluence": last.get("confluence"),
        "mtf_alignment": last.get("mtf_alignment"),
        "liquidity": last.get("liquidity"),
        "spread": last.get("spread") or latest.get("spread"),
        "atr": last.get("atr") or latest.get("atr"),
        "fvg": last.get("fvg"),
        "order_blocks": last.get("order_blocks"),
        "bos": last.get("bos"),
        "choch": last.get("choch"),
        "risk_score": last.get("risk_score"),
        "expected_rr": last.get("expected_rr"),
        "reasons": unique_reasons,
        "current_blocker": pvm.get("current_blocker"),
    }


def _market_context(
    *, diagnostics: dict[str, Any], pvm: dict[str, Any], auto: Any
) -> dict[str, Any]:
    latest = _as_dict(diagnostics.get("latest"))
    last = _as_dict(pvm.get("last_validation"))
    diag = _as_dict(latest.get("market_context_diagnostics"))
    facts = getattr(auto, "facts", None)
    return {
        "trend": diag.get("trend") or latest.get("trend") or "—",
        "market_structure": diag.get("structure") or "—",
        "mtf_alignment": last.get("mtf_alignment") or diag.get("mtf") or "—",
        "session": pvm.get("current_session") or diag.get("trading_session") or "—",
        "session_allowed": diag.get("session_allowed"),
        "news_protection": diag.get("news") or diag.get("news_protection") or "—",
        "volatility": diag.get("volatility") or "—",
        "spread": last.get("spread") or diag.get("spread"),
        "atr": last.get("atr") or diag.get("atr"),
        "liquidity": last.get("liquidity"),
        "market_data_live": (
            bool(getattr(facts, "market_data_live", False)) if facts else None
        ),
        "snapshot_present": latest.get("snapshot_present"),
    }


def _positions_read_only() -> list[dict[str, Any]]:
    """Best-effort open positions from ITE runtime PME — never opens/closes."""
    rows: list[dict[str, Any]] = []
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime

        runtime = get_ite_runtime()
        if runtime is None:
            return rows
        engine = getattr(getattr(runtime, "position_management", None), "engine", None)
        positions = getattr(engine, "_positions", None) or {}
        for ticket, pos in list(positions.items()):
            rows.append(
                {
                    "ticket": int(ticket) if str(ticket).isdigit() else ticket,
                    "symbol": getattr(pos, "symbol", None),
                    "direction": str(
                        getattr(getattr(pos, "direction", None), "value", None)
                        or getattr(pos, "side", None)
                        or getattr(pos, "type", None)
                        or "—"
                    ),
                    "entry": str(
                        getattr(pos, "entry_price", None)
                        or getattr(pos, "price_open", None)
                        or "—"
                    ),
                    "current_price": str(
                        getattr(pos, "current_price", None)
                        or getattr(pos, "price_current", None)
                        or "—"
                    ),
                    "profit": str(
                        getattr(pos, "profit", None)
                        or getattr(pos, "unrealized_pnl", None)
                        or "—"
                    ),
                    "swap": str(getattr(pos, "swap", None) or "—"),
                    "duration": str(
                        getattr(pos, "duration", None)
                        or getattr(pos, "opened_at", None)
                        or "—"
                    ),
                    "risk": str(getattr(pos, "risk", None) or "—"),
                    "floating_pnl": str(
                        getattr(pos, "profit", None)
                        or getattr(pos, "unrealized_pnl", None)
                        or "—"
                    ),
                    "broker": "MT5",
                }
            )
    except Exception:
        logger.exception("noc_positions_read_failed")
    return rows


def _closed_trades_read_only(*, limit: int = 20) -> list[dict[str, Any]]:
    """Recent closed trades from journal when available."""
    rows: list[dict[str, Any]] = []
    try:
        # Prefer bridge journal on runtime if present
        from app.application.services.institutional_ite_runtime import get_ite_runtime

        runtime = get_ite_runtime()
        journal = None
        if runtime is not None:
            journal = getattr(getattr(runtime, "execution", None), "bridge", None)
            journal = getattr(journal, "journal", None)
        if journal is None:
            return rows
        recent = []
        if hasattr(journal, "recent"):
            recent = list(journal.recent(limit=limit) or [])
        elif hasattr(journal, "entries"):
            recent = list(getattr(journal, "entries", []) or [])[-limit:]
        for entry in recent:
            d = (
                entry.to_dict()
                if hasattr(entry, "to_dict")
                else (entry if isinstance(entry, dict) else {})
            )
            if not d:
                continue
            status = str(d.get("status") or d.get("execution_result") or "").lower()
            if (
                "close" not in status
                and "exit" not in status
                and d.get("mt5_ticket") is None
            ):
                # Still surface filled attempts as execution history when close unknown
                pass
            rows.append(
                {
                    "ticket": d.get("mt5_ticket") or d.get("ticket"),
                    "entry": d.get("comment") or d.get("execution_result") or "—",
                    "exit": d.get("status") or "—",
                    "net_profit": None,  # unknown unless journal carries it
                    "win_loss": None,
                    "execution_latency_ms": d.get("latency_ms"),
                    "slippage": None,
                    "reason_closed": d.get("abort_reason") or d.get("comment") or None,
                    "timestamp": d.get("timestamp"),
                    "symbol": d.get("symbol"),
                    "action": d.get("decision_action"),
                }
            )
    except Exception:
        logger.exception("noc_closed_trades_read_failed")
    return rows[:limit]


def _oms_dashboard(
    *, pvm: dict[str, Any], attempts: list[dict[str, Any]]
) -> dict[str, Any]:
    last = _as_dict(pvm.get("last_validation"))
    oms = _as_dict(last.get("oms"))
    successes = 0
    failures = 0
    latencies: list[float] = []
    retries = 0
    for a in attempts:
        o = a.get("oms") if isinstance(a.get("oms"), dict) else None
        if not o:
            continue
        resp = o.get("response") if isinstance(o.get("response"), dict) else {}
        outcome = str(resp.get("outcome") or "").lower()
        if outcome in {"success", "filled", "done"}:
            successes += 1
        elif outcome:
            failures += 1
        if o.get("latency_ms") is not None:
            try:
                latencies.append(float(o["latency_ms"]))
            except (TypeError, ValueError):
                logger.debug("noc_oms_latency_parse_skipped")
        retries += int(o.get("retry_count") or 0)
    total = successes + failures
    return {
        "queue_size": None,  # not exposed by production OMS path
        "last_submit": oms or None,
        "average_latency_ms": (sum(latencies) / len(latencies)) if latencies else None,
        "retries": retries,
        "failures_today": failures,
        "success_rate": (successes / total) if total else None,
        "status": pvm.get("oms_status"),
    }


def _gateway_dashboard(
    *, pvm: dict[str, Any], services: dict[str, Any], live: dict[str, Any]
) -> dict[str, Any]:
    last = _as_dict(pvm.get("last_validation"))
    gw = _as_dict(last.get("gateway"))
    svc: dict[str, Any] = {}
    for row in services.get("services") or []:
        if isinstance(row, dict) and str(row.get("name", "")).lower() == "gateway":
            svc = row
            break
    connected = pvm.get("gateway_status") in {"PASS", "OK"} or svc.get("status") in {
        "healthy",
        "ok",
        "up",
    }
    return {
        "gateway_version": live.get("gateway_version") or svc.get("version"),
        "connection": (
            "connected"
            if connected
            else str(pvm.get("gateway_status") or svc.get("status") or "unknown")
        ),
        "ping_ms": gw.get("gateway_latency_ms")
        or svc.get("latency_ms")
        or live.get("gateway_latency_ms"),
        "reconnect_count": live.get("reconnect_attempts") or svc.get("reconnect_count"),
        "last_error": svc.get("last_error") or live.get("gateway_last_error"),
        "order_send_latency_ms": gw.get("order_send_latency_ms"),
        "http_code": gw.get("http_code"),
        "status": pvm.get("gateway_status"),
    }


def _broker_dashboard(*, auto: Any, live: dict[str, Any]) -> dict[str, Any]:
    facts = getattr(auto, "facts", None)
    account = _as_dict(live.get("account"))
    return {
        "broker_connected": (
            bool(getattr(facts, "broker_connected", False)) if facts else None
        ),
        "account": account.get("login") or live.get("login"),
        "balance": account.get("balance") or live.get("balance"),
        "equity": account.get("equity") or live.get("equity"),
        "margin": account.get("margin") or live.get("margin"),
        "free_margin": account.get("free_margin") or live.get("free_margin"),
        "leverage": account.get("leverage") or live.get("leverage"),
        "server": account.get("server") or live.get("server"),
        "currency": account.get("currency") or live.get("currency"),
    }


def _performance(*, diagnostics: dict[str, Any]) -> dict[str, Any]:
    stats = _as_dict(diagnostics.get("statistics"))
    # Only surface fields that diagnostics actually provides — never invent win rate/PF.
    weekly = stats.get("weekly")
    monthly = stats.get("monthly")
    return {
        "today": {
            "trades": stats.get("forwarded_count")
            or stats.get("trades")
            or stats.get("oms_requests"),
            "signals": stats.get("signals_generated") or stats.get("cycle_count"),
            "rejected": stats.get("signals_rejected") or stats.get("no_trade_count"),
            "win_rate": stats.get("win_rate"),  # may be null
            "profit_factor": stats.get("profit_factor"),
            "expectancy": stats.get("expectancy"),
            "average_rr": stats.get("average_rr"),
            "average_latency_ms": stats.get("average_latency_ms")
            or stats.get("avg_latency_ms"),
            "net_profit": stats.get("net_profit"),
            "drawdown": stats.get("drawdown") or stats.get("max_drawdown"),
        },
        "weekly": weekly if isinstance(weekly, dict) else None,
        "monthly": monthly if isinstance(monthly, dict) else None,
        "source": "strategy_diagnostics",
    }


def _event_stream(
    *,
    pipeline: dict[str, Any],
    attempts: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for node in pipeline.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        st = str(node.get("status") or "")
        events.append(
            {
                "kind": "pipeline",
                "level": (
                    "critical"
                    if st == "FAIL"
                    else "info" if st == "PASS" else "warning"
                ),
                "message": f"{node.get('stage')} {st}",
                "reason": node.get("reason"),
                "timestamp": node.get("timestamp"),
                "validation_id": pipeline.get("validation_id"),
            }
        )
    for a in attempts[:30]:
        events.append(
            {
                "kind": "validation",
                "level": "info" if a.get("accepted") else "warning",
                "message": f"Validation {a.get('final_result') or 'IN_PROGRESS'}",
                "reason": a.get("first_blocker"),
                "timestamp": a.get("timestamp"),
                "validation_id": a.get("validation_id"),
            }
        )
    for al in alerts[:40]:
        if not isinstance(al, dict):
            continue
        sev = str(al.get("severity") or al.get("level") or "info").lower()
        events.append(
            {
                "kind": "alert",
                "level": sev if sev in {"critical", "warning", "info"} else "info",
                "message": al.get("message") or al.get("kind") or "alert",
                "reason": al.get("detail"),
                "timestamp": al.get("created_at") or al.get("timestamp"),
                "validation_id": None,
            }
        )
    events.sort(key=lambda e: str(e.get("timestamp") or ""), reverse=True)
    return events[:100]


def _alert_center(
    *, plane: Any, pvm: dict[str, Any], auto: Any
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    try:
        alert_svc = getattr(plane, "alerts", None)
        if alert_svc is not None and hasattr(alert_svc, "list"):
            raw = alert_svc.list(unacked_only=False, limit=100)
            for item in raw or []:
                row: dict[str, Any] | None
                if hasattr(item, "to_dict"):
                    converted = item.to_dict()
                    row = converted if isinstance(converted, dict) else None
                elif isinstance(item, dict):
                    row = item
                else:
                    row = None
                if row:
                    alerts.append(row)
    except Exception:
        logger.exception("noc_alerts_read_failed")

    # Synthetic operational notices from live facts (not fabricated metrics)
    if pvm.get("current_blocker"):
        alerts.insert(
            0,
            {
                "id": "noc-current-blocker",
                "severity": "warning",
                "kind": "execution_blocker",
                "message": str(pvm.get("current_blocker")),
                "created_at": _now(),
                "acknowledged": False,
            },
        )
    safety = getattr(auto, "safety", None)
    if safety is not None and not getattr(safety, "allowed", True):
        for r in list(getattr(safety, "failed_reasons", ()) or ())[:5]:
            alerts.append(
                {
                    "id": f"noc-safety-{hash(str(r)) & 0xFFFF}",
                    "severity": "warning",
                    "kind": "safety",
                    "message": str(r),
                    "created_at": _now(),
                    "acknowledged": False,
                }
            )
    redacted = _redact(alerts)
    if not isinstance(redacted, list):
        return alerts[:80]
    return [row for row in redacted if isinstance(row, dict)][:80]


def _collect_ops_metrics_safe(
    *, gateway: dict[str, Any], oms: dict[str, Any], live: dict[str, Any]
) -> dict[str, Any]:
    """Best-effort real metrics — never fabricates series or invents trade counts."""
    out: dict[str, Any] = {}
    try:
        from app.domain.institutional_observability.metrics import (
            collect_resource_metrics,
        )

        resources = collect_resource_metrics()
        out["cpu_percent"] = resources.get("cpu_percent")
        out["memory_percent"] = resources.get("memory_percent")
        out["memory_used_mb"] = resources.get("memory_used_mb")
        out["collected_at"] = resources.get("observed_at")
        out["resource_source"] = resources.get("source")
    except Exception:
        logger.exception("noc_resource_metrics_failed")

    out["gateway_latency_ms"] = gateway.get("ping_ms")
    out["oms_latency_ms"] = oms.get("average_latency_ms")
    out["broker_latency_ms"] = live.get("broker_latency_ms")

    # Process request metrics when DI metrics_collector is available (production).
    try:
        from core.di.container import get_container

        collector = getattr(get_container(), "metrics_collector", None)
        if collector is not None and hasattr(collector, "snapshot"):
            snap = collector.snapshot()
            payload = snap.to_dict() if hasattr(snap, "to_dict") else {}
            if isinstance(payload, dict):
                out["request_latency_ms_avg"] = payload.get("request_latency_ms_avg")
                out["throughput_per_minute"] = payload.get("throughput_per_minute")
                out["error_rate"] = payload.get("error_rate")
                out["request_count"] = payload.get("request_count")
                out["error_count"] = payload.get("error_count")
    except Exception:
        # Common in unit tests / pre-boot — avoid exception spam.
        logger.debug("noc_metrics_collector_unavailable", exc_info=True)

    try:
        from app.infrastructure.brokers.mt5.metrics import gateway_metrics

        gw_snap = gateway_metrics.snapshot()
        if isinstance(gw_snap, dict):
            out.setdefault(
                "gateway_latency_ms",
                gw_snap.get("latency_ms") or gw_snap.get("avg_latency_ms"),
            )
            out["execution_count"] = gw_snap.get("order_send_count") or gw_snap.get(
                "orders_sent"
            )
    except Exception:
        logger.debug("noc_gateway_metrics_unavailable", exc_info=True)

    return out


def _system_metrics(*, ops_metrics: dict[str, Any] | None) -> dict[str, Any]:
    m = ops_metrics or {}
    # Only real collected metrics — never invent CPU/memory series.
    return {
        "cpu": m.get("cpu_percent") or m.get("cpu"),
        "memory": m.get("memory_percent") or m.get("memory"),
        "memory_used_mb": m.get("memory_used_mb"),
        "gateway_latency_ms": m.get("gateway_latency_ms"),
        "oms_latency_ms": m.get("oms_latency_ms"),
        "broker_latency_ms": m.get("broker_latency_ms"),
        "request_latency_ms_avg": m.get("request_latency_ms_avg"),
        "throughput_per_minute": m.get("throughput_per_minute"),
        "error_rate": m.get("error_rate"),
        "request_count": m.get("request_count"),
        "error_count": m.get("error_count"),
        "execution_count": m.get("execution_count"),
        "trades_today": m.get("trades_today"),
        "series": m.get("series") if isinstance(m.get("series"), dict) else None,
        "collected_at": m.get("collected_at"),
        "resource_source": m.get("resource_source"),
        "note": "Null means unavailable (never mocked).",
    }


def _production_acceptance_widget() -> dict[str, Any]:
    """Production Acceptance — VERIFIED only after real certificate-eligible trade."""
    try:
        from app.application.services.execution_evidence import (
            build_execution_evidence_status,
        )

        status = build_execution_evidence_status()
        return (
            status
            if isinstance(status, dict)
            else {
                "status": "NOT VERIFIED",
                "verified": False,
                "message": "Waiting for first eligible production execution.",
                "observe_only": True,
            }
        )
    except Exception:
        logger.exception("noc_production_acceptance_failed")
        return {
            "status": "NOT VERIFIED",
            "verified": False,
            "message": "Waiting for first eligible production execution.",
            "latest_broker_ticket": None,
            "latest_execution": None,
            "latest_latency_ms": None,
            "latest_certificate": None,
            "observe_only": True,
            "never_fabricated": True,
        }


def _symbol_scan(*, runtime_scan: dict[str, Any] | None) -> dict[str, Any]:
    """Per-symbol multi-asset scanner rows for NOC (observe-only)."""
    scan = runtime_scan if isinstance(runtime_scan, dict) else None
    if scan is None:
        try:
            from app.application.services.institutional_multi_asset_scanner import (
                get_last_multi_asset_scan,
            )

            scan = get_last_multi_asset_scan()
        except Exception:
            scan = None
    if not isinstance(scan, dict):
        try:
            from app.domain.institutional_trading.ai_scalping.config import (
                DEFAULT_SCALPING_UNIVERSE,
            )

            return {
                "enabled": True,
                "universe": list(DEFAULT_SCALPING_UNIVERSE),
                "rows": [],
                "best_symbol": None,
                "eligible_count": 0,
                "as_of": None,
                "note": "awaiting_first_scan",
                "governed_by_existing_ai_and_risk": True,
            }
        except Exception:
            return {
                "enabled": True,
                "universe": [],
                "rows": [],
                "best_symbol": None,
                "eligible_count": 0,
                "as_of": None,
                "note": "scanner_unavailable",
                "governed_by_existing_ai_and_risk": True,
            }
    rows = scan.get("noc_rows")
    if not isinstance(rows, list):
        rows = []
    return {
        "enabled": bool(scan.get("enabled", True)),
        "universe": list(scan.get("universe") or []),
        "rows": rows,
        "best_symbol": scan.get("best_symbol"),
        "eligible_count": int(scan.get("eligible_count") or 0),
        "blocked_by_portfolio": bool(scan.get("blocked_by_portfolio")),
        "portfolio_block_reason": scan.get("portfolio_block_reason"),
        "as_of": scan.get("as_of"),
        "version": scan.get("version"),
        "note": scan.get("note"),
        "quality_floor": scan.get("quality_floor", 80),
        "confidence_floor": scan.get("confidence_floor", 80),
        "forced_trades": False,
        "governed_by_existing_ai_and_risk": True,
    }


def _execution_trace_panel(
    *,
    diagnostics: dict[str, Any],
    pvm: dict[str, Any],
    runtime_scan: dict[str, Any] | None,
) -> dict[str, Any]:
    try:
        from app.domain.institutional_trading.ai_scalping.execution_trace import (
            build_institutional_execution_trace,
        )

        latest = _as_dict(diagnostics.get("latest"))
        last = _as_dict(pvm.get("last_validation"))
        ai_score = _as_dict(latest.get("ai_score") or latest.get("details"))
        return build_institutional_execution_trace(
            symbol=str(last.get("symbol") or latest.get("symbol") or "") or None,
            decision_id=str(
                last.get("validation_id") or pvm.get("last_validation_id") or ""
            )
            or None,
            ai_score=ai_score or {
                "trade_quality": last.get("quality_score"),
                "ai_confidence": last.get("ai_confidence"),
                "reject": str(last.get("ai_action") or "").upper()
                in {"", "NONE", "NO_TRADE"},
                "reject_reason": last.get("first_blocker") or pvm.get("current_blocker"),
                "direction": last.get("ai_action"),
                "liquidity": last.get("liquidity"),
                "mtf_alignment": last.get("mtf_alignment"),
                "volatility_decision": {"reason": _as_dict(latest).get("volatility")},
            },
            scanner=runtime_scan,
            decision_action=str(last.get("ai_action") or latest.get("decision_action")),
            market_ok=bool(latest.get("snapshot_present"))
            if latest.get("snapshot_present") is not None
            else None,
        )
    except Exception:
        logger.exception("noc_execution_trace_failed")
        return {
            "stages": [],
            "first_blocker": None,
            "observe_only": True,
            "error": "trace_unavailable",
        }


def _learning_panel() -> dict[str, Any]:
    try:
        from app.domain.institutional_trading.ai_scalping.learning import (
            get_scalping_learning_store,
        )

        return {
            "summary": get_scalping_learning_store().summary(),
            "observe_only": True,
        }
    except Exception:
        return {"summary": {"trades": 0}, "observe_only": True}


def _continuous_protection_panel() -> dict[str, Any]:
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime
        from app.domain.institutional_trading.ai_scalping.live_health import (
            get_live_health_monitor,
        )

        runtime = get_ite_runtime()
        co = None
        if runtime is not None:
            co = getattr(runtime, "_last_continuous_op", None)
        health = get_live_health_monitor().snapshot()
        return {
            "continuous_operation": co if isinstance(co, dict) else None,
            "live_health": health,
            "observe_only": True,
        }
    except Exception:
        return {"continuous_operation": None, "live_health": None, "observe_only": True}


def _build_cop_noc_panels_sync() -> dict[str, Any]:
    """Sync wrapper for COP NOC panels — never blocks trading on failure."""
    import asyncio
    import concurrent.futures

    async def _run() -> dict[str, Any]:
        from app.application.services.customer_operations_platform import (
            build_customer_ops_noc_panels,
        )

        return await build_customer_ops_noc_panels()

    try:
        try:
            asyncio.get_running_loop()
            running = True
        except RuntimeError:
            running = False
        if running:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(_run())).result(timeout=12)
        return asyncio.run(_run())
    except Exception:
        logger.exception("cop_noc_panels_sync_failed")
        return {
            "fabricated": False,
            "observe_only": True,
            "error": "cop_panels_unavailable",
            "flags": {"never_modifies_trading": True, "cop_version": "v1.0.0"},
        }


def _build_enterprise_noc_panels_sync() -> dict[str, Any]:
    """Sync wrapper for Enterprise NOC panels — observe-only."""
    import asyncio
    import concurrent.futures

    async def _run() -> dict[str, Any]:
        from app.application.services.enterprise_platform import (
            build_enterprise_noc_panels,
        )

        return await build_enterprise_noc_panels()

    try:
        try:
            asyncio.get_running_loop()
            running = True
        except RuntimeError:
            running = False
        if running:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(_run())).result(timeout=12)
        return asyncio.run(_run())
    except Exception:
        logger.exception("enterprise_noc_panels_sync_failed")
        return {
            "fabricated": False,
            "observe_only": True,
            "flags": {
                "never_modifies_trading": True,
                "enterprise_version": "v1.0.0",
            },
        }


def _build_reliability_noc_panels_sync() -> dict[str, Any]:
    """Sync wrapper for Production Reliability NOC panels — observe-only."""
    import asyncio
    import concurrent.futures

    async def _run() -> dict[str, Any]:
        from app.application.services.production_reliability_program import (
            build_reliability_noc_panels,
        )

        return await build_reliability_noc_panels()

    try:
        try:
            asyncio.get_running_loop()
            running = True
        except RuntimeError:
            running = False
        if running:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(_run())).result(timeout=15)
        return asyncio.run(_run())
    except Exception:
        logger.exception("reliability_noc_panels_sync_failed")
        return {
            "fabricated": False,
            "observe_only": True,
            "error": "reliability_panels_unavailable",
            "flags": {
                "never_modifies_trading": True,
                "destructive_ops_forbidden": True,
                "program_version": "v1.0.0",
            },
        }


def build_noc_command_center() -> dict[str, Any]:
    from app.application.services.auto_trading_status import build_auto_trading_status
    from app.application.services.production_validation_mode import (
        build_production_validation_dashboard,
        list_production_validation_attempts,
    )
    from app.application.services.strategy_diagnostics import (
        get_strategy_diagnostics_store,
    )
    from app.domain.institutional_trading.operations.control_plane import (
        get_control_plane,
    )
    from core.config.settings import get_settings

    settings = get_settings()
    plane = get_control_plane()

    auto = _safe_call(
        "auto_trading",
        lambda: build_auto_trading_status(plane, settings=settings),
    )
    pvm = _safe_call("pvm", build_production_validation_dashboard, {}) or {}
    attempts_payload = _safe_call(
        "pvm_attempts",
        lambda: list_production_validation_attempts(limit=50),
        {"attempts": []},
    ) or {"attempts": []}
    attempts = list(attempts_payload.get("attempts") or [])
    diagnostics = (
        _safe_call(
            "diagnostics",
            lambda: get_strategy_diagnostics_store().snapshot(limit=40),
            {},
        )
        or {}
    )

    # Reuse services-health construction lightly
    services: dict[str, Any] = {}
    try:
        # Call underlying logic without FastAPI user dep — duplicate minimal collect
        from app.application.services.auto_trading_status import build_status_facts
        from app.application.services.institutional_ite_runtime import get_ite_runtime
        from app.application.services.institutional_live_probes import (
            LiveProbeCollector,
        )

        facts, live = build_status_facts(plane, settings=settings)
        runtime = get_ite_runtime()
        if runtime is not None:
            probes = runtime.probes.collect()
        else:
            probes = LiveProbeCollector(settings=settings).collect()
        services = {
            "services": [
                {
                    "name": "gateway",
                    "status": (
                        "healthy"
                        if getattr(probes, "gateway_ok", False)
                        or facts.gateway_connected
                        else "unhealthy"
                    ),
                    "latency_ms": getattr(probes, "gateway_latency_ms", None),
                    "last_error": getattr(probes, "gateway_error", None),
                    "heartbeat_at": getattr(probes, "as_of", None),
                },
                {
                    "name": "mt5",
                    "status": "healthy" if facts.broker_connected else "unhealthy",
                    "latency_ms": getattr(probes, "mt5_latency_ms", None),
                    "last_error": getattr(probes, "mt5_error", None),
                    "heartbeat_at": getattr(probes, "as_of", None),
                },
                {
                    "name": "oms",
                    "status": str(pvm.get("oms_status") or "unknown"),
                    "latency_ms": None,
                    "heartbeat_at": None,
                },
            ],
            "live": live if isinstance(live, dict) else {},
        }
        live_map = (
            services.get("live") if isinstance(services.get("live"), dict) else {}
        )
    except Exception:
        logger.exception("noc_services_collect_failed")
        live_map = getattr(auto, "live", None) or {}
        services = {"services": [], "live": live_map}

    if auto is None:
        # Minimal empty auto stand-in
        class _Empty:
            def __init__(self) -> None:
                self.facts = None
                self.safety = None
                self.live: dict[str, Any] = {}
                self.execution_state: dict[str, Any] = {}
                self.primary_blocker = None

        auto = _Empty()

    pipeline = _pipeline_from_pvm(pvm)
    alerts = _alert_center(plane=plane, pvm=pvm, auto=auto)
    header = _header(settings=settings)
    # Railway API process online only when auto-trading facts collected.
    # Never invent deploy meta.
    header["railway_status"] = (
        "online" if getattr(auto, "facts", None) is not None else "unknown"
    )
    header["deployment_time"] = None

    oms = _oms_dashboard(pvm=pvm, attempts=attempts)
    gateway = _gateway_dashboard(
        pvm=pvm,
        services=services,
        live=live_map if isinstance(live_map, dict) else {},
    )
    ops_metrics = _collect_ops_metrics_safe(
        gateway=gateway,
        oms=oms,
        live=live_map if isinstance(live_map, dict) else {},
    )

    history: list[dict[str, Any]] = []
    for a in attempts:
        if not isinstance(a, dict):
            continue
        raw_pipe = a.get("pipeline")
        pipe: list[Any] = raw_pipe if isinstance(raw_pipe, list) else []
        latencies = [
            float(s["latency_ms"])
            for s in pipe
            if isinstance(s, dict) and s.get("latency_ms") is not None
        ]
        fails = [
            str(s.get("stage"))
            for s in pipe
            if isinstance(s, dict) and str(s.get("status")).upper() == "FAIL"
        ]
        history.append(
            {
                "validation_id": a.get("validation_id"),
                "timestamp": a.get("timestamp"),
                "pipeline_status": (
                    "FAIL"
                    if fails
                    else (
                        "PASS"
                        if a.get("accepted")
                        else str(a.get("final_result") or "IN_PROGRESS")
                    )
                ),
                "latency_ms": round(sum(latencies), 2) if latencies else None,
                "final_result": a.get("final_result"),
                "result": (
                    "PASS"
                    if a.get("accepted")
                    else "FAIL" if fails else a.get("final_result")
                ),
                "reason": a.get("first_blocker") or (fails[0] if fails else None),
                "first_blocker": a.get("first_blocker"),
                "ai_action": a.get("ai_action"),
                "symbol": a.get("symbol"),
                "accepted": a.get("accepted"),
            }
        )

    live_for_broker: dict[str, Any] = live_map if isinstance(live_map, dict) else {}
    runtime_scan: dict[str, Any] | None = None
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime

        rt = get_ite_runtime()
        if rt is not None and hasattr(rt, "last_multi_asset_scan"):
            runtime_scan = rt.last_multi_asset_scan()
    except Exception:
        runtime_scan = None
    payload: dict[str, Any] = {
        "header": header,
        "global_health": _health_cards(
            _plane=plane,
            settings=settings,
            auto=auto,
            services=services,
            pvm=pvm,
        ),
        "pipeline": pipeline,
        "ai_engine": _ai_engine(diagnostics=diagnostics, pvm=pvm),
        "market_context": _market_context(diagnostics=diagnostics, pvm=pvm, auto=auto),
        "symbol_scan": _symbol_scan(runtime_scan=runtime_scan),
        "execution_trace": _execution_trace_panel(
            diagnostics=diagnostics, pvm=pvm, runtime_scan=runtime_scan
        ),
        "learning": _learning_panel(),
        "protection": _continuous_protection_panel(),
        "intelligence": _safe_call(
            "intelligence",
            lambda: __import__(
                "app.application.services.noc_intelligence_panels",
                fromlist=["build_intelligence_panels"],
            ).build_intelligence_panels(runtime_scan=runtime_scan),
            {},
        )
        or {},
        "customer_operations": _safe_call(
            "customer_operations",
            _build_cop_noc_panels_sync,
            {},
        )
        or {},
        "enterprise_platform": _safe_call(
            "enterprise_platform",
            _build_enterprise_noc_panels_sync,
            {},
        )
        or {},
        "production_reliability": _safe_call(
            "production_reliability",
            _build_reliability_noc_panels_sync,
            {},
        )
        or {},
        "open_positions": _positions_read_only(),
        "closed_trades": _closed_trades_read_only(limit=25),
        "oms": oms,
        "gateway": gateway,
        "broker": _broker_dashboard(auto=auto, live=live_for_broker),
        "performance": _performance(diagnostics=diagnostics),
        "event_stream": _event_stream(
            pipeline=pipeline, attempts=attempts, alerts=alerts
        ),
        "alerts": alerts,
        "validation_history": history,
        "system_metrics": _system_metrics(ops_metrics=ops_metrics),
        "execution_state": getattr(auto, "execution_state", {}) or {},
        "primary_blocker": getattr(auto, "primary_blocker", None)
        or pvm.get("current_blocker"),
        "production_acceptance": _production_acceptance_widget(),
        "flags": {
            "observe_only": True,
            "never_modifies_trading": True,
            "never_fabricates_metrics": True,
            "never_exposes_secrets": True,
        },
    }
    redacted = _redact(payload)
    return redacted if isinstance(redacted, dict) else payload


def answer_noc_copilot(
    question: str, *, telemetry: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Rule-based copilot — answers only from provided/real telemetry. Never invents."""
    q = " ".join((question or "").strip().lower().split())
    data = telemetry if isinstance(telemetry, dict) else build_noc_command_center()
    evidence: list[str] = []
    answer_parts: list[str] = []

    def cite(label: str, value: Any) -> None:
        if value is None or value == "" or value == "—":
            evidence.append(f"{label}=unavailable")
        else:
            evidence.append(f"{label}={value}")

    if not q:
        return {
            "answer": (
                "Ask a production telemetry question "
                "(e.g. why isn't QuantForg trading?)."
            ),
            "evidence": [],
            "grounded": True,
            "hallucination_guard": True,
        }

    ai = data.get("ai_engine") or {}
    pipeline = data.get("pipeline") or {}
    health = data.get("global_health") or []
    blocker = data.get("primary_blocker") or ai.get("current_blocker")

    if any(
        k in q
        for k in (
            "why",
            "not trading",
            "isn't trading",
            "isnt trading",
            "no trade",
            "rejected",
        )
    ):
        cite("decision", ai.get("decision"))
        cite("blocker", blocker)
        cite("session", ai.get("current_session"))
        cite("quality", ai.get("quality_score"))
        cite("threshold", ai.get("threshold"))
        reasons = ai.get("reasons") or []
        if reasons:
            answer_parts.append("NO_TRADE / block reasons from live telemetry:")
            answer_parts.extend(f"- {r}" for r in reasons[:20])
        elif blocker:
            answer_parts.append(f"Current production blocker: {blocker}")
        else:
            answer_parts.append(
                "No explicit blocker field in current telemetry snapshot."
            )
        if pipeline.get("first_blocker"):
            answer_parts.append(
                f"Pipeline first blocker: {pipeline.get('first_blocker')}"
            )
            cite("pipeline_first_blocker", pipeline.get("first_blocker"))

    elif "latency" in q or "broker latency" in q or "gateway latency" in q:
        gw = data.get("gateway") or {}
        oms = data.get("oms") or {}
        metrics = data.get("system_metrics") or {}
        answer_parts.append(
            f"Gateway ping_ms={gw.get('ping_ms')!s}; "
            f"order_send_latency_ms={gw.get('order_send_latency_ms')!s}; "
            f"OMS avg_latency_ms={oms.get('average_latency_ms')!s}; "
            f"request_latency_ms_avg={metrics.get('request_latency_ms_avg')!s}."
        )
        cite("gateway_ping_ms", gw.get("ping_ms"))
        cite("oms_avg_latency_ms", oms.get("average_latency_ms"))

    elif "failure" in q or "fail" in q:
        fails = [
            e
            for e in (data.get("event_stream") or [])
            if str(e.get("level")) == "critical"
            or "FAIL" in str(e.get("message") or "")
        ]
        if not fails:
            answer_parts.append(
                "No FAIL/critical events in the current NOC event stream window."
            )
        else:
            answer_parts.append(f"{len(fails)} failure/critical events in stream:")
            for e in fails[:15]:
                reason = e.get("reason") or "—"
                answer_parts.append(
                    f"- {e.get('timestamp')}: {e.get('message')} ({reason})"
                )
                evidence.append(str(e.get("message")))

    elif "health" in q or "summar" in q:
        answer_parts.append("Global health cards (live):")
        for c in health:
            if not isinstance(c, dict):
                continue
            answer_parts.append(
                f"- {c.get('label')}: {c.get('status')} "
                f"(latency_ms={c.get('latency_ms')!s})"
            )
            cite(str(c.get("label")), c.get("status"))
        if blocker:
            answer_parts.append(f"Primary blocker: {blocker}")

    else:
        answer_parts.append(
            "I can only answer from live NOC telemetry. "
            "Try: why isn't QuantForg trading; show execution failures; "
            "show broker latency; summarize production health."
        )
        cite("supported", "trading_blockers|failures|latency|health")

    return {
        "question": question,
        "answer": "\n".join(answer_parts),
        "evidence": evidence,
        "grounded": True,
        "hallucination_guard": True,
        "as_of": (data.get("header") or {}).get("as_of"),
        "validation_id": pipeline.get("validation_id"),
    }
