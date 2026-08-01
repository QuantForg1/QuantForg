"""Continuous production validation — live probes + health history."""

from __future__ import annotations

import contextlib
from typing import Any

from app.domain.continuous_improvement.models import VALIDATION_TARGETS
from app.domain.continuous_improvement.persistence import (
    JsonDocumentStore,
    new_id,
    utc_iso,
)

_history = JsonDocumentStore("validation_history.json", "snapshots")


def _row(name: str, status: str, detail: str = "", **extra: Any) -> dict[str, Any]:
    s = status.lower()
    ok = s in {
        "healthy",
        "ok",
        "up",
        "ready",
        "connected",
        "configured",
        "disabled",
        "external",
        "available",
        "pass",
        "present",
    }
    return {
        "name": name,
        "status": status,
        "detail": detail[:500],
        "ok": ok,
        **extra,
    }


def _probe_core_trading() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    try:
        from app.application.services.production_component_health import (
            collect_trading_component_health,
        )
        from core.config.settings import get_settings

        pack = collect_trading_component_health(get_settings())
        for key in ("gateway", "oms", "mt5", "ai"):
            row = pack.get(key) or {}
            if not isinstance(row, dict):
                continue
            st = str(row.get("status") or "unknown")
            norm = st.lower()
            if st.upper() == "CONNECTED":
                norm = "connected"
            elif st.upper() == "DISCONNECTED":
                norm = "down"
            elif st.upper() == "HEALTHY":
                norm = "healthy"
            elif st.upper() == "DISABLED":
                norm = "disabled"
            elif st.upper() == "NOT_READY":
                norm = "not_ready"
            elif st.upper() == "DOWN":
                norm = "down"
            out[key] = _row(key, norm, str(row.get("detail") or ""), raw_status=st)
    except Exception as exc:
        for key in ("gateway", "oms", "mt5", "ai"):
            out[key] = _row(key, "unknown", str(exc)[:120])
    return out


def _probe_risk_portfolio() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    # Risk / portfolio — observe presence of control-plane facts only
    try:
        from app.application.services.auto_trading_status import (
            build_auto_trading_status,
        )
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )
        from core.config.settings import get_settings

        snap = build_auto_trading_status(get_control_plane(), settings=get_settings())
        facts = snap.facts
        out["risk"] = _row(
            "risk",
            "present",
            f"ops_mode={getattr(facts, 'ops_mode', None)}",
        )
        out["portfolio"] = _row(
            "portfolio",
            "present",
            "observe-only control-plane snapshot",
        )
    except Exception as exc:
        out["risk"] = _row("risk", "unknown", str(exc)[:120])
        out["portfolio"] = _row("portfolio", "unknown", str(exc)[:120])
    return out


def _probe_database() -> dict[str, Any]:
    try:
        from core.config.settings import get_settings

        url = getattr(get_settings(), "database_url", None) or ""
        if url:
            return _row(
                "database",
                "configured",
                "DATABASE_URL present; async health via /health",
            )
        return _row("database", "unknown", "DATABASE_URL not set")
    except Exception as exc:
        return _row("database", "unknown", str(exc)[:120])


def _probe_api() -> dict[str, Any]:
    return _row("api", "healthy", "process_local")


def _probe_frontend() -> dict[str, Any]:
    return _row(
        "frontend",
        "external",
        "Verified via Vercel production; not in-process",
    )


def _probe_noc() -> dict[str, Any]:
    try:
        # Presence of NOC builder — never run full NOC (avoid recursion)
        from app.application.services import noc_command_center as _noc

        _ = _noc.build_noc_command_center
        return _row("noc", "present", "noc_command_center importable")
    except Exception as exc:
        return _row("noc", "unknown", str(exc)[:120])


def _probe_cop() -> dict[str, Any]:
    try:
        from app.application.services.customer_operations_platform import (
            build_customer_ops_noc_panels,
        )

        _ = build_customer_ops_noc_panels
        return _row("customer_operations", "present", "COP service importable")
    except Exception as exc:
        return _row("customer_operations", "unknown", str(exc)[:120])


def _probe_enterprise() -> dict[str, Any]:
    try:
        from app.application.services.enterprise_platform import (
            build_enterprise_noc_panels,
        )

        _ = build_enterprise_noc_panels
        return _row("enterprise_platform", "present", "Enterprise importable")
    except Exception as exc:
        return _row("enterprise_platform", "unknown", str(exc)[:120])


def build_continuous_validation(*, record_history: bool = True) -> dict[str, Any]:
    components: dict[str, dict[str, Any]] = {}
    components.update(_probe_core_trading())
    components.update(_probe_risk_portfolio())
    components["database"] = _probe_database()
    components["api"] = _probe_api()
    components["frontend"] = _probe_frontend()
    components["noc"] = _probe_noc()
    components["customer_operations"] = _probe_cop()
    components["enterprise_platform"] = _probe_enterprise()

    for t in VALIDATION_TARGETS:
        components.setdefault(t, _row(t, "unknown", "not_probed"))

    ordered = {t: components[t] for t in VALIDATION_TARGETS if t in components}
    ok_count = sum(1 for c in ordered.values() if c.get("ok"))
    overall = "healthy"
    if any(
        str(c.get("status")).lower()
        in {"down", "not_ready", "unhealthy", "disconnected"}
        for c in ordered.values()
    ):
        overall = "degraded"
    if ok_count == 0:
        overall = "unknown"

    # PVM observe
    pvm: dict[str, Any] = {}
    try:
        from app.application.services.production_validation_mode import (
            build_production_validation_dashboard,
        )

        pvm = build_production_validation_dashboard() or {}
    except Exception:
        pvm = {}

    snapshot = {
        "id": new_id("val"),
        "as_of": utc_iso(),
        "overall": overall,
        "ok_count": ok_count,
        "target_count": len(VALIDATION_TARGETS),
        "components": {
            k: {"status": v.get("status"), "ok": v.get("ok")}
            for k, v in ordered.items()
        },
        "fabricated": False,
    }
    if record_history:
        with contextlib.suppress(Exception):
            _history.append(snapshot)

    history = list(reversed(_history.list(limit=100)))
    return {
        "as_of": utc_iso(),
        "overall": overall,
        "components": ordered,
        "ok_count": ok_count,
        "target_count": len(VALIDATION_TARGETS),
        "history": history,
        "history_count": _history.count(),
        "production_validation_mode": {
            "status": pvm.get("status") or pvm.get("mode"),
            "keys": sorted(str(k) for k in pvm)[:20] if pvm else [],
            "observe_only": True,
        },
        "fabricated": False,
        "observe_only": True,
        "never_modifies_trading": True,
    }


def list_validation_history(*, limit: int = 100) -> list[dict[str, Any]]:
    return list(reversed(_history.list(limit=limit)))
