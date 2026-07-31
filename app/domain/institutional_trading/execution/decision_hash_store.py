"""Durable decision-hash store — prevent duplicate OMS submits after restart."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = threading.Lock()
_DEFAULT_MAX = 10_000


def _path() -> Path:
    try:
        from core.config.settings import get_settings

        base = Path(getattr(get_settings(), "data_dir", None) or "data")
    except Exception:
        base = Path("data")
    try:
        from app.domain.institutional_trading.production_hardening.config import (
            DEFAULT_HARDENING_CONFIG,
        )

        name = getattr(
            DEFAULT_HARDENING_CONFIG,
            "decision_hash_filename",
            "execution_decision_hashes.json",
        )
    except Exception:
        name = "execution_decision_hashes.json"
    return base / name


def load_executed_hashes(
    *, max_hashes: int = _DEFAULT_MAX
) -> tuple[set[str], list[str]]:
    """Load persisted decision hashes (order preserved for eviction)."""
    path = _path()
    if not path.exists():
        return set(), []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw.get("hashes", []) if isinstance(raw, dict) else raw
        if not isinstance(rows, list):
            return set(), []
        order = [str(h) for h in rows if h][-max_hashes:]
        return set(order), order
    except Exception:
        logger.exception("decision_hash_load_failed")
        return set(), []


def persist_executed_hashes(
    hashes_in_order: list[str],
    *,
    max_hashes: int = _DEFAULT_MAX,
) -> None:
    """Persist decision hashes for cold restart dedupe."""
    path = _path()
    try:
        trimmed = list(hashes_in_order[-max_hashes:])
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "updated_at": datetime.now(UTC).isoformat(),
            "hashes": trimmed,
        }
        with _LOCK:
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("decision_hash_persist_failed")
