"""Durable Ops mode + Demo certification persistence.

Restores official workflow state across process restarts.
Never fabricates certification. Never forces LIVE.

Backends (in priority order on load):
1. Postgres ``ite_ops_runtime_state`` (survives Railway redeploys)
2. Local / volume JSON file (``QUANTFORG_OPS_STATE_PATH`` or Railway volume)

Saves write to both when available.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

import httpx

from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = Lock()
_TABLE = "ite_ops_runtime_state"


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


def is_volume_backed() -> bool:
    if (os.environ.get("QUANTFORG_OPS_STATE_PATH") or "").strip():
        return True
    return bool((os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or "").strip())


def _supabase_rest_config() -> tuple[str, str] | None:
    """Return (base_rest_url, service_or_api_key) or None when unconfigured."""
    try:
        from core.config.settings import get_settings

        settings = get_settings()
    except Exception:
        return None
    url = (settings.supabase_url or "").strip().rstrip("/")
    if not url:
        return None
    key = ""
    if settings.supabase_service_role_key is not None:
        key = settings.supabase_service_role_key.get_secret_value().strip()
    if not key:
        api = settings.supabase_api_key
        if api is not None:
            key = api if isinstance(api, str) else str(api)
    if not key:
        return None
    return f"{url}/rest/v1", key


def _load_postgres_state() -> dict[str, Any]:
    cfg = _supabase_rest_config()
    if cfg is None:
        return {}
    base, key = cfg
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(
                f"{base}/{_TABLE}",
                params={"singleton": "eq.true", "select": "payload"},
                headers=headers,
            )
            if resp.status_code == 404:
                return {}
            resp.raise_for_status()
            rows = resp.json()
    except Exception as exc:
        logger.warning("ops_state_postgres_load_failed", error=str(exc))
        return {}
    if not isinstance(rows, list) or not rows:
        return {}
    payload = rows[0].get("payload") if isinstance(rows[0], dict) else None
    return payload if isinstance(payload, dict) else {}


def _save_postgres_state(state: dict[str, Any]) -> bool:
    cfg = _supabase_rest_config()
    if cfg is None:
        return False
    base, key = cfg
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    body = {"singleton": True, "payload": state}
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(
                f"{base}/{_TABLE}",
                params={"on_conflict": "singleton"},
                headers=headers,
                json=body,
            )
            if resp.status_code in {200, 201, 204}:
                return True
            # Some PostgREST setups prefer PATCH upsert
            if resp.status_code in {409, 400}:
                patch = client.patch(
                    f"{base}/{_TABLE}",
                    params={"singleton": "eq.true"},
                    headers={
                        **headers,
                        "Prefer": "return=minimal",
                    },
                    json={"payload": state},
                )
                if patch.status_code in {200, 204}:
                    return True
                logger.warning(
                    "ops_state_postgres_patch_failed",
                    status=patch.status_code,
                    body=patch.text[:200],
                )
                return False
            logger.warning(
                "ops_state_postgres_save_failed",
                status=resp.status_code,
                body=resp.text[:200],
            )
            return False
    except Exception as exc:
        logger.warning("ops_state_postgres_save_failed", error=str(exc))
        return False


def _record_mode_transition(
    *,
    from_mode: str | None,
    to_mode: str,
    reason: str,
) -> None:
    """Best-effort append to existing ite_ops_mode_transitions (audit)."""
    cfg = _supabase_rest_config()
    if cfg is None or not to_mode:
        return
    base, key = cfg
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    row = {
        "id": str(uuid4()),
        "from_mode": (from_mode or "UNKNOWN").upper(),
        "to_mode": to_mode.upper(),
        "operator": "ops_state_persistence",
        "reason": reason or "persisted",
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            client.post(
                f"{base}/ite_ops_mode_transitions",
                headers=headers,
                json=row,
            )
    except Exception as exc:
        logger.debug("ops_mode_transition_record_failed", error=str(exc))


def load_ops_state() -> dict[str, Any]:
    """Load durable ops state — Postgres preferred, file as merge fallback."""
    file_state: dict[str, Any] = {}
    path = ops_state_path()
    try:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                file_state = raw
    except Exception as exc:
        logger.warning("ops_state_load_failed", path=str(path), error=str(exc))

    pg_state = _load_postgres_state()
    # Postgres wins on conflicting keys (survives redeploy); file fills gaps.
    merged = {**file_state, **pg_state}
    if pg_state:
        merged["_hydrate_source"] = "postgres"
    elif file_state:
        merged["_hydrate_source"] = "file"
    else:
        merged["_hydrate_source"] = "empty"
    return merged


def save_ops_state(patch: dict[str, Any]) -> None:
    """Merge patch into durable ops state (file + Postgres when available)."""
    path = ops_state_path()
    with _LOCK:
        current = load_ops_state()
        # Drop diagnostic-only keys from persistence payload
        current.pop("_hydrate_source", None)
        prev_mode = str(current.get("ops_mode") or "").strip().upper() or None
        current.update({k: v for k, v in patch.items() if v is not None})
        current.pop("_hydrate_source", None)

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

        pg_ok = _save_postgres_state(current)
        new_mode = str(current.get("ops_mode") or "").strip().upper()
        if pg_ok and new_mode and new_mode != prev_mode:
            _record_mode_transition(
                from_mode=prev_mode,
                to_mode=new_mode,
                reason=str(current.get("ops_mode_reason") or "ops_mode_persist"),
            )


def ops_state_diagnostics() -> dict[str, Any]:
    """Operator-facing persistence health — never includes secrets."""
    path = ops_state_path()
    state = load_ops_state()
    pg_cfg = _supabase_rest_config() is not None
    pg_state = _load_postgres_state() if pg_cfg else {}
    durable = bool(pg_state) or is_volume_backed()
    return {
        "durable": durable,
        "volume_backed": is_volume_backed(),
        "postgres_configured": pg_cfg,
        "postgres_has_state": bool(pg_state),
        "file_path": str(path),
        "file_present": path.is_file(),
        "hydrate_source": state.get("_hydrate_source", "empty"),
        "persisted_ops_mode": state.get("ops_mode"),
        "persisted_auto_trading_run_state": state.get("auto_trading_run_state"),
        "persisted_auto_trading_enabled": state.get("auto_trading_enabled"),
    }
