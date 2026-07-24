"""ITE Reliability & Observability API — Phase G."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.application.dto.auth import AuthUserDTO
from app.domain.enums.user import UserRole
from app.domain.institutional_trading.reliability.health import ProbeInputs
from app.domain.institutional_trading.reliability.models import (
    ComponentName,
)
from app.domain.institutional_trading.reliability.platform import (
    get_reliability_platform,
)
from app.presentation.dependencies.auth import require_roles

router = APIRouter(prefix="/ite/reliability", tags=["ite-reliability"])

OperatorUser = Annotated[
    AuthUserDTO,
    Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
]


class ProbeBody(BaseModel):
    gateway_latency_ms: float = 0
    gateway_available: bool = True
    mt5_connected: bool = True
    cloudflare_tunnel_up: bool = True
    railway_api_up: bool = True
    supabase_up: bool = True
    database_latency_ms: float = 0
    oms_latency_ms: float = 0
    execution_latency_ms: float = 0
    decision_latency_ms: float = 0
    pme_latency_ms: float = 0
    use_live_probes: bool = True


class HeartbeatBody(BaseModel):
    component: str
    latency_ms: float = 0


class ChaosBody(BaseModel):
    failure: str


class TraceBody(BaseModel):
    decision_id: str | None = None
    latencies: dict[str, float] = Field(default_factory=dict)


@router.get("/dashboard")
def dashboard(_user: OperatorUser) -> dict[str, Any]:
    return get_reliability_platform().operational_dashboard()


@router.get("/production-hardening")
def production_hardening_dashboard(_user: OperatorUser) -> dict[str, Any]:
    """v6 Production Hardening — health, performance, lifecycle, learning, secrets audit."""
    from app.application.services.production_reliability import (
        build_production_reliability_dashboard,
    )

    return build_production_reliability_dashboard()


@router.get("/ai-validation")
def ai_validation_dashboard(
    _user: OperatorUser,
    replay_day: str | None = Query(default=None),
) -> dict[str, Any]:
    """v7 AI Validation & Performance Optimization dashboard."""
    from app.application.services.ai_validation import build_ai_validation_dashboard

    return build_ai_validation_dashboard(replay_day=replay_day)


@router.get("/performance-lab")
def performance_lab_dashboard(
    _user: OperatorUser,
    symbol: str | None = Query(default=None),
    session: str | None = Query(default=None),
    regime: str | None = Query(default=None),
    replay_id: str | None = Query(default=None),
    frame_index: int = Query(default=0),
) -> dict[str, Any]:
    """v8 Live Performance Lab — champion/challenger, calibration, replay, rankings."""
    from app.application.services.performance_lab import build_performance_lab_dashboard

    return build_performance_lab_dashboard(
        symbol=symbol,
        session=session,
        regime=regime,
        replay_id=replay_id,
        frame_index=frame_index,
    )


@router.get("/network")
def network_dashboard(_user: OperatorUser) -> dict[str, Any]:
    """DNS/network incidents, reconnect log, gateway/MT5 uptime."""
    platform = get_reliability_platform()
    return {
        "network": platform.network.dashboard(),
        "incidents": [i.to_dict() for i in platform.network.list_incidents(limit=100)],
        "reconnect_log": [
            e.to_dict() for e in platform.network.list_reconnect_logs(limit=100)
        ],
    }


@router.post("/tick")
def tick(body: ProbeBody, _user: OperatorUser) -> dict[str, Any]:
    """Health tick — live probes by default (no manual CF/Railway flags required)."""
    from app.application.services.institutional_ite_runtime import get_ite_runtime

    runtime = get_ite_runtime()
    if body.use_live_probes and runtime is not None:
        return runtime.tick_health()
    platform = get_reliability_platform()
    payload = body.model_dump(exclude={"use_live_probes"})
    return platform.tick(
        ProbeInputs(**payload),
        required_heartbeats=(
            ComponentName.GATEWAY,
            ComponentName.MT5,
            ComponentName.DECISION,
            ComponentName.OMS,
        ),
    )


@router.post("/tick/live")
def tick_live(_user: OperatorUser) -> dict[str, Any]:
    """Always collect live Gateway/MT5/Railway/Supabase/Cloudflare probes."""
    from app.application.services.institutional_ite_runtime import get_ite_runtime

    runtime = get_ite_runtime()
    if runtime is None:
        raise HTTPException(status_code=503, detail="ITE runtime not wired")
    return runtime.tick_health()


@router.get("/shadow/status")
def shadow_status(_user: OperatorUser) -> dict[str, Any]:
    from app.application.services.institutional_ite_runtime import get_ite_runtime

    runtime = get_ite_runtime()
    if runtime is None:
        raise HTTPException(status_code=503, detail="ITE runtime not wired")
    return runtime.status()


@router.get("/execution-attempts")
def execution_attempts(
    _user: OperatorUser,
    limit: int = 50,
) -> dict[str, Any]:
    """Read-only bridge execution attempt journal (includes NO_TRADE reasons)."""
    from app.application.services.institutional_ite_runtime import get_ite_runtime

    runtime = get_ite_runtime()
    if runtime is None:
        raise HTTPException(status_code=503, detail="ITE runtime not wired")
    journal = getattr(runtime.execution.bridge, "journal", None)
    if journal is None or not hasattr(journal, "list"):
        return {"items": [], "count": 0}
    capped = max(1, min(int(limit), 200))
    items = [
        r.to_dict() if hasattr(r, "to_dict") else dict(r)
        for r in journal.list(limit=capped)
    ]
    return {"items": items, "count": len(items)}


@router.post("/shadow/cycle")
def shadow_cycle(_user: OperatorUser) -> dict[str, Any]:
    """Run one automatic shadow cycle (health + optional decision path)."""
    from app.application.services.institutional_ite_runtime import get_ite_runtime

    runtime = get_ite_runtime()
    if runtime is None:
        raise HTTPException(status_code=503, detail="ITE runtime not wired")
    return runtime.run_shadow_cycle().to_dict()


@router.get("/shadow/readiness")
def shadow_readiness(_user: OperatorUser) -> dict[str, Any]:
    """Shadow Production readiness — READY only if every blocker is clear."""
    from app.application.services.institutional_ite_runtime import get_ite_runtime
    from core.di.container import get_container

    blockers: list[str] = []
    try:
        container = get_container()
        settings = container.settings
    except RuntimeError:
        return {
            "result": "NOT READY",
            "blockers": ["DI container not initialised"],
        }

    runtime = get_ite_runtime()
    if runtime is None:
        blockers.append("ITE runtime not wired (GuardedOMS / orchestrator)")
    else:
        if runtime.execution.bridge.ops_plane is None:
            blockers.append("ExecutionBridge not bound to ops plane")
        if runtime.execution.bridge.kill_switch.plane is None:
            blockers.append("Kill switch not bound to shared ops plane")
        if runtime.position_management.ops_plane is None:
            blockers.append("PME not bound to shared ops plane")
        if runtime.plane.mode.value != "SHADOW":
            blockers.append(f"Ops mode is {runtime.plane.mode.value}, need SHADOW")

    if bool(settings.execution_enabled):
        blockers.append("EXECUTION_ENABLED=true — must be false for Shadow")

    checks: dict[str, bool] = {}
    health = None
    gateway_url_configured = bool((settings.mt5_gateway_base_url or "").strip())
    if runtime is not None:
        # One live collect via tick_health — do not re-probe for readiness flags.
        health = runtime.tick_health()
        raw_checks = health.get("live_probes") if isinstance(health, dict) else None
        if isinstance(raw_checks, dict):
            checks = {
                "gateway": bool(raw_checks.get("gateway")),
                "mt5": bool(raw_checks.get("mt5")),
                "railway": bool(raw_checks.get("railway")),
                "supabase": bool(raw_checks.get("supabase")),
                "cloudflare": bool(raw_checks.get("cloudflare")),
            }
        else:
            probes = runtime.probes.collect()
            checks = {
                "gateway": probes.gateway_available,
                "mt5": probes.mt5_connected,
                "railway": probes.railway_api_up,
                "supabase": probes.supabase_up,
                "cloudflare": probes.cloudflare_tunnel_up,
            }
        if not gateway_url_configured:
            blockers.append("MT5_GATEWAY_BASE_URL not configured")
        else:
            if not checks.get("gateway"):
                blockers.append("Gateway not reachable")
            if not checks.get("cloudflare"):
                blockers.append("Cloudflare tunnel not reachable")
            if not checks.get("mt5"):
                blockers.append("MT5 not connected via gateway")
        if (settings.railway_public_domain or "").strip() and not checks.get("railway"):
            blockers.append("Railway API not reachable")
        if getattr(settings, "supabase_configured", False) and not checks.get(
            "supabase"
        ):
            blockers.append("Supabase not reachable")

    result = "READY FOR SHADOW" if not blockers else "NOT READY"
    return {
        "result": result,
        "blockers": blockers,
        "execution_enabled": bool(settings.execution_enabled),
        "mode": runtime.plane.mode.value if runtime else None,
        "kill_switch": runtime.plane.kill_switch_armed if runtime else None,
        "live_probes": checks,
        "gateway_url_configured": gateway_url_configured,
        "health": health,
        "orchestrator": runtime.status() if runtime else None,
        "autotrading": "OFF (terminal-side — confirm manually)",
    }


@router.post("/heartbeat")
def heartbeat(body: HeartbeatBody, _user: OperatorUser) -> dict[str, Any]:
    try:
        comp = ComponentName(body.component)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid component") from exc
    hb = get_reliability_platform().heartbeats.publish(comp, latency_ms=body.latency_ms)
    return hb.to_dict()


@router.get("/traces")
def list_traces(_user: OperatorUser, limit: int = 50) -> dict[str, Any]:
    rows = get_reliability_platform().traces.list(limit=limit)
    return {"traces": [t.to_dict() for t in rows]}


@router.get("/traces/{trace_id}")
def get_trace(trace_id: str, _user: OperatorUser) -> dict[str, Any]:
    t = get_reliability_platform().traces.get(trace_id)
    if t is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return t.to_dict()


@router.post("/traces")
def create_trace(body: TraceBody, _user: OperatorUser) -> dict[str, Any]:
    from app.domain.institutional_trading.reliability.models import TraceStage

    lat: dict[TraceStage, float] = {}
    for k, v in body.latencies.items():
        try:
            lat[TraceStage(k)] = float(v)
        except ValueError:
            continue
    tid = get_reliability_platform().record_trade_path(
        decision_id=body.decision_id, latencies=lat or None
    )
    return {"trace_id": tid}


@router.get("/incidents")
def list_incidents(_user: OperatorUser) -> dict[str, Any]:
    rows = get_reliability_platform().incidents.list(limit=100)
    return {"incidents": [i.to_dict() for i in rows]}


@router.post("/incidents/{incident_id}/ack")
def ack_incident(incident_id: UUID, user: OperatorUser) -> dict[str, Any]:
    updated = get_reliability_platform().incidents.acknowledge(
        incident_id, by=user.display_name or str(user.id)
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return updated.to_dict()


@router.post("/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: UUID, _user: OperatorUser) -> dict[str, Any]:
    updated = get_reliability_platform().incidents.resolve(incident_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return updated.to_dict()


@router.post("/recovery/gateway")
def recover_gateway(_user: OperatorUser) -> dict[str, Any]:
    return get_reliability_platform().recovery.recover_gateway().to_dict()


@router.post("/recovery/mt5")
def recover_mt5(_user: OperatorUser) -> dict[str, Any]:
    return get_reliability_platform().recovery.recover_mt5().to_dict()


@router.post("/recovery/safe-read")
def recover_safe_read(_user: OperatorUser) -> dict[str, Any]:
    return get_reliability_platform().recovery.retry_safe_read().to_dict()


@router.get("/metrics")
def metrics(_user: OperatorUser) -> dict[str, Any]:
    return get_reliability_platform().metrics.snapshot()


@router.get("/timeline")
def timeline(
    _user: OperatorUser,
    q: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    trace_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    rows = get_reliability_platform().timeline.search(
        q=q,
        category=category,
        severity=severity,
        trace_id=trace_id,
        limit=limit,
    )
    return {"events": [e.to_dict() for e in rows], "count": len(rows)}


@router.get("/timeline/export")
def timeline_export(
    _user: OperatorUser,
    fmt: str = Query(default="json", pattern="^(json|csv)$"),
) -> dict[str, Any]:
    tl = get_reliability_platform().timeline
    if fmt == "csv":
        return {"format": "csv", "content": tl.export_csv()}
    return {"format": "json", "content": tl.export_json()}


@router.post("/chaos/inject")
def chaos_inject(body: ChaosBody, _user: OperatorUser) -> dict[str, Any]:
    try:
        get_reliability_platform().chaos.inject(body.failure)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"active": list(get_reliability_platform().chaos.active())}


@router.post("/chaos/clear")
def chaos_clear(_user: OperatorUser, failure: str | None = None) -> dict[str, Any]:
    get_reliability_platform().chaos.clear(failure)
    return {"active": list(get_reliability_platform().chaos.active())}


@router.get("/chaos")
def chaos_status(_user: OperatorUser) -> dict[str, Any]:
    return {"active": list(get_reliability_platform().chaos.active())}
