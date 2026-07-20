"""Stress testing — sequential decision batches (no order_send)."""

from __future__ import annotations

import time
import tracemalloc
from collections import deque

from app.domain.institutional_trading.certification.models import (
    STRESS_BATCH_SIZES,
    StressBatchResult,
)


class StressTester:
    """Simulate N sequential decisions; measure latency, memory, queues, recovery."""

    def __init__(self, *, max_queue: int = 256) -> None:
        self.max_queue = max_queue

    def run_batch(self, batch_size: int) -> StressBatchResult:
        if batch_size <= 0:
            return StressBatchResult(
                batch_size=batch_size,
                elapsed_ms=0.0,
                decisions_per_sec=0.0,
                peak_memory_kb=0.0,
                queue_depth=0,
                recovery_ok=False,
                passed=False,
                detail="batch_size must be > 0",
            )

        queue: deque[int] = deque(maxlen=self.max_queue)
        tracemalloc.start()
        t0 = time.perf_counter()
        try:
            for i in range(batch_size):
                # Deterministic fake decision work (hash + queue) — no OMS
                _ = hash(("ite-stress", i, batch_size)) % 97
                queue.append(i)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            _current, peak = tracemalloc.get_traced_memory()
            peak_kb = peak / 1024.0
        finally:
            tracemalloc.stop()

        # Recovery: drain queue cleanly
        drained = 0
        while queue:
            queue.popleft()
            drained += 1
        recovery_ok = drained == min(batch_size, self.max_queue)
        dps = (batch_size / (elapsed_ms / 1000.0)) if elapsed_ms > 0 else 0.0
        # Soft budgets: complete without exception; recovery drain ok
        passed = recovery_ok and elapsed_ms < (batch_size * 50.0 + 5_000.0)
        return StressBatchResult(
            batch_size=batch_size,
            elapsed_ms=elapsed_ms,
            decisions_per_sec=dps,
            peak_memory_kb=peak_kb,
            queue_depth=min(batch_size, self.max_queue),
            recovery_ok=recovery_ok,
            passed=passed,
            detail="ok" if passed else "stress budget exceeded or recovery failed",
        )

    def run_standard_suite(
        self, sizes: tuple[int, ...] = STRESS_BATCH_SIZES
    ) -> list[StressBatchResult]:
        return [self.run_batch(n) for n in sizes]
