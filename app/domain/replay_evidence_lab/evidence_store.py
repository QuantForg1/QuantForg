"""Evidence database — Live / Demo / Replay / Research lanes never mix."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domain.replay_evidence_lab.models import EVIDENCE_LANES, EvidenceLane


class EvidenceDatabase:
    """In-process evidence store with hard lane isolation.

    Persists separately from live execution journals. Never mixes datasets.
    """

    def __init__(self) -> None:
        self._lanes: dict[str, list[dict[str, Any]]] = {
            lane: [] for lane in EVIDENCE_LANES
        }

    def clear(self, lane: EvidenceLane | None = None) -> None:
        if lane is None:
            for key in EVIDENCE_LANES:
                self._lanes[key] = []
            return
        self._lanes[str(lane)] = []

    def add(self, lane: EvidenceLane, record: dict[str, Any]) -> dict[str, Any]:
        if lane not in EVIDENCE_LANES:
            raise ValueError(f"Unknown evidence lane: {lane}")
        if not isinstance(record, dict):
            raise TypeError("Evidence record must be a dict")
        stored = deepcopy(record)
        stored["evidence_lane"] = lane
        stored.setdefault("research_only", lane in {"replay", "research"})
        self._lanes[lane].append(stored)
        return stored

    def extend(self, lane: EvidenceLane, records: list[dict[str, Any]] | None) -> int:
        n = 0
        for raw in records or []:
            if isinstance(raw, dict):
                self.add(lane, raw)
                n += 1
        return n

    def list(self, lane: EvidenceLane) -> list[dict[str, Any]]:
        """Return a copy of one lane only — never merges lanes."""
        if lane not in EVIDENCE_LANES:
            raise ValueError(f"Unknown evidence lane: {lane}")
        return deepcopy(self._lanes[lane])

    def counts(self) -> dict[str, int]:
        return {lane: len(self._lanes[lane]) for lane in EVIDENCE_LANES}

    def inventory(self) -> dict[str, Any]:
        counts = self.counts()
        return {
            "status": "available",
            "lanes": counts,
            "total_records": sum(counts.values()),
            "never_mix_evidence_lanes": True,
            "note": "Live, Demo, Replay, and Research are stored separately",
        }


# Process-scoped lab store (not the live execution journal)
_LAB_DB = EvidenceDatabase()


def get_evidence_database() -> EvidenceDatabase:
    return _LAB_DB
