"""Weltrade production orchestration — Railway API → Windows MT5 Gateway.

Does not change Strategy / Portfolio / Execution Intelligence.
Broker passwords are forwarded to the gateway for login; optional AES-encrypted
restore profile may be persisted locally (never plain text).
"""

from __future__ import annotations

import asyncio
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
    _connect_gate: asyncio.Lock | None = field(default=None, init=False)
    _connect_inflight: asyncio.Task[Any] | None = field(default=None, init=False)
    _connect_inflight_key: str | None = field(default=None, init=False)
    _auth_failed: bool = field(default=False, init=False)
    _reconnect_task: asyncio.Task[Any] | None = field(default=None, init=False)

    def _gate(self) -> asyncio.Lock:
        if self._connect_gate is None:
            self._connect_gate = asyncio.Lock()
        return self._connect_gate

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

    async def health(
        self, *, user_id: UUID, role: str | None = None
    ) -> dict[str, Any]:
        """Production health probe for tunnel + gateway + MT5 session."""
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
            gateway_payload = await asyncio.to_thread(gw.gateway_health)
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
                snap = await asyncio.to_thread(self.adapter.health)
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
                    info = await asyncio.to_thread(self.adapter.account_info)
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
            ownership_heal = await self.ensure_user_session_bound(
                user_id=user_id, role=role
            )
        else:
            ownership_heal = {
                "attempted": False,
                "adopted": False,
                "reason": "gateway_or_mt5_unavailable",
            }

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

        gateway_mt5 = gateway_payload.get("mt5")
        mt5_block: dict[str, Any] = gateway_mt5 if isinstance(gateway_mt5, dict) else {}
        # Prefer nested mt5 capabilities; fall back to top-level if present.
        auto_raw = mt5_block.get("mt5_autotrading_enabled")
        if auto_raw is None:
            auto_raw = mt5_block.get("terminal_trade_allowed")
        if auto_raw is None:
            auto_raw = gateway_payload.get("mt5_autotrading_enabled")
        dll_raw = mt5_block.get("dlls_allowed")
        if dll_raw is None:
            dll_raw = mt5_block.get("dll_allowed")
        if dll_raw is None:
            dll_raw = gateway_payload.get("dlls_allowed")
        nested_support = mt5_block.get("capability_support")
        support = (
            nested_support
            if isinstance(nested_support, dict)
            else gateway_payload.get("capability_support")
        )
        if not isinstance(support, dict):
            support = {}

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
            # Terminal capability flags — never invented; null when unknown.
            "mt5_autotrading_enabled": (
                bool(auto_raw) if auto_raw is not None else None
            ),
            "dll_allowed": bool(dll_raw) if dll_raw is not None else None,
            "dll_enabled": bool(dll_raw) if dll_raw is not None else None,
            "dlls_allowed": bool(dll_raw) if dll_raw is not None else None,
            "autotrading_support": str(
                support.get("autotrading")
                or ("SUPPORTED" if auto_raw is not None else "NOT_SUPPORTED")
            ),
            "dll_support": str(
                support.get("dll")
                or ("SUPPORTED" if dll_raw is not None else "NOT_SUPPORTED")
            ),
            "capability_note": mt5_block.get("capability_note")
            or gateway_payload.get("capability_note"),
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
            "ownership_heal": ownership_heal,
            "status": (
                "healthy"
                if gateway_reachable and mt5_attached
                else "degraded" if gateway_reachable else "offline"
            ),
        }

    async def dashboard(
        self, *, user_id: UUID, role: str | None = None
    ) -> dict[str, Any]:
        gw = self._gateway()
        if gw is not None:
            await self.ensure_user_session_bound(user_id=user_id, role=role)
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
                diagnostic = str(upstream.get("diagnostic") or "Gateway Offline")
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
                else "degraded" if gateway_online else "offline"
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

        claimed_login = int(login or 0)
        claimed_server = (server or "").strip()
        live_login = 0
        live_server = ""
        try:
            info = self.adapter.account_info()
            live_login = int(getattr(info, "login", 0) or 0)
            live_server = str(getattr(info, "server", "") or "").strip()
        except Exception:
            if live_ref in getattr(self.adapter, "_sessions", {}):
                stored = self.adapter._sessions.get(live_ref)
                if stored is not None:
                    live_login = int(getattr(stored, "login", 0) or 0)
                    live_server = str(getattr(stored, "server", "") or "").strip()
            if live_login <= 1:
                client = self.adapter.client
                live_login = int(getattr(client, "_login", 0) or 0)

        # Live terminal identity is authoritative when known.
        if live_login > 1 and claimed_login > 1 and live_login != claimed_login:
            logger.warning(
                "weltrade_bind_skipped",
                reason="login_mismatch",
                user_id=str(user_id),
                claimed_login=claimed_login,
                live_login=live_login,
            )
            return None

        resolved_login = live_login if live_login > 1 else claimed_login
        resolved_server = live_server or claimed_server
        if resolved_login <= 1 or not resolved_server:
            logger.warning(
                "weltrade_bind_skipped",
                reason="unresolved_account_identity",
                user_id=str(user_id),
            )
            return None

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
        with contextlib.suppress(Exception):
            from app.application.services.institutional_ite_runtime import (
                get_ite_runtime,
            )

            runtime = get_ite_runtime()
            if runtime is not None:
                runtime.user_id = user_id
            from app.application.services.account_execution_gate import (
                bind_execution_account,
            )

            bind_execution_account(user_id=user_id, login=resolved_login)
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
        from app.application.services.account_execution_gate import (
            unbind_execution_account,
        )

        if self.uow_factory is None:
            unbind_execution_account(user_id=user_id)
            return
        async with self.uow_factory() as uow:
            connection = await uow.connections.get_active_for_user(user_id)
            if connection is None:
                unbind_execution_account(user_id=user_id)
                return
            session_ref = (connection.session_ref or "").strip()
            live = getattr(self.adapter, "_live_session_ref", None)
            if session_ref and live and session_ref == live:
                self.adapter.shutdown()
            connection.mark_disconnected()
            await uow.connections.update(connection)
            await uow.commit()
        unbind_execution_account(user_id=user_id)

    @staticmethod
    def _role_may_adopt_unbound_gateway(role: str | None) -> bool:
        """Owner/admin may re-claim a live gateway after ephemeral profile loss."""
        return str(role or "").strip().lower() in {"owner", "admin"}

    async def _active_foreign_owner_of_login(
        self, *, login: int, user_id: UUID
    ) -> UUID | None:
        """Return another user_id that currently owns ``login`` live, if any."""
        if self.uow_factory is None or login <= 1:
            return None
        async with self.uow_factory() as uow:
            finder = getattr(uow.connections, "get_connected_by_login", None)
            if callable(finder):
                row = await finder(login)
                if row is not None and row.user_id != user_id and row.connected:
                    return row.user_id
                return None
            # Memory / minimal repos: scan list_for_user is insufficient — walk items.
            items = getattr(uow.connections, "items", None)
            if isinstance(items, dict):
                for conn in items.values():
                    if (
                        int(getattr(conn, "login", 0) or 0) == login
                        and bool(getattr(conn, "connected", False))
                        and getattr(conn, "user_id", None) != user_id
                    ):
                        return conn.user_id
        return None

    def _sync_adapter_live_handle(self, live_ref: str) -> None:
        """Keep adapter session cache aligned with gateway client after adopt."""
        ref = (live_ref or "").strip()
        if not ref:
            return
        self.adapter._live_session_ref = ref
        client = self.adapter.client
        login = int(getattr(client, "_login", 0) or 0)
        server = str(getattr(client, "_server", "") or "")
        sessions = getattr(self.adapter, "_sessions", None)
        if not isinstance(sessions, dict):
            return
        if ref in sessions and login > 1:
            return
        sessions[ref] = MT5LoginRequest(
            login=login if login > 1 else 0,
            password="",
            server=server or "attached",
            path="",
        )

    def _ensure_process_gateway_handle(self) -> str:
        """Adopt the live Windows session into this Railway worker process.

        Research catalogue uses ``adopt_existing_session``; ownership heal must
        use the same path. ``health()`` can set ``is_connected`` without minting
        a process ``session_token`` — without this, owner adopt never binds.
        """
        client = self.adapter.client
        with contextlib.suppress(Exception):
            self.adapter.health()

        live_ref = (getattr(self.adapter, "_live_session_ref", None) or "").strip()
        if not live_ref:
            live_ref = (getattr(client, "session_token", "") or "").strip()
        if live_ref and getattr(client, "is_connected", False):
            self._sync_adapter_live_handle(live_ref)
            return live_ref

        adopt = getattr(client, "adopt_existing_session", None)
        if callable(adopt):
            try:
                if bool(adopt()):
                    live_ref = (getattr(client, "session_token", "") or "").strip()
                    if live_ref:
                        self._sync_adapter_live_handle(live_ref)
                        return live_ref
            except Exception as exc:
                logger.warning(
                    "weltrade_ensure_adopt_failed",
                    error=str(exc),
                )

        try:
            live_ref = ((self.adapter.attach(path="") or "")).strip()
        except Exception as exc:
            logger.warning(
                "weltrade_ensure_attach_failed",
                error=str(exc),
            )
            return ""
        if live_ref:
            self._sync_adapter_live_handle(live_ref)
        return live_ref

    async def _adopt_live_gateway_for_privileged_user(
        self, *, user_id: UUID, role: str | None
    ) -> dict[str, Any]:
        """Bind owner/admin to the live gateway when DB ownership was lost.

        Railway ephemeral disks drop ``broker_runtime_profile.json`` on redeploy
        while the Windows MT5 session remains attached. Research/catalogue can
        still see LIVE_BROKER, but /trading/session and /portfolio report
        Disconnected. Privileged adopt restores ownership without a password
        when the gateway already holds the session — never for unbound traders,
        never when another user already owns that login.

        Returns a non-secret diagnostic dict for /weltrade/health.
        """
        diag: dict[str, Any] = {
            "attempted": True,
            "adopted": False,
            "role_allowed": self._role_may_adopt_unbound_gateway(role),
            "reason": None,
            "has_live_ref": False,
            "client_connected": False,
            "live_login_known": False,
        }
        if not diag["role_allowed"]:
            diag["reason"] = "role_not_privileged"
            return diag
        if self.uow_factory is None:
            diag["reason"] = "uow_factory_missing"
            return diag
        live_ref = self._ensure_process_gateway_handle()
        client = self.adapter.client
        diag["has_live_ref"] = bool(live_ref)
        diag["client_connected"] = bool(getattr(client, "is_connected", False))
        if not live_ref or not diag["client_connected"]:
            diag["reason"] = "gateway_handle_unavailable"
            return diag
        live_login = 0
        live_server = ""
        try:
            info = self.adapter.account_info()
            live_login = int(getattr(info, "login", 0) or 0)
            live_server = str(getattr(info, "server", "") or "").strip()
        except Exception:
            live_login = int(getattr(client, "_login", 0) or 0)
            live_server = str(getattr(client, "_server", "") or "").strip()
        diag["live_login_known"] = live_login > 1 and bool(live_server)
        if live_login <= 1 or not live_server:
            diag["reason"] = "unresolved_live_identity"
            return diag
        foreign = await self._active_foreign_owner_of_login(
            login=live_login, user_id=user_id
        )
        if foreign is not None:
            diag["reason"] = "login_owned_by_other_user"
            logger.info(
                "weltrade_ensure_skipped",
                reason="login_owned_by_other_user",
                user_id=str(user_id),
                other_user_id=str(foreign),
                live_login=live_login,
            )
            return diag
        bound = await self.bind_user_session(
            user_id=user_id,
            login=live_login,
            server=live_server,
            path="",
            session_ref=live_ref,
        )
        if not bound:
            diag["reason"] = "bind_user_session_failed"
            return diag
        self._persist_broker_runtime_profile(
            login=live_login,
            server=live_server,
            path="",
            password="",
            user_id=user_id,
        )
        diag["adopted"] = True
        diag["reason"] = "ok"
        logger.info(
            "weltrade_owner_adopted_live_gateway",
            user_id=str(user_id),
            login=live_login,
            server=live_server,
            role=str(role or ""),
        )
        return diag

    async def ensure_user_session_bound(
        self, *, user_id: UUID, role: str | None = None
    ) -> dict[str, Any]:
        """Heal owned session after redeploy — never steal another user's terminal.

        After a Railway redeploy the Windows terminal can still be logged in while
        this process has no ``_live_session_ref``. Probe/attach first, then re-bind
        ONLY when the calling user already owns the live login.

        Owner/admin may also adopt when DB ownership + ephemeral profile were
        lost but the gateway session is still attached (see
        ``_adopt_live_gateway_for_privileged_user``).

        Returns a non-secret diagnostic dict.
        """
        diag: dict[str, Any] = {
            "attempted": True,
            "adopted": False,
            "reason": None,
            "had_existing": False,
        }
        if self.uow_factory is None:
            diag["reason"] = "uow_factory_missing"
            return diag

        live_ref = self._ensure_process_gateway_handle()
        if not live_ref:
            diag["reason"] = "gateway_handle_unavailable"
            return diag
        client = self.adapter.client
        if not getattr(client, "is_connected", False):
            diag["reason"] = "client_not_connected"
            return diag

        async with self.uow_factory() as uow:
            existing = await uow.connections.get_active_for_user(user_id)
        if existing is None:
            adopt_diag = await self._adopt_live_gateway_for_privileged_user(
                user_id=user_id, role=role
            )
            diag.update(adopt_diag)
            if not adopt_diag.get("adopted"):
                # Health/dashboard must not bind unbound traders to the shared terminal.
                logger.info(
                    "weltrade_ensure_skipped",
                    reason=str(adopt_diag.get("reason") or "no_owned_connection"),
                    user_id=str(user_id),
                )
                return diag
            async with self.uow_factory() as uow:
                existing = await uow.connections.get_active_for_user(user_id)
            if existing is None:
                diag["reason"] = "adopt_persisted_but_unreadable"
                diag["adopted"] = False
                return diag
            diag["reason"] = "ok"
            return diag

        diag["had_existing"] = True
        live_login = 0
        live_server = ""
        try:
            info = self.adapter.account_info()
            live_login = int(getattr(info, "login", 0) or 0)
            live_server = str(getattr(info, "server", "") or "").strip()
        except Exception:
            live_login = int(getattr(client, "_login", 0) or 0)
        owned_login = int(existing.login or 0)
        if live_login > 1 and owned_login > 1 and live_login != owned_login:
            diag["reason"] = "login_mismatch"
            logger.warning(
                "weltrade_ensure_skipped",
                reason="login_mismatch",
                user_id=str(user_id),
                owned_login=owned_login,
                live_login=live_login,
            )
            return diag

        if (
            existing.connected
            and (existing.session_ref or "").strip() == live_ref
            and self.adapter.is_live_session(live_ref)
            and (live_login <= 1 or live_login == owned_login)
        ):
            diag["adopted"] = True
            diag["reason"] = "already_bound"
            return diag

        bound = await self.bind_user_session(
            user_id=user_id,
            login=owned_login if owned_login > 1 else None,
            server=live_server or str(existing.server or ""),
            path=str(existing.terminal_path or ""),
            session_ref=live_ref,
        )
        diag["adopted"] = bool(bound)
        diag["reason"] = "ok" if bound else "bind_user_session_failed"
        return diag

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

        # Idempotent: concurrent Connect clicks share one in-flight attempt.
        key = f"{int(login)}:{server_name}:{account_type}"
        task: asyncio.Task[Any]
        async with self._gate():
            if (
                self._connect_inflight is not None
                and not self._connect_inflight.done()
                and self._connect_inflight_key == key
            ):
                logger.info(
                    "broker_connection_deduped",
                    login=login,
                    server=server_name,
                    correlation_id=key,
                )
                task = self._connect_inflight
            else:
                task = asyncio.create_task(
                    self._connect_unlocked(
                        user_id=user_id,
                        login=login,
                        password=password,
                        server_name=server_name,
                        account_type=account_type,
                        prefer_attach=prefer_attach,
                        path=path,
                        correlation_id=key,
                    ),
                    name=f"weltrade-connect-{login}",
                )
                self._connect_inflight = task
                self._connect_inflight_key = key
        try:
            return await task
        finally:
            async with self._gate():
                if self._connect_inflight is task and task.done():
                    self._connect_inflight = None
                    self._connect_inflight_key = None

    async def _connect_unlocked(
        self,
        *,
        user_id: UUID,
        login: int,
        password: str,
        server_name: str,
        account_type: str,
        prefer_attach: bool,
        path: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        t0 = datetime.now(UTC)
        logger.info(
            "broker_connection_started",
            login=login,
            server=server_name,
            account_type=account_type,
            prefer_attach=prefer_attach,
            password_provided=bool(password),
            gateway_backed=self._gateway() is not None,
            correlation_id=correlation_id,
            state="CONNECTING",
        )

        steps: list[dict[str, Any]] = []
        gw = self._gateway()
        if gw is None:
            logger.warning(
                "gateway_unavailable",
                reason="gateway_not_configured",
                correlation_id=correlation_id,
                state="GATEWAY_UNAVAILABLE",
            )
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
                "gateway_unavailable",
                error=detail,
                base_url=gw.base_url,
                last_upstream=upstream,
                correlation_id=correlation_id,
                state="GATEWAY_UNAVAILABLE",
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
                    correlation_id=correlation_id,
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
                    correlation_id=correlation_id,
                )
                detail = str(exc)
                if "Invalid Gateway Token" in detail or "HTTP 401" in detail:
                    raise RuntimeError(
                        "Gateway MT5 session is attached, but Railway auth to the "
                        "gateway failed (HTTP 401 Invalid Gateway Token). "
                        "Set MT5_GATEWAY_CALLER_TOKEN on Railway to the same value "
                        "as Windows MT5_GATEWAY_TOKEN, then redeploy. "
                        f"Upstream: {detail}"
                    ) from exc
                raise RuntimeError(
                    "Gateway reports an attached MT5 session, but Railway "
                    f"could not adopt it: {detail}"
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
                    correlation_id=correlation_id,
                )
            except Exception as exc:
                steps.append({"step": "attach", "ok": False, "detail": str(exc)})
                logger.exception(
                    "weltrade_attach_unavailable",
                    error=str(exc),
                    login=login,
                    server=server_name,
                    correlation_id=correlation_id,
                )

        if attached:
            live_login = 0
            live_server = ""
            try:
                info = self.adapter.account_info()
                live_login = int(getattr(info, "login", 0) or 0)
                live_server = str(getattr(info, "server", "") or "").strip()
            except Exception:
                live_login = int(getattr(self.adapter.client, "_login", 0) or 0)
            if live_login > 1 and live_login != int(login):
                if password:
                    logger.info(
                        "weltrade_attach_login_mismatch_forcing_auth",
                        claimed_login=login,
                        live_login=live_login,
                        correlation_id=correlation_id,
                    )
                    steps.append(
                        {
                            "step": "reuse_session",
                            "ok": False,
                            "detail": (
                                "Attached session belongs to a different account; "
                                "authenticating requested login"
                            ),
                        }
                    )
                    with contextlib.suppress(Exception):
                        self.adapter.shutdown()
                    attached = False
                    session_ref = ""
                else:
                    raise RuntimeError(
                        "ACCOUNT_SESSION_MISMATCH: The gateway MT5 session belongs "
                        "to a different account. Disconnect it first, or provide "
                        "your password to switch to your own login."
                    )
            elif live_login > 1:
                if live_server:
                    server_name = live_server
                steps.append(
                    {
                        "step": "verify_live_login",
                        "ok": True,
                        "detail": (
                            f"Live login matches requested account ({live_login})"
                        ),
                    }
                )

        if not attached:
            if not password:
                raise RuntimeError(
                    "No active MT5 session to attach and password was empty. "
                    "Log into Weltrade in MetaTrader, or provide password."
                )
            logger.info(
                "broker_connection_validating",
                login=login,
                server=server_name,
                correlation_id=correlation_id,
                state="VALIDATING",
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
                self._auth_failed = True
                logger.exception(
                    "broker_auth_failed",
                    login=login,
                    server=server_name,
                    error=str(exc),
                    last_upstream=(
                        gw.last_upstream() if hasattr(gw, "last_upstream") else None
                    ),
                    correlation_id=correlation_id,
                    state="AUTH_FAILED",
                )
                raise RuntimeError(f"Weltrade authentication failed: {exc}") from exc
            self._auth_failed = False
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

        bound = await self.bind_user_session(
            user_id=user_id,
            login=login,
            server=server_name,
            path=path,
            session_ref=session_ref,
        )
        if not bound:
            raise RuntimeError(
                "ACCOUNT_SESSION_MISMATCH: Could not bind your owned broker session "
                "to the live MT5 terminal. Disconnect and verify with your own login."
            )
        self._persist_broker_runtime_profile(
            login=login,
            server=server_name,
            path=path,
            password=password,
            user_id=user_id,
        )
        sync = await self.dashboard(user_id=user_id)
        steps.append({"step": "sync", "ok": True, "detail": "Account synchronized"})
        latency_ms = round((datetime.now(UTC) - t0).total_seconds() * 1000.0, 1)
        logger.info(
            "broker_connected",
            login=login,
            server=server_name,
            mt5_connected=sync["connection"]["mt5_connected"],
            correlation_id=correlation_id,
            state="CONNECTED",
            latency_ms=latency_ms,
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
            "state": "CONNECTED",
        }

    def _persist_broker_runtime_profile(
        self,
        *,
        login: int,
        server: str,
        path: str = "",
        password: str = "",
        user_id: UUID | None = None,
    ) -> None:
        """Persist broker/server/login/terminal_path; encrypt password if present."""
        try:
            from app.domain.institutional_trading.ai_scalping import (
                broker_profile_store as _bps,
            )
            from core.config.settings import get_settings

            secret: str | None = None
            if password:
                secret = get_settings().secret_key.get_secret_value()
            _bps.get_broker_profile_store().save(
                broker=WELTRADE_BROKER,
                server=server,
                login=int(login),
                terminal_path=path or "",
                password_plaintext=password or None,
                secret_key=secret,
                user_id=str(user_id) if user_id else None,
            )
        except Exception:
            logger.exception("broker_runtime_profile_persist_failed")

    def load_persisted_broker_profile(self) -> dict[str, Any] | None:
        """Public restore payload (no ciphertext)."""
        try:
            from app.domain.institutional_trading.ai_scalping import (
                broker_profile_store as _bps,
            )

            profile = _bps.get_broker_profile_store().load()
            return profile.to_public_dict() if profile else None
        except Exception:
            logger.exception("broker_runtime_profile_public_load_failed")
            return None

    async def restore_from_persisted_profile(
        self, *, user_id: UUID, account_type: str = "demo"
    ) -> dict[str, Any] | None:
        """Auto-restore broker session from encrypted profile after restart."""
        try:
            from app.domain.institutional_trading.ai_scalping import (
                broker_profile_store as _bps,
            )
            from core.config.settings import get_settings

            store = _bps.get_broker_profile_store()
            profile = store.load()
            if profile is None or profile.login <= 0:
                return None
            if self._auth_failed:
                logger.warning(
                    "broker_auth_failed",
                    reason="skip_restore_after_auth_failure",
                    login=profile.login,
                    server=profile.server,
                    state="AUTH_FAILED",
                )
                return None
            password = ""
            if profile.password_ciphertext:
                secret = get_settings().secret_key.get_secret_value()
                password = store.decrypt_password(profile, secret_key=secret) or ""
            return await self.connect(
                user_id=user_id,
                login=profile.login,
                password=password,
                server=profile.server,
                account_type=account_type,
                prefer_attach=True,
                path=profile.terminal_path,
            )
        except Exception:
            logger.exception("broker_runtime_profile_restore_failed")
            return None

    async def auto_restore_on_startup(self) -> dict[str, Any] | None:
        """Backend-owned reconnect after Railway worker/process restart.

        Does not require a browser. Uses encrypted profile + attach-first.
        """
        try:
            from app.domain.institutional_trading.ai_scalping import (
                broker_profile_store as _bps,
            )

            profile = _bps.get_broker_profile_store().load()
            if profile is None or profile.login <= 0:
                logger.info(
                    "broker_connection_started",
                    reason="no_persisted_profile",
                    state="NOT_CONFIGURED",
                )
                return None
            if self._auth_failed:
                return None

            user_id: UUID | None = None
            if profile.user_id:
                with contextlib.suppress(Exception):
                    user_id = UUID(str(profile.user_id))

            logger.info(
                "broker_reconnect_started",
                login=profile.login,
                server=profile.server,
                state="RECONNECTING",
                has_user_id=bool(user_id),
            )

            if user_id is not None:
                result = await self.restore_from_persisted_profile(user_id=user_id)
                if result is not None:
                    logger.info(
                        "broker_reconnected",
                        login=profile.login,
                        server=profile.server,
                        state="CONNECTED",
                    )
                    self.schedule_bounded_reconnect_watch()
                return result

            # No stored user — heal gateway session only; bind on next auth hit.
            gw = self._gateway()
            if gw is None:
                logger.warning(
                    "gateway_unavailable",
                    reason="startup_restore_no_gateway",
                    state="GATEWAY_UNAVAILABLE",
                )
                return None
            try:
                health = gw.gateway_health()
                if _gateway_mt5_already_connected(health):
                    self.adapter.attach(path=profile.terminal_path or "")
                    logger.info(
                        "broker_reconnected",
                        login=profile.login,
                        server=profile.server,
                        state="CONNECTED",
                        mode="attach_only",
                    )
                    self.schedule_bounded_reconnect_watch()
                    return {
                        "ok": True,
                        "broker": WELTRADE_BROKER,
                        "server": profile.server,
                        "state": "CONNECTED",
                        "mode": "attach_only",
                    }
            except Exception as exc:
                logger.warning(
                    "broker_disconnected",
                    reason=str(exc),
                    state="DISCONNECTED",
                )
            # Prefer encrypted login when gateway has no session yet
            from core.config.settings import get_settings

            store = _bps.get_broker_profile_store()
            password = ""
            if profile.password_ciphertext:
                secret = get_settings().secret_key.get_secret_value()
                password = store.decrypt_password(profile, secret_key=secret) or ""
            if not password:
                return None
            request = MT5LoginRequest(
                login=profile.login,
                password=password,
                server=profile.server,
                path=profile.terminal_path or "",
            )
            if not self.adapter.initialize(path=profile.terminal_path or ""):
                return None
            try:
                self.adapter.login(request)
            except Exception as exc:
                self._auth_failed = True
                logger.exception(
                    "broker_auth_failed",
                    login=profile.login,
                    error=str(exc),
                    state="AUTH_FAILED",
                )
                return None
            finally:
                del request
            logger.info(
                "broker_reconnected",
                login=profile.login,
                server=profile.server,
                state="CONNECTED",
                mode="login_without_user_bind",
            )
            self.schedule_bounded_reconnect_watch()
            return {
                "ok": True,
                "broker": WELTRADE_BROKER,
                "server": profile.server,
                "state": "CONNECTED",
                "mode": "login_without_user_bind",
            }
        except Exception:
            logger.exception(
                "broker_disconnected",
                reason="startup_restore_failed",
                state="DISCONNECTED",
            )
            return None

    def schedule_bounded_reconnect_watch(self) -> None:
        """Bounded exponential backoff if gateway/MT5 drops after restore."""
        import os

        if os.environ.get("QF_BROKER_RECONNECT_WATCH", "true").lower() in {
            "0",
            "false",
            "no",
            "off",
        }:
            return
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        if self._auth_failed:
            return

        async def _watch() -> None:
            delays = (2.0, 4.0, 8.0, 16.0, 32.0, 60.0)
            failures = 0
            while failures < len(delays):
                await asyncio.sleep(delays[failures])
                if self._auth_failed:
                    logger.warning(
                        "broker_auth_failed",
                        reason="reconnect_watch_halted",
                        state="AUTH_FAILED",
                    )
                    return
                gw = self._gateway()
                if gw is None:
                    logger.warning(
                        "gateway_unavailable",
                        reason="reconnect_watch",
                        state="GATEWAY_UNAVAILABLE",
                    )
                    failures += 1
                    continue
                try:
                    health = gw.gateway_health()
                    if _gateway_mt5_already_connected(health):
                        if failures:
                            logger.info(
                                "gateway_recovered",
                                state="CONNECTED",
                            )
                        failures = 0
                        # Keep watching lightly after recovery
                        await asyncio.sleep(30.0)
                        continue
                except Exception as exc:
                    logger.warning(
                        "gateway_unavailable",
                        error=str(exc),
                        state="GATEWAY_UNAVAILABLE",
                    )
                    failures += 1
                    continue
                # MT5 dropped — attempt restore once per backoff step
                logger.info(
                    "broker_reconnect_started",
                    attempt=failures + 1,
                    state="RECONNECTING",
                )
                restored = await self.auto_restore_on_startup()
                if restored is not None:
                    logger.info("broker_reconnected", state="CONNECTED")
                    failures = 0
                    await asyncio.sleep(30.0)
                else:
                    failures += 1
            logger.warning(
                "broker_disconnected",
                reason="reconnect_backoff_exhausted",
                state="DISCONNECTED",
            )

        self._reconnect_task = asyncio.create_task(
            _watch(), name="weltrade-reconnect-watch"
        )

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
        logger.info(
            "broker_disconnected",
            state="DISCONNECTED",
            reason="user_disconnect",
        )
        return {
            "ok": True,
            "broker": WELTRADE_BROKER,
            "dashboard": await self.dashboard(user_id=user_id),
        }

    async def reconnect(self, *, user_id: UUID) -> dict[str, Any]:
        # Prefer gateway-side passwordless reconnect / attach from a real session.
        # Never fall through to a synthetic login=1 credential.
        logger.info(
            "broker_reconnect_started",
            user_id=str(user_id),
            state="RECONNECTING",
        )
        live = self.adapter._live_session_ref
        request: MT5LoginRequest | None = None
        if live and live in self.adapter._sessions:
            prior = self.adapter._sessions[live]
            if int(prior.login or 0) > 1:
                request = MT5LoginRequest(
                    login=prior.login,
                    password="",
                    server=prior.server or "Weltrade-MT5",
                    path=prior.path,
                )
        if request is None:
            # No trusted in-process session — encrypted restore only
            restored = await self.restore_from_persisted_profile(user_id=user_id)
            if restored is not None:
                restored["restored_from_profile"] = True
                logger.info("broker_reconnected", state="CONNECTED")
                return restored
            raise RuntimeError(
                "Weltrade reconnect refused: no live session and no persisted "
                "broker profile (refusing login=1 fallback)"
            )
        logger.info("weltrade_reconnect_start", login=request.login)
        try:
            session_ref = self.adapter.reconnect(request)
        except Exception:
            restored = await self.restore_from_persisted_profile(user_id=user_id)
            if restored is not None:
                restored["restored_from_profile"] = True
                logger.info("broker_reconnected", state="CONNECTED")
                return restored
            raise
        await self.bind_user_session(
            user_id=user_id,
            login=request.login,
            server=request.server,
            path=request.path,
            session_ref=session_ref,
        )
        logger.info("broker_reconnected", login=request.login, state="CONNECTED")
        return {
            "ok": True,
            "broker": WELTRADE_BROKER,
            "dashboard": await self.dashboard(user_id=user_id),
        }
