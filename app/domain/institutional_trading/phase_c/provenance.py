"""Immutable research-run provenance. Missing fields → UNVERIFIED."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import uuid4


REQUIRED_FIELDS = (
    "strategy_id",
    "model_id",
    "code_commit",
    "dataset_id",
    "dataset_hash",
    "data_start",
    "data_end",
    "timeframe",
    "symbols",
    "validation_method",
    "number_of_trials",
)


@dataclass
class ResearchProvenanceRecord:
    research_run_id: str
    strategy_id: str
    model_id: str
    code_commit: str
    dataset_id: str
    dataset_hash: str
    data_start: str
    data_end: str
    timeframe: str
    symbols: tuple[str, ...]
    broker_assumptions: dict[str, Any]
    spread_assumptions: dict[str, Any]
    slippage_assumptions: dict[str, Any]
    commission_assumptions: dict[str, Any]
    parameter_space: dict[str, Any]
    number_of_trials: int
    validation_method: str
    random_seed: int | None
    research_timestamp: str
    verified: bool
    status: str  # VERIFIED_RESEARCH_RESULT | UNVERIFIED_RESEARCH_RESULT

    def to_dict(self) -> dict[str, Any]:
        # Spec aliases (trial_count / created_at / timeframes) keep API explicit
        # without inventing metrics when fields are empty.
        return {
            "research_run_id": self.research_run_id,
            "strategy_id": self.strategy_id,
            "model_id": self.model_id,
            "code_commit": self.code_commit,
            "dataset_id": self.dataset_id,
            "dataset_hash": self.dataset_hash,
            "data_start": self.data_start,
            "data_end": self.data_end,
            "timeframe": self.timeframe,
            "timeframes": [self.timeframe] if self.timeframe else [],
            "symbols": list(self.symbols),
            "broker_assumptions": dict(self.broker_assumptions),
            "spread_assumptions": dict(self.spread_assumptions),
            "slippage_assumptions": dict(self.slippage_assumptions),
            "commission_assumptions": dict(self.commission_assumptions),
            "parameter_space": dict(self.parameter_space),
            "number_of_trials": self.number_of_trials,
            "trial_count": self.number_of_trials,
            "validation_method": self.validation_method,
            "random_seed": self.random_seed,
            "random_seed_if_used": self.random_seed,
            "research_timestamp": self.research_timestamp,
            "created_at": self.research_timestamp,
            "verified": self.verified,
            "status": self.status,
        }


def _missing(payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in REQUIRED_FIELDS:
        val = payload.get(key)
        if val is None or val == "" or val == () or val == []:
            missing.append(key)
    return missing


def hash_dataset_payload(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass
class ProvenanceStore:
    records: list[ResearchProvenanceRecord] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def register(self, **kwargs: Any) -> ResearchProvenanceRecord:
        missing = _missing(kwargs)
        verified = not missing
        symbols = kwargs.get("symbols") or ()
        if isinstance(symbols, str):
            symbols = (symbols,)
        rec = ResearchProvenanceRecord(
            research_run_id=str(kwargs.get("research_run_id") or uuid4()),
            strategy_id=str(kwargs.get("strategy_id") or ""),
            model_id=str(kwargs.get("model_id") or ""),
            code_commit=str(kwargs.get("code_commit") or ""),
            dataset_id=str(kwargs.get("dataset_id") or ""),
            dataset_hash=str(kwargs.get("dataset_hash") or ""),
            data_start=str(kwargs.get("data_start") or ""),
            data_end=str(kwargs.get("data_end") or ""),
            timeframe=str(kwargs.get("timeframe") or ""),
            symbols=tuple(str(s) for s in symbols),
            broker_assumptions=dict(kwargs.get("broker_assumptions") or {}),
            spread_assumptions=dict(kwargs.get("spread_assumptions") or {}),
            slippage_assumptions=dict(kwargs.get("slippage_assumptions") or {}),
            commission_assumptions=dict(kwargs.get("commission_assumptions") or {}),
            parameter_space=dict(kwargs.get("parameter_space") or {}),
            number_of_trials=int(kwargs.get("number_of_trials") or 0),
            validation_method=str(kwargs.get("validation_method") or ""),
            random_seed=(
                int(kwargs["random_seed"])
                if kwargs.get("random_seed") is not None
                else None
            ),
            research_timestamp=str(
                kwargs.get("research_timestamp") or datetime.now(UTC).isoformat()
            ),
            verified=verified,
            status=(
                "VERIFIED_RESEARCH_RESULT"
                if verified
                else "UNVERIFIED_RESEARCH_RESULT"
            ),
        )
        if missing:
            # Attach reason without fabricating metrics
            rec.broker_assumptions = {
                **rec.broker_assumptions,
                "_missing_fields": missing,
            }
        with self._lock:
            self.records.append(rec)
            if len(self.records) > 200:
                self.records = self.records[-200:]
        return rec

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = [r.to_dict() for r in self.records]
        latest = rows[-1] if rows else None
        return {
            "count": len(rows),
            "verified_count": sum(1 for r in rows if r.get("verified")),
            "unverified_count": sum(1 for r in rows if not r.get("verified")),
            "latest": latest,
            "recent": rows[-15:],
        }
