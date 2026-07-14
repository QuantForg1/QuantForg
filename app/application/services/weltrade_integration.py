"""Weltrade production orchestration — Railway API → Windows MT5 Gateway.

Does not change Strategy / Portfolio / Execution Intelligence.
Broker passwords are forwarded once to the gateway and never persisted here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

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


@dataclass
class WeltradeIntegrationService:
    """Thin orchestration for the Weltrade-only production connection UX."""

    adapter: MT5Adapter
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
        if gw is not None:
            base_url = gw.base_url
            token_configured = bool(gw.token)
        return {
            "gateway_backed": gw is not None,
            "mt5_gateway_base_url_configured": bool(base_url),
            "mt5_gateway_caller_token_configured": token_configured,
            "execution_enabled": self.adapter.execution_enabled,
        }

    def health(self, *, user_id: UUID) -> dict[str, Any]:
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
        detail = "ok"
        gateway_payload: dict[str, Any] = {}

        if gw is None:
            detail = (
                "Railway is not configured for the Windows gateway. "
                "Set MT5_GATEWAY_BASE_URL and MT5_GATEWAY_CALLER_TOKEN."
            )
            return {
                "ok": False,
                "healthy": False,
                "broker": WELTRADE_BROKER,
                "configuration": cfg,
                "gateway_reachable": False,
                "tunnel_reachable": False,
                "mt5_attached": False,
                "latency_ms": None,
                "version": None,
                "server": None,
                "account": None,
                "session": {"mode": "none"},
                "detail": detail,
            }

        try:
            gateway_payload = gw.gateway_health()
            tunnel_reachable = True
            gateway_reachable = gateway_payload.get("status") == "ok"
            if not gateway_reachable:
                detail = str(gateway_payload.get("detail") or "Gateway unhealthy")
        except Exception as exc:
            detail = f"Gateway unreachable: {exc}"
            logger.warning("weltrade_gateway_health_failed", error=str(exc))

        if gateway_reachable:
            try:
                snap = self.adapter.health()
                latency_ms = snap.latency_ms
                version = snap.version or ""
                server = snap.server or None
                mt5_attached = bool(snap.connected)
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
                logger.warning("weltrade_mt5_probe_failed", error=str(exc))

        healthy = gateway_reachable and (mt5_attached or tunnel_reachable)
        return {
            "ok": tunnel_reachable,
            "healthy": bool(gateway_reachable),
            "broker": WELTRADE_BROKER,
            "configuration": cfg,
            "gateway_reachable": gateway_reachable,
            "tunnel_reachable": tunnel_reachable,
            "mt5_attached": mt5_attached,
            "latency_ms": latency_ms,
            "version": version or None,
            "server": server,
            "account": account,
            "session": {"mode": session_mode},
            "gateway": {
                "status": gateway_payload.get("status"),
                "service": gateway_payload.get("service"),
                "bridge_available": gateway_payload.get("bridge_available"),
                "token_configured": gateway_payload.get("token_configured"),
            },
            "detail": detail if not gateway_reachable or not mt5_attached else "ok",
            # Aliases matching UI copy
            "gateway_online": gateway_reachable,
            "mt5_connected": mt5_attached,
            "weltrade_connected": bool(gateway_reachable and mt5_attached),
            "status": "healthy" if healthy else "degraded",
        }

    def dashboard(self, *, user_id: UUID) -> dict[str, Any]:
        _ = user_id
        gw = self._gateway()
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

    def connect(
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
            steps.append(
                {
                    "step": "gateway_check",
                    "ok": ok,
                    "detail": "Gateway reachable" if ok else "Gateway unhealthy",
                }
            )
            if not ok:
                raise RuntimeError("Gateway health check failed")
        except Exception as exc:
            steps.append({"step": "gateway_check", "ok": False, "detail": str(exc)})
            logger.warning("weltrade_connect_gateway_unavailable", error=str(exc))
            raise RuntimeError(f"Gateway unavailable: {exc}") from exc

        attached = False
        if prefer_attach:
            try:
                self.adapter.attach(path=path)
                attached = True
                steps.append(
                    {
                        "step": "attach",
                        "ok": True,
                        "detail": "Attached to existing MT5 session",
                    }
                )
                logger.info(
                    "weltrade_connect_attached",
                    login=login,
                    server=server_name,
                )
            except Exception as exc:
                steps.append({"step": "attach", "ok": False, "detail": str(exc)})
                logger.info("weltrade_attach_unavailable", error=str(exc))

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
                logger.warning(
                    "weltrade_login_failed",
                    login=login,
                    server=server_name,
                    error=str(exc),
                )
                raise RuntimeError(f"Weltrade authentication failed: {exc}") from exc
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

        sync = self.dashboard(user_id=user_id)
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

    def attach(self, *, user_id: UUID, path: str = "") -> dict[str, Any]:
        self.adapter.attach(path=path)
        dash = self.dashboard(user_id=user_id)
        return {"ok": True, "broker": WELTRADE_BROKER, "dashboard": dash}

    def disconnect(self, *, user_id: UUID) -> dict[str, Any]:
        self.adapter.shutdown()
        return {
            "ok": True,
            "broker": WELTRADE_BROKER,
            "dashboard": self.dashboard(user_id=user_id),
        }

    def reconnect(self, *, user_id: UUID) -> dict[str, Any]:
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
        self.adapter.reconnect(request)
        return {
            "ok": True,
            "broker": WELTRADE_BROKER,
            "dashboard": self.dashboard(user_id=user_id),
        }
