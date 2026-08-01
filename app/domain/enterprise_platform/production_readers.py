"""Production readers for Enterprise Platform — observe-only."""

from __future__ import annotations

from typing import Any

from app.domain.enterprise_platform.persistence import redact
from core.logging import get_logger

logger = get_logger(__name__)


async def _platform_uow():
    try:
        from core.di.container import get_container

        factory = getattr(get_container(), "platform_uow_factory", None)
        if factory is None:
            return None
        uow = factory()
        await uow.__aenter__()
        return uow
    except Exception:
        logger.debug("enterprise_platform_uow_unavailable", exc_info=True)
        return None


async def _close_uow(uow: Any) -> None:
    import contextlib

    with contextlib.suppress(Exception):
        if uow is not None:
            await uow.__aexit__(None, None, None)


async def read_organizations(*, limit: int = 200) -> list[dict[str, Any]]:
    uow = await _platform_uow()
    if uow is None:
        return []
    try:
        from sqlalchemy import text

        session = uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT id, name, slug, org_type, created_at, updated_at
                FROM organizations
                ORDER BY COALESCE(updated_at, created_at) DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        rows = []
        for r in result.mappings().all():
            rows.append(
                redact(
                    {
                        "id": str(r["id"]),
                        "name": r.get("name"),
                        "slug": r.get("slug"),
                        "org_type": r.get("org_type"),
                        "created_at": (
                            r["created_at"].isoformat()
                            if r.get("created_at") is not None
                            else None
                        ),
                        "source": "public.organizations",
                    }
                )
            )
        return rows
    except Exception:
        logger.exception("enterprise_read_organizations_failed")
        return []
    finally:
        await _close_uow(uow)


async def read_organization_members(
    *, organization_id: str | None = None, limit: int = 500
) -> list[dict[str, Any]]:
    uow = await _platform_uow()
    if uow is None:
        return []
    try:
        from sqlalchemy import text

        session = uow._require_session()
        if organization_id:
            result = await session.execute(
                text(
                    """
                    SELECT id, organization_id, user_id, role, status,
                           created_at, updated_at
                    FROM organization_members
                    WHERE organization_id::text = :oid
                    ORDER BY COALESCE(updated_at, created_at) DESC
                    LIMIT :limit
                    """
                ),
                {"oid": organization_id, "limit": limit},
            )
        else:
            result = await session.execute(
                text(
                    """
                    SELECT id, organization_id, user_id, role, status,
                           created_at, updated_at
                    FROM organization_members
                    ORDER BY COALESCE(updated_at, created_at) DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
        rows = []
        for r in result.mappings().all():
            rows.append(
                redact(
                    {
                        "id": str(r["id"]),
                        "organization_id": str(r["organization_id"]),
                        "user_id": str(r["user_id"]) if r.get("user_id") else None,
                        "role": r.get("role"),
                        "status": r.get("status"),
                        "source": "public.organization_members",
                    }
                )
            )
        return rows
    except Exception:
        logger.debug("enterprise_read_members_failed", exc_info=True)
        return []
    finally:
        await _close_uow(uow)


async def read_users(*, limit: int = 500) -> list[dict[str, Any]]:
    uow = await _platform_uow()
    if uow is None:
        return []
    try:
        from sqlalchemy import text

        session = uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT id, email, display_name, role, status, last_login_at,
                       created_at
                FROM users
                ORDER BY COALESCE(updated_at, created_at) DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [
            redact(
                {
                    "id": str(r["id"]),
                    "email": r.get("email"),
                    "display_name": r.get("display_name"),
                    "role": r.get("role"),
                    "status": r.get("status"),
                    "last_login_at": (
                        r["last_login_at"].isoformat()
                        if r.get("last_login_at") is not None
                        else None
                    ),
                    "source": "public.users",
                }
            )
            for r in result.mappings().all()
        ]
    except Exception:
        logger.exception("enterprise_read_users_failed")
        return []
    finally:
        await _close_uow(uow)


async def read_sessions(*, limit: int = 200) -> list[dict[str, Any]]:
    uow = await _platform_uow()
    if uow is None:
        return []
    try:
        from sqlalchemy import text

        session = uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT id, user_id, ip_address, user_agent, created_at,
                       last_active_at, revoked_at, is_active
                FROM user_sessions
                ORDER BY COALESCE(last_active_at, created_at) DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [
            redact(
                {
                    "id": str(r["id"]),
                    "user_id": str(r["user_id"]) if r.get("user_id") else None,
                    "ip": r.get("ip_address"),
                    "user_agent": r.get("user_agent"),
                    "created_at": (
                        r["created_at"].isoformat()
                        if r.get("created_at") is not None
                        else None
                    ),
                    "last_seen_at": (
                        r["last_active_at"].isoformat()
                        if r.get("last_active_at") is not None
                        else None
                    ),
                    "revoked": r.get("revoked_at") is not None,
                    "is_active": bool(r.get("is_active")),
                    "source": "public.user_sessions",
                }
            )
            for r in result.mappings().all()
        ]
    except Exception:
        logger.debug("enterprise_read_sessions_failed", exc_info=True)
        return []
    finally:
        await _close_uow(uow)


async def read_devices(*, limit: int = 200) -> list[dict[str, Any]]:
    uow = await _platform_uow()
    if uow is None:
        return []
    try:
        from sqlalchemy import text

        session = uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT id, user_id, device_label, user_agent, last_seen_at,
                       created_at
                FROM user_devices
                ORDER BY COALESCE(last_seen_at, created_at) DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [
            redact(
                {
                    "id": str(r["id"]),
                    "user_id": str(r["user_id"]) if r.get("user_id") else None,
                    "device_name": r.get("device_label"),
                    "device_type": None,
                    "user_agent": r.get("user_agent"),
                    "last_seen_at": (
                        r["last_seen_at"].isoformat()
                        if r.get("last_seen_at") is not None
                        else None
                    ),
                    "source": "public.user_devices",
                }
            )
            for r in result.mappings().all()
        ]
    except Exception:
        logger.debug("enterprise_read_devices_failed", exc_info=True)
        return []
    finally:
        await _close_uow(uow)


async def read_audit_logs(*, limit: int = 200) -> list[dict[str, Any]]:
    uow = await _platform_uow()
    if uow is None:
        return []
    try:
        from sqlalchemy import text

        session = uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT id, action, actor_user_id, occurred_at, ip_address,
                       message, created_at
                FROM audit_logs
                ORDER BY COALESCE(occurred_at, created_at) DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [
            redact(
                {
                    "id": str(r["id"]),
                    "action": r.get("action"),
                    "actor_user_id": (
                        str(r["actor_user_id"]) if r.get("actor_user_id") else None
                    ),
                    "occurred_at": (
                        (r.get("occurred_at") or r.get("created_at")).isoformat()
                        if (r.get("occurred_at") or r.get("created_at")) is not None
                        else None
                    ),
                    "ip": r.get("ip_address"),
                    "message": r.get("message"),
                    "source": "public.audit_logs",
                }
            )
            for r in result.mappings().all()
        ]
    except Exception:
        logger.debug("enterprise_read_audit_failed", exc_info=True)
        return []
    finally:
        await _close_uow(uow)
