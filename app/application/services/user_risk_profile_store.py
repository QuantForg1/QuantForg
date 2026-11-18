"""Persistent per-user risk profiles (``user_risk_profiles``) and their audit trail.

One row per user. ``settings`` holds only the fields the user customised;
every other field resolves to the approved default. Writes are optimistic
(``version``) so two concurrent saves cannot silently overwrite each other.
Every change is appended to ``user_risk_profile_events``. A read failure is
never replaced by another user's profile: callers fail closed.
"""

from __future__ import annotations

import json
import os
import threading
import time
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.domain.institutional_trading.risk_profile import (
    EffectiveProfile,
    resolve_profile,
    validate_profile_changes,
)
from core.logging import get_logger

logger = get_logger(__name__)

CACHE_TTL_SECONDS = 15.0
_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, dict[str, Any], int, str | None]] = {}
_MEMORY: dict[str, dict[str, Any]] = {}
_MEMORY_EVENTS: list[dict[str, Any]] = []


class ProfileStoreError(RuntimeError):
    """The profile could not be read or written."""


class ProfileConflictError(ProfileStoreError):
    """The profile changed since the caller read it."""


class ProfileValidationError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


def _testing() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    try:
        from core.config.settings import get_settings

        return bool(getattr(get_settings(), "is_testing", False))
    except Exception:
        return False


def _pg() -> tuple[Any, Any, Any]:
    from app.infrastructure.persistence.direct_postgres import (
        direct_postgres_available,
        execute,
        fetch,
    )

    return direct_postgres_available, execute, fetch


def _use_memory() -> bool:
    available, _e, _f = _pg()
    try:
        if available():
            return False
    except Exception:
        return _testing()
    return _testing()


def reset_for_tests() -> None:
    with _LOCK:
        _CACHE.clear()
        _MEMORY.clear()
        _MEMORY_EVENTS.clear()


def invalidate(user_id: UUID | str | None = None) -> None:
    with _LOCK:
        if user_id is None:
            _CACHE.clear()
        else:
            _CACHE.pop(str(user_id), None)


def _jsonable(values: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in values.items():
        out[key] = format(value, "f") if isinstance(value, Decimal) else value
    return out


def _load_row(user_id: str) -> tuple[dict[str, Any], int, str | None]:
    """(custom settings, version, updated_at). Missing row -> ({}, 0, None)."""
    if _use_memory():
        row = _MEMORY.get(user_id)
        if not row:
            return {}, 0, None
        return dict(row["settings"]), int(row["version"]), row.get("updated_at")
    available, _execute, fetch = _pg()
    if not available():
        raise ProfileStoreError("profile_storage_unavailable")
    try:
        rows = fetch(
            """
            SELECT settings, version, updated_at
              FROM public.user_risk_profiles
             WHERE user_id = $1::uuid
            """,
            user_id,
        )
    except Exception as exc:
        raise ProfileStoreError(f"profile_read_failed:{type(exc).__name__}") from exc
    if not rows:
        return {}, 0, None
    settings = rows[0].get("settings") or {}
    if isinstance(settings, str):
        settings = json.loads(settings)
    if not isinstance(settings, dict):
        raise ProfileStoreError("profile_settings_invalid")
    updated = rows[0].get("updated_at")
    return (
        dict(settings),
        int(rows[0].get("version") or 0),
        (str(updated) if updated is not None else None),
    )


def load_settings(
    user_id: UUID | str, *, use_cache: bool = True
) -> tuple[dict[str, Any], int, str | None]:
    key = str(user_id)
    now = time.monotonic()
    if use_cache:
        with _LOCK:
            hit = _CACHE.get(key)
        if hit and now - hit[0] < CACHE_TTL_SECONDS:
            return dict(hit[1]), hit[2], hit[3]
    settings, version, updated = _load_row(key)
    with _LOCK:
        _CACHE[key] = (now, dict(settings), version, updated)
    return settings, version, updated


def effective_profile(
    user_id: UUID | str, *, use_cache: bool = True
) -> EffectiveProfile:
    """Effective profile of exactly this user. Raises ProfileStoreError."""
    settings, version, _updated = load_settings(user_id, use_cache=use_cache)
    return resolve_profile(settings, version=version)


def _record_event(
    *,
    user_id: str,
    actor_id: str | None,
    action: str,
    before: dict[str, Any],
    after: dict[str, Any],
    version: int,
    reason: str,
) -> None:
    event = {
        "user_id": user_id,
        "actor_id": actor_id,
        "action": action,
        "before": _jsonable(before),
        "after": _jsonable(after),
        "version": version,
        "reason": reason[:300],
    }
    if _use_memory():
        _MEMORY_EVENTS.append(event | {"created_at": time.time()})
        return
    _available, execute, _fetch = _pg()
    execute(
        """
        INSERT INTO public.user_risk_profile_events
          (user_id, actor_id, action, before, after, version, reason)
        VALUES ($1::uuid, $2::uuid, $3, $4::jsonb, $5::jsonb, $6, $7)
        """,
        user_id,
        actor_id,
        action,
        json.dumps(event["before"]),
        json.dumps(event["after"]),
        version,
        event["reason"],
    )


def _write(
    *,
    user_id: str,
    settings: dict[str, Any],
    expected_version: int,
    actor_id: str | None,
) -> int:
    new_version = expected_version + 1
    payload = _jsonable(settings)
    if _use_memory():
        with _LOCK:
            row = _MEMORY.get(user_id)
            current = int(row["version"]) if row else 0
            if current != expected_version:
                raise ProfileConflictError("profile_version_conflict")
            _MEMORY[user_id] = {
                "settings": payload,
                "version": new_version,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        return new_version
    available, execute, _fetch = _pg()
    if not available():
        raise ProfileStoreError("profile_storage_unavailable")
    if expected_version == 0:
        status = execute(
            """
            INSERT INTO public.user_risk_profiles
              (user_id, settings, version, schema_version, updated_by)
            VALUES ($1::uuid, $2::jsonb, 1, 1, $3::uuid)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
            json.dumps(payload),
            actor_id,
        )
    else:
        status = execute(
            """
            UPDATE public.user_risk_profiles
               SET settings = $2::jsonb,
                   version = version + 1,
                   updated_by = $4::uuid,
                   updated_at = timezone('utc', now())
             WHERE user_id = $1::uuid AND version = $3
            """,
            user_id,
            json.dumps(payload),
            expected_version,
            actor_id,
        )
    if not str(status).strip().endswith(" 1"):
        raise ProfileConflictError("profile_version_conflict")
    return new_version


def save_profile(
    user_id: UUID | str,
    changes: dict[str, Any],
    *,
    actor_id: UUID | str | None,
    expected_version: int | None = None,
    reason: str = "user_edit",
) -> EffectiveProfile:
    """Validate and persist a partial update for exactly this user."""
    key = str(user_id)
    current, version, _updated = load_settings(key, use_cache=False)
    if expected_version is not None and int(expected_version) != version:
        raise ProfileConflictError("profile_version_conflict")
    checked = validate_profile_changes(current, changes)
    if not checked.ok:
        raise ProfileValidationError(checked.errors)
    new_version = _write(
        user_id=key,
        settings=checked.values,
        expected_version=version,
        actor_id=str(actor_id) if actor_id else None,
    )
    invalidate(key)
    try:
        _record_event(
            user_id=key,
            actor_id=str(actor_id) if actor_id else None,
            action="update",
            before=current,
            after=checked.values,
            version=new_version,
            reason=reason,
        )
    except Exception as exc:  # the saved profile stands; the trail gap is logged
        logger.warning("risk_profile_event_failed", error=type(exc).__name__)
    logger.info(
        "risk_profile_saved",
        user_id=key,
        version=new_version,
        custom_keys=sorted(checked.values),
    )
    return resolve_profile(checked.values, version=new_version)


def reset_profile(
    user_id: UUID | str,
    *,
    actor_id: UUID | str | None,
    expected_version: int | None = None,
) -> EffectiveProfile:
    """Restore every field to the approved default."""
    key = str(user_id)
    current, version, _updated = load_settings(key, use_cache=False)
    if expected_version is not None and int(expected_version) != version:
        raise ProfileConflictError("profile_version_conflict")
    new_version = _write(
        user_id=key,
        settings={},
        expected_version=version,
        actor_id=str(actor_id) if actor_id else None,
    )
    invalidate(key)
    try:
        _record_event(
            user_id=key,
            actor_id=str(actor_id) if actor_id else None,
            action="reset",
            before=current,
            after={},
            version=new_version,
            reason="reset_to_defaults",
        )
    except Exception as exc:
        logger.warning("risk_profile_event_failed", error=type(exc).__name__)
    return resolve_profile({}, version=new_version)


def list_events(user_id: UUID | str, *, limit: int = 30) -> list[dict[str, Any]]:
    key = str(user_id)
    lim = max(1, min(int(limit), 100))
    if _use_memory():
        rows = [e for e in _MEMORY_EVENTS if e["user_id"] == key]
        return list(reversed(rows))[:lim]
    available, _execute, fetch = _pg()
    if not available():
        return []
    rows = fetch(
        """
        SELECT action, before, after, version, reason, created_at
          FROM public.user_risk_profile_events
         WHERE user_id = $1::uuid
         ORDER BY created_at DESC
         LIMIT $2
        """,
        key,
        lim,
    )
    out = []
    for row in rows:
        item = dict(row)
        for col in ("before", "after"):
            if isinstance(item.get(col), str):
                item[col] = json.loads(item[col])
        item["created_at"] = str(item.get("created_at") or "")
        out.append(item)
    return out
