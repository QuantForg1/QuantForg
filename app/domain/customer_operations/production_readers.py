"""Production data readers for COP — observe-only, redacted, never invent."""

from __future__ import annotations

import contextlib
from typing import Any

from app.domain.customer_operations.cop_persistence import redact
from core.logging import get_logger

logger = get_logger(__name__)


async def _platform_session():
    try:
        from core.di.container import get_container

        factory = getattr(get_container(), "platform_uow_factory", None)
        if factory is None:
            return None
        uow = factory()
        await uow.__aenter__()
        return uow
    except Exception:
        logger.debug("cop_platform_uow_unavailable", exc_info=True)
        return None


async def read_users(*, limit: int = 500) -> list[dict[str, Any]]:
    """Read production users (no password hashes)."""
    uow = await _platform_session()
    if uow is None:
        return []
    try:
        from sqlalchemy import text

        session = uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT id, email, display_name, role, status,
                       last_login_at, created_at, updated_at, deactivated_at
                FROM users
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
                        "email": r.get("email"),
                        "display_name": r.get("display_name"),
                        "role": r.get("role"),
                        "status": r.get("status"),
                        "last_login_at": (
                            r["last_login_at"].isoformat()
                            if r.get("last_login_at") is not None
                            else None
                        ),
                        "created_at": (
                            r["created_at"].isoformat()
                            if r.get("created_at") is not None
                            else None
                        ),
                        "country": None,
                        "source": "public.users",
                    }
                )
            )
        return rows
    except Exception:
        logger.exception("cop_read_users_failed")
        return []
    finally:
        with contextlib.suppress(Exception):
            await uow.__aexit__(None, None, None)


async def read_licenses(*, limit: int = 500) -> list[dict[str, Any]]:
    uow = await _platform_session()
    if uow is None:
        return []
    try:
        from sqlalchemy import text

        session = uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT id, user_id, tier, status, seats, issued_at,
                       expires_at, revoked_at, notes, created_at, updated_at
                FROM licenses
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
                        "user_id": str(r["user_id"]) if r.get("user_id") else None,
                        "tier": r.get("tier"),
                        "status": r.get("status"),
                        "seats": r.get("seats"),
                        "issued_at": (
                            r["issued_at"].isoformat()
                            if r.get("issued_at") is not None
                            else None
                        ),
                        "expires_at": (
                            r["expires_at"].isoformat()
                            if r.get("expires_at") is not None
                            else None
                        ),
                        "revoked_at": (
                            r["revoked_at"].isoformat()
                            if r.get("revoked_at") is not None
                            else None
                        ),
                        "notes": r.get("notes") or "",
                        "source": "public.licenses",
                    }
                )
            )
        return rows
    except Exception:
        logger.exception("cop_read_licenses_failed")
        return []
    finally:
        with contextlib.suppress(Exception):
            await uow.__aexit__(None, None, None)


async def read_mt5_connections(*, limit: int = 500) -> list[dict[str, Any]]:
    """MT5 connections — never credentials."""
    uow = await _platform_session()
    if uow is None:
        return []
    try:
        from sqlalchemy import text

        session = uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT id, user_id, login, server, status, session_ref,
                       latency_ms, last_heartbeat_at, connected, login_status,
                       last_error, created_at, updated_at
                FROM mt5_connections
                ORDER BY COALESCE(updated_at, created_at) DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        rows = []
        for r in result.mappings().all():
            login = r.get("login")
            masked = None
            if login is not None:
                s = str(login)
                masked = ("*" * max(0, len(s) - 3)) + s[-3:] if len(s) > 3 else "***"
            rows.append(
                redact(
                    {
                        "id": str(r["id"]),
                        "user_id": str(r["user_id"]) if r.get("user_id") else None,
                        "broker": None,
                        "server": r.get("server"),
                        "login_masked": masked,
                        "status": r.get("status") or (
                            "connected" if r.get("connected") else "disconnected"
                        ),
                        "connected": bool(r.get("connected")),
                        "login_status": r.get("login_status"),
                        "last_heartbeat": (
                            r["last_heartbeat_at"].isoformat()
                            if r.get("last_heartbeat_at") is not None
                            else None
                        ),
                        "latency_ms": r.get("latency_ms"),
                        "trading_permission": None,
                        "auto_trading_status": None,
                        "last_error": r.get("last_error"),
                        "source": "public.mt5_connections",
                        "credentials_exposed": False,
                    }
                )
            )
        return rows
    except Exception:
        logger.exception("cop_read_mt5_connections_failed")
        return []
    finally:
        with contextlib.suppress(Exception):
            await uow.__aexit__(None, None, None)


async def read_audit_login_history(
    *, user_id: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    uow = await _platform_session()
    if uow is None:
        return []
    try:
        from sqlalchemy import text

        session = uow._require_session()
        if user_id:
            result = await session.execute(
                text(
                    """
                    SELECT id, action, actor_user_id, occurred_at, ip_address,
                           message, created_at
                    FROM audit_logs
                    WHERE actor_user_id::text = :uid
                       OR (metadata::text ILIKE :uid_like)
                    ORDER BY COALESCE(occurred_at, created_at) DESC
                    LIMIT :limit
                    """
                ),
                {"uid": user_id, "uid_like": f"%{user_id}%", "limit": limit},
            )
        else:
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
        rows = []
        for r in result.mappings().all():
            rows.append(
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
            )
        return rows
    except Exception:
        logger.debug("cop_read_audit_failed", exc_info=True)
        return []
    finally:
        with contextlib.suppress(Exception):
            await uow.__aexit__(None, None, None)


def live_trading_health_snapshot() -> dict[str, Any]:
    """Observe-only snapshot from existing runtime — never mutates."""
    out: dict[str, Any] = {
        "robot_online": None,
        "gateway": None,
        "mt5": None,
        "ai": None,
        "oms": None,
        "open_positions": None,
        "pnl": None,
        "risk_status": None,
        "last_signal": None,
        "health": "unknown",
        "fabricated": False,
        "observe_only": True,
    }
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime

        rt = get_ite_runtime()
        if rt is not None:
            out["robot_online"] = True
            out["ai"] = "online"
            engine = getattr(getattr(rt, "position_management", None), "engine", None)
            positions = getattr(engine, "_positions", None) if engine else None
            if isinstance(positions, (dict, list)):
                out["open_positions"] = len(positions)
            out["health"] = "healthy"
        else:
            out["robot_online"] = False
            out["ai"] = "idle"
    except Exception:
        out["robot_online"] = None

    try:
        from core.config.settings import get_settings

        settings = get_settings()
        gw = getattr(settings, "mt5_gateway_url", None) or getattr(
            settings, "gateway_url", None
        )
        out["gateway"] = "configured" if gw else "unknown"
    except Exception:
        # settings unavailable — leave gateway unknown
        logger.debug("cop_gateway_settings_unavailable", exc_info=True)
        out["gateway"] = "unknown"

    return redact(out)
