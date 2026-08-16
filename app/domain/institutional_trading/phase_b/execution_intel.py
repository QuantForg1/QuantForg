"""Execution-quality intelligence — OBSERVE → MEASURE → COMPARE → REPORT.

Does not change execution policy in Phase B.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any


@dataclass
class ExecutionObservation:
    at: str
    symbol: str
    # Pre
    spread: float | None = None
    quote_age_ms: float | None = None
    gateway_rtt_ms: float | None = None
    mt5_rtt_ms: float | None = None
    market_data_quality: str | None = None
    volatility_state: str | None = None
    # Post
    requested_price: float | None = None
    fill_price: float | None = None
    slippage: float | None = None
    spread_at_entry: float | None = None
    order_submit_latency_ms: float | None = None
    ack_latency_ms: float | None = None
    fill_latency_ms: float | None = None
    broker_retcode: int | None = None
    outcome: str = "unknown"
    slippage_points: float | None = None
    slippage_cost: float | None = None
    execution_quality_score: float | None = None
    execution_degradation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "at": self.at,
            "symbol": self.symbol,
            "spread": self.spread,
            "quote_age_ms": self.quote_age_ms,
            "gateway_rtt_ms": self.gateway_rtt_ms,
            "MT5_rtt_ms": self.mt5_rtt_ms,
            "market_data_quality": self.market_data_quality,
            "volatility_state": self.volatility_state,
            "requested_price": self.requested_price,
            "fill_price": self.fill_price,
            "slippage": self.slippage,
            "spread_at_entry": self.spread_at_entry,
            "order_submit_latency": self.order_submit_latency_ms,
            "ack_latency": self.ack_latency_ms,
            "fill_latency": self.fill_latency_ms,
            "broker_retcode": self.broker_retcode,
            "outcome": self.outcome,
            "slippage_points": self.slippage_points,
            "slippage_cost": self.slippage_cost,
            "execution_quality_score": self.execution_quality_score,
            "execution_degradation": self.execution_degradation,
        }


def score_execution(
    *,
    slippage: float | None,
    latency_ms: float | None,
    spread: float | None,
    outcome: str,
) -> tuple[float | None, bool]:
    """Deterministic 0–100 score; degradation flag is observational only."""
    if outcome in {"reject", "failed", "timeout", "ambiguous"}:
        return 0.0, True
    if outcome not in {"success", "filled", "partial"}:
        return None, False
    score = 100.0
    if slippage is not None:
        score -= min(40.0, abs(float(slippage)) * 20.0)
    if latency_ms is not None:
        if latency_ms > 2000:
            score -= 30.0
        elif latency_ms > 800:
            score -= 15.0
    if spread is not None and spread > 1.0:
        score -= min(20.0, (float(spread) - 1.0) * 10.0)
    score = max(0.0, min(100.0, score))
    return score, score < 55.0


@dataclass
class ExecutionIntelStore:
    events: deque[ExecutionObservation] = field(default_factory=lambda: deque(maxlen=300))
    _lock: RLock = field(default_factory=RLock, repr=False)

    def record(self, **kwargs: Any) -> ExecutionObservation:
        outcome = str(kwargs.get("outcome") or "unknown")
        slip = kwargs.get("slippage")
        lat = kwargs.get("fill_latency_ms") or kwargs.get("order_submit_latency_ms")
        spread = kwargs.get("spread_at_entry") or kwargs.get("spread")
        score, deg = score_execution(
            slippage=float(slip) if slip is not None else None,
            latency_ms=float(lat) if lat is not None else None,
            spread=float(spread) if spread is not None else None,
            outcome=outcome,
        )
        slip_pts = float(slip) if slip is not None else None
        obs = ExecutionObservation(
            at=datetime.now(UTC).isoformat(),
            symbol=str(kwargs.get("symbol") or ""),
            spread=float(kwargs["spread"]) if kwargs.get("spread") is not None else None,
            quote_age_ms=(
                float(kwargs["quote_age_ms"])
                if kwargs.get("quote_age_ms") is not None
                else None
            ),
            gateway_rtt_ms=(
                float(kwargs["gateway_rtt_ms"])
                if kwargs.get("gateway_rtt_ms") is not None
                else None
            ),
            mt5_rtt_ms=(
                float(kwargs["mt5_rtt_ms"])
                if kwargs.get("mt5_rtt_ms") is not None
                else None
            ),
            market_data_quality=kwargs.get("market_data_quality"),
            volatility_state=kwargs.get("volatility_state"),
            requested_price=(
                float(kwargs["requested_price"])
                if kwargs.get("requested_price") is not None
                else None
            ),
            fill_price=(
                float(kwargs["fill_price"])
                if kwargs.get("fill_price") is not None
                else None
            ),
            slippage=float(slip) if slip is not None else None,
            spread_at_entry=float(spread) if spread is not None else None,
            order_submit_latency_ms=(
                float(kwargs["order_submit_latency_ms"])
                if kwargs.get("order_submit_latency_ms") is not None
                else None
            ),
            ack_latency_ms=(
                float(kwargs["ack_latency_ms"])
                if kwargs.get("ack_latency_ms") is not None
                else None
            ),
            fill_latency_ms=(
                float(kwargs["fill_latency_ms"])
                if kwargs.get("fill_latency_ms") is not None
                else None
            ),
            broker_retcode=(
                int(kwargs["broker_retcode"])
                if kwargs.get("broker_retcode") is not None
                else None
            ),
            outcome=outcome,
            slippage_points=slip_pts,
            slippage_cost=slip_pts,  # points proxy; cost unknown without contract
            execution_quality_score=score,
            execution_degradation=deg,
        )
        with self._lock:
            self.events.append(obs)
        return obs

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = list(self.events)
        # Also merge existing execution quality store
        legacy: dict[str, Any] = {}
        try:
            from app.domain.institutional_trading.ai_scalping.execution_quality import (
                get_execution_quality_store,
            )

            legacy = get_execution_quality_store().snapshot()
        except Exception:
            legacy = {}
        scores = [
            r.execution_quality_score
            for r in rows
            if r.execution_quality_score is not None
        ]
        return {
            "mode": "OBSERVE_MEASURE_COMPARE_REPORT",
            "policy_change": False,
            "samples": len(rows),
            "avg_execution_quality_score": (
                round(sum(scores) / len(scores), 2) if scores else None
            ),
            "degradation_events": sum(1 for r in rows if r.execution_degradation),
            "recent": [r.to_dict() for r in list(rows)[-15:]],
            "legacy_execution_quality": legacy,
        }
