"""MT5 Gateway runtime — terminal management, heartbeat, reconnect.

Broker credentials are held only in process memory on the Windows host.
They are never written to Railway env, logs, or API responses.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, TypeVar

from services.mt5_gateway.settings import MT5GatewaySettings, get_gateway_settings

logger = logging.getLogger("quantforg.mt5_gateway")

T = TypeVar("T")

# Heartbeat considered fresh enough to report MT5 connected after a probe timeout.
_HEARTBEAT_FRESH_SECONDS = 30.0


class MT5CallTimeout(TimeoutError):
    """MetaTrader5 API call exceeded its bounded timeout."""


def call_mt5_bounded(
    fn: Callable[[], T],
    *,
    timeout_seconds: float,
    label: str = "mt5_call",
) -> T:
    """Run an MT5 API callable with a hard wall-clock timeout.

    MetaTrader5 has no native cancel. We join a daemon worker; if it exceeds
    ``timeout_seconds`` we raise :class:`MT5CallTimeout` and leave the worker
    to finish in the background (preferred over hanging the HTTP server).
    """
    box: list[T] = []
    err: list[BaseException] = []

    def _target() -> None:
        try:
            box.append(fn())
        except BaseException as exc:  # noqa: BLE001 — boundary to caller thread
            err.append(exc)

    worker = threading.Thread(target=_target, name=f"mt5-bounded-{label}", daemon=True)
    worker.start()
    worker.join(timeout=max(0.05, float(timeout_seconds)))
    if worker.is_alive():
        raise MT5CallTimeout(
            f"{label} exceeded {timeout_seconds:.3f}s (MT5 API unresponsive)"
        )
    if err:
        raise err[0]
    if not box:
        raise RuntimeError(f"{label} returned no result")
    return box[0]


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

_DATE_TOKEN_RE = re.compile(r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$|^\d{4}-\d{2}-\d{2}")


def _looks_like_date(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if _DATE_TOKEN_RE.match(text):
        return True
    # e.g. "28 Apr 2026", "15 Jan 2027"
    parts = text.split()
    return bool(len(parts) == 3 and parts[1].isalpha())


def _safe_int(value: Any, default: int = 0) -> int:
    """Convert MT5 numeric fields without crashing on date strings."""
    if value is None or value is False:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return default
    if _looks_like_date(text):
        return default
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return default


def _terminal_capability_fields(term: Any | None) -> dict[str, Any]:
    """Extract AutoTrading / DLL flags from MetaTrader5.terminal_info().

    The official MetaTrader5 Python API exposes:
      - terminal_info().trade_allowed  → Algo Trading / AutoTrading toolbar
      - terminal_info().dlls_allowed   → Allow DLL imports

    Never invents values. When attributes are absent, reports NOT_SUPPORTED.
    """
    if term is None:
        return {
            "terminal_trade_allowed": None,
            "mt5_autotrading_enabled": None,
            "dlls_allowed": None,
            "dll_allowed": None,
            "capability_support": {
                "autotrading": "NOT_SUPPORTED",
                "dll": "NOT_SUPPORTED",
            },
            "capability_note": "terminal_info unavailable",
        }

    has_trade = hasattr(term, "trade_allowed")
    has_dll = hasattr(term, "dlls_allowed")
    trade_raw = getattr(term, "trade_allowed", None) if has_trade else None
    dll_raw = getattr(term, "dlls_allowed", None) if has_dll else None
    trade_val = bool(trade_raw) if trade_raw is not None else None
    dll_val = bool(dll_raw) if dll_raw is not None else None
    return {
        "terminal_trade_allowed": trade_val,
        "mt5_autotrading_enabled": trade_val,
        "dlls_allowed": dll_val,
        "dll_allowed": dll_val,
        "capability_support": {
            "autotrading": "SUPPORTED" if has_trade else "NOT_SUPPORTED",
            "dll": "SUPPORTED" if has_dll else "NOT_SUPPORTED",
        },
        "capability_note": (
            "From MetaTrader5.terminal_info() "
            "(trade_allowed=AutoTrading, dlls_allowed=DLL imports)"
            if has_trade or has_dll
            else "terminal_info present but capability attributes missing"
        ),
    }


def _empty_capability_fields(*, reason: str) -> dict[str, Any]:
    """Explicit unknown capability block — never invent Enabled/Disabled."""
    return {
        "terminal_trade_allowed": None,
        "mt5_autotrading_enabled": None,
        "dlls_allowed": None,
        "dll_allowed": None,
        "capability_support": {
            "autotrading": "NOT_SUPPORTED",
            "dll": "NOT_SUPPORTED",
        },
        "capability_note": reason,
    }


def _parse_mt5_version(raw: Any) -> tuple[int, int, str]:
    """Parse MetaTrader5.version().

    Official package returns ``(version, build, release_date)`` where
    ``release_date`` is often a human string such as ``\"28 Apr 2026\"``.
    Never coerce that third element with ``int()``.
    """
    if not raw:
        return (0, 0, "")
    try:
        parts = list(raw)
    except TypeError:
        return (_safe_int(raw, 0), 0, "")
    while len(parts) < 3:
        parts.append(0)
    major = _safe_int(parts[0], 0)
    build = _safe_int(parts[1], 0)
    release = parts[2]
    if _looks_like_date(release):
        release_str = str(release).strip()
    elif isinstance(release, (int, float)) and not isinstance(release, bool):
        release_str = str(int(release))
    else:
        text = str(release or "").strip()
        release_str = text if text else ""
        # Legacy numeric third element stored as string.
        if text and not _looks_like_date(text):
            as_int = _safe_int(text, default=-1)
            if as_int >= 0 and text.replace(".", "", 1).isdigit():
                release_str = str(as_int)
    return major, build, release_str


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

    def version(self) -> tuple[int, int, str]:
        """Return ``(version, build, release_date)``.

        MetaTrader5 may supply ``release_date`` as ``\"28 Apr 2026\"``.
        """
        raw = self.require().version()
        return _parse_mt5_version(raw)

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
        return self.require().copy_rates_from_pos(symbol, timeframe, start_pos, count)

    def positions_get(self) -> Any:
        return self.require().positions_get()

    def orders_get(self) -> Any:
        return self.require().orders_get()

    def history_orders_get(self, date_from: datetime, date_to: datetime) -> Any:
        return self.require().history_orders_get(date_from, date_to)

    def history_deals_get(self, date_from: datetime, date_to: datetime) -> Any:
        return self.require().history_deals_get(date_from, date_to)

    def symbol_info(self, symbol: str) -> Any:
        return self.require().symbol_info(symbol)

    def order_check(self, request: dict[str, Any]) -> Any:
        return self.require().order_check(request)

    def order_send(self, request: dict[str, Any]) -> Any:
        return self.require().order_send(request)

    def order_calc_margin(
        self, order_type: int, symbol: str, volume: float, price: float
    ) -> Any:
        return self.require().order_calc_margin(order_type, symbol, volume, price)

    def order_calc_profit(
        self,
        order_type: int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> Any:
        return self.require().order_calc_profit(
            order_type, symbol, volume, price_open, price_close
        )


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
            login = _safe_int(info.login)
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
        """Fast health snapshot — never blocks indefinitely on MetaTrader5.

        Live ``account_info`` is bounded by ``mt5_health_probe_timeout_seconds``.
        On timeout, returns degraded status from the last successful heartbeat
        instead of hanging the HTTP worker.
        """
        connected = False
        latency_ms: float | None = None
        terminal_build: int | None = None
        build_date = ""
        server = self.diagnostics.server
        login_status = "disconnected"
        version = ""
        degraded = False
        probe = "skipped"
        caps = _empty_capability_fields(reason="MT5 session not connected — capabilities not probed")
        if not (self.bridge.available and self.diagnostics.connected):
            if not self.bridge.available:
                caps = _empty_capability_fields(
                    reason="MetaTrader5 bridge unavailable — capabilities NOT_SUPPORTED"
                )
            return {
                "connected": False,
                "session_mode": self.diagnostics.session_mode,
                "latency_ms": None,
                "terminal_build": None,
                "build_date": None,
                "server": server or None,
                "login_status": login_status,
                "last_heartbeat_at": self.diagnostics.last_heartbeat_at,
                "version": version,
                "bridge_available": self.bridge.available,
                "degraded": False,
                "probe": probe,
                **caps,
            }

        timeout = float(self.settings.mt5_health_probe_timeout_seconds)
        try:
            t0 = time.perf_counter()
            info = call_mt5_bounded(
                self.bridge.account_info,
                timeout_seconds=timeout,
                label="health.account_info",
            )
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            connected = info is not None
            login_status = "connected" if connected else "error"
            probe = "live"
            if info is not None:
                server = str(getattr(info, "server", server) or server)
        except MT5CallTimeout as exc:
            logger.warning(
                "mt5_gateway_health_probe_timeout: %s",
                exc,
            )
            self._record_failure(str(exc))
            degraded = True
            probe = "timeout"
            # Prefer last successful heartbeat over inventing a disconnect.
            if self._heartbeat_is_fresh():
                connected = True
                login_status = "degraded"
                latency_ms = self.diagnostics.last_heartbeat_ms
            else:
                connected = False
                login_status = "timeout"
            return {
                "connected": connected,
                "session_mode": self.diagnostics.session_mode,
                "latency_ms": latency_ms,
                "terminal_build": None,
                "build_date": None,
                "server": server or None,
                "login_status": login_status,
                "last_heartbeat_at": self.diagnostics.last_heartbeat_at,
                "version": version,
                "bridge_available": self.bridge.available,
                "degraded": degraded,
                "probe": probe,
                **_empty_capability_fields(
                    reason="account_info probe timed out — terminal capabilities not read"
                ),
            }
        except Exception as exc:
            logger.exception("mt5_gateway_health_account_failed")
            self._record_failure(f"{type(exc).__name__}: {exc}")
            login_status = "error"
            connected = False
            probe = "error"
            return {
                "connected": False,
                "session_mode": self.diagnostics.session_mode,
                "latency_ms": latency_ms,
                "terminal_build": None,
                "build_date": None,
                "server": server or None,
                "login_status": login_status,
                "last_heartbeat_at": self.diagnostics.last_heartbeat_at,
                "version": version,
                "bridge_available": self.bridge.available,
                "degraded": True,
                "probe": probe,
                **_empty_capability_fields(
                    reason="account_info probe failed — terminal capabilities not read"
                ),
            }

        # Metadata must never flip a healthy session to disconnected.
        # Also never hang health on secondary probes.
        meta_timeout = min(timeout, 0.2)
        try:
            term = call_mt5_bounded(
                self.bridge.terminal_info,
                timeout_seconds=meta_timeout,
                label="health.terminal_info",
            )
            if term is not None:
                terminal_build = _safe_int(getattr(term, "build", 0), 0)
                caps = _terminal_capability_fields(term)
            else:
                caps = _empty_capability_fields(
                    reason="terminal_info returned None"
                )
        except Exception as exc:
            logger.info(
                "mt5_gateway_health_terminal_skipped: %s",
                f"{type(exc).__name__}: {exc}",
            )
            self._record_failure(f"terminal_info: {type(exc).__name__}: {exc}")
            caps = _empty_capability_fields(
                reason=f"terminal_info probe failed: {type(exc).__name__}"
            )

        try:
            major, build, release = call_mt5_bounded(
                self.bridge.version,
                timeout_seconds=meta_timeout,
                label="health.version",
            )
            build_date = release
            if terminal_build is None or terminal_build == 0:
                terminal_build = build or None
            if release and _looks_like_date(release):
                version = f"{major}.{build} ({release})"
            else:
                version = f"{major}.{build}.{release}".rstrip(".")
        except Exception as exc:
            logger.info(
                "mt5_gateway_health_version_skipped: %s",
                f"{type(exc).__name__}: {exc}",
            )
            self._record_failure(f"version: {type(exc).__name__}: {exc}")

        return {
            "connected": connected,
            "session_mode": self.diagnostics.session_mode,
            "latency_ms": latency_ms,
            "terminal_build": terminal_build,
            "build_date": build_date or None,
            "server": server or None,
            "login_status": login_status,
            "last_heartbeat_at": self.diagnostics.last_heartbeat_at,
            "version": version,
            "bridge_available": self.bridge.available,
            "degraded": degraded,
            "probe": probe,
            **caps,
        }

    def _heartbeat_is_fresh(self) -> bool:
        raw = self.diagnostics.last_heartbeat_at
        if not raw:
            return False
        try:
            when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return False
        age = (datetime.now(UTC) - when.astimezone(UTC)).total_seconds()
        return 0.0 <= age <= _HEARTBEAT_FRESH_SECONDS

    def heartbeat(self) -> dict[str, Any]:
        """Ping MT5 with a bounded timeout — never hold the session lock during the API call."""
        if not self.diagnostics.connected:
            raise RuntimeError("MT5 not connected")
        timeout = float(self.settings.mt5_api_call_timeout_seconds)
        t0 = time.perf_counter()
        info = call_mt5_bounded(
            self.bridge.account_info,
            timeout_seconds=timeout,
            label="heartbeat.account_info",
        )
        ms = round((time.perf_counter() - t0) * 1000.0, 3)
        if info is None:
            self._record_failure("heartbeat: account_info returned None")
            raise RuntimeError("heartbeat failed")
        now = datetime.now(UTC).isoformat()
        with self._lock:
            self.diagnostics.last_heartbeat_at = now
            self.diagnostics.last_heartbeat_ms = ms
            mode = self.diagnostics.session_mode
        return {
            "ok": True,
            "ping_ms": ms,
            "at": now,
            "session_mode": mode,
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
        timeout = float(self.settings.mt5_api_call_timeout_seconds)
        try:
            path = creds.path or self.settings.mt5_terminal_path
            initialized = call_mt5_bounded(
                lambda: self.bridge.initialize(path),
                timeout_seconds=timeout,
                label="reconnect.initialize",
            )
            if not initialized:
                raise RuntimeError(f"initialize failed: {self.bridge.last_error()}")
            if creds.password:
                logged_in = call_mt5_bounded(
                    lambda: self.bridge.login(
                        creds.login, creds.password, creds.server
                    ),
                    timeout_seconds=timeout,
                    label="reconnect.login",
                )
                if not logged_in:
                    raise RuntimeError(f"login failed: {self.bridge.last_error()}")
            else:
                info = call_mt5_bounded(
                    self.bridge.account_info,
                    timeout_seconds=timeout,
                    label="reconnect.account_info",
                )
                if info is None:
                    raise RuntimeError(
                        "attached session lost — terminal has no account; "
                        "use POST /session/connect"
                    )
                creds.login = _safe_int(info.login)
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
            self.diagnostics.reconnect_events = self.diagnostics.reconnect_events[-20:]

    def _heartbeat_loop(self) -> None:
        interval = self.settings.mt5_heartbeat_interval_seconds
        while not self._stop.wait(interval):
            with self._lock:
                should_beat = self.diagnostics.connected and self._creds is not None
            if not should_beat:
                continue
            try:
                # Do not hold _lock across MT5 API — hangs would freeze connect/attach.
                self.heartbeat()
            except Exception:
                backoff = self.settings.mt5_reconnect_backoff_seconds
                with self._lock:
                    self._try_reconnect()
                time.sleep(backoff)

    def _ensure_symbol(self, symbol: str) -> None:
        if not self.bridge.symbol_select(symbol, True):
            err = self.bridge.last_error()
            raise RuntimeError(f"symbol_select failed for {symbol}: {err}")

    def account(self) -> dict[str, Any]:
        info = self._require_account()
        return {
            "login": _safe_int(info.login),
            "balance": str(info.balance),
            "equity": str(info.equity),
            "margin": str(info.margin),
            "free_margin": str(getattr(info, "margin_free", 0)),
            "margin_level": str(getattr(info, "margin_level", 0)),
            "profit": str(info.profit),
            "leverage": _safe_int(info.leverage, 1),
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
                "digits": _safe_int(getattr(s, "digits", 0)),
                "volume_min": str(getattr(s, "volume_min", 0) or 0),
                "volume_max": str(getattr(s, "volume_max", 0) or 0),
                "volume_step": str(getattr(s, "volume_step", 0) or 0),
                "trade_mode": _safe_int(getattr(s, "trade_mode", 0)),
                "filling_mode": _safe_int(getattr(s, "filling_mode", 0)),
                "point": str(getattr(s, "point", 0) or 0),
                "contract_size": str(getattr(s, "trade_contract_size", 0) or 0),
            }
            for s in rows
        ]
        return {"items": items, "count": len(items)}

    def symbol_specs(self, symbol: str) -> dict[str, Any]:
        """Live MT5 trading constraints for one symbol — never hardcoded."""
        from services.mt5_gateway.symbol_specs import serialize_symbol_specs

        self._require_connected()
        self._ensure_symbol(symbol)
        info = self.bridge.symbol_info(symbol)
        if info is None:
            err = self.bridge.last_error()
            raise RuntimeError(f"symbol_info failed for {symbol}: {err}")
        tick = self.bridge.symbol_info_tick(symbol)
        return serialize_symbol_specs(info, tick=tick)

    def quote(self, symbol: str) -> dict[str, Any]:
        self._require_connected()
        self._ensure_symbol(symbol)
        tick = self.bridge.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"symbol unavailable: {symbol}")
        specs: dict[str, Any] = {}
        try:
            specs = self.symbol_specs(symbol)
        except RuntimeError:
            specs = {}
        return {
            "symbol": symbol.upper(),
            "bid": str(tick.bid),
            "ask": str(tick.ask),
            "time": _safe_int(getattr(tick, "time", 0)),
            "specs": specs,
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
                "time": _safe_int(r["time"]),
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
                "ticket": _safe_int(p.ticket),
                "symbol": str(p.symbol),
                "type": _safe_int(p.type),
                "volume": str(p.volume),
                "price_open": str(p.price_open),
                "price_current": str(p.price_current),
                "sl": str(getattr(p, "sl", 0) or 0),
                "tp": str(getattr(p, "tp", 0) or 0),
                "profit": str(p.profit),
                "swap": str(getattr(p, "swap", 0) or 0),
                "magic": _safe_int(getattr(p, "magic", 0)),
                "comment": str(getattr(p, "comment", "") or ""),
                "time": _safe_int(getattr(p, "time", 0)),
            }
            for p in rows
        ]
        return {"items": items}

    def orders(self) -> dict[str, Any]:
        self._require_connected()
        rows = self.bridge.orders_get() or []
        items = [
            {
                "ticket": _safe_int(o.ticket),
                "symbol": str(o.symbol),
                "type": _safe_int(o.type),
                "volume_current": str(o.volume_current),
                "price_open": str(o.price_open),
                "sl": str(getattr(o, "sl", 0) or 0),
                "tp": str(getattr(o, "tp", 0) or 0),
                "time_setup": _safe_int(getattr(o, "time_setup", 0)),
            }
            for o in rows
        ]
        return {"items": items}

    def history_orders(self, *, days: int = 30) -> dict[str, Any]:
        self._require_connected()
        # MetaTrader5 history_* APIs are sensitive to tz-aware datetimes and to
        # broker server clocks that stamp deals ahead of UTC. Use naive UTC and
        # pad date_to forward so just-executed fills are included.
        now = datetime.now(UTC).replace(tzinfo=None)
        date_to = now + timedelta(days=1)
        date_from = now - timedelta(days=days)
        rows = self.bridge.history_orders_get(date_from, date_to) or []
        items = [
            {
                "ticket": _safe_int(o.ticket),
                "symbol": str(o.symbol),
                "state": _safe_int(getattr(o, "state", 0)),
            }
            for o in rows
        ]
        return {"items": items}

    def history_deals(self, *, days: int = 30) -> dict[str, Any]:
        self._require_connected()
        now = datetime.now(UTC).replace(tzinfo=None)
        date_to = now + timedelta(days=1)
        date_from = now - timedelta(days=days)
        rows = self.bridge.history_deals_get(date_from, date_to) or []
        items = [
            {
                "ticket": _safe_int(d.ticket),
                "order": _safe_int(getattr(d, "order", 0)),
                "symbol": str(d.symbol),
                "type": _safe_int(getattr(d, "type", 0)),
                "entry": _safe_int(getattr(d, "entry", 0)),
                "volume": str(d.volume),
                "price": str(getattr(d, "price", 0) or 0),
                "profit": str(d.profit),
                "swap": str(getattr(d, "swap", 0) or 0),
                "commission": str(getattr(d, "commission", 0) or 0),
                "time": _safe_int(getattr(d, "time", 0)),
                "magic": _safe_int(getattr(d, "magic", 0)),
                "comment": str(getattr(d, "comment", "") or ""),
                "position_id": _safe_int(getattr(d, "position_id", 0)),
            }
            for d in rows
        ]
        return {"items": items}

    def order_check(self, body: dict[str, Any]) -> dict[str, Any]:
        """Validate a trade request via MetaTrader5.order_check (no fill)."""
        from services.mt5_gateway.trade import (
            build_mt5_trade_request,
            order_check_with_filling_fallback,
            serialize_check_result,
        )

        self._require_connected()
        symbol = str(body.get("symbol") or "").strip().upper()
        if not symbol:
            raise RuntimeError("symbol is required")
        self._ensure_symbol(symbol)
        mt5 = self.bridge.require()
        request = build_mt5_trade_request(
            mt5,
            symbol=symbol,
            action=str(body.get("action") or "buy"),
            volume=float(body.get("volume") or 0),
            price=float(body.get("price") or 0),
            stop_loss=float(body.get("sl") or body.get("stop_loss") or 0),
            take_profit=float(body.get("tp") or body.get("take_profit") or 0),
            deviation=int(body.get("deviation") or body.get("slippage") or 20),
            magic=int(body.get("magic") or 0),
            comment=str(body.get("comment") or "quantforg"),
            position=int(body.get("position") or 0),
            order_ticket=int(body.get("order_ticket") or body.get("order") or 0),
            oms_kind=str(body.get("oms_kind") or ""),
        )
        info = self.bridge.symbol_info(symbol)
        result, request = order_check_with_filling_fallback(mt5, request, info=info)
        filling_attempts = request.pop("_filling_attempts", [])
        payload = serialize_check_result(result, request)
        payload["component"] = "mt5_order_check"
        payload["filling_attempts"] = filling_attempts
        try:
            payload["symbol_specs"] = self.symbol_specs(symbol)
        except RuntimeError:
            payload["symbol_specs"] = {}
        if result is None:
            err = self.bridge.last_error()
            payload["comment"] = f"order_check failed: {err}"
        return payload

    def order_calc_margin(self, body: dict[str, Any]) -> dict[str, Any]:
        from services.mt5_gateway.trade import order_type_for_action

        self._require_connected()
        symbol = str(body.get("symbol") or "").strip().upper()
        action = str(body.get("action") or "buy")
        volume = float(body.get("volume") or 0)
        price = float(body.get("price") or 0)
        if not symbol or volume <= 0:
            raise RuntimeError("symbol and positive volume are required")
        self._ensure_symbol(symbol)
        if price <= 0:
            tick = self.bridge.symbol_info_tick(symbol)
            if tick is None:
                raise RuntimeError(f"no quote for {symbol}")
            price = float(tick.ask if "buy" in action.lower() else tick.bid)
        order_type = order_type_for_action(action)
        margin = self.bridge.order_calc_margin(order_type, symbol, volume, price)
        if margin is None:
            err = self.bridge.last_error()
            return {
                "margin": "0",
                "retcode": 10013,
                "comment": f"order_calc_margin failed: {err}",
            }
        return {
            "margin": str(margin),
            "retcode": 10009,
            "comment": "done",
        }

    def order_calc_profit(self, body: dict[str, Any]) -> dict[str, Any]:
        from services.mt5_gateway.trade import order_type_for_action

        self._require_connected()
        symbol = str(body.get("symbol") or "").strip().upper()
        action = str(body.get("action") or "buy")
        volume = float(body.get("volume") or 0)
        price_open = float(body.get("price") or body.get("price_open") or 0)
        price_close = float(body.get("close_price") or body.get("price_close") or 0)
        if not symbol or volume <= 0:
            raise RuntimeError("symbol and positive volume are required")
        self._ensure_symbol(symbol)
        tick = self.bridge.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"no quote for {symbol}")
        if price_open <= 0:
            price_open = float(tick.ask if "buy" in action.lower() else tick.bid)
        if price_close <= 0:
            price_close = float(tick.bid if "buy" in action.lower() else tick.ask)
        order_type = order_type_for_action(action)
        profit = self.bridge.order_calc_profit(
            order_type, symbol, volume, price_open, price_close
        )
        if profit is None:
            err = self.bridge.last_error()
            return {
                "profit": "0",
                "retcode": 10013,
                "comment": f"order_calc_profit failed: {err}",
            }
        return {
            "profit": str(profit),
            "retcode": 10009,
            "comment": "done",
        }

    def order_send(self, body: dict[str, Any]) -> dict[str, Any]:
        """Live MetaTrader5.order_send — returns real broker retcode / ticket."""
        from services.mt5_gateway.trade import (
            TRADE_ACTION_SLTP,
            apply_filling_mode,
            build_mt5_trade_request,
            filling_name,
            mt5_retcode,
            order_check_with_filling_fallback,
            serialize_send_result,
        )

        self._require_connected()
        symbol = str(body.get("symbol") or "").strip().upper()
        if not symbol:
            raise RuntimeError("symbol is required")
        oms_kind = str(body.get("oms_kind") or "").strip().lower()
        action = str(body.get("action") or "buy").strip().lower()
        is_sltp = oms_kind in {"sltp", "modify_sltp"} or action in {
            "sltp",
            "modify_sltp",
        }
        volume = float(body.get("volume") or 0)
        if not is_sltp and volume <= 0:
            raise RuntimeError("volume must be > 0")
        self._ensure_symbol(symbol)
        mt5 = self.bridge.require()
        request = build_mt5_trade_request(
            mt5,
            symbol=symbol,
            action=action,
            volume=volume if volume > 0 else 0.01,
            price=float(body.get("price") or 0),
            stop_loss=float(body.get("sl") or body.get("stop_loss") or 0),
            take_profit=float(body.get("tp") or body.get("take_profit") or 0),
            deviation=int(body.get("deviation") or body.get("slippage") or 20),
            magic=int(body.get("magic") or 0),
            comment=str(body.get("comment") or "quantforg"),
            position=int(body.get("position") or 0),
            order_ticket=int(body.get("order_ticket") or body.get("order") or 0),
            oms_kind=oms_kind,
        )
        # Re-validate with filling fallback so order_send uses a broker-accepted mode.
        if int(request.get("action") or 0) != TRADE_ACTION_SLTP:
            info = self.bridge.symbol_info(symbol)
            check_result, request = order_check_with_filling_fallback(
                mt5, request, info=info
            )
            filling_attempts = request.pop("_filling_attempts", [])
            check_retcode = mt5_retcode(check_result)
            if check_result is None or check_retcode not in {0, 10009}:
                payload = serialize_send_result(None, request)
                payload["component"] = "mt5_order_send"
                payload["ok"] = False
                payload["retcode"] = check_retcode
                payload["comment"] = (
                    f"order_check blocked send: "
                    f"{getattr(check_result, 'comment', '') or 'failed'} "
                    f"(retcode {check_retcode})"
                )
                payload["filling_attempts"] = filling_attempts
                payload["order_check_retcode"] = check_retcode
                try:
                    payload["symbol_specs"] = self.symbol_specs(symbol)
                except RuntimeError:
                    payload["symbol_specs"] = {}
                return payload
            request = apply_filling_mode(
                request, int(request.get("type_filling") or 0)
            )
            logger.info(
                "mt5_order_send_after_check symbol=%s filling=%s",
                symbol,
                filling_name(int(request.get("type_filling") or -1)),
            )

        result = self.bridge.order_send(request)
        payload = serialize_send_result(result, request)
        payload["component"] = "mt5_order_send"
        try:
            payload["symbol_specs"] = self.symbol_specs(symbol)
        except RuntimeError:
            payload["symbol_specs"] = {}
        if result is None:
            err = self.bridge.last_error()
            payload["comment"] = (
                f"order_send failed: {err}. "
                "Enable AutoTrading in MT5 and allow algo trading for this EA/account."
            )
        return payload

    def order_cancel(self, ticket: int) -> dict[str, Any]:
        from services.mt5_gateway.trade import (
            TRADE_ACTION_REMOVE,
            serialize_send_result,
        )

        self._require_connected()
        if ticket <= 0:
            raise RuntimeError("ticket must be > 0")
        request = {"action": TRADE_ACTION_REMOVE, "order": int(ticket)}
        result = self.bridge.order_send(request)
        payload = serialize_send_result(result, request)
        if result is None:
            err = self.bridge.last_error()
            payload["comment"] = f"order_cancel failed: {err}"
        return payload

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
