"""Production Reliability & Operational Excellence API.

Additive observe-only ops. Never modifies trading, AI, OMS, MT5, risk,
COP, Enterprise business rules, auth, or pricing. No destructive backup ops.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query

from app.application.dto.auth import AuthUserDTO
from app.domain.enums.user import UserRole
from app.domain.production_reliability.backup_recovery import (
    build_disaster_recovery,
    record_recovery_evidence,
)
from app.domain.production_reliability.incidents import (
    build_incident_center,
    get_incident,
    list_incidents,
    open_incident,
    update_incident_status,
)
from app.domain.production_reliability.observability import build_observability
from app.domain.production_reliability.performance import build_performance_monitoring
from app.domain.production_reliability.platform import (
    build_production_reliability_program,
    build_reliability_noc_panels,
)
from app.domain.production_reliability.production_health import build_production_health
from app.domain.production_reliability.reliability_dashboard import (
    build_reliability_dashboard,
)
from app.domain.production_reliability.security_ops import build_security_ops_async
from app.presentation.dependencies.auth import require_roles

router = APIRouter(
    prefix="/production-reliability",
    tags=["production-reliability"],
)

OperatorUser = Annotated[
    AuthUserDTO,
    Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
]


def _operator(user: AuthUserDTO) -> str:
    return str(getattr(user, "email", None) or getattr(user, "id", None) or "operator")


@router.get("/program")
async def program(_user: OperatorUser) -> dict[str, Any]:
    return await build_production_reliability_program()


@router.get("/observability")
async def observability(_user: OperatorUser) -> dict[str, Any]:
    return build_observability()


@router.get("/reliability")
async def reliability(_user: OperatorUser) -> dict[str, Any]:
    health = build_production_health()
    obs = build_observability()
    return build_reliability_dashboard(health=health, observability=obs)


@router.get("/health")
async def production_health(_user: OperatorUser) -> dict[str, Any]:
    return build_production_health()


@router.get("/incidents")
async def incidents(
    _user: OperatorUser,
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    if status:
        rows = list_incidents(limit=limit, status=status)
        return {"incidents": rows, "count": len(rows), "fabricated": False}
    return build_incident_center()


@router.get("/incidents/{incident_id}")
async def incident_detail(
    incident_id: str, _user: OperatorUser
) -> dict[str, Any]:
    row = get_incident(incident_id)
    if not row:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "incident": row}


@router.post("/incidents")
async def create_incident(
    _user: OperatorUser,
    body: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    row = open_incident(
        title=str(body.get("title") or "Untitled incident"),
        severity=str(body.get("severity") or "medium"),
        summary=str(body.get("summary") or ""),
        operator=_operator(_user),
    )
    return {"ok": True, "incident": row}


@router.post("/incidents/{incident_id}/status")
async def set_incident_status(
    incident_id: str,
    _user: OperatorUser,
    body: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    actions = body.get("actions")
    action_list = (
        [str(a) for a in actions] if isinstance(actions, list) else None
    )
    return update_incident_status(
        incident_id,
        status=str(body.get("status") or ""),
        note=str(body.get("note") or ""),
        operator=_operator(_user),
        root_cause=(
            str(body["root_cause"]) if body.get("root_cause") is not None else None
        ),
        actions=action_list,
        postmortem=(
            str(body["postmortem"]) if body.get("postmortem") is not None else None
        ),
    )


@router.get("/backup-recovery")
async def backup_recovery(_user: OperatorUser) -> dict[str, Any]:
    return build_disaster_recovery()


@router.post("/backup-recovery/evidence")
async def backup_evidence(
    _user: OperatorUser,
    body: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """Record recovery evidence only — never executes restore."""
    row = record_recovery_evidence(
        checklist_id=str(body.get("checklist_id") or ""),
        result=str(body.get("result") or "observed"),
        notes=str(body.get("notes") or ""),
        operator=_operator(_user),
    )
    return {"ok": True, "evidence": row, "destructive_ops_forbidden": True}


@router.get("/security-ops")
async def security_ops(_user: OperatorUser) -> dict[str, Any]:
    return await build_security_ops_async()


@router.get("/performance")
async def performance(_user: OperatorUser) -> dict[str, Any]:
    return build_performance_monitoring(observability=build_observability())


@router.get("/noc-panels")
async def noc_panels(_user: OperatorUser) -> dict[str, Any]:
    return await build_reliability_noc_panels()
