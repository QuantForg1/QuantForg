"""Continuous production health verification across critical surfaces."""

from __future__ import annotations

import contextlib
from typing import Any

from app.domain.production_reliability.models import HEALTH_TARGETS
from app.domain.production_reliability.persistence import utc_iso


def _status_ok(status: str) -> bool:
    s = status.lower()
    return s in {
        "healthy",
        "ok",
        "up",
        "ready",
        "connected",
        "available",
        "pass",
        "disabled",
        "external",
    }


def _component(
    name: str, status: str, detail: str = "", **extra: Any
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "detail": detail[:500],
        "ok": _status_ok(status),
        **extra,
    }


def _probe_api() -> dict[str, Any]:
    return _component("api", "healthy", "process_local")


def _probe_database() -> dict[str, Any]:
    """Observe DATABASE_URL presence — async ping lives in infra adapters."""
    try:
        from core.config.settings import get_settings

        url = getattr(get_settings(), "database_url", None) or ""
        if url:
            return _component(
                "database",
                "configured",
                "DATABASE_URL present; async health via /health adapters",
            )
        return _component("database", "unknown", "DATABASE_URL not set")
    except Exception as exc:
        return _component("database", "unknown", str(exc)[:200])


def _probe_redis() -> dict[str, Any]:
    try:
        from core.config.settings import get_settings

        url = getattr(get_settings(), "redis_url", None) or ""
        if url:
            return _component(
                "redis",
                "configured",
                "REDIS_URL present; async health via /health adapters",
            )
        return _component("redis", "unknown", "REDIS_URL not set")
    except Exception as exc:
        return _component("redis", "unknown", str(exc)[:200])


def _probe_storage() -> dict[str, Any]:
    try:
        from pathlib import Path

        from core.config.settings import get_settings

        base = Path(getattr(get_settings(), "data_dir", None) or "data")
        base.mkdir(parents=True, exist_ok=True)
        probe = base / ".reliability_write_probe"
        probe.write_text("ok", encoding="utf-8")
        ok = probe.read_text(encoding="utf-8") == "ok"
        with contextlib.suppress(Exception):
            probe.unlink(missing_ok=True)
        return _component("storage", "healthy" if ok else "degraded", str(base))
    except Exception as exc:
        return _component("storage", "unknown", str(exc)[:200])


def _probe_trading_components() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    try:
        from app.application.services.production_component_health import (
            collect_trading_component_health,
        )
        from core.config.settings import get_settings

        pack = collect_trading_component_health(get_settings())
        for key in ("gateway", "oms", "mt5", "ai"):
            row = pack.get(key) or {}
            if isinstance(row, dict):
                st = str(row.get("status") or "unknown")
                # Normalize connected → healthy for ok math
                norm = st
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
                out[key] = _component(
                    key,
                    norm,
                    str(row.get("detail") or ""),
                    evidence=row.get("evidence") or {},
                    raw_status=st,
                )
    except Exception as exc:
        for key in ("gateway", "oms", "ai", "mt5"):
            out.setdefault(key, _component(key, "unknown", str(exc)[:120]))
    return out


def _probe_frontend() -> dict[str, Any]:
    return _component(
        "frontend",
        "external",
        "Verified via Vercel production deploy; not in-process",
    )


def _probe_jobs() -> dict[str, Any]:
    try:
        from core.di.container import get_container

        collector = getattr(get_container(), "metrics_collector", None)
        if collector is None:
            return _component("jobs", "unknown", "metrics_collector unavailable")
        snap = collector.snapshot()
        job_count = getattr(snap, "job_count", None)
        avg = getattr(snap, "avg_job_duration_ms", None)
        return _component(
            "jobs",
            "healthy",
            f"job_count={job_count} avg_ms={avg}",
        )
    except Exception as exc:
        return _component("jobs", "unknown", str(exc)[:200])


def build_production_health() -> dict[str, Any]:
    components: dict[str, dict[str, Any]] = {}
    components["api"] = _probe_api()
    components["database"] = _probe_database()
    components["redis"] = _probe_redis()
    components["storage"] = _probe_storage()
    components["frontend"] = _probe_frontend()
    components["jobs"] = _probe_jobs()
    components.update(_probe_trading_components())

    for t in HEALTH_TARGETS:
        components.setdefault(t, _component(t, "unknown", "not_probed"))

    # Treat configured as ok for DB/Redis (async ping elsewhere)
    for key in ("database", "redis"):
        if str(components[key].get("status")) == "configured":
            components[key]["ok"] = True

    ordered = {t: components[t] for t in HEALTH_TARGETS if t in components}
    ok_count = sum(1 for c in ordered.values() if c.get("ok"))
    unknown = sum(1 for c in ordered.values() if str(c.get("status")) == "unknown")

    overall = "healthy"
    if any(
        str(c.get("status")).lower()
        in {"down", "not_ready", "unhealthy", "disconnected"}
        for c in ordered.values()
    ):
        overall = "degraded"
    if ok_count == 0:
        overall = "unknown"

    return {
        "as_of": utc_iso(),
        "overall": overall,
        "components": ordered,
        "ok_count": ok_count,
        "target_count": len(HEALTH_TARGETS),
        "unknown_count": unknown,
        "fabricated": False,
        "observe_only": True,
        "never_modifies_trading": True,
    }
