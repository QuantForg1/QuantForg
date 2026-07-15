"""Weltrade production orchestration — Railway API → Windows MT5 Gateway.

Does not change Strategy / Portfolio / Execution Intelligence.
Broker passwords are forwarded once to the gateway and never persisted here.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.domain.entities.mt5 import MT5Connection
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client
from core.logging import get_logger

logger = get_logger(__name__)

WELTRADE_BROKER = "weltrade"
WELTRADE_SERVERS = {
    "demo": ("Weltrade-Demo", "Weltrade-MT5"),
    "live": ("Weltrade-MT5", "Weltrade-Demo"),
}


def _gateway_mt5_already_connected(health: dict[str, Any]) -> bool:
    """True when gateway /health shows an active MT5 session.

    Supports both nested ``mt5.connected`` (current gateway) and flattened
    top-level ``connected`` / ``session_mode`` (public health probes).
    """
    if bool(health.get("connected")):
        return True
    nested = health.get("mt5")
    if isinstance(nested, dict) and bool(nested.get("connected")):
        return True
    mode = str(health.get("session_mode") or "").strip().lower()
    if mode in {"attached", "connected"}:
        return True
    if isinstance(nested, dict):
        nested_mode = str(nested.get("session_mode") or "").strip().lower()
        if nested_mode in {"attached", "connected"}:
            return True
    return False


@dataclass
class WeltradeIntegrationService:
    """Thin orchestration for the Weltrade-only production connection UX.

    After connect/attach, persists ``MT5Connection`` so Dashboard / Portfolio /
    Execution / Ops share the same live session as ``/broker``.
    """

    adapter: MT5Adapter
    uow_factory: Any = None
    _last_sync_at: str | None = field(default=None, init=False)

    def profile(self) -> dict[str, Any]:
        return {
            "broker": WELTRADE_BROKER,
            "name": "Weltrade",
            "platform": "MT5",
            "website": "https://www.weltrade.com",
            "servers": {
                "demo": list(WELTRADE_SERVERS["demo"]),
                "live": list(WELTRADE_SERVERS["live"]),
            },
            "gateway_backed": isinstance(self.adapter.client, GatewayMT5Client),
            "execution_enabled": self.adapter.execution_enabled,
            "note": (
                "Browser talks only to Railway. Railway talks to the Windows "
                "MT5 Gateway. Broker passwords stay in gateway memory."
            ),
        }

    def _gateway(self) -> GatewayMT5Client | None:
        client = self.adapter.client
        return client if isinstance(client, GatewayMT5Client) else None

    def _configuration(self) -> dict[str, Any]:
        gw = self._gateway()
        base_url = ""
        token_configured = False
        timeout_seconds: float | None = None
        last_upstream: dict[str, Any] = {}
        if gw is not None:
            base_url = gw.base_url
            token_configured = bool(gw.token)
            timeout_seconds = float(gw.timeout_seconds)
            last_upstream = gw.last_upstream()
        return {
            "gateway_backed": gw is not None,
            "mt5_gateway_base_url": base_url or None,
            "mt5_gateway_base_url_configured": bool(base_url),
            "mt5_gateway_caller_token_configured": token_configured,
            "timeout_seconds": timeout_seconds,
            "last_upstream": last_upstream,
            "execution_enabled": self.adapter.execution_enabled,
        }

    async def health(self, *, user_id: UUID) -> dict[str, Any]:
        """Production health probe for tunnel + gateway + MT5 session."""
        _ = user_id
        cfg = self._configuration()
        gw = self._gateway()
        latency_ms: float | None = None
        tunnel_reachable = False
        gateway_reachable = False
        mt5_attached = False
        version = ""
        server: str | None = None
        account: dict[str, Any] | None = None
        session_mode = "none"
        login_status = "logged_out"
        detail = "ok"
        diagnostic = "ok"
        gateway_payload: dict[str, Any] = {}
        upstream_error: str | None = None

        if gw is None:
            detail = (
                "Railway is not using GatewayMT5Client. "
                "Confirm MT5_GATEWAY_BASE_URL and MT5_GATEWAY_CALLER_TOKEN are set "
                "on the Railway service (absolute HTTPS URL, e.g. "
                "https://xxxx.trycloudflare.com) and redeploy."
            )
            diagnostic = "Gateway not configured"
            return {
                "ok": False,
                "healthy": False,
                "broker": WELTRADE_BROKER,
                "configuration": cfg,
                "gateway_reachable": False,
                "tunnel_reachable": False,
                "mt5_attached": False,
                "latency_ms": None,
                "latency": None,
                "version": None,
                "server": None,
                "account": None,
                "session": {"mode": "none"},
                "detail": detail,
                "upstream_error": detail,
                "last_upstream_error": detail,
                "last_http_status": None,
                "last_body_preview": None,
                "redirects_followed": None,
                "gateway_url": None,
                "cloudflare": {"detected": False, "ray": None, "cache": None},
                "diagnostic": diagnostic,
                "login_status": login_status,
                "gateway_online": False,
                "mt5_connected": False,
                "weltrade_connected": False,
                "status": "offline",
                "transport": {},
            }

        try:
            gateway_payload = gw.gateway_health()
            tunnel_reachable = True
            gateway_reachable = gateway_payload.get("status") == "ok"
            if not gateway_reachable:
                detail = (
                    f"Gateway /health returned unexpected payload: {gateway_payload}"
                )
                upstream_error = detail
                diagnostic = "Gateway unhealthy"
        except Exception as exc:
            detail = str(exc)
            upstream_error = detail
            diagnostic = str(
                gw.last_upstream().get("diagnostic") or "Gateway unreachable"
            )
            logger.warning(
                "weltrade_gateway_health_failed",
                error=str(exc),
                base_url=gw.base_url,
                last_upstream=gw.last_upstream(),
            )

        if gateway_reachable:
            try:
                snap = self.adapter.health()
                latency_ms = snap.latency_ms
                version = snap.version or ""
                server = snap.server or None
                mt5_attached = bool(snap.connected)
                login_status = snap.login_status or (
                    "connected" if mt5_attached else "logged_out"
                )
                session_mode = str(
                    getattr(self.adapter.client, "session_mode", "none") or "none"
                )
                if mt5_attached:
                    info = self.adapter.account_info()
                    account = {
                        "login": info.login,
                        "name": info.name,
                        "balance": str(info.balance),
                        "equity": str(info.equity),
                        "margin": str(info.margin),
                        "free_margin": str(info.free_margin),
                        "leverage": info.leverage,
                        "currency": info.currency,
                        "server": info.server,
                    }
                    server = info.server or server
            except Exception as exc:
                detail = f"MT5 session probe failed: {exc}"
                upstream_error = detail
                diagnostic = "MT5 session probe failed"
                logger.warning("weltrade_mt5_probe_failed", error=str(exc))

        if gateway_reachable and mt5_attached:
            await self.ensure_user_session_bound(user_id=user_id)

        cfg = self._configuration()
        transport = gw.diagnostics_probe()
        upstream = gw.last_upstream()
        transport_latency = upstream.get("latency_ms")
        if latency_ms is None and transport_latency is not None:
            latency_ms = float(transport_latency)

        if gateway_reachable and mt5_attached:
            detail = "ok"
            diagnostic = "ok"
            upstream_error = None
        elif gateway_reachable and diagnostic == "ok":
            diagnostic = "Gateway Online"

        return {
            "ok": tunnel_reachable,
            "healthy": bool(gateway_reachable),
            "broker": WELTRADE_BROKER,
            "configuration": cfg,
            "gateway_reachable": gateway_reachable,
            "tunnel_reachable": tunnel_reachable,
            "mt5_attached": mt5_attached,
            "latency_ms": latency_ms,
            "latency": latency_ms,
            "version": version or None,
            "server": server,
            "account": account,
            "session": {
                "mode": session_mode,
                "login_status": login_status,
                "server": server,
            },
            "gateway": {
                "status": gateway_payload.get("status"),
                "service": gateway_payload.get("service"),
                "bridge_available": gateway_payload.get("bridge_available"),
                "token_configured": gateway_payload.get("token_configured"),
            },
            "transport": transport,
            "detail": detail,
            "upstream_error": upstream_error,
            "last_upstream_error": upstream_error or upstream.get("error"),
            "last_http_status": upstream.get("status_code"),
            "last_body_preview": upstream.get("body_preview"),
            "redirects_followed": upstream.get("redirects_followed"),
            "gateway_url": gw.base_url,
            "cloudflare": {
                "detected": bool(
                    transport.get("cloudflare") or upstream.get("cloudflare")
                ),
                "ray": upstream.get("cloudflare_ray"),
                "cache": upstream.get("cloudflare_cache"),
                "http_version": upstream.get("http_version"),
            },
            "diagnostic": diagnostic,
            "login_status": login_status,
            "gateway_online": gateway_reachable,
            "mt5_connected": mt5_attached,
            "weltrade_connected": bool(gateway_reachable and mt5_attached),
            "status": (
                "healthy"
                if gateway_reachable and mt5_attached
                else "degraded"
                if gateway_reachable
                else "offline"
            ),
        }

    async def dashboard(self, *, user_id: UUID) -> dict[str, Any]:
        gw = self._gateway()
        if gw is not None:
            await self.ensure_user_session_bound(user_id=user_id)
        gateway_online = False
        gateway_payload: dict[str, Any] = {}
        if gw is not None:
            try:
                gateway_payload = gw.gateway_health()
                gateway_online = gateway_payload.get("status") == "ok"
            except Exception as exc:
                gateway_payload = {"status": "error", "detail": str(exc)}
                logger.warning("weltrade_dashboard_gateway_error", error=str(exc))

        health = self.adapter.health()
        mt5_connected = bool(health.connected)
        account: dict[str, Any] | None = None
        positions: list[dict[str, Any]] = []
        orders: list[dict[str, Any]] = []
        history: list[dict[str, Any]] = []
        if mt5_connected:
            try:
                snap = self.adapter.account_info()
                account = {
                    "login": snap.login,
                    "balance": str(snap.balance),
                    "equity": str(snap.equity),
                    "margin": str(snap.margin),
                    "free_margin": str(snap.free_margin),
                    "margin_level": str(snap.margin_level),
                    "profit": str(snap.profit),
                    "leverage": snap.leverage,
                    "currency": snap.currency,
                    "server": snap.server,
                    "name": snap.name,
                }
                positions = [p.to_dict() for p in self.adapter.list_positions()]
                orders = [o.to_dict() for o in self.adapter.list_orders()]
                history = [d.to_dict() for d in self.adapter.history_deals()]
                self._last_sync_at = datetime.now(UTC).isoformat()
            except Exception as exc:
                account = {"error": str(exc)}
                logger.warning("weltrade_dashboard_sync_error", error=str(exc))

        session_mode = getattr(self.adapter.client, "session_mode", "none")
        diagnostics: dict[str, Any] = {}
        if gw is not None and mt5_connected:
            try:
                diagnostics = gw.diagnostics()
            except Exception as exc:
                diagnostics = {"error": str(exc)}

        upstream = gw.last_upstream() if gw is not None else {}
        transport = gw.diagnostics_probe() if gw is not None else {}
        upstream_error: str | None = None
        diagnostic = "ok"
        if not gateway_online:
            if gw is None:
                upstream_error = (
                    "Railway is not using GatewayMT5Client. "
                    "Confirm MT5_GATEWAY_BASE_URL and MT5_GATEWAY_CALLER_TOKEN."
                )
                diagnostic = "Gateway not configured"
            else:
                upstream_error = str(
                    gateway_payload.get("detail")
                    or upstream.get("error")
                    or "Gateway /health failed"
                )
                diagnostic = str(
                    upstream.get("diagnostic") or "Gateway Offline"
                )
        elif not mt5_connected:
            diagnostic = "Gateway Online"

        return {
            "broker": WELTRADE_BROKER,
            "profile": self.profile(),
            "configuration": self._configuration(),
            "connection": {
                "gateway_online": gateway_online,
                "mt5_connected": mt5_connected,
                "weltrade_connected": mt5_connected and gateway_online,
                "session_mode": session_mode,
                "latency_ms": health.latency_ms,
                "heartbeat_at": health.last_heartbeat_at,
                "login_status": health.login_status,
                "server": health.server or None,
                "broker_version": health.version or None,
                "terminal_build": health.terminal_build,
                "last_sync_at": self._last_sync_at,
            },
            "gateway": gateway_payload,
            "transport": transport,
            "detail": upstream_error or "ok",
            "upstream_error": upstream_error,
            "last_upstream_error": upstream_error or upstream.get("error"),
            "last_http_status": upstream.get("status_code"),
            "last_body_preview": upstream.get("body_preview"),
            "redirects_followed": upstream.get("redirects_followed"),
            "gateway_url": gw.base_url if gw is not None else None,
            "latency": health.latency_ms or upstream.get("latency_ms"),
            "cloudflare": {
                "detected": bool(transport.get("cloudflare")),
                "ray": upstream.get("cloudflare_ray"),
                "cache": upstream.get("cloudflare_cache"),
                "http_version": upstream.get("http_version"),
            },
            "diagnostic": diagnostic,
            "login_status": health.login_status,
            "session": {
                "mode": session_mode,
                "login_status": health.login_status,
                "server": health.server or None,
            },
            "gateway_online": gateway_online,
            "gateway_reachable": gateway_online,
            "mt5_connected": mt5_connected,
            "account": account,
            "positions": {"items": positions, "count": len(positions)},
            "orders": {"items": orders, "count": len(orders)},
            "history": {"items": history, "count": len(history)},
            "diagnostics": diagnostics,
            "execution_enabled": self.adapter.execution_enabled,
            "status": (
                "healthy"
                if gateway_online and mt5_connected
                else "degraded"
                if gateway_online
                else "offline"
            ),
        }


    async def bind_user_session(
        self,
        *,
        user_id: UUID,
        login: int | None = None,
        server: str | None = None,
        path: str = "",
        session_ref: str | None = None,
    ) -> str | None:
        """Persist the live adapter session for this user (single source of truth)."""
        if self.uow_factory is None:
            logger.warning("weltrade_bind_skipped", reason="uow_factory_missing")
            return None
        live_ref = (
            (session_ref or "").strip()
            or (getattr(self.adapter, "_live_session_ref", None) or "")
            or (getattr(self.adapter.client, "session_token", "") or "")
        )
        live_ref = live_ref.strip()
        if not live_ref or not getattr(self.adapter.client, "is_connected", False):
            return None

        resolved_login = int(login or 0)
        resolved_server = (server or "").strip()
        if resolved_login <= 0 or not resolved_server:
            try:
                info = self.adapter.account_info()
                resolved_login = resolved_login or int(info.login)
                resolved_server = resolved_server or str(info.server or "")
            except Exception:
                stored = None
                if live_ref in getattr(self.adapter, "_sessions", {}):
                    stored = self.adapter._sessions.get(live_ref)
                if stored is not None:
                    resolved_login = resolved_login or int(stored.login or 0)
                    resolved_server = resolved_server or str(stored.server or "")
        if resolved_login <= 0:
            resolved_login = 1
        if not resolved_server:
            resolved_server = "Weltrade-MT5"

        build: int | None = None
        version = ""
        latency: float | None = None
        with contextlib.suppress(Exception):
            snap = self.adapter.health()
            build = snap.terminal_build
            version = snap.version or ""
            latency = snap.latency_ms
        with contextlib.suppress(Exception):
            terminal = self.adapter.terminal_info()
            build = build or terminal.build

        connection = MT5Connection.create(
            user_id=user_id,
            login=resolved_login,
            server=resolved_server,
            terminal_path=path,
        )
        connection.mark_connected(
            session_ref=live_ref,
            terminal_build=build,
            terminal_version=version,
            latency_ms=latency,
        )
        async with self.uow_factory() as uow:
            await uow.connections.upsert_for_user(connection)
            await uow.commit()
        logger.info(
            "weltrade_session_bound",
            user_id=str(user_id),
            login=resolved_login,
            server=resolved_server,
            session_ref=live_ref[:24],
        )
        return live_ref

    async def unbind_user_session(self, *, user_id: UUID) -> None:
        """Mark the user's DB connection disconnected (does not stop other tenants)."""
        if self.uow_factory is None:
            return
        async with self.uow_factory() as uow:
            connection = await uow.connections.get_active_for_user(user_id)
            if connection is None:
                return
            session_ref = (connection.session_ref or "").strip()
            live = getattr(self.adapter, "_live_session_ref", None)
            if session_ref and live and session_ref == live:
                self.adapter.shutdown()
            connection.mark_disconnected()
            await uow.connections.update(connection)
            await uow.commit()

    async def ensure_user_session_bound(self, *, user_id: UUID) -> None:
        """Heal: if gateway session is live but DB row missing, bind it.

        After a Railway redeploy the Windows terminal can still be logged in while
        this process has no ``_live_session_ref``. Probe/attach first, then bind.
        """
        if self.uow_factory is None:
            return

        client = self.adapter.client
        # Sync in-process connected flag from gateway /session/status.
        with contextlib.suppress(Exception):
            self.adapter.health()

        if not getattr(client, "is_connected", False):
            return

        live_ref = (getattr(self.adapter, "_live_session_ref", None) or "").strip()
        if not live_ref:
            live_ref = (getattr(client, "session_token", "") or "").strip()
        if not live_ref:
            # Terminal is live on Windows but this process has no session handle yet.
            try:
                live_ref = self.adapter.attach(path="")
            except Exception as exc:
                logger.warning(
                    "weltrade_ensure_attach_failed",
                    error=str(exc),
                    user_id=str(user_id),
                )
                return
            live_ref = (live_ref or "").strip()
        if not live_ref:
            return

        async with self.uow_factory() as uow:
            existing = await uow.connections.get_active_for_user(user_id)
        if (
            existing is not None
            and existing.connected
            and (existing.session_ref or "").strip() == live_ref
            and self.adapter.is_live_session(live_ref)
        ):
            return
        await self.bind_user_session(user_id=user_id, session_ref=live_ref)

    async def connect(
        self,
        *,
        user_id: UUID,
        login: int,
        password: str,
        server: str,
        account_type: str = "demo",
        prefer_attach: bool = True,
        path: str = "",
    ) -> dict[str, Any]:
        account_type = (account_type or "demo").strip().lower()
        if account_type not in {"demo", "live"}:
            raise ValueError("account_type must be demo or live")
        if login <= 0:
            raise ValueError("login must be a positive integer")
        server_name = (server or "").strip()
        if not server_name or server_name.lower() in {"auto", "auto detect"}:
            server_name = WELTRADE_SERVERS[account_type][0]

        logger.info(
            "weltrade_connect_start",
            login=login,
            server=server_name,
            account_type=account_type,
            prefer_attach=prefer_attach,
            password_provided=bool(password),
            gateway_backed=self._gateway() is not None,
        )

        steps: list[dict[str, Any]] = []
        gw = self._gateway()
        if gw is None:
            raise RuntimeError(
                "Windows MT5 Gateway is not configured on Railway. "
                "Set MT5_GATEWAY_BASE_URL and MT5_GATEWAY_CALLER_TOKEN "
                "(must match Windows MT5_GATEWAY_TOKEN)."
            )

        try:
            health = gw.gateway_health()
            ok = health.get("status") == "ok"
            if not ok:
                raise RuntimeError(
                    f"Gateway /health unexpected payload at {gw.base_url}: {health}"
                )
            steps.append(
                {
                    "step": "gateway_check",
                    "ok": True,
                    "detail": f"Gateway reachable ({gw.base_url})",
                }
            )
        except Exception as exc:
            upstream = gw.last_upstream()
            detail = str(exc)
            steps.append(
                {
                    "step": "gateway_check",
                    "ok": False,
                    "detail": detail,
                    "upstream": upstream,
                }
            )
            logger.exception(
                "weltrade_connect_gateway_unavailable",
                error=detail,
                base_url=gw.base_url,
                last_upstream=upstream,
            )
            raise RuntimeError(
                f"MT5 gateway unavailable at {gw.base_url}: {detail}"
            ) from exc

        attached = False
        session_ref = ""
        already_connected = _gateway_mt5_already_connected(health)

        # Gateway already has a live MT5 session: adopt it and never re-login.
        if already_connected:
            try:
                session_ref = self.adapter.attach(path=path)
                attached = True
                steps.append(
                    {
                        "step": "reuse_session",
                        "ok": True,
                        "detail": (
                            "Reused attached MT5 gateway session "
                            "(skipped broker login)"
                        ),
                        "session_ref": session_ref,
                    }
                )
                logger.info(
                    "weltrade_connect_reused_attached_session",
                    login=login,
                    server=server_name,
                    gateway_health_connected=True,
                )
            except Exception as exc:
                steps.append(
                    {
                        "step": "reuse_session",
                        "ok": False,
                        "detail": str(exc),
                    }
                )
                logger.exception(
                    "weltrade_reuse_attached_session_failed",
                    login=login,
                    server=server_name,
                    error=str(exc),
                )
                raise RuntimeError(
                    "Gateway reports an attached MT5 session, but Railway "
                    f"could not adopt it: {exc}"
                ) from exc

        elif prefer_attach:
            try:
                session_ref = self.adapter.attach(path=path)
                attached = True
                steps.append(
                    {
                        "step": "attach",
                        "ok": True,
                        "detail": "Attached to existing MT5 session",
                        "session_ref": session_ref,
                    }
                )
                logger.info(
                    "weltrade_connect_attached",
                    login=login,
                    server=server_name,
                )
            except Exception as exc:
                steps.append({"step": "attach", "ok": False, "detail": str(exc)})
                logger.exception(
                    "weltrade_attach_unavailable",
                    error=str(exc),
                    login=login,
                    server=server_name,
                )

        if not attached:
            if not password:
                raise RuntimeError(
                    "No active MT5 session to attach and password was empty. "
                    "Log into Weltrade in MetaTrader, or provide password."
                )
            request = MT5LoginRequest(
                login=login,
                password=password,
                server=server_name,
                path=path,
            )
            if not self.adapter.initialize(path=path):
                raise RuntimeError("Gateway initialize failed")
            try:
                session_ref = self.adapter.login(request)
            except Exception as exc:
                logger.exception(
                    "weltrade_login_failed",
                    login=login,
                    server=server_name,
                    error=str(exc),
                    last_upstream=(
                        gw.last_upstream() if hasattr(gw, "last_upstream") else None
                    ),
                )
                raise RuntimeError(
                    f"Weltrade authentication failed: {exc}"
                ) from exc
            steps.append(
                {
                    "step": "connect",
                    "ok": True,
                    "detail": "Authenticated via gateway",
                    "session_ref": session_ref,
                }
            )
            # Password falls out of scope — adapter stores redacted copy for GW.
            del request

        await self.bind_user_session(
            user_id=user_id,
            login=login,
            server=server_name,
            path=path,
            session_ref=session_ref,
        )
        sync = await self.dashboard(user_id=user_id)
        steps.append({"step": "sync", "ok": True, "detail": "Account synchronized"})
        logger.info(
            "weltrade_connect_ok",
            login=login,
            server=server_name,
            mt5_connected=sync["connection"]["mt5_connected"],
        )
        return {
            "ok": True,
            "broker": WELTRADE_BROKER,
            "server": server_name,
            "account_type": account_type,
            "steps": steps,
            "dashboard": sync,
            "account": sync.get("account"),
            "session": {
                "mode": sync["connection"].get("session_mode"),
                "server": sync["connection"].get("server"),
            },
            "status": sync.get("status"),
        }

    async def attach(self, *, user_id: UUID, path: str = "") -> dict[str, Any]:
        session_ref = self.adapter.attach(path=path)
        await self.bind_user_session(
            user_id=user_id, path=path, session_ref=session_ref
        )
        dash = await self.dashboard(user_id=user_id)
        return {"ok": True, "broker": WELTRADE_BROKER, "dashboard": dash}

    async def disconnect(self, *, user_id: UUID) -> dict[str, Any]:
        await self.unbind_user_session(user_id=user_id)
        # Explicit desk disconnect always clears the process terminal session.
        if getattr(self.adapter.client, "is_connected", False) or getattr(
            self.adapter, "_live_session_ref", None
        ):
            self.adapter.shutdown()
        return {
            "ok": True,
            "broker": WELTRADE_BROKER,
            "dashboard": await self.dashboard(user_id=user_id),
        }

    async def reconnect(self, *, user_id: UUID) -> dict[str, Any]:
        # Prefer gateway-side passwordless reconnect / attach.
        request = MT5LoginRequest(login=1, password="", server="Weltrade-MT5")
        live = self.adapter._live_session_ref
        if live and live in self.adapter._sessions:
            prior = self.adapter._sessions[live]
            request = MT5LoginRequest(
                login=prior.login,
                password="",
                server=prior.server or "Weltrade-MT5",
                path=prior.path,
            )
        logger.info("weltrade_reconnect_start", login=request.login)
        session_ref = self.adapter.reconnect(request)
        await self.bind_user_session(
            user_id=user_id,
            login=request.login,
            server=request.server,
            path=request.path,
            session_ref=session_ref,
        )
        return {
            "ok": True,
            "broker": WELTRADE_BROKER,
            "dashboard": await self.dashboard(user_id=user_id),
        }
