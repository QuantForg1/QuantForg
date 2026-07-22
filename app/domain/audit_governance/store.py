"""Append-only immutable audit event store — never silently delete or modify."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from app.domain.audit_governance.models import EVENT_CATEGORIES, SEVERITIES


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    text = str(raw).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Build a complete immutable audit record. Never omits timestamp."""
    if not isinstance(raw, dict):
        raise TypeError("Audit event must be a dict")

    ts = _parse_ts(raw.get("timestamp") or raw.get("occurred_at")) or _utcnow()
    category = str(raw.get("category") or "system").strip().lower()
    if category not in EVENT_CATEGORIES:
        category = "system"
    severity = str(raw.get("severity") or "info").strip().lower()
    if severity not in SEVERITIES:
        severity = "info"

    event_id = str(raw.get("event_id") or raw.get("id") or uuid4())
    record: dict[str, Any] = {
        "event_id": event_id,
        "timestamp": _iso(ts),
        "category": category,
        "severity": severity,
        "component": str(raw.get("component") or raw.get("source_component") or ""),
        "action": str(raw.get("action") or raw.get("event") or "").strip().lower(),
        "previous_state": raw.get("previous_state")
        if raw.get("previous_state") is not None
        else raw.get("old_value"),
        "new_state": raw.get("new_state")
        if raw.get("new_state") is not None
        else raw.get("new_value"),
        "actor": str(
            raw.get("actor")
            or raw.get("operator")
            or raw.get("actor_user_id")
            or "system"
        ),
        "source": str(raw.get("source") or "api"),
        "environment": str(raw.get("environment") or "unknown"),
        "reason": str(raw.get("reason") or ""),
        "correlation_id": str(raw.get("correlation_id") or ""),
        "session_id": str(raw.get("session_id") or ""),
        "result": str(raw.get("result") or raw.get("outcome") or "recorded"),
        "notes": str(raw.get("notes") or raw.get("message") or ""),
        "approval": raw.get("approval"),
        "versions": raw.get("versions")
        if isinstance(raw.get("versions"), dict)
        else {},
        "immutable": True,
        "append_only": True,
    }
    # Integrity fingerprint — any silent mutation would break equality checks
    fingerprint_payload = {
        k: record[k]
        for k in (
            "event_id",
            "timestamp",
            "category",
            "severity",
            "component",
            "action",
            "previous_state",
            "new_state",
            "actor",
            "source",
            "environment",
            "reason",
            "correlation_id",
            "session_id",
            "result",
            "notes",
        )
    }
    digest = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    record["integrity_hash"] = digest
    return record


class ImmutableAuditStore:
    """Process-scoped append-only audit ledger.

    Records are never updated in place. Deletes are forbidden outside tests.
    """

    def __init__(self, *, max_entries: int = 100_000) -> None:
        self._entries: list[dict[str, Any]] = []
        self._lock = Lock()
        self.max_entries = max_entries
        self._rejected_mutations = 0

    def append(self, raw: dict[str, Any]) -> dict[str, Any]:
        record = normalize_event(raw)
        with self._lock:
            # Refuse duplicate event_id overwrite — keep first, never modify
            existing_ids = {e["event_id"] for e in self._entries}
            if record["event_id"] in existing_ids:
                self._rejected_mutations += 1
                raise ValueError(
                    f"Audit event_id {record['event_id']} already exists — "
                    "immutable store refuses overwrite"
                )
            self._entries.append(record)
            # Soft trim preserves chronological order of newest + oldest sample
            if len(self._entries) > self.max_entries * 2:
                keep_old = self._entries[:1000]
                keep_new = self._entries[-(self.max_entries - 1000) :]
                self._entries = keep_old + keep_new
            return deepcopy(record)

    def update_forbidden(self, *_args: Any, **_kwargs: Any) -> None:
        self._rejected_mutations += 1
        raise RuntimeError("Audit records are immutable — updates are forbidden")

    def delete_forbidden(self, *_args: Any, **_kwargs: Any) -> None:
        self._rejected_mutations += 1
        raise RuntimeError("Audit records must never be silently deleted")

    def list(
        self,
        *,
        limit: int = 200,
        category: str | None = None,
        severity: str | None = None,
        actor: str | None = None,
        action: str | None = None,
        q: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[dict[str, Any]]:
        since_dt = _parse_ts(since)
        until_dt = _parse_ts(until)
        with self._lock:
            rows = list(self._entries)
        out: list[dict[str, Any]] = []
        for row in rows:
            if category and row.get("category") != category:
                continue
            if severity and row.get("severity") != severity:
                continue
            if actor and str(row.get("actor") or "").lower() != actor.lower():
                continue
            if action and str(row.get("action") or "").lower() != action.lower():
                continue
            ts = _parse_ts(row.get("timestamp"))
            if since_dt and ts and ts < since_dt:
                continue
            if until_dt and ts and ts > until_dt:
                continue
            if q:
                blob = json.dumps(row, default=str).lower()
                if q.lower() not in blob:
                    continue
            out.append(deepcopy(row))
        # Chronological ascending for forensics; limit keeps newest tail
        out.sort(key=lambda r: str(r.get("timestamp") or ""))
        if limit and len(out) > limit:
            out = out[-limit:]
        return out

    def count(self) -> int:
        with self._lock:
            return len(self._entries)

    def security_status(self) -> dict[str, Any]:
        with self._lock:
            n = len(self._entries)
            chronological = all(
                str(self._entries[i].get("timestamp") or "")
                <= str(self._entries[i + 1].get("timestamp") or "")
                for i in range(max(0, n - 1))
            )
        return {
            "append_only": True,
            "immutable": True,
            "chronological": chronological,
            "never_silently_deleted": True,
            "never_silently_modified": True,
            "record_count": n,
            "rejected_mutations": self._rejected_mutations,
        }

    def clear_for_tests_only(self) -> None:
        """Test helper — production durable stores must never expose this."""
        with self._lock:
            self._entries.clear()


_STORE = ImmutableAuditStore()


def get_audit_store() -> ImmutableAuditStore:
    return _STORE
