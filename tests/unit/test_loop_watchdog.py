from __future__ import annotations

import asyncio
import time
from typing import Any

from app.infrastructure.observability import loop_watchdog as wd


def _block_loop(seconds: float) -> None:
    time.sleep(seconds)  # deliberately block the calling (loop) thread


def test_watchdog_reports_a_blocked_loop(monkeypatch: Any) -> None:
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr(wd, "_started", False)
    monkeypatch.setattr(
        wd.logger, "warning", lambda event, **kw: seen.append({"event": event, **kw})
    )

    async def scenario() -> None:
        wd.start_loop_watchdog(asyncio.get_running_loop(), threshold_s=1.0)
        await asyncio.sleep(0.1)
        _block_loop(2.6)
        await asyncio.sleep(0.1)

    asyncio.run(scenario())
    assert seen and seen[0]["event"] == "event_loop_blocked"
    assert any("test_loop_watchdog" in line for line in seen[0]["stack"])
