"""Distributed trade tracing — one trace_id across Decision→…→Journal."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from app.domain.institutional_trading.reliability.models import (
    TradeTrace,
    TraceSpan,
    TraceStage,
)


def new_trace_id() -> str:
    return uuid4().hex


@dataclass
class TradeTraceStore:
    _traces: dict[str, TradeTrace] = field(default_factory=dict, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)
    max_traces: int = 5000

    def start(
        self,
        *,
        trace_id: str | None = None,
        decision_id: str | None = None,
        symbol: str = "XAUUSD",
        now: datetime | None = None,
    ) -> TradeTrace:
        tid = trace_id or new_trace_id()
        trace = TradeTrace(
            trace_id=tid,
            created_at=now or datetime.now(UTC),
            decision_id=decision_id,
            symbol=symbol,
        )
        with self._lock:
            self._traces[tid] = trace
            if len(self._traces) > self.max_traces:
                # drop oldest by created_at
                oldest = sorted(self._traces.values(), key=lambda t: t.created_at)
                for t in oldest[: len(self._traces) - self.max_traces]:
                    self._traces.pop(t.trace_id, None)
        return trace

    def span(
        self,
        trace_id: str,
        stage: TraceStage,
        *,
        latency_ms: float,
        ok: bool = True,
        detail: str = "",
        now: datetime | None = None,
    ) -> TraceSpan | None:
        moment = now or datetime.now(UTC)
        started = moment
        # approximate start from latency
        from datetime import timedelta

        started = moment - timedelta(milliseconds=max(0.0, latency_ms))
        span = TraceSpan(
            stage=stage,
            started_at=started,
            ended_at=moment,
            latency_ms=latency_ms,
            ok=ok,
            detail=detail,
        )
        with self._lock:
            trace = self._traces.get(trace_id)
            if trace is None:
                return None
            trace.spans.append(span)
        return span

    def get(self, trace_id: str) -> TradeTrace | None:
        with self._lock:
            return self._traces.get(trace_id)

    def list(self, *, limit: int = 100) -> list[TradeTrace]:
        with self._lock:
            rows = sorted(self._traces.values(), key=lambda t: t.created_at)
            return list(rows[-limit:])

    @staticmethod
    def fingerprint_stages(stages: list[TraceStage]) -> str:
        raw = "|".join(s.value for s in stages)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
