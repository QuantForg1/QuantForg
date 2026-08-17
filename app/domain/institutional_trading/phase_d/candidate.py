"""AlphaCandidate contract — missing material evidence → NOT_PROMOTABLE."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import uuid4


REQUIRED_IDENTITY = (
    "strategy_id",
    "model_id",
    "version",
    "code_commit",
    "research_run_id",
    "dataset_hash",
    "symbols",
    "timeframes",
)

REQUIRED_RESEARCH = (
    "walk_forward_status",
    "oos_status",
    "pbo",
    "dsr",
    "monte_carlo_status",
    "parameter_sensitivity",
    "live_parity_status",
    "shadow_status",
    "sample_size",
)

REQUIRED_RISK = (
    "risk_impact",
    "drawdown_impact",
    "correlation_impact",
    "execution_impact",
)


@dataclass
class AlphaCandidate:
    candidate_id: str
    strategy_id: str
    model_id: str
    version: str
    code_commit: str
    research_run_id: str
    dataset_hash: str
    symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    regimes: tuple[str, ...]
    creation_timestamp: str
    research_evidence: dict[str, Any]
    risk_evidence: dict[str, Any]
    change_isolation: dict[str, Any]
    status: str  # PROMOTABLE | NOT_PROMOTABLE
    missing_fields: tuple[str, ...] = ()
    why_blocked: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "strategy_id": self.strategy_id,
            "model_id": self.model_id,
            "version": self.version,
            "code_commit": self.code_commit,
            "research_run_id": self.research_run_id,
            "dataset_hash": self.dataset_hash,
            "symbols": list(self.symbols),
            "timeframes": list(self.timeframes),
            "regimes": list(self.regimes),
            "creation_timestamp": self.creation_timestamp,
            "research_evidence": dict(self.research_evidence),
            "risk_evidence": dict(self.risk_evidence),
            "change_isolation": dict(self.change_isolation),
            "status": self.status,
            "missing_fields": list(self.missing_fields),
            "why_blocked": self.why_blocked,
            "execution_authority": False,
        }


def _missing(payload: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for key in keys:
        val = payload.get(key)
        if val is None or val == "" or val == () or val == [] or val == {}:
            out.append(key)
    return out


@dataclass
class AlphaCandidateStore:
    candidates: dict[str, AlphaCandidate] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, repr=False)
    _seen_promotion_requests: set[str] = field(default_factory=set, repr=False)

    def register(self, **kwargs: Any) -> AlphaCandidate:
        identity = {k: kwargs.get(k) for k in REQUIRED_IDENTITY}
        research = dict(kwargs.get("research_evidence") or {})
        risk = dict(kwargs.get("risk_evidence") or {})
        missing = (
            _missing(identity, REQUIRED_IDENTITY)
            + [f"research.{k}" for k in _missing(research, REQUIRED_RESEARCH)]
            + [f"risk.{k}" for k in _missing(risk, REQUIRED_RISK)]
        )
        symbols = kwargs.get("symbols") or ()
        timeframes = kwargs.get("timeframes") or ()
        regimes = kwargs.get("regimes") or ()
        if isinstance(symbols, str):
            symbols = (symbols,)
        if isinstance(timeframes, str):
            timeframes = (timeframes,)
        if isinstance(regimes, str):
            regimes = (regimes,)
        status = "NOT_PROMOTABLE" if missing else "PROMOTABLE"
        cand = AlphaCandidate(
            candidate_id=str(kwargs.get("candidate_id") or uuid4()),
            strategy_id=str(kwargs.get("strategy_id") or ""),
            model_id=str(kwargs.get("model_id") or ""),
            version=str(kwargs.get("version") or ""),
            code_commit=str(kwargs.get("code_commit") or ""),
            research_run_id=str(kwargs.get("research_run_id") or ""),
            dataset_hash=str(kwargs.get("dataset_hash") or ""),
            symbols=tuple(str(s) for s in symbols),
            timeframes=tuple(str(t) for t in timeframes),
            regimes=tuple(str(r) for r in regimes),
            creation_timestamp=str(
                kwargs.get("creation_timestamp") or datetime.now(UTC).isoformat()
            ),
            research_evidence=research,
            risk_evidence=risk,
            change_isolation=dict(kwargs.get("change_isolation") or {}),
            status=status,
            missing_fields=tuple(missing),
            why_blocked=("missing material evidence: " + ",".join(missing))
            if missing
            else None,
        )
        with self._lock:
            self.candidates[cand.candidate_id] = cand
        return cand

    def get(self, candidate_id: str) -> AlphaCandidate | None:
        with self._lock:
            return self.candidates.get(candidate_id)

    def claim_promotion_request(self, request_id: str) -> bool:
        """Idempotency — duplicate promotion requests are rejected."""
        rid = str(request_id or "").strip()
        if not rid:
            return False
        with self._lock:
            if rid in self._seen_promotion_requests:
                return False
            self._seen_promotion_requests.add(rid)
            if len(self._seen_promotion_requests) > 500:
                # Bound memory; keep recent ids only
                self._seen_promotion_requests = set(
                    list(self._seen_promotion_requests)[-250:]
                )
            return True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = [c.to_dict() for c in self.candidates.values()]
        return {
            "count": len(rows),
            "promotable": sum(1 for r in rows if r["status"] == "PROMOTABLE"),
            "not_promotable": sum(1 for r in rows if r["status"] == "NOT_PROMOTABLE"),
            "recent": rows[-20:],
        }
