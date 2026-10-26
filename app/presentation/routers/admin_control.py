"""Owner control center API.

GET never enables live trading. Policy writes are rejected unless the
authenticated user is the verified designated owner.
"""

from __future__ import annotations

import os
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.application.dto.auth import AuthUserDTO
from app.application.services.account_execution_gate import bound_execution_account
from app.application.services.live_trading_control_service import (
    read_live_probe_facts,
)
from app.application.services.runtime_policy_store import (
    last_applied_version,
    load_runtime_policy,
    memory_audit_events,
    save_runtime_policy,
)
from app.domain.enums.user import UserRole
from app.domain.exceptions.auth import AuthorizationError
from app.domain.identity.designated_owner import is_designated_owner_email
from app.domain.institutional_trading.live_trading_control import (
    get_live_trading_controller,
)
from app.presentation.dependencies.auth import require_roles

router = APIRouter(prefix="/admin/control", tags=["admin-control"])

OwnerUser = Annotated[AuthUserDTO, Depends(require_roles(UserRole.OWNER))]


class PolicyUpdate(BaseModel):
    expected_version: int = Field(ge=0)
    changes: dict[str, Any]
    reason: str = Field(min_length=3, max_length=500)


def _commit_sha() -> str:
    for key in ("RAILWAY_GIT_COMMIT_SHA", "GITHUB_SHA", "VERCEL_GIT_COMMIT_SHA"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value[:12]
    return ""


def _audit_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from app.infrastructure.persistence.direct_postgres import (
            direct_postgres_available,
            fetch,
        )

        if direct_postgres_available():
            loaded = fetch("""
                SELECT action, outcome, resource_type,
                       actor_user_id::text AS actor_user_id,
                       occurred_at, message
                FROM audit_logs
                WHERE resource_type IN ('user_role', 'trading_policy')
                ORDER BY occurred_at DESC
                LIMIT 30
                """)
            for row in loaded:
                stamp = row.get("occurred_at")
                occurred_at = str(stamp or "")
                isoformat = getattr(stamp, "isoformat", None)
                if callable(isoformat):
                    occurred_at = str(isoformat())
                rows.append(
                    {
                        "action": row.get("action"),
                        "outcome": row.get("outcome"),
                        "target": row.get("resource_type"),
                        "actor_user_id": row.get("actor_user_id"),
                        "occurred_at": occurred_at,
                        "message": row.get("message") or "",
                    }
                )
    except Exception:
        rows = []
    if rows:
        return rows
    return memory_audit_events()


@router.get("/overview")
async def admin_overview(user: OwnerUser) -> dict[str, Any]:
    """Read-only system snapshot. Does not arm or enable live trading."""
    facts = read_live_probe_facts()
    _user, bound_login = bound_execution_account()
    policy = load_runtime_policy()
    controller = get_live_trading_controller()
    return {
        "opens_live_trading": False,
        "owner": {
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role,
            "designated_owner": is_designated_owner_email(user.email),
            "other_owner_admin_allowed": False,
        },
        "deployment": {"commit_sha": _commit_sha()},
        "broker": {
            "ownership": facts.get("ownership") or "NOT_OWNED",
            "gateway_online": bool(facts.get("gateway_online")),
            "mt5_connected": bool(facts.get("mt5_connected")),
            "mt5_attached": bool(facts.get("mt5_attached")),
            "server": facts.get("broker_server_masked") or "",
            "account": facts.get("account_login_masked") or "",
            "account_mode": facts.get("account_mode") or "",
            "equity": (
                str(facts.get("equity")) if facts.get("equity") is not None else None
            ),
            "balance": (
                str(facts.get("balance")) if facts.get("balance") is not None else None
            ),
            "open_positions": facts.get("open_positions") or 0,
            "bound": bound_login > 1 and facts.get("ownership") == "OWNED",
        },
        "live_trading": {
            "state": controller.snapshot_state(),
            "kill_switch_independent": True,
        },
        "policy": {
            "ok": policy.ok,
            "version": policy.version,
            "source": policy.source,
            "status": policy.status or ("saved" if policy.version else "baseline"),
            "applied_version": last_applied_version(),
            "error": policy.error,
            "document": policy.document,
        },
        "audit": _audit_rows(),
    }


@router.get("/policy")
async def get_policy(_user: OwnerUser) -> dict[str, Any]:
    policy = load_runtime_policy()
    return {
        "ok": policy.ok,
        "version": policy.version,
        "source": policy.source,
        "status": policy.status or ("saved" if policy.version else "baseline"),
        "applied_version": last_applied_version(),
        "error": policy.error,
        "document": policy.document,
        "pending_restart": False,
    }


@router.put("/policy")
async def put_policy(body: PolicyUpdate, user: OwnerUser) -> dict[str, Any]:
    if not is_designated_owner_email(user.email):
        raise AuthorizationError(
            "Designated owner required",
            code="designated_owner_required",
        )
    saved = save_runtime_policy(
        actor_id=user.id if isinstance(user.id, UUID) else UUID(str(user.id)),
        expected_version=body.expected_version,
        changes=body.changes,
    )
    return {
        "ok": saved.ok,
        "version": saved.version,
        "source": saved.source,
        "status": saved.status or saved.source,
        "error": saved.error,
        "document": saved.document,
        "applied_version": last_applied_version(),
        "pending_restart": False,
    }


@router.get("/audit")
async def get_audit(_user: OwnerUser) -> dict[str, Any]:
    return {"events": _audit_rows()}
