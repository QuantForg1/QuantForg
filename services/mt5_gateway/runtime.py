"""MT5 Gateway runtime — terminal management, heartbeat, reconnect.

Broker credentials are held only in process memory on the Windows host.
They are never written to Railway env, logs, or API responses.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from services.mt5_gateway.settings import MT5GatewaySettings, get_gateway_settings

logger = logging.getLogger("quantforg.mt5_gateway")

_TIMEFRAME_MAP: dict[str, int] = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 16385,
    "H4": 16388,
    "D1": 16408,
    "W1": 32769,
    "MN1": 49153,
}

SessionMode = Literal["none", "connected", "attached"]


@dataclass
class SessionCredentials:
    """In-memory only — never serialize to disk or Railway."""

    login: int
    password: str
    server: str
    path: str = ""
    mode: SessionMode = "connected"


@dataclass
class GatewayDiagnostics:
    last_heartbeat_at: str | None = None
    last_heartbeat_ms: float | None = None
    reconnect_attempts: int = 0
    reconnect_events: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    connected: bool = False
    server: str = ""
    login: int | None = None
    session_mode: SessionMode = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "session_mode": self.session_mode,
            "server": self.server or None,
            "login": self.login,
            "last_heartbeat_at": self.last_heartbeat_at,
            "last_heartbeat_ms": self.last_heartbeat_ms,
            "reconnect_attempts": self.reconnect_attempts,
            "reconnect_events": list(self.reconnect_events[-20:]),
            "failures": list(self.failures[-20:]),
        }


class LiveMT5Bridge:
    """Thin wrapper over the MetaTrader5 package (Windows only)."""

    def __init__(self) -> None:
        self._mt5: Any | None = None
        self._import_error: str | None = None
        try:
            import MetaTrader5 as mt5

            self._mt5 = mt5
        except Exception as exc:
            self._import_error = f"{type(exc).__name__}: {exc}"

    @property
    def available(self) -> bool:
        return self._mt5 is not None

    def require(self) -> Any:
        if self._mt5 is None:
            raise RuntimeError(
                "MetaTrader5 package unavailable. "
                f"Install on Windows host. ({self._import_error or 'no detail'})"
            )
        return self._mt5

    def initialize(self, path: str = "") -> bool:
        mt5 = self.require()
        if path:
            return bool(mt5.initialize(path=path))
        return bool(mt5.initialize())

    def login(self, login: int, password: str, server: str) -> bool:
        mt5 = self.require()
        return bool(mt5.login(login=login, password=password, server=server))

    def shutdown(self) -> None:
        if self._mt5 is not None:
            self._mt5.shutdown()

    def terminal_info(self) -> Any:
        return self.require().terminal_info()

    def account_info(self) -> Any:
        return self.require().account_info()

    def version(self) -> tuple[int, int, int]:
        raw = self.require().version()
        if not raw:
            return (0, 0, 0)
        return int(raw[0]), int(raw[1]), int(raw[2])

    def last_error(self) -> Any:
        return self.require().last_error()

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        mt5 = self.require()
        select = getattr(mt5, "symbol_select", None)
        if select is None:
            return True
        return bool(select(symbol, enable))

    def symbol_info_tick(self, symbol: str) -> Any:
        return self.require().symbol_info_tick(symbol)

    def symbols_get(self) -> Any:
        return self.require().symbols_get()

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> Any:
        return self.require().copy_rates_from_pos(
            symbol, timeframe, start_pos, count
        )

    def positions_get(self) -> Any:
        return self.require().positions_get()

    def orders_get(self) -> Any:
        return self.require().orders_get()

    def history_orders_get(self, date_from: datetime, date_to: datetime) -> Any:
        return self.require().history_orders_get(date_from, date_to)

    def history_deals_get(self, date_from: datetime, date_to: datetime) -> Any:
        return self.require().history_deals_get(date_from, date_to)


class MT5GatewayRuntime:
    """Owns the live terminal session + heartbeat / auto-reconnect loop."""

    def __init__(
        self,
        *,
        settings: MT5GatewaySettings | None = None,
        bridge: LiveMT5Bridge | None = None,
    ) -> None:
        self.settings = settings or get_gateway_settings()
        self.bridge = bridge or LiveMT5Bridge()
        self._creds: SessionCredentials | None = None
        self._lock = threading.RLock()
        self.diagnostics = GatewayDiagnostics()
        self._stop = threading.Event()
        self._hb_thread: threading.Thread | None = None

    def start_background(self) -> None:
        if self._hb_thread and self._hb_thread.is_alive():
            return
        self._stop.clear()
        self._hb_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="mt5-gateway-heartbeat",
            daemon=True,
        )
        self._hb_thread.start()

    def stop_background(self) -> None:
        self._stop.set()
        if self._hb_thread and self._hb_thread.is_alive():
            self._hb_thread.join(timeout=2.0)

    def _record_failure(self, reason: str) -> None:
        self.diagnostics.failures.append(
            {"at": datetime.now(UTC).isoformat(), "reason": reason}
        )
        self.diagnostics.failures = self.diagnostics.failures[-50:]

    def _mark_session(
        self,
        *,
        login: int,
        server: str,
        path: str,
        password: str,
        mode: SessionMode,
    ) -> None:
        self._creds = SessionCredentials(
            login=login,
            password=password,
            server=server,
            path=path,
            mode=mode,
        )
        self.diagnostics.connected = True
        self.diagnostics.server = server
        self.diagnostics.login = login
        self.diagnostics.session_mode = mode
        self.diagnostics.reconnect_attempts = 0

    def connect(
        self, *, login: int, password: str, server: str, path: str = ""
    ) -> dict[str, Any]:
        with self._lock:
            term_path = path or self.settings.mt5_terminal_path
            if not self.bridge.initialize(term_path):
                err = (
                    self.bridge.last_error()
                    if self.bridge.available
                    else self.bridge._import_error
                )
                msg = f"MT5 initialize failed: {err}"
                self._record_failure(msg)
                raise RuntimeError(msg)
            if not self.bridge.login(login, password, server):
                err = self.bridge.last_error()
                msg = f"MT5 login failed: {err}"
                self._record_failure(msg)
                self.bridge.shutdown()
                raise RuntimeError(msg)
            # Credentials stay in memory for reconnect only — never returned.
            self._mark_session(
                login=login,
                server=server,
                path=term_path,
                password=password,
                mode="connected",
            )
            return {
                "connected": True,
                "session_mode": "connected",
                "server": server,
                "login": login,
                "note": (
                    "Credentials retained in gateway memory for reconnect only. "
                    "Not stored in Railway."
                ),
            }

    def attach(self, *, path: str = "") -> dict[str, Any]:
        """Adopt an already logged-in MT5 terminal without collecting a password.

        Requires the Windows MetaTrader 5 terminal session to already be
        authenticated. Reconnect without a stored password reuses initialize()
        + account_info(); full re-login needs POST /session/connect.
        """
        with self._lock:
            term_path = path or self.settings.mt5_terminal_path
            if not self.bridge.initialize(term_path):
                err = (
                    self.bridge.last_error()
                    if self.bridge.available
                    else self.bridge._import_error
                )
                msg = f"MT5 initialize failed: {err}"
                self._record_failure(msg)
                raise RuntimeError(msg)
            info = self.bridge.account_info()
            if info is None:
                msg = (
                    "MT5 terminal has no active account session. "
                    "Log in via the MetaTrader UI first, or use "
                    "POST /session/connect with login/password/server."
                )
                self._record_failure(msg)
                self.bridge.shutdown()
                raise RuntimeError(msg)
            login = int(info.login)
            server = str(getattr(info, "server", "") or "")
            self._mark_session(
                login=login,
                server=server,
                path=term_path,
                password="",
                mode="attached",
            )
            return {
                "connected": True,
                "session_mode": "attached",
                "server": server or None,
                "login": login,
                "currency": str(getattr(info, "currency", "")),
                "note": (
                    "Attached to existing MT5 terminal session. "
                    "Broker password was not collected and is not stored. "
                    "Password-based reconnect requires POST /session/connect."
                ),
            }

    def disconnect(self) -> dict[str, Any]:
        with self._lock:
            self._creds = None
            try:
                self.bridge.shutdown()
            except Exception as exc:
                self._record_failure(f"shutdown: {exc}")
            self.diagnostics.connected = False
            self.diagnostics.server = ""
            self.diagnostics.login = None
            self.diagnostics.session_mode = "none"
            return {"connected": False, "session_mode": "none"}

    def status(self) -> dict[str, Any]:
        with self._lock:
            health = self.health()
            return {
                "connected": self.diagnostics.connected,
                "session_mode": self.diagnostics.session_mode,
                "server": self.diagnostics.server or None,
                "login": self.diagnostics.login,
                "bridge_available": self.bridge.available,
                "health": health,
            }

    def health(self) -> dict[str, Any]:
        connected = False
        latency_ms: float | None = None
        terminal_build: int | None = None
        server = self.diagnostics.server
        login_status = "disconnected"
        version = ""
        try:
            if self.bridge.available and self.diagnostics.connected:
                t0 = time.perf_counter()
                info = self.bridge.account_info()
                latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
                connected = info is not None
                login_status = "ok" if connected else "error"
                term = self.bridge.terminal_info()
                if term is not None:
                    terminal_build = int(getattr(term, "build", 0) or 0)
                ver = self.bridge.version()
                version = f"{ver[0]}.{ver[1]}.{ver[2]}"
                if info is not None:
                    server = str(getattr(info, "server", server) or server)
        except Exception as exc:
            login_status = f"error:{type(exc).__name__}"
            self._record_failure(str(exc))
            connected = False
        return {
            "connected": connected,
            "session_mode": self.diagnostics.session_mode,
            "latency_ms": latency_ms,
            "terminal_build": terminal_build,
            "server": server or None,
            "login_status": login_status,
            "last_heartbeat_at": self.diagnostics.last_heartbeat_at,
            "version": version,
            "bridge_available": self.bridge.available,
        }

    def heartbeat(self) -> dict[str, Any]:
        with self._lock:
            if not self.diagnostics.connected:
                raise RuntimeError("MT5 not connected")
            t0 = time.perf_counter()
            info = self.bridge.account_info()
            ms = round((time.perf_counter() - t0) * 1000.0, 3)
            if info is None:
                self._record_failure("heartbeat: account_info returned None")
                raise RuntimeError("heartbeat failed")
            now = datetime.now(UTC).isoformat()
            self.diagnostics.last_heartbeat_at = now
            self.diagnostics.last_heartbeat_ms = ms
            return {
                "ok": True,
                "ping_ms": ms,
                "at": now,
                "session_mode": self.diagnostics.session_mode,
            }

    def _try_reconnect(self) -> bool:
        if not self.settings.mt5_reconnect_enabled:
            return False
        creds = self._creds
        if creds is None:
            return False
        if (
            self.diagnostics.reconnect_attempts
            >= self.settings.mt5_reconnect_max_attempts
        ):
            return False
        self.diagnostics.reconnect_attempts += 1
        event: dict[str, Any] = {
            "at": datetime.now(UTC).isoformat(),
            "attempt": self.diagnostics.reconnect_attempts,
            "mode": creds.mode,
        }
        try:
            path = creds.path or self.settings.mt5_terminal_path
            if not self.bridge.initialize(path):
                raise RuntimeError(f"initialize failed: {self.bridge.last_error()}")
            if creds.password:
                if not self.bridge.login(creds.login, creds.password, creds.server):
                    raise RuntimeError(f"login failed: {self.bridge.last_error()}")
            else:
                info = self.bridge.account_info()
                if info is None:
                    raise RuntimeError(
                        "attached session lost — terminal has no account; "
                        "use POST /session/connect"
                    )
                creds.login = int(info.login)
                creds.server = str(getattr(info, "server", "") or creds.server)
                self.diagnostics.login = creds.login
                self.diagnostics.server = creds.server
            self.diagnostics.connected = True
            self.diagnostics.session_mode = creds.mode
            event["result"] = "ok"
            self.diagnostics.reconnect_events.append(event)
            return True
        except Exception as exc:
            event["result"] = "failed"
            event["reason"] = str(exc)
            self.diagnostics.reconnect_events.append(event)
            self._record_failure(f"reconnect: {exc}")
            self.diagnostics.connected = False
            return False
        finally:
            self.diagnostics.reconnect_events = (
                self.diagnostics.reconnect_events[-20:]
            )

    def _heartbeat_loop(self) -> None:
        interval = self.settings.mt5_heartbeat_interval_seconds
        while not self._stop.wait(interval):
            with self._lock:
                if not self.diagnostics.connected or self._creds is None:
                    continue
                try:
                    self.heartbeat()
                except Exception:
                    backoff = self.settings.mt5_reconnect_backoff_seconds
                    self._try_reconnect()
                    time.sleep(backoff)

    def _ensure_symbol(self, symbol: str) -> None:
        if not self.bridge.symbol_select(symbol, True):
            err = self.bridge.last_error()
            raise RuntimeError(f"symbol_select failed for {symbol}: {err}")

    def account(self) -> dict[str, Any]:
        info = self._require_account()
        return {
            "login": int(info.login),
            "balance": str(info.balance),
            "equity": str(info.equity),
            "margin": str(info.margin),
            "free_margin": str(getattr(info, "margin_free", 0)),
            "margin_level": str(getattr(info, "margin_level", 0)),
            "profit": str(info.profit),
            "leverage": int(info.leverage),
            "currency": str(getattr(info, "currency", "")),
            "server": str(getattr(info, "server", "")),
            "name": str(getattr(info, "name", "")),
            "session_mode": self.diagnostics.session_mode,
        }

    def symbols(self) -> dict[str, Any]:
        self._require_connected()
        rows = self.bridge.symbols_get() or []
        items = [
            {
                "code": str(getattr(s, "name", "")),
                "description": str(getattr(s, "description", "")),
                "digits": int(getattr(s, "digits", 0)),
            }
            for s in rows
        ]
        return {"items": items, "count": len(items)}

    def quote(self, symbol: str) -> dict[str, Any]:
        self._require_connected()
        self._ensure_symbol(symbol)
        tick = self.bridge.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"symbol unavailable: {symbol}")
        return {
            "symbol": symbol.upper(),
            "bid": str(tick.bid),
            "ask": str(tick.ask),
            "time": int(getattr(tick, "time", 0)),
        }

    def candles(
        self, symbol: str, *, timeframe: str = "H1", count: int = 100
    ) -> dict[str, Any]:
        self._require_connected()
        self._ensure_symbol(symbol)
        tf = _TIMEFRAME_MAP.get(timeframe.strip().upper())
        if tf is None:
            raise RuntimeError(f"unsupported timeframe: {timeframe}")
        rates = self.bridge.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None:
            raise RuntimeError(f"candles unavailable for {symbol}")
        items = [
            {
                "time": int(r["time"]),
                "open": str(r["open"]),
                "high": str(r["high"]),
                "low": str(r["low"]),
                "close": str(r["close"]),
            }
            for r in rates
        ]
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe.upper(),
            "items": items,
        }

    def positions(self) -> dict[str, Any]:
        self._require_connected()
        rows = self.bridge.positions_get() or []
        items = [
            {
                "ticket": int(p.ticket),
                "symbol": str(p.symbol),
                "type": int(p.type),
                "volume": str(p.volume),
                "price_open": str(p.price_open),
                "price_current": str(p.price_current),
                "profit": str(p.profit),
            }
            for p in rows
        ]
        return {"items": items}

    def orders(self) -> dict[str, Any]:
        self._require_connected()
        rows = self.bridge.orders_get() or []
        items = [
            {
                "ticket": int(o.ticket),
                "symbol": str(o.symbol),
                "type": int(o.type),
                "volume_current": str(o.volume_current),
                "price_open": str(o.price_open),
            }
            for o in rows
        ]
        return {"items": items}

    def history_orders(self, *, days: int = 30) -> dict[str, Any]:
        self._require_connected()
        date_to = datetime.now(UTC)
        date_from = datetime.fromtimestamp(
            date_to.timestamp() - days * 86400, tz=UTC
        )
        rows = self.bridge.history_orders_get(date_from, date_to) or []
        items = [
            {
                "ticket": int(o.ticket),
                "symbol": str(o.symbol),
                "state": int(getattr(o, "state", 0)),
            }
            for o in rows
        ]
        return {"items": items}

    def history_deals(self, *, days: int = 30) -> dict[str, Any]:
        self._require_connected()
        date_to = datetime.now(UTC)
        date_from = datetime.fromtimestamp(
            date_to.timestamp() - days * 86400, tz=UTC
        )
        rows = self.bridge.history_deals_get(date_from, date_to) or []
        items = [
            {
                "ticket": int(d.ticket),
                "symbol": str(d.symbol),
                "profit": str(d.profit),
                "volume": str(d.volume),
            }
            for d in rows
        ]
        return {"items": items}

    def diagnostics_snapshot(self) -> dict[str, Any]:
        password_in_memory = bool(self._creds and self._creds.password)
        return {
            **self.diagnostics.to_dict(),
            "bridge_available": self.bridge.available,
            "import_error": self.bridge._import_error,
            "credentials_in_memory": self._creds is not None,
            "password_in_memory": password_in_memory,
            "auto_attach_enabled": self.settings.mt5_gateway_auto_attach,
            "credentials_note": (
                "Broker password never leaves Windows gateway memory / "
                "never stored in Railway. Attached sessions store no password."
            ),
        }

    def _require_connected(self) -> None:
        if not self.diagnostics.connected:
            raise RuntimeError(
                "MT5 not connected. Call POST /session/attach "
                "(terminal already logged in) or POST /session/connect."
            )
        if not self.bridge.available:
            raise RuntimeError("MetaTrader5 bridge unavailable")

    def _require_account(self) -> Any:
        self._require_connected()
        info = self.bridge.account_info()
        if info is None:
            raise RuntimeError("account_info unavailable")
        return info
