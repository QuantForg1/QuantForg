#!/usr/bin/env python3
"""Lightweight concurrent load probe against local ASGI app (no network)."""

from __future__ import annotations

import asyncio
import os
import statistics
import time
from typing import Any

os.environ["APP_ENV"] = "testing"
os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-that-is-long-enough-for-validation-32chars",
)
os.environ["RELOAD"] = "false"
os.environ["EXECUTION_ENABLED"] = "false"
os.environ["ALLOWED_HOSTS"] = "*"
os.environ["DEBUG"] = "true"
os.environ["LOG_LEVEL"] = "ERROR"

from httpx import ASGITransport, AsyncClient  # noqa: E402

from core.config.settings import get_settings  # noqa: E402


async def _run_wave(
    client: AsyncClient, path: str, concurrency: int
) -> dict[str, Any]:
    latencies: list[float] = []
    errors = 0

    async def one() -> None:
        nonlocal errors
        t0 = time.perf_counter()
        try:
            r = await client.get(path, headers={"Host": "test"})
            if r.status_code >= 500:
                errors += 1
        except Exception:
            errors += 1
        latencies.append((time.perf_counter() - t0) * 1000)

    await asyncio.gather(*[one() for _ in range(concurrency)])
    latencies.sort()

    def pct(p: float) -> float:
        if not latencies:
            return 0.0
        idx = min(len(latencies) - 1, int(round((p / 100) * (len(latencies) - 1))))
        return round(latencies[idx], 2)

    return {
        "concurrency": concurrency,
        "path": path,
        "count": len(latencies),
        "errors": errors,
        "error_rate": round(errors / max(len(latencies), 1), 4),
        "p50_ms": pct(50),
        "p95_ms": pct(95),
        "p99_ms": pct(99),
        "avg_ms": round(statistics.mean(latencies), 2) if latencies else 0.0,
        "max_ms": round(max(latencies), 2) if latencies else 0.0,
    }


async def main() -> None:
    get_settings.cache_clear()
    from core.config.environments import testing_settings
    import core.config.settings as settings_module

    settings = testing_settings()
    settings_module.get_settings = lambda: settings  # type: ignore[assignment]

    from app.main import create_app

    app = create_app(settings=settings)
    transport = ASGITransport(app=app)
    results = []
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            for n in (100, 500, 1000):
                for path in ("/", "/health/live", "/api/v1/version"):
                    wave = await _run_wave(client, path, n)
                    results.append(wave)
                    print(
                        f"c={n:4d} {path:20s} "
                        f"p50={wave['p50_ms']:7.1f} "
                        f"p95={wave['p95_ms']:7.1f} "
                        f"p99={wave['p99_ms']:7.1f} "
                        f"err={wave['error_rate']:.4f}",
                        flush=True,
                    )
    import json
    from pathlib import Path

    Path("/tmp/qf_load_test.json").write_text(json.dumps(results, indent=2))
    print("LOAD_TEST_COMPLETE", len(results), "waves")


if __name__ == "__main__":
    asyncio.run(main())
