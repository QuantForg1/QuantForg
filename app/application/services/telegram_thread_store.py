"""Durable Telegram thread + seen-id mapping.

Observability only. Never participates in Risk, OMS, MT5, or PME policy.
Restart must not replay public channel history as new messages.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from threading import Lock
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = Lock()
_MAX_ENTRIES = 2048
_SEEN_TTL_SECONDS = 30 * 24 * 3600
_cache: dict[str, Any] | None = None


def telegram_threads_path() -> Path:
    raw = (os.environ.get("QUANTFORG_TELEGRAM_THREADS_PATH") or "").strip()
    if raw:
        return Path(raw)
    from app.application.services.ops_state_persistence import ops_state_path

    return ops_state_path().with_name("telegram_threads.json")


def reset_telegram_threads_for_tests() -> None:
    global _cache
    with _LOCK:
        _cache = _empty()


def drop_telegram_threads_cache() -> None:
    """Simulate process restart: next read loads from disk."""
    global _cache
    with _LOCK:
        _cache = None


def _empty() -> dict[str, Any]:
    return {"version": 1, "message_ids": {}, "seen": {}, "tickets": {}}


def _load_unlocked() -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    path = telegram_threads_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            _cache = {
                "version": 1,
                "message_ids": {
                    str(k): int(v)
                    for k, v in dict(raw.get("message_ids") or {}).items()
                    if str(k).strip()
                    and str(v).strip().lstrip("-").isdigit()
                    and int(v) > 0
                },
                "seen": {
                    str(k): float(v)
                    for k, v in dict(raw.get("seen") or {}).items()
                    if str(k).strip()
                },
                "tickets": {
                    str(k): str(v)
                    for k, v in dict(raw.get("tickets") or {}).items()
                    if str(k).strip() and str(v).strip()
                },
            }
            return _cache
    except FileNotFoundError:
        pass
    except Exception:
        logger.exception("telegram_threads_load_failed")
    _cache = _empty()
    return _cache


def _save_unlocked(store: dict[str, Any]) -> None:
    try:
        path = telegram_threads_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(store, separators=(",", ":"), ensure_ascii=True),
            encoding="utf-8",
        )
        tmp.replace(path)
    except Exception:
        logger.exception("telegram_threads_save_failed")


def _prune(store: dict[str, Any]) -> None:
    now = time.time()
    seen = store["seen"]
    stale = [key for key, exp in seen.items() if float(exp) <= now]
    for key in stale:
        seen.pop(key, None)
    for bucket in ("seen", "message_ids", "tickets"):
        data = store[bucket]
        while len(data) > _MAX_ENTRIES:
            data.pop(next(iter(data)))


def persisted_seen_ids() -> set[str]:
    with _LOCK:
        store = _load_unlocked()
        now = time.time()
        return {key for key, exp in store["seen"].items() if float(exp) > now}


def mark_event_seen(event_id: str) -> None:
    key = str(event_id or "").strip()
    if not key:
        return
    with _LOCK:
        store = _load_unlocked()
        store["seen"][key] = time.time() + _SEEN_TTL_SECONDS
        _prune(store)
        _save_unlocked(store)


def lookup_message_id(
    *,
    ticket: str | None = None,
    signal_id: str | None = None,
) -> int | None:
    with _LOCK:
        store = _load_unlocked()
        ids = store["message_ids"]
        for raw in (ticket, signal_id):
            text = str(raw or "").strip()
            if not text:
                continue
            for key in (f"ticket:{text}", f"signal:{text}", text):
                found = ids.get(key)
                if found:
                    try:
                        n = int(found)
                    except (TypeError, ValueError):
                        continue
                    if n > 0:
                        return n
        return None


def bind_thread(
    *,
    message_id: int,
    ticket: str | None = None,
    signal_id: str | None = None,
) -> None:
    try:
        mid = int(message_id)
    except (TypeError, ValueError):
        return
    if mid <= 0:
        return
    with _LOCK:
        store = _load_unlocked()
        ids = store["message_ids"]
        sig = str(signal_id or "").strip()
        tic = str(ticket or "").strip()
        if sig:
            ids.setdefault(f"signal:{sig}", mid)
        if tic:
            ids.setdefault(f"ticket:{tic}", mid)
            if sig:
                store["tickets"].setdefault(sig, tic)
        _prune(store)
        _save_unlocked(store)
