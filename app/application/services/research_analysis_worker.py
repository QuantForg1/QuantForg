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
    "instruments_eligible": None,
    "instruments_unavailable": None,
    "instruments_failed": None,
    "instruments_skipped": None,
    "instruments_closed": None,
    "instruments_queued": None,
    "instruments_unsupported": None,
    "coverage_pct": None,
    "coverage_pct_catalogue": None,
    "coverage_state": None,
    "coverage_basis": None,
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
                "instruments_eligible": None,
                "instruments_unavailable": None,
                "instruments_failed": None,
                "instruments_skipped": None,
                "instruments_closed": None,
                "instruments_queued": None,
                "instruments_unsupported": None,
                "coverage_pct": None,
                "coverage_pct_catalogue": None,
                "coverage_state": None,
                "coverage_basis": None,
                "signals_generated": None,
                "catalogue_source": None,
                "cycles": 0,
                "failures": 0,
            }
        )


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value == value:
        return int(value)
    return None


def _coverage_pct(discovered: Any, analyzed: Any) -> float | None:
    disc = _as_int(discovered)
    anal = _as_int(analyzed)
    if disc is None or anal is None or disc <= 0:
        return None
    return round(min(100.0, max(0.0, (anal / disc) * 100.0)), 1)


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
    by_state = (
        obs.get("data_quality_counts")
        if isinstance(obs.get("data_quality_counts"), dict)
        else {}
    )
    discovered = obs.get("symbols_discovered", obs.get("symbol_count"))
    eligible = obs.get("symbols_eligible")
    analyzed = obs.get("symbols_scored")
    unavailable = 0
    if isinstance(by_state, dict):
        for key in ("NO_DATA", "UNAVAILABLE", "INSUFFICIENT_DATA", "STALE"):
            n = _as_int(by_state.get(key))
            if n is not None:
                unavailable += n
    unavailable_out: int | None = unavailable if isinstance(by_state, dict) else None
    closed = (
        _as_int(by_state.get("MARKET_CLOSED")) if isinstance(by_state, dict) else None
    )
    unsupported = 0
    unsupported_found = False
    if isinstance(by_state, dict):
        for key in ("UNSUPPORTED", "DISABLED"):
            n = _as_int(by_state.get(key))
            if n is not None:
                unsupported_found = True
                unsupported += n
    unsupported_out: int | None = unsupported if unsupported_found else None
    failed = obs.get("symbols_failed", obs.get("failed_n"))
    attempted = obs.get("symbols_research_attempted")
    returned = obs.get("symbols_research_returned")
    skipped = obs.get("symbols_skipped")
    if skipped is None:
        att = _as_int(attempted)
        ret = _as_int(returned)
        if att is not None and ret is not None and att >= ret:
            skipped = att - ret
    # Prefer eligible-basis coverage; fall back to catalogue ratio.
    coverage = _coverage_pct(eligible, analyzed)
    if coverage is None:
        coverage = _coverage_pct(discovered, analyzed)
    coverage_catalogue = obs.get("coverage_pct_catalogue")
    if not isinstance(coverage_catalogue, (int, float)):
        coverage_catalogue = _coverage_pct(discovered, analyzed)
    status = "RUNNING"
    if source in {"UNAVAILABLE", "ERROR", "MOCK"}:
        status = "DEGRADED"
    _bump(cycles=True)
    _set_health(
        status=status,
        coverage_state=(
            "DEGRADED"
            if status == "DEGRADED"
            else (
                "READY"
                if coverage is not None and coverage >= 99.5
                else "PARTIAL"
                if coverage is not None
                else "UNKNOWN"
            )
        ),
        last_scan_completed=datetime.now(UTC).isoformat(),
        scan_duration_ms=elapsed_ms,
        instruments_discovered=discovered,
        instruments_eligible=eligible,
        instruments_analyzed=analyzed,
        instruments_unavailable=unavailable_out,
        instruments_failed=failed,
        instruments_skipped=skipped,
        instruments_closed=closed,
        instruments_queued=obs.get("symbols_queued"),
        instruments_unsupported=unsupported_out,
        coverage_pct=coverage,
        coverage_pct_catalogue=coverage_catalogue,
        coverage_basis=obs.get("coverage_basis") or "eligible",
        instruments_research_attempted=attempted,
        instruments_research_returned=returned,
        research_batch=obs.get("research_batch"),
        asset_class_counts=obs.get("asset_class_counts"),
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
