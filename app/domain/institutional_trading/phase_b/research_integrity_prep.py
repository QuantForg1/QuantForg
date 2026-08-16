"""Phase C preparation — research integrity data structures only.

Do NOT run PBO / Deflated Sharpe in LIVE decisioning in Phase B.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass
class ResearchTrialRecord:
    trial_id: str
    strategy: str
    parameter_set: dict[str, Any]
    sample_count: int
    oos_windows: int
    walk_forward_windows: int
    research_performance: dict[str, Any]
    validation_performance: dict[str, Any]
    live_performance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "strategy": self.strategy,
            "parameter_set": dict(self.parameter_set),
            "sample_count": self.sample_count,
            "out_of_sample_windows": self.oos_windows,
            "walk_forward_windows": self.walk_forward_windows,
            "research_performance": dict(self.research_performance),
            "validation_performance": dict(self.validation_performance),
            "live_performance": dict(self.live_performance),
        }


@dataclass
class ResearchIntegrityPrepStore:
    trials: list[ResearchTrialRecord] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def register_trial(self, **kwargs: Any) -> ResearchTrialRecord:
        rec = ResearchTrialRecord(
            trial_id=str(kwargs.get("trial_id") or ""),
            strategy=str(kwargs.get("strategy") or ""),
            parameter_set=dict(kwargs.get("parameter_set") or {}),
            sample_count=int(kwargs.get("sample_count") or 0),
            oos_windows=int(kwargs.get("oos_windows") or 0),
            walk_forward_windows=int(kwargs.get("walk_forward_windows") or 0),
            research_performance=dict(kwargs.get("research_performance") or {}),
            validation_performance=dict(kwargs.get("validation_performance") or {}),
            live_performance=dict(kwargs.get("live_performance") or {}),
        )
        with self._lock:
            self.trials.append(rec)
            if len(self.trials) > 200:
                self.trials = self.trials[-200:]
        return rec

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "phase": "B_PREP_FOR_C",
                "deflated_sharpe_in_live": False,
                "pbo_in_live": False,
                "number_of_strategy_trials": len(self.trials),
                "trials": [t.to_dict() for t in self.trials[-20:]],
            }
