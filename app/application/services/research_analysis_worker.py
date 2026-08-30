"""Research analysis worker — keeps market-universe research snapshot fresh.

NOT a second scanner / gateway / trading engine.
Reuses MarketUniverseService.build_snapshot + research batch scoring.
Never calls OMS / order_send. Never enables live trading.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# Slow cadence — catalogue TTL is 60s; avoid request storms.
RESEARCH_ANALYSIS_INTERVAL_S = 90.0
RESEARCH_ANALYSIS_BACKOFF_S = 30.0

_LOCK = Lock()
_HEALTH: dict[str, Any] = {
    "status": "STOPPED",
    "layer": "RESEARCH_ANALYSIS",
    "authorizes_trade": False,
    "ALLOW_LIVE_PROMOTION": False,
    "would_submit_order": False,
    "forwarded_to_oms": False,
    "second_scanner": False,
    "second_engine": False,
    "second_gateway": False,
    "last_scan_started": None,
    "last_scan_completed": None,
    "last_error": None,
    "scan_duration_ms": None,
    "instruments_discovered": None,
    "instruments_analyzed": None,
    "signals_generated": None,
    "catalogue_source": None,
    "cycles": 0,
    "failures": 0,
}


def get_research_analysis_health() -> dict[str, Any]:
    with _LOCK:
        return dict(_HEALTH)


def _set_health(**fields: Any) -> None:
    with _LOCK:
        _HEALTH.update(fields)


def _bump(*, failures: bool = False, cycles: bool = False) -> None:
    with _LOCK:
        if failures:
            _HEALTH["failures"] = int(_HEALTH.get("failures") or 0) + 1
        if cycles:
            _HEALTH["cycles"] = int(_HEALTH.get("cycles") or 0) + 1


def reset_research_analysis_health_for_tests() -> None:
    with _LOCK:
        _HEALTH.update(
            {
                "status": "STOPPED",
                "last_scan_started": None,
                "last_scan_completed": None,
                "last_error": None,
                "scan_duration_ms": None,
                "instruments_discovered": None,
                "instruments_analyzed": None,
                "signals_generated": None,
                "catalogue_source": None,
                "cycles": 0,
                "failures": 0,
            }
        )


def _resolve_adapter() -> Any | None:
    try:
        from core.di.container import get_container

        container = get_container()
    except Exception:
        return None
    return getattr(container, "mt5_adapter", None)


def run_research_analysis_once(*, mt5_adapter: Any | None = None) -> dict[str, Any]:
    """One research refresh cycle. Never OMS."""
    from app.application.services.market_universe_service import MarketUniverseService
    from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION

    if ALLOW_LIVE_PROMOTION:
        raise RuntimeError("ALLOW_LIVE_PROMOTION must stay false")

    adapter = mt5_adapter if mt5_adapter is not None else _resolve_adapter()
    started = datetime.now(UTC).isoformat()
    _set_health(status="RUNNING", last_scan_started=started, last_error=None)
    t0 = datetime.now(UTC)
    try:
        snap = MarketUniverseService().snapshot(
            refresh=True,
            mt5_adapter=adapter,
        )
    except Exception as exc:
        _set_health(
            status="DEGRADED",
            last_error=f"{type(exc).__name__}:{exc}",
        )
        _bump(failures=True)
        logger.exception("research_analysis_cycle_failed")
        return get_research_analysis_health()

    elapsed_ms = int((datetime.now(UTC) - t0).total_seconds() * 1000)
    obs = snap.get("observability") if isinstance(snap, dict) else {}
    if not isinstance(obs, dict):
        obs = {}
    rs = snap.get("research_signals") if isinstance(snap, dict) else {}
    signal_n = rs.get("n") if isinstance(rs, dict) else None
    source = snap.get("catalogue_source") if isinstance(snap, dict) else None
    status = "RUNNING"
    if source in {"UNAVAILABLE", "ERROR", "MOCK"}:
        status = "DEGRADED"
    _bump(cycles=True)
    _set_health(
        status=status,
        last_scan_completed=datetime.now(UTC).isoformat(),
        scan_duration_ms=elapsed_ms,
        instruments_discovered=obs.get("symbol_count"),
        instruments_analyzed=obs.get("symbols_scored"),
        instruments_research_attempted=obs.get("symbols_research_attempted"),
        instruments_research_returned=obs.get("symbols_research_returned"),
        research_batch=obs.get("research_batch"),
        signals_generated=signal_n,
        catalogue_source=source,
        authorizes_trade=False,
        would_submit_order=False,
        forwarded_to_oms=False,
        second_scanner=False,
    )
    return get_research_analysis_health()


async def research_analysis_loop(
    *,
    interval_s: float = RESEARCH_ANALYSIS_INTERVAL_S,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Background research refresh. Distinct from live-trading robot start."""
    stop = stop_event or asyncio.Event()
    _set_health(status="RUNNING")
    logger.info(
        "research_analysis_worker_started",
        interval_s=interval_s,
        authorizes_trade=False,
        second_scanner=False,
    )
    # Wait for broker auto-restore attempt so first scan does not race redeploy.
    try:
        from core.di.container import get_container

        container = get_container()
        ev = getattr(container, "broker_restore_finished", None)
        if ev is not None and not ev.is_set():
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(ev.wait(), timeout=45.0)
        else:
            await asyncio.sleep(2.0)
    except Exception:
        await asyncio.sleep(2.0)
    while not stop.is_set():
        try:
            await asyncio.to_thread(run_research_analysis_once)
        except asyncio.CancelledError:
            _set_health(status="STOPPED")
            raise
        except Exception:
            _set_health(status="DEGRADED")
            _bump(failures=True)
            logger.exception("research_analysis_loop_error")
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=RESEARCH_ANALYSIS_BACKOFF_S)
            continue
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=max(15.0, float(interval_s)))
    _set_health(status="STOPPED")
