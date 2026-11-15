"""In-process recommendation registry — governance only, never LIVE."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from app.domain.institutional_intelligence import RECOMMENDATION_STATUSES

_ALLOWED = set(RECOMMENDATION_STATUSES)
_TRANSITIONS: dict[str, set[str]] = {
    "Proposed": {"Under Review", "Rejected", "Expired"},
    "Under Review": {"Approved", "Rejected", "Expired"},
    "Approved": {"Applied", "Expired", "Rejected"},
    "Rejected": set(),
    "Expired": set(),
    "Applied": set(),
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Recommendation:
    id: str
    recommendation: str
    reasoning_summary: str
    supporting_evidence: list[str]
    data_timestamp: str
    confidence: float | None
    expected_benefits: list[str]
    risks_and_limitations: list[str]
    affected_strategy_or_account: str | None
    required_approval: bool
    status: str
    created_at: str
    updated_at: str
    approved_is_not_live: bool = True
    never_order_send: bool = True
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RecommendationStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._rows: dict[str, Recommendation] = {}

    def list_all(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = sorted(
                self._rows.values(),
                key=lambda r: r.updated_at,
                reverse=True,
            )
            return [r.to_dict() for r in rows[:limit]]

    def get(self, rec_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._rows.get(rec_id)
            return row.to_dict() if row else None

    def create(
        self,
        *,
        recommendation: str,
        reasoning_summary: str,
        supporting_evidence: list[str] | None = None,
        confidence: float | None = None,
        expected_benefits: list[str] | None = None,
        risks_and_limitations: list[str] | None = None,
        affected_strategy_or_account: str | None = None,
        required_approval: bool = True,
        data_timestamp: str | None = None,
    ) -> dict[str, Any]:
        now = _now()
        rec_id = f"rec-{uuid4().hex[:12]}"
        evidence = [str(x) for x in (supporting_evidence or [])][:40]
        benefits = [str(x) for x in (expected_benefits or [])][:20]
        risks = [str(x) for x in (risks_and_limitations or [])][:20]
        row = Recommendation(
            id=rec_id,
            recommendation=(recommendation or "")[:2000],
            reasoning_summary=(reasoning_summary or "")[:4000],
            supporting_evidence=evidence,
            data_timestamp=data_timestamp or now,
            confidence=confidence,
            expected_benefits=benefits,
            risks_and_limitations=risks,
            affected_strategy_or_account=affected_strategy_or_account,
            required_approval=bool(required_approval),
            status="Proposed",
            created_at=now,
            updated_at=now,
            history=[{"at": now, "status": "Proposed", "note": "created"}],
        )
        with self._lock:
            self._rows[rec_id] = row
            return row.to_dict()

    def set_status(
        self,
        rec_id: str,
        *,
        status: str,
        note: str = "",
    ) -> dict[str, Any] | None:
        if status not in _ALLOWED:
            return {
                "ok": False,
                "error": "invalid_status",
                "allowed": list(RECOMMENDATION_STATUSES),
            }
        with self._lock:
            row = self._rows.get(rec_id)
            if row is None:
                return None
            allowed = _TRANSITIONS.get(row.status, set())
            if status != row.status and status not in allowed:
                return {
                    "ok": False,
                    "error": "invalid_transition",
                    "from": row.status,
                    "to": status,
                    "allowed": sorted(allowed),
                    "approved_is_not_live": True,
                }
            now = _now()
            row.status = status
            row.updated_at = now
            row.history.append(
                {
                    "at": now,
                    "status": status,
                    "note": (note or "")[:500],
                }
            )
            out = row.to_dict()
            out["ok"] = True
            out["approved_is_not_live"] = True
            out["never_authorizes_live_execution"] = True
            return out


_STORE: RecommendationStore | None = None
_STORE_LOCK = Lock()


def get_recommendation_store() -> RecommendationStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = RecommendationStore()
        return _STORE
