"""Portable MT5 slot prepare / start / stop (local Windows).

Copies the official MT5 install into an isolated directory and launches
``terminal64.exe /portable`` so each worker has its own data tree.

Never starts or stops the LIVE Program Files terminal.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from services.mt5_worker_agent.paths import (
    assert_worker_terminal_path,
    live_terminal_path,
    slot_dir,
    slot_terminal_exe,
)

logger = logging.getLogger("quantforg.mt5_worker_agent.slots")

_SOURCE_INSTALL = Path(r"C:\Program Files\MetaTrader 5")
_SYSTEM32 = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32"
_POWERSHELL = str(_SYSTEM32 / "WindowsPowerShell" / "v1.0" / "powershell.exe")
_TASKKILL = str(_SYSTEM32 / "taskkill.exe")


@dataclass(frozen=True, slots=True)
class SlotStatus:
    slot_id: str
    prepared: bool
    terminal_exe: str
    process_running: bool
    pid: int | None
    portable: bool
    updated_at: str


def _min_free_bytes_for_slots(count: int) -> int:
    # ~0.5 GiB per portable copy + headroom for charts/history.
    return int(count * 0.6 * 1024**3) + 512 * 1024**2


def disk_free_bytes(path: Path) -> int:
    usage = shutil.disk_usage(path if path.exists() else path.anchor)
    return int(usage.free)


def prepare_portable_slot(
    slot_id: str,
    *,
    source: Path | None = None,
    force: bool = False,
) -> Path:
    """Create an isolated portable MT5 copy for ``slot_id``.

    Refuses if free disk is insufficient. Never modifies the LIVE install.
    """
    src = source or _SOURCE_INSTALL
    if not (src / "terminal64.exe").is_file():
        raise FileNotFoundError(f"MT5 source install missing: {src}")

    dest = slot_dir(slot_id)
    free = disk_free_bytes(dest.parent if dest.parent.exists() else Path(dest.anchor))
    need = _min_free_bytes_for_slots(1)
    if free < need:
        raise OSError(
            f"Insufficient disk free={free} need>={need} for portable slot {slot_id}"
        )

    live = live_terminal_path().resolve()
    if src.resolve() == live.parent.resolve():
        logger.info(
            "preparing_portable_slot slot=%s from_live_install=copy_only "
            "(LIVE process not modified)",
            slot_id,
        )

    if dest.exists() and not force:
        exe = slot_terminal_exe(slot_id)
        if exe.is_file():
            assert_worker_terminal_path(exe)
            logger.info("portable_slot_exists slot=%s path=%s", slot_id, dest)
            return dest
        raise FileExistsError(f"Slot directory exists but incomplete: {dest}")

    if dest.exists() and force:
        # Never delete if it somehow points at Program Files.
        if dest.resolve() == live.parent.resolve():
            raise RuntimeError("Refusing to wipe LIVE MT5 install directory")
        shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    # Copytree without following links; skip uninstallers if needed.
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns("uninstall.exe", "*.log", "Logs", "Tester"),
        dirs_exist_ok=False,
    )
    # Portable marker file (some builds honor this; we also pass /portable).
    (dest / "portable").write_text("1\n", encoding="utf-8")
    exe = assert_worker_terminal_path(slot_terminal_exe(slot_id))
    logger.info("portable_slot_prepared slot=%s exe=%s", slot_id, exe)
    return dest


def _list_terminal_processes() -> list[tuple[int, str]]:
    """Return (pid, executable_path) for terminal64/terminal via CIM."""
    script = (
        "Get-CimInstance Win32_Process -Filter "
        "\"Name='terminal64.exe' OR Name='terminal.exe'\" | "
        "Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(  # noqa: S603
            [
                _POWERSHELL,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    raw = (completed.stdout or "").strip()
    if not raw:
        return []
    import json

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    rows = data if isinstance(data, list) else [data]
    out: list[tuple[int, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = row.get("ProcessId")
        path = row.get("ExecutablePath") or ""
        if pid is None:
            continue
        try:
            out.append((int(pid), str(path)))
        except (TypeError, ValueError):
            continue
    return out


def _find_slot_process(slot_id: str) -> tuple[int | None, bool]:
    exe = str(slot_terminal_exe(slot_id).resolve()).lower()
    for pid, path in _list_terminal_processes():
        if (path or "").lower() == exe:
            return pid, True
    return None, False


def start_slot_terminal(slot_id: str) -> int:
    """Start portable terminal for the slot. Does not login."""
    exe = assert_worker_terminal_path(slot_terminal_exe(slot_id))
    pid, running = _find_slot_process(slot_id)
    if running and pid is not None:
        logger.info("slot_terminal_already_running slot=%s pid=%s", slot_id, pid)
        return pid
    # Detached process; /portable keeps data inside the slot directory.
    proc = subprocess.Popen(  # noqa: S603
        [str(exe), "/portable"],
        cwd=str(exe.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    logger.info("slot_terminal_started slot=%s pid=%s", slot_id, proc.pid)
    return int(proc.pid)


def stop_slot_terminal(slot_id: str) -> bool:
    """Stop only this slot's terminal process. Never touches LIVE path."""
    exe = str(slot_terminal_exe(slot_id).resolve()).lower()
    live = str(live_terminal_path().resolve()).lower()
    if exe == live:
        raise RuntimeError("Refusing to stop LIVE terminal via slot manager")
    stopped = False
    for pid, path in _list_terminal_processes():
        if (path or "").lower() != exe:
            continue
        completed = subprocess.run(  # noqa: S603
            [_TASKKILL, "/PID", str(pid), "/T"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode == 0:
            stopped = True
            logger.info("slot_terminal_stopped slot=%s pid=%s", slot_id, pid)
    return stopped


def slot_status(slot_id: str) -> SlotStatus:
    exe = slot_terminal_exe(slot_id)
    prepared = exe.is_file()
    pid, running = _find_slot_process(slot_id) if prepared else (None, False)
    return SlotStatus(
        slot_id=slot_id,
        prepared=prepared,
        terminal_exe=str(exe),
        process_running=running,
        pid=pid,
        portable=prepared and (slot_dir(slot_id) / "portable").is_file(),
        updated_at=datetime.now(UTC).isoformat(),
    )


def list_configured_slot_ids() -> list[str]:
    raw = (os.environ.get("QF_MT5_LOCAL_SLOTS") or "demo-a,demo-b,demo-c").strip()
    return [part.strip() for part in raw.split(",") if part.strip()]
