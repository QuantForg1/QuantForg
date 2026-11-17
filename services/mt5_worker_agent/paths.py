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


def _lexical_abs(path: Path | str) -> Path:
    """Absolute, '..'-normalised path WITHOUT following links."""
    p = Path(path)
    p = p if p.is_absolute() else Path.cwd() / p
    return Path(os.path.normpath(str(p)))


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _under_program_files(path: Path) -> bool:
    return any(part.lower().startswith("program files") for part in path.parts)


def assert_worker_terminal_path(path: Path | str) -> Path:
    """Reject any terminal that is not an isolated slot install.

    Refused unless QF_ALLOW_WORKER_ON_LIVE_TERMINAL is set (it must stay
    false in Production):
    - the configured LIVE terminal (QF_LIVE_MT5_TERMINAL_PATH);
    - any terminal under a "Program Files" folder, where installed broker
      terminals live (the owner's Weltrade terminal may not be at the default
      path, so the LIVE path setting alone is not enough; 17 Nov 2026);
    - any terminal outside the slot root (QF_MT5_SLOT_ROOT). The check uses
      the path as configured and, for Program Files, its resolved target, so
      a slot link cannot point at an installed terminal.
    """
    raw = _lexical_abs(path)
    resolved = Path(path).resolve()
    live = live_terminal_path().resolve()
    if not allow_live_terminal_override():
        if resolved == live:
            raise ValueError(
                "Refusing to use the LIVE MetaTrader terminal path for a worker "
                "slot. Prepare an isolated portable install under "
                "QF_MT5_SLOT_ROOT instead."
            )
        if _under_program_files(resolved) or _under_program_files(raw):
            raise ValueError(
                "Refusing a terminal under Program Files for a worker slot: "
                "installed broker terminals (including the LIVE one) live "
                "there. Use an isolated portable install under QF_MT5_SLOT_ROOT."
            )
        root = _lexical_abs(slot_root())
        if not _is_within(raw, root):
            raise ValueError(
                f"Refusing a worker terminal outside the slot root {root}."
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
