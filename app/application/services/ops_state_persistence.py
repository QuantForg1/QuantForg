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
import time
from collections.abc import Mapping
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

import httpx

from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = Lock()
_TABLE = "ite_ops_runtime_state"
_PG_CACHE_TTL_S = 15.0
_pg_state_cache: tuple[float, dict[str, Any]] | None = None

_VALID_TRADING_MODES = frozenset({"swing", "scalping", "alpha"})
# Unlabeled persisted "swing" is the pre-scalping code default that Start/Pause
# echoed into ops state. Only an explicit operator mode selection keeps swing.
_LEGACY_DEFAULT_MODE = "swing"
_AUTHORITATIVE_DEFAULT_MODE = "scalping"


def _trading_mode_explicit(value: Any) -> bool:
    if value is True or value == 1:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


def reset_postgres_state_cache() -> None:
    """Test helper — drop the short Postgres ops-state GET cache."""
    global _pg_state_cache
    _pg_state_cache = None


def resolve_persisted_trading_mode(
    state: Mapping[str, Any] | None,
) -> tuple[str, str]:
    """Resolve AutoTradePolicy trading_mode from persisted ops state.

    Returns ``(mode, source)`` where source is one of:
    ``missing_default``, ``persisted``, ``explicit``, ``legacy_swing_migrated``.

    Precedence:
    1. Missing / empty / invalid → scalping (authoritative code default)
    2. ``trading_mode_explicit=true`` → keep the persisted valid mode
    3. Unlabeled persisted ``swing`` → stale legacy default → scalping
    4. Other unlabeled valid modes (scalping, alpha) → keep
    """
    data = state if isinstance(state, Mapping) else {}
    raw = str(data.get("trading_mode") or "").strip().lower()
    explicit = _trading_mode_explicit(data.get("trading_mode_explicit"))
    if raw not in _VALID_TRADING_MODES:
        return _AUTHORITATIVE_DEFAULT_MODE, "missing_default"
    if explicit:
        return raw, "explicit"
    if raw == _LEGACY_DEFAULT_MODE:
        return _AUTHORITATIVE_DEFAULT_MODE, "legacy_swing_migrated"
    return raw, "persisted"


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


def load_postgres_state_strict() -> tuple[bool, bool, dict[str, Any], str | None]:
    """Load singleton payload without treating transport failure as empty.

    Returns ``(configured, ok, payload, error)``.
    ``ok=False`` means durable state could not be verified — callers must
    fail closed rather than interpret missing history as "never happened".
    Does not change ``_load_postgres_state`` swallow-to-empty semantics used
    by ops-mode restore.
    """
    cfg = _supabase_rest_config()
    if cfg is None:
        return False, True, {}, None
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
                return True, True, {}, None
            resp.raise_for_status()
            rows = resp.json()
    except Exception as exc:
        logger.warning("ops_state_postgres_strict_load_failed", error=str(exc))
        return True, False, {}, type(exc).__name__
    if not isinstance(rows, list) or not rows:
        return True, True, {}, None
    payload = rows[0].get("payload") if isinstance(rows[0], dict) else None
    result = payload if isinstance(payload, dict) else {}
    return True, True, dict(result), None


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
    global _pg_state_cache
    now = time.monotonic()
    cached = _pg_state_cache
    if cached is not None and (now - cached[0]) <= _PG_CACHE_TTL_S:
        return dict(cached[1])
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
                _pg_state_cache = (now, {})
                return {}
            resp.raise_for_status()
            rows = resp.json()
    except Exception as exc:
        logger.warning("ops_state_postgres_load_failed", error=str(exc))
        return {}
    if not isinstance(rows, list) or not rows:
        _pg_state_cache = (now, {})
        return {}
    payload = rows[0].get("payload") if isinstance(rows[0], dict) else None
    result = payload if isinstance(payload, dict) else {}
    _pg_state_cache = (now, dict(result))
    return result


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
        reset_postgres_state_cache()
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
    postgres_has_state = state.get("_hydrate_source") == "postgres"
    durable = postgres_has_state or is_volume_backed()
    resolved_mode, resolved_source = resolve_persisted_trading_mode(state)
    return {
        "durable": durable,
        "volume_backed": is_volume_backed(),
        "postgres_configured": pg_cfg,
        "postgres_has_state": postgres_has_state,
        "file_path": str(path),
        "file_present": path.is_file(),
        "hydrate_source": state.get("_hydrate_source", "empty"),
        "persisted_ops_mode": state.get("ops_mode"),
        "persisted_auto_trading_run_state": state.get("auto_trading_run_state"),
        "persisted_auto_trading_enabled": state.get("auto_trading_enabled"),
        "persisted_trading_mode": state.get("trading_mode"),
        "persisted_trading_mode_explicit": _trading_mode_explicit(
            state.get("trading_mode_explicit")
        ),
        "resolved_trading_mode": resolved_mode,
        "resolved_trading_mode_source": resolved_source,
        "persisted_max_open_positions": state.get("max_open_positions"),
    }
