"""MT5 connectivity bridge — wraps live MT5Adapter, no simulated venue."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.broker_connectivity.matrix import profile_for
from app.domain.broker_connectivity.types import (
    BrokerCapabilityProfile,
    ConnectivityCapability,
    ConnectivityResult,
    ConnectivityStatus,
)
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.domain.market_data.timeframe import Timeframe
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from core.config.settings import get_settings


class MT5ConnectivityAdapter:
    """Connectivity Framework adapter backed by the real MT5 integration."""

    platform = "mt5"
    name = "MetaTrader 5"

    def __init__(self, mt5: MT5Adapter) -> None:
        self._mt5 = mt5
        self._reconnect_events: list[dict[str, Any]] = []
        self._failures: list[dict[str, Any]] = []

    def capability_profile(self) -> BrokerCapabilityProfile:
        profile = profile_for("mt5")
        assert profile is not None
        return profile

    def _ok(
        self,
        capability: ConnectivityCapability,
        data: Any,
        *,
        latency_ms: float | None = None,
        reason: str = "",
    ) -> ConnectivityResult:
        return ConnectivityResult(
            status=ConnectivityStatus.OK,
            capability=capability,
            platform=self.platform,
            data=data,
            reason=reason,
            latency_ms=latency_ms,
        )

    def _unavailable(
        self, capability: ConnectivityCapability, reason: str
    ) -> ConnectivityResult:
        self._failures.append(
            {
                "at": datetime.now(UTC).isoformat(),
                "capability": capability.value,
                "reason": reason,
            }
        )
        self._failures = self._failures[-50:]
        return ConnectivityResult(
            status=ConnectivityStatus.UNAVAILABLE,
            capability=capability,
            platform=self.platform,
            reason=reason,
        )

    def _error(
        self, capability: ConnectivityCapability, exc: Exception
    ) -> ConnectivityResult:
        reason = f"{type(exc).__name__}: {exc}"
        self._failures.append(
            {
                "at": datetime.now(UTC).isoformat(),
                "capability": capability.value,
                "reason": reason,
            }
        )
        self._failures = self._failures[-50:]
        return ConnectivityResult(
            status=ConnectivityStatus.ERROR,
            capability=capability,
            platform=self.platform,
            reason=reason,
        )

    def _connected(self) -> bool:
        ref = getattr(self._mt5, "_live_session_ref", None)
        if not ref:
            return bool(getattr(self._mt5.client, "is_connected", False))
        return self._mt5.is_live_session(ref)

    def connect(self, params: dict[str, Any]) -> ConnectivityResult:
        try:
            if self._connected() and not params.get("force"):
                return self._ok(
                    ConnectivityCapability.CONNECT,
                    {"connected": True, "session_ref": self._mt5._live_session_ref},
                    reason="Already connected via MT5 adapter",
                )
            login = params.get("login")
            password = params.get("password")
            server = params.get("server")
            if not login or not password or not server:
                return self._unavailable(
                    ConnectivityCapability.CONNECT,
                    "Missing login/password/server — use /mt5/connect or supply params",
                )
            path = str(params.get("path") or "")
            self._mt5.initialize(path=path)
            req = MT5LoginRequest(
                login=int(login),
                password=str(password),
                server=str(server),
            )
            t0 = time.perf_counter()
            session_ref = self._mt5.login(req)
            latency = (time.perf_counter() - t0) * 1000.0
            self._reconnect_events.append(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "event": "connect",
                    "session_ref": session_ref,
                }
            )
            return self._ok(
                ConnectivityCapability.CONNECT,
                {"connected": True, "session_ref": session_ref},
                latency_ms=round(latency, 3),
            )
        except Exception as exc:  # surface as structured error
            return self._error(ConnectivityCapability.CONNECT, exc)

    def disconnect(self) -> ConnectivityResult:
        try:
            self._mt5.shutdown()
            return self._ok(
                ConnectivityCapability.DISCONNECT,
                {"connected": False},
                reason="MT5 session shut down",
            )
        except Exception as exc:
            return self._error(ConnectivityCapability.DISCONNECT, exc)

    def health(self) -> ConnectivityResult:
        try:
            if not self._connected():
                return self._unavailable(
                    ConnectivityCapability.HEALTH,
                    "MT5 not connected",
                )
            t0 = time.perf_counter()
            snap = self._mt5.health()
            latency = (time.perf_counter() - t0) * 1000.0
            data = {
                "connected": bool(snap.connected),
                "latency_ms": snap.latency_ms,
                "server": snap.server,
                "login_status": snap.login_status,
                "terminal_build": snap.terminal_build,
                "version": snap.version,
                "last_heartbeat_at": snap.last_heartbeat_at,
            }
            return self._ok(
                ConnectivityCapability.HEALTH, data, latency_ms=round(latency, 3)
            )
        except Exception as exc:
            return self._error(ConnectivityCapability.HEALTH, exc)

    def heartbeat(self) -> ConnectivityResult:
        try:
            if not self._connected():
                return self._unavailable(
                    ConnectivityCapability.HEARTBEAT, "MT5 not connected"
                )
            t0 = time.perf_counter()
            ping_ms = float(self._mt5.ping())
            elapsed = (time.perf_counter() - t0) * 1000.0
            return self._ok(
                ConnectivityCapability.HEARTBEAT,
                {
                    "ping_ms": ping_ms,
                    "at": datetime.now(UTC).isoformat(),
                },
                latency_ms=round(elapsed, 3),
            )
        except Exception as exc:
            return self._error(ConnectivityCapability.HEARTBEAT, exc)

    def balances(self) -> ConnectivityResult:
        try:
            if not self._connected():
                return self._unavailable(
                    ConnectivityCapability.BALANCES, "MT5 not connected"
                )
            snap = self._mt5.account_snapshot()
            return self._ok(
                ConnectivityCapability.BALANCES,
                {
                    "balance": str(snap.balance),
                    "equity": str(snap.equity),
                    "margin": str(snap.margin),
                    "free_margin": str(snap.free_margin),
                    "currency": snap.currency,
                    "leverage": snap.leverage,
                },
            )
        except Exception as exc:
            return self._error(ConnectivityCapability.BALANCES, exc)

    def positions(self) -> ConnectivityResult:
        try:
            if not self._connected():
                return self._unavailable(
                    ConnectivityCapability.POSITIONS, "MT5 not connected"
                )
            rows = [
                {
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "side": p.side,
                    "volume": str(p.volume),
                    "open_price": str(p.open_price),
                    "profit": str(p.profit),
                }
                for p in self._mt5.list_positions()
            ]
            return self._ok(ConnectivityCapability.POSITIONS, {"items": rows})
        except Exception as exc:
            return self._error(ConnectivityCapability.POSITIONS, exc)

    def orders(self) -> ConnectivityResult:
        try:
            if not self._connected():
                return self._unavailable(
                    ConnectivityCapability.ORDERS, "MT5 not connected"
                )
            rows = [
                {
                    "ticket": o.ticket,
                    "symbol": o.symbol,
                    "side": o.side,
                    "order_type": o.order_type,
                    "volume": str(o.volume),
                    "price": str(o.price),
                }
                for o in self._mt5.list_orders()
            ]
            return self._ok(ConnectivityCapability.ORDERS, {"items": rows})
        except Exception as exc:
            return self._error(ConnectivityCapability.ORDERS, exc)

    def history(self, *, limit: int = 100) -> ConnectivityResult:
        try:
            if not self._connected():
                return self._unavailable(
                    ConnectivityCapability.HISTORY, "MT5 not connected"
                )
            deals = self._mt5.history_deals()[:limit]
            orders = self._mt5.history_orders()[:limit]
            return self._ok(
                ConnectivityCapability.HISTORY,
                {
                    "deals": [
                        {
                            "ticket": d.ticket,
                            "symbol": d.symbol,
                            "profit": str(d.profit),
                            "time": d.time.isoformat() if d.time else None,
                        }
                        for d in deals
                    ],
                    "orders": [
                        {
                            "ticket": o.ticket,
                            "symbol": o.symbol,
                            "state": o.state,
                        }
                        for o in orders
                    ],
                },
            )
        except Exception as exc:
            return self._error(ConnectivityCapability.HISTORY, exc)

    def symbols(self) -> ConnectivityResult:
        try:
            if not self._connected():
                return self._unavailable(
                    ConnectivityCapability.SYMBOLS, "MT5 not connected"
                )
            items = [
                {
                    "code": s.code if hasattr(s, "code") else str(s),
                    "description": getattr(s, "description", ""),
                }
                for s in self._mt5.list_symbols()
            ]
            return self._ok(ConnectivityCapability.SYMBOLS, {"items": items})
        except Exception as exc:
            return self._error(ConnectivityCapability.SYMBOLS, exc)

    def quotes(self, symbol: str) -> ConnectivityResult:
        try:
            if not self._connected():
                return self._unavailable(
                    ConnectivityCapability.QUOTES, "MT5 not connected"
                )
            tick = self._mt5.latest_tick(symbol)
            return self._ok(
                ConnectivityCapability.QUOTES,
                {
                    "symbol": tick.symbol,
                    "bid": str(tick.bid),
                    "ask": str(tick.ask),
                    "time": (
                        tick.timestamp.isoformat()
                        if getattr(tick, "timestamp", None)
                        else None
                    ),
                },
            )
        except Exception as exc:
            return self._error(ConnectivityCapability.QUOTES, exc)

    def candles(
        self, symbol: str, *, timeframe: str = "H1", count: int = 100
    ) -> ConnectivityResult:
        try:
            if not self._connected():
                return self._unavailable(
                    ConnectivityCapability.CANDLES, "MT5 not connected"
                )
            tf = Timeframe.parse(timeframe)
            start = datetime.now(UTC) - tf.duration * max(count, 1)
            rates = self._mt5.copy_rates_from(symbol, tf, start, count)
            items = [
                {
                    "time": r.open_time.isoformat(),
                    "open": str(r.open),
                    "high": str(r.high),
                    "low": str(r.low),
                    "close": str(r.close),
                }
                for r in rates
            ]
            return self._ok(
                ConnectivityCapability.CANDLES,
                {"symbol": symbol, "timeframe": timeframe, "items": items},
            )
        except Exception as exc:
            return self._error(ConnectivityCapability.CANDLES, exc)

    def trading(self, intent: dict[str, Any]) -> ConnectivityResult:
        """Does not place orders — reports gate + redirects to execution API."""
        _ = intent
        settings = get_settings()
        enabled = bool(settings.execution_enabled and self._mt5.execution_enabled)
        if not enabled:
            return ConnectivityResult(
                status=ConnectivityStatus.UNAVAILABLE,
                capability=ConnectivityCapability.TRADING,
                platform=self.platform,
                data={
                    "execution_enabled": False,
                    "submit_path": "POST /execution/submit",
                },
                reason=(
                    "Live trading gated by EXECUTION_ENABLED — "
                    "Connectivity Framework never enables it"
                ),
            )
        return self._ok(
            ConnectivityCapability.TRADING,
            {
                "execution_enabled": True,
                "submit_path": "POST /execution/submit",
                "note": "Use Execution Gateway — this framework does not order_send",
            },
            reason="Trading permitted at gateway; use /execution/submit",
        )

    def capabilities(self) -> ConnectivityResult:
        return self._ok(
            ConnectivityCapability.CAPABILITIES,
            self.capability_profile().to_dict(),
        )

    def diagnostics(self) -> dict[str, Any]:
        health = self.health()
        hb = self.heartbeat() if self._connected() else None
        return {
            "platform": self.platform,
            "implemented": True,
            "connected": self._connected(),
            "health": health.to_dict(),
            "heartbeat": hb.to_dict() if hb else None,
            "reconnect_history": list(self._reconnect_events[-20:]),
            "failures": list(self._failures[-20:]),
            "capability_checks": {
                c.value: c in self.capability_profile().capabilities
                for c in ConnectivityCapability
            },
            "latency_ms": health.latency_ms,
        }
