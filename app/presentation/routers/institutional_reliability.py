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


@router.post("/tick")
def tick(body: ProbeBody, _user: OperatorUser) -> dict[str, Any]:
    platform = get_reliability_platform()
    return platform.tick(
        ProbeInputs(**body.model_dump()),
        required_heartbeats=(
            ComponentName.GATEWAY,
            ComponentName.MT5,
            ComponentName.DECISION,
            ComponentName.OMS,
        ),
    )


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
