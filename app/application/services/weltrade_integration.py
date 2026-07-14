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
        _ = user_id
        account_type = (account_type or "demo").strip().lower()
        if account_type not in {"demo", "live"}:
            raise ValueError("account_type must be demo or live")
        server_name = (server or "").strip()
        if not server_name or server_name.lower() in {"auto", "auto detect"}:
            server_name = WELTRADE_SERVERS[account_type][0]

        steps: list[dict[str, Any]] = []
        gw = self._gateway()
        if gw is not None:
            try:
                health = gw.gateway_health()
                steps.append(
                    {
                        "step": "gateway_check",
                        "ok": health.get("status") == "ok",
                        "detail": "Gateway reachable",
                    }
                )
            except Exception as exc:
                steps.append({"step": "gateway_check", "ok": False, "detail": str(exc)})
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
            except Exception as exc:
                steps.append({"step": "attach", "ok": False, "detail": str(exc)})

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
            session_ref = self.adapter.login(request)
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
        return {
            "ok": True,
            "broker": WELTRADE_BROKER,
            "server": server_name,
            "account_type": account_type,
            "steps": steps,
            "dashboard": sync,
        }

    def attach(self, *, user_id: UUID, path: str = "") -> dict[str, Any]:
        self.adapter.attach(path=path)
        return {
            "ok": True,
            "broker": WELTRADE_BROKER,
            "dashboard": self.dashboard(user_id=user_id),
        }

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
        self.adapter.reconnect(request)
        return {
            "ok": True,
            "broker": WELTRADE_BROKER,
            "dashboard": self.dashboard(user_id=user_id),
        }
