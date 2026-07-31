"""MT5 Gateway single-instance protection (port 8765).

Prevents WinError 10048 by never binding when a healthy QuantForg gateway
already owns the listen port. Supports ``--restart`` for clean recycle.
"""

from __future__ import annotations

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

_HEALTH_TIMEOUT_SEC = 2.5
_PORT_RELEASE_TIMEOUT_SEC = 20.0
_PORT_RELEASE_POLL_SEC = 0.25
_POST_START_HEALTH_TIMEOUT_SEC = 30.0


@dataclass(frozen=True, slots=True)
class GatewayHealthSnapshot:
    """Normalized fields from a live ``GET /health`` response."""

    ok: bool
    gateway_version: str = "unknown"
    mt5_status: str = "unknown"
    broker: str = "unknown"
    session: str = "unknown"
    raw: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ListenerProbe:
    listening: bool
    pid: int | None = None
    health: GatewayHealthSnapshot | None = None


def health_url(host: str, port: int) -> str:
    # Bind host 0.0.0.0 / :: is not a connect target — probe loopback.
    connect_host = host
    if host in {"0.0.0.0", "::", "[::]", ""}:
        connect_host = "127.0.0.1"
    return f"http://{connect_host}:{int(port)}/health"


def port_is_listening(host: str, port: int, *, timeout: float = 0.5) -> bool:
    """Return True if something accepts TCP connections on host:port."""
    connect_host = "127.0.0.1" if host in {"0.0.0.0", "::", "[::]", ""} else host
    try:
        with socket.create_connection((connect_host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def find_listening_pid(port: int) -> int | None:
    """Best-effort owning PID for a TCP LISTEN on ``port`` (Windows + POSIX)."""
    port = int(port)
    if sys.platform.startswith("win"):
        return _find_pid_windows(port)
    return _find_pid_posix(port)


def _find_pid_windows(port: int) -> int | None:
    # Prefer netstat — available on all supported Windows gateway hosts.
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
        if "LISTENING" not in upper and "LISTEN" not in upper:
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
    # ss is common; fall back to lsof.
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
        # ss: users:(("python",pid=1234,fd=3))
        import re

        m = re.search(r"pid=(\d+)", text)
        if m:
            return int(m.group(1))
        m = re.search(r"\b(\d+)\b", text)
        # lsof COMMAND PID ...
        for line in text.splitlines():
            if "LISTEN" not in line.upper() and "IPv" not in line:
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
    """GET /health and normalize QuantForg gateway identity fields."""
    url = health_url(host, port)
    try:
        req = Request(url, method="GET", headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — local gateway only
            status = getattr(resp, "status", None) or resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return GatewayHealthSnapshot(ok=False, error=f"HTTP {exc.code}: {exc.reason}")
    except (URLError, TimeoutError, OSError) as exc:
        return GatewayHealthSnapshot(ok=False, error=str(exc))

    if int(status) != 200:
        return GatewayHealthSnapshot(ok=False, error=f"HTTP {status}")

    try:
        import json

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


def probe_listener(host: str, port: int) -> ListenerProbe:
    if not port_is_listening(host, port):
        return ListenerProbe(listening=False)
    pid = find_listening_pid(port)
    health = fetch_gateway_health(host, port)
    return ListenerProbe(listening=True, pid=pid, health=health)


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


def stop_gateway_process(pid: int, *, timeout: float = 10.0) -> None:
    """Stop a gateway PID safely (terminate → wait → kill if needed)."""
    if pid <= 0:
        raise ValueError("invalid pid")
    if pid == os.getpid():
        raise RuntimeError("refusing to stop the current process")

    logger.info("Stopping existing gateway pid=%s", pid)
    if sys.platform.startswith("win"):
        # Soft request first
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
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not port_is_listening(host, port):
            # Brief settle — Windows can report free then briefly reclaim.
            time.sleep(0.35)
            if not port_is_listening(host, port):
                return True
        time.sleep(_PORT_RELEASE_POLL_SEC)
    return not port_is_listening(host, port)


def wait_for_healthy_gateway(
    host: str,
    port: int,
    *,
    timeout: float = _POST_START_HEALTH_TIMEOUT_SEC,
) -> GatewayHealthSnapshot:
    deadline = time.monotonic() + timeout
    last = GatewayHealthSnapshot(ok=False, error="not checked")
    while time.monotonic() < deadline:
        if port_is_listening(host, port):
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
    """Gate gateway startup.

    Returns
    -------
    ``already_running``
        Healthy instance owns the port — caller must exit 0 (do not bind).
    ``start``
        Safe to start uvicorn (port free, or unhealthy peer stopped).
    """
    probe = probe_listener(host, port)

    if restart:
        if probe.listening:
            pid = probe.pid
            if pid is None:
                # Last resort: cannot identify PID — refuse silent double-bind.
                raise RuntimeError(
                    f"Port {port} is listening but PID could not be resolved. "
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
            logger.info("Gateway --restart: no listener on port %s", port)
        return "start"

    if not probe.listening:
        logger.info("No listener on port %s — starting gateway", port)
        return "start"

    health = probe.health
    if health is not None and health.ok:
        # Verify /health again before exiting (requirement 3).
        verified = fetch_gateway_health(host, port)
        if not verified.ok:
            logger.warning(
                "Initial health ok but re-verify failed (%s) — treating unhealthy",
                verified.error,
            )
            health = verified
        else:
            msg = format_already_running_message(pid=probe.pid, health=verified)
            print(msg, flush=True)
            print("Gateway already running", flush=True)
            logger.info(
                "Gateway already running pid=%s version=%s",
                probe.pid,
                verified.gateway_version,
            )
            return "already_running"

    # Unhealthy listener — stop safely and allow restart.
    pid = probe.pid
    err = health.error if health else "unknown"
    logger.warning(
        "Unhealthy gateway on port %s pid=%s error=%s — stopping for restart",
        port,
        pid,
        err,
    )
    print(
        f"Unhealthy QuantForg MT5 Gateway detected on port {port} "
        f"(PID: {pid if pid is not None else 'unknown'}). Restarting…",
        flush=True,
    )
    if pid is None:
        raise RuntimeError(
            f"Port {port} is occupied by an unhealthy process but PID is unknown. "
            "Stop it manually, then start the gateway again."
        )
    stop_gateway_process(pid)
    if not wait_for_port_release(host, port):
        raise RuntimeError(
            f"Port {port} did not release after stopping unhealthy PID {pid}"
        )
    return "start"
