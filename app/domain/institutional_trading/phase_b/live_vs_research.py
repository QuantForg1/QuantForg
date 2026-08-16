"""Live vs research parity — detection/support only. No auto-disable."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass
class EvidenceBucket:
    trade_count: int = 0
    wins: int = 0
    sum_r: float = 0.0
    sum_hold_s: float = 0.0
    hold_n: int = 0
    sum_mae: float = 0.0
    mae_n: int = 0
    sum_mfe: float = 0.0
    mfe_n: int = 0
    sum_slip: float = 0.0
    slip_n: int = 0

    def add(self, **kwargs: Any) -> None:
        self.trade_count += 1
        if kwargs.get("win") is True:
            self.wins += 1
        if kwargs.get("realized_r") is not None:
            self.sum_r += float(kwargs["realized_r"])
        if kwargs.get("holding_time_s") is not None:
            self.sum_hold_s += float(kwargs["holding_time_s"])
            self.hold_n += 1
        if kwargs.get("mae_r") is not None:
            self.sum_mae += float(kwargs["mae_r"])
            self.mae_n += 1
        if kwargs.get("mfe_r") is not None:
            self.sum_mfe += float(kwargs["mfe_r"])
            self.mfe_n += 1
        if kwargs.get("slippage") is not None:
            self.sum_slip += float(kwargs["slippage"])
            self.slip_n += 1

    def metrics(self) -> dict[str, Any]:
        n = self.trade_count
        return {
            "trade_count": n,
            "win_rate": (100.0 * self.wins / n) if n else None,
            "avg_R": (self.sum_r / n) if n else None,
            "expectancy": (self.sum_r / n) if n else None,
            "holding_time": (self.sum_hold_s / self.hold_n) if self.hold_n else None,
            "MAE_R": (self.sum_mae / self.mae_n) if self.mae_n else None,
            "MFE_R": (self.sum_mfe / self.mfe_n) if self.mfe_n else None,
            "slippage": (self.sum_slip / self.slip_n) if self.slip_n else None,
        }


def classify_parity(
    *,
    research: dict[str, Any],
    live: dict[str, Any],
    min_sample: int,
) -> str:
    ln = int(live.get("trade_count") or 0)
    rn = int(research.get("trade_count") or 0)
    if ln < min_sample or rn < min_sample:
        return "INSUFFICIENT_SAMPLE"
    la = live.get("avg_R")
    ra = research.get("avg_R")
    if la is None or ra is None:
        return "INSUFFICIENT_SAMPLE"
    # Soft bands — observational only
    if float(la) >= float(ra) * 1.05:
        return "LIVE_OUTPERFORMING"
    if float(la) <= float(ra) * 0.85:
        return "LIVE_DEGRADING"
    return "LIVE_ALIGNED"


@dataclass
class LiveVsResearchStore:
    research: dict[str, EvidenceBucket] = field(default_factory=dict)
    live: dict[str, EvidenceBucket] = field(default_factory=dict)
    min_sample: int = 20
    _lock: RLock = field(default_factory=RLock, repr=False)

    def record_live(self, strategy: str = "ALL", **kwargs: Any) -> None:
        key = str(strategy or "ALL")
        with self._lock:
            self.live.setdefault(key, EvidenceBucket()).add(**kwargs)

    def record_research(self, strategy: str = "ALL", **kwargs: Any) -> None:
        key = str(strategy or "ALL")
        with self._lock:
            self.research.setdefault(key, EvidenceBucket()).add(**kwargs)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            keys = sorted(set(self.research) | set(self.live))
            rows = []
            for k in keys:
                r = self.research.get(k, EvidenceBucket()).metrics()
                l = self.live.get(k, EvidenceBucket()).metrics()
                rows.append(
                    {
                        "strategy": k,
                        "RESEARCH_EXPECTATION": r,
                        "LIVE_REALIZATION": l,
                        "state": classify_parity(
                            research=r, live=l, min_sample=self.min_sample
                        ),
                    }
                )
        return {
            "min_sample_trades": self.min_sample,
            "comparisons": rows,
            "auto_disable": False,
        }
