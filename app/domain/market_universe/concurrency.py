"""Bounded research concurrency. Never a second trading engine."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.domain.market_universe.constants import MAX_RESEARCH_WORKERS


def map_isolated(
    items: list[Any],
    fn: Callable[[Any], Any],
    *,
    max_workers: int = MAX_RESEARCH_WORKERS,
) -> list[dict[str, Any]]:
    """Apply fn per item. Exceptions become ERROR rows; others continue."""
    workers = max(1, min(int(max_workers or 1), MAX_RESEARCH_WORKERS, len(items) or 1))
    out: list[dict[str, Any]] = []
    if not items:
        return out

    def _run(item: Any) -> dict[str, Any]:
        try:
            result = fn(item)
            return {"ok": True, "item": item, "result": result, "state": "OK"}
        except Exception as exc:
            return {
                "ok": False,
                "item": item,
                "result": None,
                "state": "ERROR",
                "error": str(exc)[:200],
            }

    if workers == 1 or len(items) == 1:
        return [_run(item) for item in items]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_run, item): item for item in items}
        for fut in as_completed(futures):
            try:
                out.append(fut.result())
            except Exception as exc:
                out.append(
                    {
                        "ok": False,
                        "item": futures[fut],
                        "result": None,
                        "state": "ERROR",
                        "error": str(exc)[:200],
                    }
                )
    return out
