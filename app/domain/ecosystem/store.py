"""Trading Ecosystem — process-memory user data (no DB schema)."""

from __future__ import annotations

import threading
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

DEFAULT_PREFERENCES: dict[str, Any] = {
    "theme": "dark",
    "language": "en",
    "timezone": "UTC",
    "hotkeys_enabled": True,
    "hotkeys": {
        "focus_workspace": "Alt+W",
        "open_journal": "Alt+J",
        "open_decision": "Alt+D",
    },
    "default_layout": "institutional",
    "density": "comfortable",
}

LEARNING_CATALOG: list[dict[str, Any]] = [
    {
        "id": "guide-paper-first",
        "title": "Paper-first workflow",
        "category": "best_practices",
        "minutes": 8,
        "summary": (
            "Complete Get Started → paper → Decision Engine WAIT bias before live."
        ),
    },
    {
        "id": "guide-decision-wait",
        "title": "Why Decision Engine defaults to WAIT",
        "category": "quant_guides",
        "minutes": 6,
        "summary": "Capital preservation scoring — never bypass the gatekeeper.",
    },
    {
        "id": "guide-research-lab",
        "title": "Research Lab validation path",
        "category": "tutorials",
        "minutes": 12,
        "summary": "Library → Validation → Compare → Promotion eligibility only.",
    },
    {
        "id": "guide-risk-rules",
        "title": "Risk rules for sessions",
        "category": "best_practices",
        "minutes": 10,
        "summary": "Session risk caps, news windows, and heat limits.",
    },
    {
        "id": "guide-journal",
        "title": "Trading Journal discipline",
        "category": "tutorials",
        "minutes": 7,
        "summary": "Capture emotion, lessons, tags — attach DE score when present.",
    },
]


class EcosystemStore:
    """Per-user ecosystem artifacts. Never submits trades or touches broker state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._journal: dict[str, list[dict[str, Any]]] = {}
        self._playbooks: dict[str, list[dict[str, Any]]] = {}
        self._watchlists: dict[str, list[dict[str, Any]]] = {}
        self._workspaces: dict[str, list[dict[str, Any]]] = {}
        self._alerts: dict[str, list[dict[str, Any]]] = {}
        self._learning: dict[str, dict[str, Any]] = {}
        self._preferences: dict[str, dict[str, Any]] = {}
        self._sync_meta: dict[str, dict[str, Any]] = {}

    def _uid(self, user_id: UUID) -> str:
        return str(user_id)

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    # --- journal ---------------------------------------------------------

    def list_journal(self, user_id: UUID, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._journal.get(self._uid(user_id), []))
        return list(reversed(rows[-limit:]))

    def upsert_journal(
        self, user_id: UUID, entry: dict[str, Any], *, entry_id: str | None = None
    ) -> dict[str, Any]:
        eid = entry_id or entry.get("id") or str(uuid4())
        row = {
            **deepcopy(entry),
            "id": eid,
            "updated_at": self._now(),
            "created_at": entry.get("created_at") or self._now(),
        }
        with self._lock:
            bucket = self._journal.setdefault(self._uid(user_id), [])
            for i, existing in enumerate(bucket):
                if existing.get("id") == eid:
                    row["created_at"] = existing.get("created_at", row["created_at"])
                    bucket[i] = row
                    break
            else:
                bucket.append(row)
                if len(bucket) > 2000:
                    del bucket[:-1500]
        return row

    def search_journal(
        self,
        user_id: UUID,
        *,
        query: str = "",
        tag: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        q = query.strip().lower()
        rows = self.list_journal(user_id, limit=500)
        out: list[dict[str, Any]] = []
        for r in rows:
            tags = [str(t).lower() for t in (r.get("tags") or [])]
            if tag and tag.lower() not in tags:
                continue
            blob = " ".join(
                [
                    str(r.get("symbol") or ""),
                    str(r.get("emotion_notes") or ""),
                    str(r.get("lessons_learned") or ""),
                    str(r.get("ai_review") or ""),
                    " ".join(tags),
                ]
            ).lower()
            if q and q not in blob:
                continue
            out.append(r)
            if len(out) >= limit:
                break
        return out

    def journal_stats(self, user_id: UUID) -> dict[str, Any]:
        rows = self.list_journal(user_id, limit=500)
        if not rows:
            return {
                "status": "unavailable",
                "reason": "No journal entries yet",
                "count": 0,
            }
        tags: dict[str, int] = {}
        emotions: dict[str, int] = {}
        for r in rows:
            for t in r.get("tags") or []:
                tags[str(t)] = tags.get(str(t), 0) + 1
            emo = str(r.get("emotion") or "unspecified")
            emotions[emo] = emotions.get(emo, 0) + 1
        scored = [r for r in rows if r.get("decision_engine_score") is not None]
        avg_score = None
        if scored:
            avg_score = round(
                sum(float(r["decision_engine_score"]) for r in scored) / len(scored),
                2,
            )
        return {
            "status": "available",
            "count": len(rows),
            "with_de_score": len(scored),
            "avg_decision_score": avg_score,
            "top_tags": sorted(tags.items(), key=lambda x: -x[1])[:10],
            "emotions": emotions,
        }

    # --- playbooks -------------------------------------------------------

    def list_playbooks(self, user_id: UUID) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._playbooks.get(self._uid(user_id), []))

    def save_playbook(
        self, user_id: UUID, playbook: dict[str, Any], *, playbook_id: str | None = None
    ) -> dict[str, Any]:
        pid = playbook_id or playbook.get("id") or str(uuid4())
        row = {
            **deepcopy(playbook),
            "id": pid,
            "updated_at": self._now(),
            "created_at": playbook.get("created_at") or self._now(),
        }
        with self._lock:
            bucket = self._playbooks.setdefault(self._uid(user_id), [])
            for i, existing in enumerate(bucket):
                if existing.get("id") == pid:
                    row["created_at"] = existing.get("created_at", row["created_at"])
                    bucket[i] = row
                    break
            else:
                bucket.append(row)
        return row

    # --- watchlists ------------------------------------------------------

    def list_watchlists(self, user_id: UUID) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._watchlists.get(self._uid(user_id), []))

    def save_watchlist(
        self,
        user_id: UUID,
        watchlist: dict[str, Any],
        *,
        watchlist_id: str | None = None,
    ) -> dict[str, Any]:
        wid = watchlist_id or watchlist.get("id") or str(uuid4())
        row = {
            **deepcopy(watchlist),
            "id": wid,
            "updated_at": self._now(),
            "created_at": watchlist.get("created_at") or self._now(),
            "cloud_synced": True,
        }
        with self._lock:
            bucket = self._watchlists.setdefault(self._uid(user_id), [])
            for i, existing in enumerate(bucket):
                if existing.get("id") == wid:
                    row["created_at"] = existing.get("created_at", row["created_at"])
                    bucket[i] = row
                    break
            else:
                bucket.append(row)
        return row

    # --- workspaces ------------------------------------------------------

    def list_workspaces(self, user_id: UUID) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._workspaces.get(self._uid(user_id), []))

    def save_workspace(
        self,
        user_id: UUID,
        workspace: dict[str, Any],
        *,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        wid = workspace_id or workspace.get("id") or str(uuid4())
        row = {
            **deepcopy(workspace),
            "id": wid,
            "updated_at": self._now(),
            "created_at": workspace.get("created_at") or self._now(),
            "never_modifies_terminal_defaults": True,
        }
        with self._lock:
            bucket = self._workspaces.setdefault(self._uid(user_id), [])
            for i, existing in enumerate(bucket):
                if existing.get("id") == wid:
                    row["created_at"] = existing.get("created_at", row["created_at"])
                    bucket[i] = row
                    break
            else:
                bucket.append(row)
        return row

    # --- alerts ----------------------------------------------------------

    def list_alerts(self, user_id: UUID, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._alerts.get(self._uid(user_id), []))
        return list(reversed(rows[-limit:]))

    def add_alert(self, user_id: UUID, alert: dict[str, Any]) -> dict[str, Any]:
        row = {
            **deepcopy(alert),
            "id": alert.get("id") or str(uuid4()),
            "created_at": self._now(),
            "read": bool(alert.get("read", False)),
            "advisory_only": True,
        }
        with self._lock:
            bucket = self._alerts.setdefault(self._uid(user_id), [])
            bucket.append(row)
            if len(bucket) > 1000:
                del bucket[:-800]
        return row

    def mark_alert_read(self, user_id: UUID, alert_id: str) -> dict[str, Any] | None:
        with self._lock:
            for row in self._alerts.get(self._uid(user_id), []):
                if row.get("id") == alert_id:
                    row["read"] = True
                    return deepcopy(row)
        return None

    # --- learning --------------------------------------------------------

    def learning_progress(self, user_id: UUID) -> dict[str, Any]:
        with self._lock:
            prog = deepcopy(
                self._learning.get(
                    self._uid(user_id),
                    {"completed": [], "updated_at": None},
                )
            )
        return {
            "catalog": deepcopy(LEARNING_CATALOG),
            "completed": prog.get("completed") or [],
            "updated_at": prog.get("updated_at"),
        }

    def complete_lesson(self, user_id: UUID, lesson_id: str) -> dict[str, Any]:
        with self._lock:
            prog = self._learning.setdefault(
                self._uid(user_id), {"completed": [], "updated_at": None}
            )
            completed = list(prog.get("completed") or [])
            if lesson_id not in completed:
                completed.append(lesson_id)
            prog["completed"] = completed
            prog["updated_at"] = self._now()
            return deepcopy(prog)

    # --- preferences -----------------------------------------------------

    def get_preferences(self, user_id: UUID) -> dict[str, Any]:
        with self._lock:
            prefs = self._preferences.get(self._uid(user_id))
            if not prefs:
                return deepcopy(DEFAULT_PREFERENCES)
            return deepcopy(prefs)

    def set_preferences(self, user_id: UUID, updates: dict[str, Any]) -> dict[str, Any]:
        base = self.get_preferences(user_id)
        for k, v in updates.items():
            if k in DEFAULT_PREFERENCES or k in base:
                base[k] = v
        base["updated_at"] = self._now()
        with self._lock:
            self._preferences[self._uid(user_id)] = deepcopy(base)
        return base

    # --- cloud sync snapshot ---------------------------------------------

    def export_sync_bundle(self, user_id: UUID) -> dict[str, Any]:
        journal = self.list_journal(user_id, limit=500)
        playbooks = self.list_playbooks(user_id)
        watchlists = self.list_watchlists(user_id)
        workspaces = self.list_workspaces(user_id)
        alerts = self.list_alerts(user_id, limit=200)
        learning = self.learning_progress(user_id)
        preferences = self.get_preferences(user_id)
        bundle = {
            "version": 1,
            "exported_at": self._now(),
            "journal": journal,
            "playbooks": playbooks,
            "watchlists": watchlists,
            "workspaces": workspaces,
            "alerts": alerts,
            "learning": learning,
            "preferences": preferences,
            "advisory_only": True,
            "never_submits_orders": True,
        }
        with self._lock:
            self._sync_meta[self._uid(user_id)] = {
                "last_sync_at": self._now(),
                "items": {
                    "journal": len(journal),
                    "playbooks": len(playbooks),
                    "watchlists": len(watchlists),
                    "workspaces": len(workspaces),
                },
            }
            meta = deepcopy(self._sync_meta[self._uid(user_id)])
        bundle["sync_meta"] = meta
        return bundle

    def import_sync_bundle(
        self, user_id: UUID, bundle: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge cloud bundle into memory — never touches broker or orders."""
        counts = {"journal": 0, "playbooks": 0, "watchlists": 0, "workspaces": 0}
        for entry in bundle.get("journal") or []:
            if isinstance(entry, dict):
                self.upsert_journal(user_id, entry, entry_id=entry.get("id"))
                counts["journal"] += 1
        for pb in bundle.get("playbooks") or []:
            if isinstance(pb, dict):
                self.save_playbook(user_id, pb, playbook_id=pb.get("id"))
                counts["playbooks"] += 1
        for wl in bundle.get("watchlists") or []:
            if isinstance(wl, dict):
                self.save_watchlist(user_id, wl, watchlist_id=wl.get("id"))
                counts["watchlists"] += 1
        for ws in bundle.get("workspaces") or []:
            if isinstance(ws, dict):
                self.save_workspace(user_id, ws, workspace_id=ws.get("id"))
                counts["workspaces"] += 1
        prefs = bundle.get("preferences")
        if isinstance(prefs, dict):
            self.set_preferences(user_id, prefs)
        learning = bundle.get("learning") or {}
        for lid in learning.get("completed") or []:
            self.complete_lesson(user_id, str(lid))
        with self._lock:
            self._sync_meta[self._uid(user_id)] = {
                "last_sync_at": self._now(),
                "imported": counts,
            }
            meta = deepcopy(self._sync_meta[self._uid(user_id)])
        return {
            "status": "available",
            "imported": counts,
            "sync_meta": meta,
            "never_modifies_broker_state": True,
            "never_submits_orders": True,
        }

    def sync_status(self, user_id: UUID) -> dict[str, Any]:
        with self._lock:
            meta = deepcopy(self._sync_meta.get(self._uid(user_id)) or {})
        return {
            "status": "available" if meta else "idle",
            "meta": meta,
            "scopes": [
                "watchlists",
                "journal",
                "playbooks",
                "research_refs",
                "workspace_layouts",
            ],
            "cloud_synced": bool(meta),
        }


_STORE = EcosystemStore()


def get_ecosystem_store() -> EcosystemStore:
    return _STORE
