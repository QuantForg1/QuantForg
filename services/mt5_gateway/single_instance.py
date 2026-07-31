"""MT5 Gateway single-instance protection (port 8765).

Fail-closed gate that MUST run before ``uvicorn.run`` / socket bind.

Primary occupancy signal is an exclusive TCP bind attempt (not a client
connect). On Windows this uses ``SO_EXCLUSIVEADDRUSE`` so we detect the same
conflict that would otherwise surface as WinError 10048.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("quantforg.mt5_gateway.single_instance")

StartupAction = Literal["start", "already_running"]

_HEALTH_TIMEOUT_SEC = 3.0
_PORT_RELEASE_TIMEOUT_SEC = 25.0
_PORT_RELEASE_POLL_SEC = 0.25
_POST_START_HEALTH_TIMEOUT_SEC = 30.0
_DEFAULT_PORT = 8765


@dataclass(frozen=True, slots=True)
class GatewayHealthSnapshot:
    ok: bool
    gateway_version: str = "unknown"
    mt5_status: str = "unknown"
    broker: str = "unknown"
    session: str = "unknown"
    raw: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def resolve_bind_host(host: str) -> str:
    if host in {"0.0.0.0", "::", "[::]", ""}:
        return "0.0.0.0"
    return host


def resolve_probe_host(host: str) -> str:
    """Host used for client connect /health (never 0.0.0.0)."""
    if host in {"0.0.0.0", "::", "[::]", ""}:
        return "127.0.0.1"
    return host


def health_url(host: str, port: int) -> str:
    return f"http://{resolve_probe_host(host)}:{int(port)}/health"


def port_can_bind_exclusively(host: str, port: int) -> bool:
    """Return True only if this process can exclusively own host:port.

    This is the authoritative pre-uvicorn gate. A successful exclusive bind
    means starting uvicorn will not raise WinError 10048 for address-in-use.
    """
    bind_host = resolve_bind_host(host)
    port = int(port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Windows: exclusive use matches the conflict uvicorn would hit.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            # POSIX: ensure we do not inherit a misleading REUSEADDR success.
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            except OSError:
                pass
        sock.bind((bind_host, port))
        return True
    except OSError as exc:
        logger.info(
            "Exclusive bind failed on %s:%s (%s) — port occupied or unavailable",
            bind_host,
            port,
            exc,
        )
        return False
    finally:
        try:
            sock.close()
        except OSError:
            pass


def port_is_listening(host: str, port: int, *, timeout: float = 0.75) -> bool:
    """Best-effort client connect probe (secondary signal only)."""
    probe_host = resolve_probe_host(host)
    try:
        with socket.create_connection((probe_host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def find_listening_pid(port: int) -> int | None:
    port = int(port)
    if sys.platform.startswith("win"):
        return _find_pid_windows(port)
    return _find_pid_posix(port)


def _find_pid_windows(port: int) -> int | None:
    try:
        completed = subprocess.run(  # noqa: S603
            ["netstat", "-ano", "-p", "tcp"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("netstat pid lookup failed: %s", exc)
        return None

    needle = f":{port}"
    for line in (completed.stdout or "").splitlines():
        upper = line.upper()
        if "LISTENING" not in upper:
            continue
        if needle not in line:
            continue
        parts = line.split()
        if not parts:
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid > 0:
            return pid
    return None


def _find_pid_posix(port: int) -> int | None:
    import re

    for cmd in (
        ["ss", "-ltnp", f"sport = :{port}"],
        ["lsof", f"-iTCP:{port}", "-sTCP:LISTEN", "-n", "-P"],
    ):
        try:
            completed = subprocess.run(  # noqa: S603
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=8,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        text = (completed.stdout or "") + "\n" + (completed.stderr or "")
        m = re.search(r"pid=(\d+)", text)
        if m:
            return int(m.group(1))
        for line in text.splitlines():
            if "LISTEN" not in line.upper():
                continue
            cols = line.split()
            if len(cols) >= 2 and cols[1].isdigit():
                return int(cols[1])
    return None


def fetch_gateway_health(
    host: str,
    port: int,
    *,
    timeout: float = _HEALTH_TIMEOUT_SEC,
) -> GatewayHealthSnapshot:
    url = health_url(host, port)
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — local only
            status = getattr(resp, "status", None) or resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return GatewayHealthSnapshot(ok=False, error=f"HTTP {exc.code}: {exc.reason}")
    except (URLError, TimeoutError, OSError) as exc:
        return GatewayHealthSnapshot(ok=False, error=str(exc))

    if int(status) != 200:
        return GatewayHealthSnapshot(ok=False, error=f"HTTP {status}")

    try:
        payload = json.loads(body)
    except Exception as exc:  # noqa: BLE001
        return GatewayHealthSnapshot(ok=False, error=f"invalid JSON: {exc}")

    if not isinstance(payload, dict):
        return GatewayHealthSnapshot(ok=False, error="health payload not an object")

    service = str(payload.get("service") or "").strip().lower()
    status_field = str(payload.get("status") or "").strip().lower()
    is_qf = service in {"mt5-gateway", "quantforg-mt5-gateway"} or (
        status_field == "ok" and "gateway_version" in payload
    )
    if not is_qf:
        return GatewayHealthSnapshot(
            ok=False,
            raw=payload,
            error=f"not a QuantForg MT5 gateway (service={service!r})",
        )

    mt5 = payload.get("mt5") if isinstance(payload.get("mt5"), dict) else {}
    connected = bool(mt5.get("connected"))
    login_status = str(mt5.get("login_status") or "").strip()
    if connected:
        mt5_status = "connected"
    elif login_status:
        mt5_status = login_status
    elif mt5:
        mt5_status = "disconnected"
    else:
        mt5_status = "unknown"

    broker = (
        str(mt5.get("server") or "").strip()
        or str(payload.get("server") or "").strip()
        or "unknown"
    )
    session = (
        str(mt5.get("session_mode") or "").strip()
        or str(payload.get("session_mode") or "").strip()
        or "unknown"
    )
    version = (
        str(payload.get("gateway_version") or "").strip()
        or str(payload.get("version") or "").strip()
        or "unknown"
    )
    return GatewayHealthSnapshot(
        ok=True,
        gateway_version=version,
        mt5_status=mt5_status,
        broker=broker if broker else "unknown",
        session=session if session else "unknown",
        raw=payload,
    )


def format_already_running_message(
    *,
    pid: int | None,
    health: GatewayHealthSnapshot,
) -> str:
    pid_txt = str(pid) if pid is not None else "unknown"
    return (
        "QuantForg MT5 Gateway is already running.\n"
        "\n"
        f"PID: {pid_txt}\n"
        f"Gateway Version: {health.gateway_version}\n"
        f"MT5 Status: {health.mt5_status}\n"
        f"Broker: {health.broker}\n"
        f"Session: {health.session}\n"
    )


def stop_gateway_process(pid: int, *, timeout: float = 12.0) -> None:
    if pid <= 0:
        raise ValueError("invalid pid")
    if pid == os.getpid():
        raise RuntimeError("refusing to stop the current process")

    logger.info("Stopping existing gateway pid=%s", pid)
    if sys.platform.startswith("win"):
        subprocess.run(  # noqa: S603
            ["taskkill", "/PID", str(pid)],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not _pid_alive(pid):
                return
            time.sleep(0.2)
        subprocess.run(  # noqa: S603
            ["taskkill", "/F", "/PID", str(pid)],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if not _pid_alive(pid):
                return
            time.sleep(0.2)
        if _pid_alive(pid):
            raise RuntimeError(f"Failed to terminate gateway PID {pid}")
        return

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    time.sleep(0.3)
    if _pid_alive(pid):
        raise RuntimeError(f"Failed to terminate gateway PID {pid}")


def _pid_alive(pid: int) -> bool:
    if sys.platform.startswith("win"):
        try:
            completed = subprocess.run(  # noqa: S603
                ["tasklist", "/FI", f"PID eq {pid}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        out = completed.stdout or ""
        return str(pid) in out and "No tasks" not in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_for_port_release(
    host: str,
    port: int,
    *,
    timeout: float = _PORT_RELEASE_TIMEOUT_SEC,
) -> bool:
    """Wait until exclusive bind succeeds (true socket release)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_can_bind_exclusively(host, port):
            time.sleep(0.2)
            if port_can_bind_exclusively(host, port):
                return True
        time.sleep(_PORT_RELEASE_POLL_SEC)
    return port_can_bind_exclusively(host, port)


def wait_for_healthy_gateway(
    host: str,
    port: int,
    *,
    timeout: float = _POST_START_HEALTH_TIMEOUT_SEC,
) -> GatewayHealthSnapshot:
    deadline = time.monotonic() + timeout
    last = GatewayHealthSnapshot(ok=False, error="not checked")
    while time.monotonic() < deadline:
        last = fetch_gateway_health(host, port)
        if last.ok:
            return last
        time.sleep(0.4)
    return last


def ensure_single_instance(
    *,
    host: str,
    port: int,
    restart: bool = False,
) -> StartupAction:
    """Fail-closed pre-bind gate. Never returns ``start`` while port is owned.

    Returns
    -------
    already_running
        Healthy QuantForg gateway owns the port — caller MUST exit 0 and MUST
        NOT call ``uvicorn.run``.
    start
        Exclusive bind is available — safe to start uvicorn.
    """
    port = int(port)
    can_bind = port_can_bind_exclusively(host, port)

    if restart:
        if not can_bind:
            pid = find_listening_pid(port)
            if pid is None:
                # Port occupied but PID unknown — still refuse to double-bind.
                raise RuntimeError(
                    f"Port {port} is in use but PID could not be resolved. "
                    "Stop the process manually, then retry --restart."
                )
            print("Restarting QuantForg MT5 Gateway…", flush=True)
            logger.info("Gateway --restart: stopping pid=%s", pid)
            stop_gateway_process(pid)
            if not wait_for_port_release(host, port):
                raise RuntimeError(
                    f"Port {port} did not release after stopping PID {pid}"
                )
            logger.info("Gateway socket released on port %s", port)
        else:
            logger.info("Gateway --restart: port %s already free", port)
        # Final fail-closed check
        if not port_can_bind_exclusively(host, port):
            raise RuntimeError(
                f"Port {port} still cannot be bound exclusively after --restart"
            )
        return "start"

    # --- Normal start ---
    if can_bind:
        logger.info("Port %s exclusively available — safe to start gateway", port)
        return "start"

    # Port occupied: require healthy /health to exit cleanly; else recycle.
    logger.info("Port %s occupied (exclusive bind failed) — probing /health", port)
    health = fetch_gateway_health(host, port)
    pid = find_listening_pid(port)

    if health.ok:
        # Re-verify before exit (requirement).
        verified = fetch_gateway_health(host, port)
        if verified.ok:
            msg = format_already_running_message(pid=pid, health=verified)
            print(msg, flush=True)
            print("Gateway already running", flush=True)
            logger.info(
                "Gateway already running pid=%s version=%s — skipping uvicorn",
                pid,
                verified.gateway_version,
            )
            return "already_running"
        health = verified

    # Unhealthy / non-QuantForg occupant
    err = health.error or "health check failed"
    print(
        f"Unhealthy process on port {port} "
        f"(PID: {pid if pid is not None else 'unknown'}): {err}. Restarting…",
        flush=True,
    )
    logger.warning("Unhealthy occupant on port %s pid=%s error=%s", port, pid, err)
    if pid is None:
        raise RuntimeError(
            f"Port {port} is occupied but PID is unknown and /health failed "
            f"({err}). Stop the process manually, then start the gateway."
        )
    stop_gateway_process(pid)
    if not wait_for_port_release(host, port):
        raise RuntimeError(
            f"Port {port} did not release after stopping unhealthy PID {pid}"
        )
    if not port_can_bind_exclusively(host, port):
        raise RuntimeError(
            f"Port {port} still cannot be bound exclusively after cleanup"
        )
    return "start"


def read_gateway_bind_settings() -> tuple[str, int]:
    """Resolve host/port without importing uvicorn/FastAPI."""
    host = os.environ.get("MT5_GATEWAY_HOST") or "0.0.0.0"
    port_raw = os.environ.get("MT5_GATEWAY_PORT") or str(_DEFAULT_PORT)
    try:
        port = int(port_raw)
    except ValueError:
        port = _DEFAULT_PORT
    # Prefer settings module when available (dotenv), but never require uvicorn.
    try:
        from services.mt5_gateway.settings import get_gateway_settings

        get_gateway_settings.cache_clear()
        settings = get_gateway_settings()
        host = settings.mt5_gateway_host or host
        port = int(settings.mt5_gateway_port or port)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Using env/default bind settings (%s)", exc)
    return host, port
