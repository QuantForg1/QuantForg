"""The shadow evaluator runs on a schedule and survives a failed pass."""

from __future__ import annotations

import asyncio

import pytest

from app.application.services import shadow_signals as ss


def test_loop_runs_passes_and_survives_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    loop_holder: dict[str, asyncio.AbstractEventLoop] = {}
    done = asyncio.Event()

    def fake_eval(*, days: int, symbol: str) -> int:
        calls.append({"days": days, "symbol": symbol})
        if len(calls) >= 3:
            loop_holder["loop"].call_soon_threadsafe(done.set)
        if len(calls) == 1:
            raise RuntimeError("supabase down")
        return 3

    monkeypatch.setattr(ss, "evaluate_and_store", fake_eval)

    async def run() -> None:
        loop_holder["loop"] = asyncio.get_running_loop()
        task = asyncio.create_task(ss.shadow_evaluation_loop(interval_s=0.01, days=2))
        await done.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(asyncio.wait_for(run(), timeout=5))
    assert calls[0] == {"days": 2, "symbol": "XAUUSD"}
    assert len(calls) >= 3
