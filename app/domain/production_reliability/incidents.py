"""Incident Center — open → investigating → mitigated → resolved → postmortem."""

from __future__ import annotations

from typing import Any

from app.domain.production_reliability.models import INCIDENT_STATUSES
from app.domain.production_reliability.persistence import (
    JsonDocumentStore,
    new_id,
    utc_iso,
)

_store = JsonDocumentStore("incidents.json", "incidents")


def list_incidents(
    *, limit: int = 200, status: str | None = None
) -> list[dict[str, Any]]:
    rows = list(reversed(_store.list(limit=limit * 2)))
    if status:
        rows = [r for r in rows if str(r.get("status")) == status]
    return rows[:limit]


def get_incident(incident_id: str) -> dict[str, Any] | None:
    return _store.get(incident_id)


def open_incident(
    *,
    title: str,
    severity: str = "medium",
    summary: str = "",
    operator: str = "operator",
) -> dict[str, Any]:
    now = utc_iso()
    doc = {
        "id": new_id("inc"),
        "title": (title or "Untitled incident")[:200],
        "severity": (severity or "medium")[:32],
        "status": "open",
        "summary": (summary or "")[:2000],
        "root_cause": "",
        "actions": [],
        "timeline": [
            {
                "at": now,
                "status": "open",
                "note": "Incident opened",
                "operator": operator,
            }
        ],
        "opened_at": now,
        "resolved_at": None,
        "created_at": now,
        "updated_at": now,
        "operator": operator,
        "postmortem": None,
        "fabricated": False,
    }
    return _store.append(doc)


def _transition(
    incident_id: str,
    *,
    status: str,
    note: str,
    operator: str,
    root_cause: str | None = None,
    actions: list[str] | None = None,
    postmortem: str | None = None,
) -> dict[str, Any]:
    if status not in INCIDENT_STATUSES:
        return {
            "ok": False,
            "error": "invalid_status",
            "allowed": list(INCIDENT_STATUSES),
        }

    def mutator(row: dict[str, Any]) -> dict[str, Any]:
        now = utc_iso()
        timeline = list(row.get("timeline") or [])
        timeline.append(
            {
                "at": now,
                "status": status,
                "note": (note or status)[:1000],
                "operator": operator,
            }
        )
        row["status"] = status
        row["timeline"] = timeline
        row["updated_at"] = now
        if root_cause is not None:
            row["root_cause"] = root_cause[:4000]
        if actions is not None:
            row["actions"] = [str(a)[:500] for a in actions][:50]
        if postmortem is not None:
            row["postmortem"] = postmortem[:8000]
        if status in {"resolved", "postmortem"} and not row.get("resolved_at"):
            row["resolved_at"] = now
        return row

    updated = _store.upsert(incident_id, mutator)
    if not updated:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "incident": updated}


def update_incident_status(
    incident_id: str,
    *,
    status: str,
    note: str = "",
    operator: str = "operator",
    root_cause: str | None = None,
    actions: list[str] | None = None,
    postmortem: str | None = None,
) -> dict[str, Any]:
    return _transition(
        incident_id,
        status=status,
        note=note,
        operator=operator,
        root_cause=root_cause,
        actions=actions,
        postmortem=postmortem,
    )


def build_incident_center() -> dict[str, Any]:
    rows = list_incidents(limit=100)
    by_status: dict[str, int] = dict.fromkeys(INCIDENT_STATUSES, 0)
    for r in rows:
        st = str(r.get("status") or "open")
        if st in by_status:
            by_status[st] += 1
    return {
        "as_of": utc_iso(),
        "incidents": rows,
        "count": len(rows),
        "by_status": by_status,
        "statuses": list(INCIDENT_STATUSES),
        "fabricated": False,
        "observe_only": False,
        "note": "Lifecycle ops only — never mutates trading engines",
    }
