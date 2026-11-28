"""Component health probes — read-only; never mutate probed systems."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_observability.metrics import measure_latency_ms
from app.domain.institutional_observability.models import COMPONENTS, HealthStatus


def _status(ok: bool | None, *, degraded: bool = False) -> HealthStatus:
    if ok is None:
        return "unknown"
    if ok and not degraded:
        return "healthy"
    if ok and degraded:
        return "degraded"
    return "down"


def probe_components(
    *,
    ops_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Probe each monitored component. Missing deps → unknown, never fabricated."""
    facts = ops_facts or {}
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    components: dict[str, Any] = {}

    # API — this process responding
    components["api"] = {
        "status": "healthy",
        "latency_ms": measure_latency_ms(lambda: None),
        "detail": "observability process reachable",
        "observed_at": now,
    }

    gw_ok = facts.get("gateway_connected")
    components["gateway"] = {
        "status": _status(gw_ok if gw_ok is not None else None),
        "detail": "from ops facts" if gw_ok is not None else "no ops facts supplied",
        "observed_at": now,
    }
    br_ok = facts.get("broker_connected")
    components["broker"] = {
        "status": _status(br_ok if br_ok is not None else None),
        "detail": "from ops facts" if br_ok is not None else "no ops facts supplied",
        "observed_at": now,
    }
    mt5_ok = facts.get("mt5_logged_in")
    components["mt5_session"] = {
        "status": _status(mt5_ok if mt5_ok is not None else None),
        "detail": "from ops facts" if mt5_ok is not None else "no ops facts supplied",
        "observed_at": now,
    }
    exec_en = facts.get("execution_enabled")
    if exec_en is True:
        exec_status: HealthStatus = "healthy"
        exec_detail = "execution_enabled=true"
    elif exec_en is False:
        exec_status = "degraded"
        exec_detail = "execution_enabled=false (expected in shadow)"
    else:
        exec_status = "unknown"
        exec_detail = "execution_enabled unknown"
    components["execution_queue"] = {
        "status": exec_status,
        "detail": exec_detail,
        "observed_at": now,
    }

    # Journal writer — probe list capability if store provided via facts
    journal_ok = facts.get("journal_ok")
    components["journal_writer"] = {
        "status": _status(journal_ok if journal_ok is not None else None),
        "detail": facts.get("journal_detail") or "probe via snapshot",
        "observed_at": now,
    }

    # Evidence lab
    try:
        from app.domain.replay_evidence_lab.evidence_store import get_evidence_database

        inv = get_evidence_database().inventory()
        components["evidence_lab"] = {
            "status": "healthy",
            "detail": f"records={inv.get('total_records')}",
            "observed_at": now,
        }
        components["replay_engine"] = {
            "status": "healthy",
            "detail": f"replay_lane={ (inv.get('lanes') or {}).get('replay', 0) }",
            "observed_at": now,
        }
    except Exception as exc:
        components["evidence_lab"] = {
            "status": "unknown",
            "detail": str(exc)[:120],
            "observed_at": now,
        }
        components["replay_engine"] = {
            "status": "unknown",
            "detail": str(exc)[:120],
            "observed_at": now,
        }

    # Warehouse
    try:
        from app.domain.institutional_data_warehouse.store import get_warehouse

        winv = get_warehouse().inventory()
        components["warehouse"] = {
            "status": "healthy" if int(winv.get("total_records") or 0) >= 0 else "down",
            "detail": f"records={winv.get('total_records')}",
            "observed_at": now,
        }
    except Exception as exc:
        components["warehouse"] = {
            "status": "unknown",
            "detail": str(exc)[:120],
            "observed_at": now,
        }

    # Governance
    try:
        from app.domain.audit_governance.store import get_audit_store

        sec = get_audit_store().security_status()
        components["governance"] = {
            "status": "healthy" if sec.get("append_only") else "degraded",
            "detail": f"events={sec.get('record_count')}",
            "observed_at": now,
        }
    except Exception as exc:
        components["governance"] = {
            "status": "unknown",
            "detail": str(exc)[:120],
            "observed_at": now,
        }

    # Performance IQ — module import only (no mutation)
    try:
        import importlib

        importlib.import_module("app.domain.performance_intelligence")
        components["performance_iq"] = {
            "status": "healthy",
            "detail": "module importable",
            "observed_at": now,
        }
    except Exception as exc:
        components["performance_iq"] = {
            "status": "unknown",
            "detail": str(exc)[:120],
            "observed_at": now,
        }

    # Operations Center
    try:
        import importlib

        importlib.import_module("app.domain.trading_operations_center")
        components["operations_center"] = {
            "status": "healthy",
            "detail": "module importable",
            "observed_at": now,
        }
    except Exception as exc:
        components["operations_center"] = {
            "status": "unknown",
            "detail": str(exc)[:120],
            "observed_at": now,
        }

    # Ensure all declared components present
    for cid in COMPONENTS:
        components.setdefault(
            cid,
            {"status": "unknown", "detail": "not probed", "observed_at": now},
        )

    healthy = sum(1 for c in components.values() if c.get("status") == "healthy")
    degraded = sum(1 for c in components.values() if c.get("status") == "degraded")
    down = sum(1 for c in components.values() if c.get("status") == "down")
    unknown = sum(1 for c in components.values() if c.get("status") == "unknown")

    overall: HealthStatus = "healthy"
    if down:
        overall = "down"
    elif degraded or unknown:
        overall = "degraded"

    return {
        "status": "available",
        "overall": overall,
        "counts": {
            "healthy": healthy,
            "degraded": degraded,
            "down": down,
            "unknown": unknown,
            "total": len(components),
        },
        "components": components,
        "observability_only": True,
    }
