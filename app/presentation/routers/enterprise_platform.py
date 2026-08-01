"""Enterprise Platform API — additive SaaS controls.

Never modifies Trading, AI, OMS, MT5, Risk, COP logic, auth, or pricing.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query, Request

from app.application.dto.auth import AuthUserDTO
from app.application.services.enterprise_platform import (
    build_enterprise_noc_panels,
    build_enterprise_platform,
)
from app.domain.enterprise_platform.admin_console import build_enterprise_dashboard
from app.domain.enterprise_platform.api_keys import (
    create_api_key,
    disable_api_key,
    list_api_keys,
    rotate_api_key,
)
from app.domain.enterprise_platform.audit_center import build_audit_center
from app.domain.enterprise_platform.compliance import (
    build_compliance_center,
    build_gdpr_export,
    set_retention_policy,
)
from app.domain.enterprise_platform.organizations import (
    assign_enterprise_role,
    build_organizations_center,
    isolation_scope,
)
from app.domain.enterprise_platform.rbac import (
    permission_matrix_table,
    require_permission,
)
from app.domain.enterprise_platform.reporting import build_enterprise_reports
from app.domain.enterprise_platform.security_center import build_security_center
from app.domain.enterprise_platform.system_admin import build_admin_console
from app.domain.enums.user import UserRole
from app.presentation.dependencies.auth import require_roles

router = APIRouter(prefix="/enterprise", tags=["enterprise-platform"])

OperatorUser = Annotated[
    AuthUserDTO,
    Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
]


def _operator(user: AuthUserDTO) -> str:
    return str(getattr(user, "email", None) or getattr(user, "id", None) or "operator")


def _role(user: AuthUserDTO) -> str:
    return str(getattr(user, "role", None) or "admin")


def _ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return ""


def _gate(user: AuthUserDTO, capability: str) -> dict[str, Any] | None:
    check = require_permission(_role(user), capability)
    if not check["allowed"]:
        return {"ok": False, "error": "permission_denied", **check}
    return None


@router.get("/platform")
async def platform(
    _user: OperatorUser,
    organization_id: str | None = Query(default=None),
) -> dict[str, Any]:
    denied = _gate(_user, "admin.console")
    if denied:
        return denied
    return await build_enterprise_platform(organization_id=organization_id)


@router.get("/dashboard")
async def dashboard(_user: OperatorUser) -> dict[str, Any]:
    denied = _gate(_user, "dashboard.view")
    if denied:
        return denied
    return await build_enterprise_dashboard()


@router.get("/organizations")
async def organizations(_user: OperatorUser) -> dict[str, Any]:
    denied = _gate(_user, "org.view")
    if denied:
        return denied
    return await build_organizations_center()


@router.get("/organizations/{organization_id}/isolation")
async def org_isolation(
    organization_id: str, _user: OperatorUser
) -> dict[str, Any]:
    denied = _gate(_user, "org.view")
    if denied:
        return denied
    return isolation_scope(organization_id)


@router.post("/organizations/{organization_id}/members/{member_id}/role")
async def set_member_role(
    organization_id: str,
    member_id: str,
    request: Request,
    user: OperatorUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    denied = _gate(user, "members.manage")
    if denied:
        return denied
    return assign_enterprise_role(
        member_id=member_id,
        organization_id=organization_id,
        enterprise_role=str(payload.get("enterprise_role") or "read_only"),
        operator=_operator(user),
        ip=_ip(request),
    )


@router.get("/rbac")
async def rbac(_user: OperatorUser) -> dict[str, Any]:
    denied = _gate(_user, "rbac.view")
    if denied:
        return denied
    return permission_matrix_table()


@router.get("/api-keys")
async def api_keys(
    _user: OperatorUser,
    organization_id: str | None = Query(default=None),
) -> dict[str, Any]:
    denied = _gate(_user, "api_keys.view")
    if denied:
        return denied
    return list_api_keys(organization_id=organization_id)


@router.post("/api-keys")
async def api_keys_create(
    request: Request,
    user: OperatorUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    denied = _gate(user, "api_keys.manage")
    if denied:
        return denied
    return create_api_key(
        organization_id=str(payload.get("organization_id") or "platform"),
        name=str(payload.get("name") or "API key"),
        scopes=list(payload.get("scopes") or []),
        operator=_operator(user),
        ip=_ip(request),
        expires_days=payload.get("expires_days", 90),
    )


@router.post("/api-keys/{key_id}/rotate")
async def api_keys_rotate(
    key_id: str, request: Request, user: OperatorUser
) -> dict[str, Any]:
    denied = _gate(user, "api_keys.manage")
    if denied:
        return denied
    return rotate_api_key(key_id=key_id, operator=_operator(user), ip=_ip(request))


@router.post("/api-keys/{key_id}/disable")
async def api_keys_disable(
    key_id: str, request: Request, user: OperatorUser
) -> dict[str, Any]:
    denied = _gate(user, "api_keys.manage")
    if denied:
        return denied
    return disable_api_key(key_id=key_id, operator=_operator(user), ip=_ip(request))


@router.get("/audit")
async def audit(
    _user: OperatorUser,
    organization_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    denied = _gate(_user, "audit.view")
    if denied:
        return denied
    return await build_audit_center(
        organization_id=organization_id, action=action, q=q, limit=limit
    )


@router.get("/security")
async def security(_user: OperatorUser) -> dict[str, Any]:
    denied = _gate(_user, "security.view")
    if denied:
        return denied
    return await build_security_center()


@router.get("/reports")
async def reports(
    _user: OperatorUser,
    organization_id: str | None = Query(default=None),
) -> dict[str, Any]:
    denied = _gate(_user, "reports.view")
    if denied:
        return denied
    return await build_enterprise_reports(organization_id=organization_id)


@router.get("/compliance")
async def compliance(_user: OperatorUser) -> dict[str, Any]:
    denied = _gate(_user, "reports.compliance")
    if denied:
        return denied
    return await build_compliance_center()


@router.post("/compliance/retention")
async def compliance_retention(
    request: Request,
    user: OperatorUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    denied = _gate(user, "compliance.export")
    if denied:
        return denied
    return set_retention_policy(
        audit_days=int(payload.get("audit_retention_days") or 365),
        access_days=int(payload.get("access_log_retention_days") or 180),
        export_days=int(payload.get("export_retention_days") or 30),
        operator=_operator(user),
        ip=_ip(request),
    )


@router.post("/compliance/gdpr-export")
async def compliance_gdpr(
    request: Request,
    user: OperatorUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    denied = _gate(user, "compliance.export")
    if denied:
        return denied
    return await build_gdpr_export(
        user_id=str(payload.get("user_id") or ""),
        operator=_operator(user),
        ip=_ip(request),
    )


@router.get("/admin")
async def admin(_user: OperatorUser) -> dict[str, Any]:
    denied = _gate(_user, "admin.console")
    if denied:
        return denied
    return await build_admin_console()


@router.get("/noc-panels")
async def noc_panels(_user: OperatorUser) -> dict[str, Any]:
    return await build_enterprise_noc_panels()
