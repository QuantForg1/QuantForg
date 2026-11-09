"""Local MT5 path policy — never hijack the LIVE Weltrade terminal.

Worker slots MUST use dedicated portable installs under the slot root.
The default Program Files terminal path is blocked unless an explicit
danger override is set (forbidden in normal local/demo workflows).
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_LIVE_TERMINAL = Path(r"C:\Program Files\MetaTrader 5\terminal64.exe")
DEFAULT_SLOT_ROOT = Path(r"C:\QuantForg-Workspace\mt5_worker_slots")


def slot_root() -> Path:
    raw = (os.environ.get("QF_MT5_SLOT_ROOT") or "").strip()
    return Path(raw) if raw else DEFAULT_SLOT_ROOT


def live_terminal_path() -> Path:
    raw = (os.environ.get("QF_LIVE_MT5_TERMINAL_PATH") or "").strip()
    return Path(raw) if raw else DEFAULT_LIVE_TERMINAL


def allow_live_terminal_override() -> bool:
    """Dangerous. Default false — workers must not attach to LIVE terminal."""
    return (
        os.environ.get("QF_ALLOW_WORKER_ON_LIVE_TERMINAL") or ""
    ).strip().lower() in {
        "1",
        "true",
        "yes",
    }


def assert_worker_terminal_path(path: Path | str) -> Path:
    """Reject the LIVE Program Files terminal unless explicitly overridden."""
    resolved = Path(path).resolve()
    live = live_terminal_path().resolve()
    if resolved == live and not allow_live_terminal_override():
        raise ValueError(
            "Refusing to use the LIVE MetaTrader terminal path for a worker slot. "
            "Prepare an isolated portable install under QF_MT5_SLOT_ROOT instead."
        )
    if not resolved.is_file():
        raise FileNotFoundError(f"terminal64.exe not found: {resolved}")
    return resolved


def slot_dir(slot_id: str) -> Path:
    safe = "".join(ch for ch in slot_id.strip().lower() if ch.isalnum() or ch in "-_")
    if not safe:
        raise ValueError("slot_id is required")
    return slot_root() / safe


def slot_terminal_exe(slot_id: str) -> Path:
    return slot_dir(slot_id) / "terminal64.exe"
