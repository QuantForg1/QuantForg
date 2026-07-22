"""Durable Ops mode + Demo certification persistence.

Restores official workflow state across process restarts.
Never fabricates certification. Never forces LIVE.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = Lock()


def ops_state_path() -> Path:
    raw = (os.environ.get("QUANTFORG_OPS_STATE_PATH") or "").strip()
    if raw:
        return Path(raw)
    volume = (os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or "").strip()
    if volume:
        return Path(volume) / "quantforg_ops_state.json"
    # Local / ephemeral fallback — better than pure memory within one host disk
    base = Path(os.environ.get("QUANTFORG_DATA_DIR") or "data")
    return base / "ops_state.json"


def load_ops_state() -> dict[str, Any]:
    path = ops_state_path()
    try:
        if not path.is_file():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception as exc:
        logger.warning("ops_state_load_failed", path=str(path), error=str(exc))
        return {}


def save_ops_state(patch: dict[str, Any]) -> None:
    """Merge patch into durable ops state file (atomic replace)."""
    path = ops_state_path()
    with _LOCK:
        current = load_ops_state()
        current.update({k: v for k, v in patch.items() if v is not None})
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(current, indent=2, default=str),
                encoding="utf-8",
            )
            tmp.replace(path)
        except Exception as exc:
            logger.warning("ops_state_save_failed", path=str(path), error=str(exc))
