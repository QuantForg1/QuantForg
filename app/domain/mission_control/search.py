"""Global search across desks, notes, and supplied timeline hits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.mission_control.config import MissionControlConfig
from app.domain.mission_control.notes import OperatorNote


@dataclass(frozen=True)
class SearchHit:
    kind: str
    title: str
    href: str
    detail: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "href": self.href,
            "detail": self.detail,
            "source": self.source,
        }


def search_desks(query: str, config: MissionControlConfig) -> list[SearchHit]:
    q = query.strip().lower()
    if not q:
        return []
    hits: list[SearchHit] = []
    for desk in config.desk_catalog:
        blob = f"{desk['label']} {desk['href']} {desk.get('group', '')}".lower()
        if q in blob:
            hits.append(
                SearchHit(
                    kind="desk",
                    title=desk["label"],
                    href=desk["href"],
                    detail=desk.get("group", ""),
                    source="mission_control.desk_catalog",
                )
            )
    return hits


def search_notes(notes: list[OperatorNote], _query: str) -> list[SearchHit]:
    return [
        SearchHit(
            kind="note",
            title=f"Note · {n.operator}",
            href="/mission-control",
            detail=n.text[:160],
            source="mission_control.operator_notes",
        )
        for n in notes
    ]


def search_timeline_rows(rows: list[dict[str, Any]], query: str) -> list[SearchHit]:
    q = query.strip().lower()
    if not q:
        return []
    hits: list[SearchHit] = []
    for row in rows:
        blob = " ".join(str(v) for v in row.values()).lower()
        if q not in blob:
            continue
        hits.append(
            SearchHit(
                kind="timeline",
                title=str(row.get("action") or row.get("category") or "event"),
                href="/ops",
                detail=str(row.get("detail") or row.get("severity") or "")[:160],
                source="ite.reliability.timeline",
            )
        )
    return hits
