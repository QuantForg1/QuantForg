"""Post-trade quality review — observation only."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any


@dataclass(frozen=True, slots=True)
class PostTradeReview:
    trade_id: str
    symbol: str
    entry_quality: str
    execution_quality: str
    position_management: str
    exit_quality: str
    outcome: str
    entry_risk: float | None
    initial_r_target: float | None
    mae_r: float | None
    mfe_r: float | None
    realized_r: float | None
    holding_time: float | None
    slippage: float | None
    exit_reason: str | None
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "ENTRY_QUALITY": self.entry_quality,
            "EXECUTION_QUALITY": self.execution_quality,
            "POSITION_MANAGEMENT": self.position_management,
            "EXIT_QUALITY": self.exit_quality,
            "OUTCOME": self.outcome,
            "entry_Risk": self.entry_risk,
            "initial_R_target": self.initial_r_target,
            "MAE_R": self.mae_r,
            "MFE_R": self.mfe_r,
            "realized_R": self.realized_r,
            "holding_time": self.holding_time,
            "slippage": self.slippage,
            "exit_reason": self.exit_reason,
            "timestamp": self.timestamp,
        }


def _band(value: float | None, *, good: float, ok: float) -> str:
    if value is None:
        return "UNKNOWN"
    if value >= good:
        return "GOOD"
    if value >= ok:
        return "FAIR"
    return "POOR"


def build_post_trade_review(**kwargs: Any) -> PostTradeReview:
    realized = kwargs.get("realized_r")
    mae = kwargs.get("mae_r")
    mfe = kwargs.get("mfe_r")
    exec_q = kwargs.get("execution_quality_score")
    outcome = "WIN" if (realized is not None and float(realized) > 0) else (
        "LOSS" if realized is not None else "UNKNOWN"
    )
    # Entry: captured MFE relative to target when known
    entry_q = "UNKNOWN"
    if mfe is not None:
        entry_q = _band(float(mfe), good=1.0, ok=0.4)
    exec_label = "UNKNOWN"
    if exec_q is not None:
        exec_label = _band(float(exec_q) / 100.0, good=0.7, ok=0.55)
    elif kwargs.get("slippage") is not None:
        exec_label = "FAIR" if abs(float(kwargs["slippage"])) < 0.5 else "POOR"
    # PME observation only
    pm = str(kwargs.get("position_management") or "OBSERVED")
    exit_q = "UNKNOWN"
    if realized is not None and mfe is not None and float(mfe) > 0:
        # Captured fraction of MFE
        frac = float(realized) / float(mfe) if float(mfe) else None
        exit_q = _band(frac, good=0.6, ok=0.3) if frac is not None else "UNKNOWN"
    return PostTradeReview(
        trade_id=str(kwargs.get("trade_id") or ""),
        symbol=str(kwargs.get("symbol") or ""),
        entry_quality=entry_q,
        execution_quality=exec_label,
        position_management=pm,
        exit_quality=exit_q,
        outcome=outcome,
        entry_risk=(
            float(kwargs["entry_risk"]) if kwargs.get("entry_risk") is not None else None
        ),
        initial_r_target=(
            float(kwargs["initial_r_target"])
            if kwargs.get("initial_r_target") is not None
            else None
        ),
        mae_r=float(mae) if mae is not None else None,
        mfe_r=float(mfe) if mfe is not None else None,
        realized_r=float(realized) if realized is not None else None,
        holding_time=(
            float(kwargs["holding_time"])
            if kwargs.get("holding_time") is not None
            else None
        ),
        slippage=(
            float(kwargs["slippage"]) if kwargs.get("slippage") is not None else None
        ),
        exit_reason=kwargs.get("exit_reason"),
        timestamp=str(kwargs.get("timestamp") or datetime.now(UTC).isoformat()),
    )


@dataclass
class PostTradeReviewStore:
    reviews: deque[PostTradeReview] = field(default_factory=lambda: deque(maxlen=300))
    _lock: RLock = field(default_factory=RLock, repr=False)

    def record(self, **kwargs: Any) -> PostTradeReview:
        rev = build_post_trade_review(**kwargs)
        with self._lock:
            self.reviews.append(rev)
        return rev

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = [r.to_dict() for r in self.reviews]
        return {"mode": "OBSERVE_ONLY", "recent": list(rows)[-20:], "count": len(rows)}
