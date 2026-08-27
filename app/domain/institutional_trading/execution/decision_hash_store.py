"""Durable decision-hash store — prevent duplicate OMS submits after restart.

Persistence order:
1. Existing Postgres ``ite_ops_runtime_state`` JSON payload (Railway-durable)
2. Atomic local/volume JSON file

Never interpret a failed durable load as "no orders happened".
Does not change hash identity / duplicate-detection criteria.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = threading.Lock()
_DEFAULT_MAX = 10_000
HASH_PAYLOAD_KEY = "execution_decision_hashes"


@dataclass(frozen=True, slots=True)
class DecisionHashLoad:
    hashes: set[str]
    order: list[str]
    verified: bool
    source: str
    durable: bool
    error: str | None = None


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


def _rows_from_blob(raw: Any, *, max_hashes: int) -> list[str]:
    if isinstance(raw, dict):
        rows = raw.get("hashes", [])
    else:
        rows = raw
    if not isinstance(rows, list):
        return []
    return [str(h) for h in rows if h][-max_hashes:]


def _union_order(*sequences: list[str], max_hashes: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for seq in sequences:
        for item in seq:
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
    return out[-max_hashes:]


def _load_file_hashes(*, max_hashes: int) -> tuple[list[str], bool, str | None]:
    """Return (order, parse_ok, error). Missing file is verified empty."""
    path = _path()
    if not path.exists():
        return [], True, None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return _rows_from_blob(raw, max_hashes=max_hashes), True, None
    except Exception as exc:
        logger.exception("decision_hash_load_failed")
        return [], False, type(exc).__name__


def load_decision_hash_report(
    *, max_hashes: int = _DEFAULT_MAX
) -> DecisionHashLoad:
    """Load hashes with an explicit verification flag."""
    file_order, file_ok, file_err = _load_file_hashes(max_hashes=max_hashes)
    configured = False
    pg_ok = True
    pg_order: list[str] = []
    pg_err: str | None = None
    durable = False
    try:
        from app.application.services.ops_state_persistence import (
            is_volume_backed,
            load_postgres_state_strict,
        )

        durable = bool(is_volume_backed())
        configured, pg_ok, payload, pg_err = load_postgres_state_strict()
        if configured and pg_ok:
            blob = payload.get(HASH_PAYLOAD_KEY)
            pg_order = _rows_from_blob(blob, max_hashes=max_hashes)
            durable = True
    except Exception as exc:
        logger.exception("decision_hash_postgres_probe_failed")
        # If the persistence module cannot be imported, file-only is still
        # valid for unit tests. A configured-but-failed GET is handled above.
        if configured:
            pg_ok = False
            pg_err = pg_err or type(exc).__name__

    if configured and not pg_ok:
        return DecisionHashLoad(
            hashes=set(),
            order=[],
            verified=False,
            source="postgres_unverified",
            durable=False,
            error=pg_err or "postgres_load_failed",
        )
    if not file_ok:
        # Corrupt local file: if Postgres verified, keep durable hashes only.
        if configured and pg_ok:
            return DecisionHashLoad(
                hashes=set(pg_order),
                order=pg_order,
                verified=True,
                source="postgres",
                durable=True,
                error=file_err,
            )
        return DecisionHashLoad(
            hashes=set(),
            order=[],
            verified=False,
            source="file_unverified",
            durable=durable,
            error=file_err or "file_load_failed",
        )

    order = _union_order(file_order, pg_order, max_hashes=max_hashes)
    if configured and pg_ok and pg_order:
        source = "postgres" if not file_order else "merged"
    elif file_order:
        source = "file"
    else:
        source = "empty"
    return DecisionHashLoad(
        hashes=set(order),
        order=order,
        verified=True,
        source=source,
        durable=durable or (configured and pg_ok),
        error=None,
    )


def load_executed_hashes(
    *, max_hashes: int = _DEFAULT_MAX
) -> tuple[set[str], list[str]]:
    """Load persisted decision hashes (order preserved for eviction)."""
    report = load_decision_hash_report(max_hashes=max_hashes)
    return report.hashes, report.order


def persist_executed_hashes(
    hashes_in_order: list[str],
    *,
    max_hashes: int = _DEFAULT_MAX,
) -> None:
    """Persist decision hashes for cold restart dedupe (file + Postgres merge)."""
    trimmed = list(hashes_in_order[-max_hashes:])
    payload: dict[str, Any] = {
        "updated_at": datetime.now(UTC).isoformat(),
        "hashes": trimmed,
    }
    path = _path()
    with _LOCK:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(path)
        except Exception:
            logger.exception("decision_hash_persist_failed")
        try:
            from app.application.services.ops_state_persistence import (
                _supabase_rest_config,
                is_volume_backed,
                save_ops_state,
            )

            if _supabase_rest_config() is not None or is_volume_backed():
                save_ops_state({HASH_PAYLOAD_KEY: payload})
        except Exception:
            logger.exception("decision_hash_postgres_persist_failed")
