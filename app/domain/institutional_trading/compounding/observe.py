"""Process-local shadow compounding telemetry. Observe only."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from app.domain.institutional_trading.compounding.engine import (
    evaluate_compounding_shadow,
)
from app.domain.institutional_trading.compounding.models import (
    CompoundingInputs,
    CompoundingObservation,
)

_MAX = 200


@dataclass
class CompoundingShadowStore:
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _recent: deque[dict[str, Any]] = field(default_factory=deque, repr=False)
    observations: int = 0
    high_conviction_signals: int = 0
    high_conviction_executions: int = 0
    capital_attack_candidates: int = 0
    capital_attack_executions: int = 0
    winner_scale_ins: int = 0
    rejected_scale_ins: int = 0
    min_lot_infeasible: int = 0
    risk_blocks: int = 0
    safety_blocks: int = 0
    live_mutations: int = 0

    def __post_init__(self) -> None:
        self._recent = deque(maxlen=_MAX)

    def observe(self, inputs: CompoundingInputs) -> CompoundingObservation:
        obs = evaluate_compounding_shadow(inputs)
        row = obs.to_dict()
        with self._lock:
            self.observations += 1
            if obs.mode in {"HIGH_CONVICTION", "CAPITAL_ATTACK"}:
                self.high_conviction_signals += 1
            if obs.mode == "CAPITAL_ATTACK":
                self.capital_attack_candidates += 1
            if inputs.forwarded_to_oms and obs.mode in {
                "HIGH_CONVICTION",
                "CAPITAL_ATTACK",
            }:
                self.high_conviction_executions += 1
            if inputs.forwarded_to_oms and obs.mode == "CAPITAL_ATTACK":
                self.capital_attack_executions += 1
            if obs.scale_in.shadow_eligible:
                self.winner_scale_ins += 1
            else:
                self.rejected_scale_ins += 1
            cls = str(inputs.min_lot_classification or "").upper()
            if "INFEASIBLE" in cls:
                self.min_lot_infeasible += 1
            stage = str(inputs.blocking_stage or "").upper()
            if stage == "RISK" or "MIN_LOT" in str(inputs.fault_code or "").upper():
                self.risk_blocks += 1
            if stage == "SAFETY":
                self.safety_blocks += 1
            self._recent.append(row)
        return obs

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            last = self._recent[-1] if self._recent else None
            return {
                "advisory_only": True,
                "mutates_engines": False,
                "live_activation": "SHADOW_ONLY",
                "live_mutations": self.live_mutations,
                "observations": self.observations,
                "high_conviction_signals": self.high_conviction_signals,
                "high_conviction_executions": self.high_conviction_executions,
                "capital_attack_candidates": self.capital_attack_candidates,
                "capital_attack_executions": self.capital_attack_executions,
                "winner_scale_ins_shadow": self.winner_scale_ins,
                "rejected_scale_ins": self.rejected_scale_ins,
                "min_lot_infeasible_signals": self.min_lot_infeasible,
                "risk_blocks": self.risk_blocks,
                "safety_blocks": self.safety_blocks,
                "last": last,
            }


_STORE: CompoundingShadowStore | None = None
_STORE_LOCK = threading.Lock()


def get_compounding_shadow_store() -> CompoundingShadowStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = CompoundingShadowStore()
        return _STORE


def reset_compounding_shadow_store_for_tests() -> None:
    global _STORE
    with _STORE_LOCK:
        _STORE = CompoundingShadowStore()
