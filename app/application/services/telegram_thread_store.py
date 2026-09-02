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
    return {
        "version": 2,
        "message_ids": {},
        "seen": {},
        "tickets": {},
        "by_message": {},
        "lifecycle": {},
        "public_status": {},
        "update_offset": 0,
    }


def _load_unlocked() -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    path = telegram_threads_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            _cache = {
                "version": 2,
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
                "by_message": dict(raw.get("by_message") or {}),
                "lifecycle": dict(raw.get("lifecycle") or {}),
                "public_status": dict(raw.get("public_status") or {}),
                "update_offset": int(raw.get("update_offset") or 0),
            }
            return _cache
    except FileNotFoundError:
        pass
    except Exception:
        logger.exception("telegram_threads_load_failed")
    _cache = _empty()
    return _cache


def record_lifecycle(
    *,
    ticket: str | None,
    signal_id: str | None,
    state: str,
    symbol: str | None = None,
    direction: str | None = None,
) -> None:
    payload = {
        "ticket": str(ticket or "").strip(),
        "signal_id": str(signal_id or "").strip(),
        "state": str(state or "").strip() or "UNKNOWN",
        "symbol": str(symbol or "").strip() or None,
        "direction": str(direction or "").strip() or None,
    }
    with _LOCK:
        store = _load_unlocked()
        store.setdefault("lifecycle", {})
        for key in (payload["ticket"], payload["signal_id"]):
            if key:
                store["lifecycle"][key] = payload
        _prune(store)
        _save_unlocked(store)


def lookup_lifecycle_by_message_id(message_id: int) -> dict[str, Any] | None:
    try:
        mid = int(message_id)
    except (TypeError, ValueError):
        return None
    with _LOCK:
        store = _load_unlocked()
        row = dict((store.get("by_message") or {}).get(str(mid)) or {})
        if not row:
            return None
        life = (store.get("lifecycle") or {}).get(str(row.get("ticket") or "")) or (
            store.get("lifecycle") or {}
        ).get(str(row.get("signal_id") or ""))
        if isinstance(life, dict):
            merged = dict(row)
            merged.update({k: v for k, v in life.items() if v})
            return merged
        return row


def forget_public_status() -> None:
    with _LOCK:
        store = _load_unlocked()
        store["public_status"] = {}
        _save_unlocked(store)


def last_public_status() -> str | None:
    with _LOCK:
        store = _load_unlocked()
        kind = dict(store.get("public_status") or {}).get("kind")
        return str(kind) if kind else None


def mark_public_status(kind: str) -> None:
    with _LOCK:
        store = _load_unlocked()
        store["public_status"] = {"kind": str(kind), "ts": time.time()}
        _save_unlocked(store)


def telegram_update_offset() -> int:
    with _LOCK:
        store = _load_unlocked()
        try:
            return int(store.get("update_offset") or 0)
        except (TypeError, ValueError):
            return 0


def set_telegram_update_offset(value: int) -> None:
    with _LOCK:
        store = _load_unlocked()
        store["update_offset"] = max(0, int(value))
        _save_unlocked(store)


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
    for bucket in ("seen", "message_ids", "tickets", "by_message", "lifecycle"):
        data = store.get(bucket) or {}
        store[bucket] = data
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
        store.setdefault("by_message", {})
        store.setdefault("lifecycle", {})
        store.setdefault("public_status", {})
        store.setdefault("update_offset", 0)
        ids = store["message_ids"]
        sig = str(signal_id or "").strip()
        tic = str(ticket or "").strip()
        if sig:
            ids.setdefault(f"signal:{sig}", mid)
        if tic:
            ids.setdefault(f"ticket:{tic}", mid)
            if sig:
                store["tickets"].setdefault(sig, tic)
        life = store["lifecycle"].get(tic) or store["lifecycle"].get(sig) or {}
        store["by_message"][str(mid)] = {
            "ticket": tic or life.get("ticket"),
            "signal_id": sig or life.get("signal_id"),
            "state": life.get("state") or "CONFIRMED",
            "symbol": life.get("symbol"),
            "direction": life.get("direction"),
        }
        _prune(store)
        _save_unlocked(store)
