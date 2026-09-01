"""24/7 autonomous worker state — derived, never a second engine.

The process stays alive across broker open/close. These labels describe
what the existing scheduler is doing. They do not authorize orders.
"""

from __future__ import annotations

from typing import Any

SCHEDULER_STALLED = "SCHEDULER_STALLED"

STARTING = "STARTING"
READY = "READY"
RUNNING = "RUNNING"
WAITING_SESSION = "WAITING_SESSION"
DEGRADED = "DEGRADED"
RECOVERING = "RECOVERING"
HALTED_BY_OPERATOR = "HALTED_BY_OPERATOR"
HALTED_BY_RISK = "HALTED_BY_RISK"
ERROR = "ERROR"

_CLOSED = frozenset({"BROKER_SESSION_CLOSED", "false", "0"})


def healthy_cycle_window_seconds(interval_seconds: float) -> float:
    """No-completed-cycle window before SCHEDULER_STALLED."""
    try:
        interval = float(interval_seconds or 5.0)
    except (TypeError, ValueError):
        interval = 5.0
    return max(90.0, interval * 12.0)


def cycle_hard_timeout_seconds(interval_seconds: float) -> float:
    """Abort a hung cycle. Cold scans may exceed the 90s stall window."""
    window = healthy_cycle_window_seconds(interval_seconds)
    return max(180.0, window * 2.0)


# Leave wall-clock for PME + one Risk→OMS path after the scan.
CYCLE_EXECUTION_RESERVE_SECONDS = 40.0
CYCLE_SCAN_BUDGET_CAP_SECONDS = 75.0
SCAN_SYMBOL_TIMEOUT_SECONDS = 12.0


def cycle_scan_budget_seconds(
    interval_seconds: float,
    *,
    remaining: float | None = None,
) -> float:
    """Scan must finish with reserve left for PME / Risk / OMS / MT5."""
    hard = cycle_hard_timeout_seconds(interval_seconds)
    cap = min(
        CYCLE_SCAN_BUDGET_CAP_SECONDS,
        max(20.0, hard - CYCLE_EXECUTION_RESERVE_SECONDS),
    )
    if remaining is None:
        return cap
    try:
        left = float(remaining)
    except (TypeError, ValueError):
        left = cap
    return max(5.0, min(cap, left - CYCLE_EXECUTION_RESERVE_SECONDS))


def scheduler_is_stalled(
    *,
    last_cycle_finished_mono: float,
    now_mono: float,
    interval_seconds: float,
    started_mono: float,
    running: bool,
    cycle_started_mono: float = 0.0,
) -> bool:
    """True when the loop has not finished a cycle inside the healthy window.

    Closed-session manage-only cycles count as completed. Stall means the
    scheduler itself stopped ticking — not WAITING_SESSION. A cycle that is
    still in flight is not stalled until it exceeds the hard timeout.
    """
    if not running:
        return False
    window = healthy_cycle_window_seconds(interval_seconds)
    hard = cycle_hard_timeout_seconds(interval_seconds)
    if cycle_started_mono > last_cycle_finished_mono:
        return (now_mono - cycle_started_mono) > hard
    if last_cycle_finished_mono <= 0:
        return (now_mono - started_mono) > window
    age = now_mono - last_cycle_finished_mono
    return age > window


def derive_worker_state(
    *,
    running: bool,
    cycles: int,
    broker_session_open: bool | None,
    operator_halt: bool,
    risk_halt: bool,
    recovering: bool,
    degraded: bool,
    last_outcome: str | None,
    stalled: bool,
) -> str:
    """Single worker_state from existing signals. Fail-closed, never invents OPEN."""
    if not running:
        return ERROR if last_outcome == "error" else STARTING
    if operator_halt:
        return HALTED_BY_OPERATOR
    if risk_halt:
        return HALTED_BY_RISK
    if stalled:
        return ERROR
    if recovering:
        return RECOVERING
    if broker_session_open is False:
        return WAITING_SESSION
    # Recoverable cycle failures (CYCLE_TIMEOUT / CYCLE_EXCEPTION) keep the
    # loop alive. ERROR is reserved for a stopped or stalled scheduler.
    if degraded:
        return DEGRADED
    if cycles <= 0:
        return STARTING if broker_session_open is not True else READY
    if broker_session_open is True:
        return RUNNING
    return READY


def derive_scheduler_state(
    *,
    running: bool,
    stalled: bool,
    broker_session_open: bool | None,
) -> str:
    if not running:
        return "STOPPED"
    if stalled:
        return SCHEDULER_STALLED
    if broker_session_open is False:
        return WAITING_SESSION
    return RUNNING


def build_cycle_ops_summary(
    *,
    cycle_id: Any = None,
    cycle_start: str | None = None,
    cycle_end: str | None = None,
    last_cycle: dict[str, Any] | None = None,
    last_scan: dict[str, Any] | None = None,
    positions_managed: int | None = None,
) -> dict[str, Any]:
    """Per-cycle ops snapshot. Observability only — never authorizes orders."""
    cycle = last_cycle if isinstance(last_cycle, dict) else {}
    scan = last_scan if isinstance(last_scan, dict) else {}
    rows = scan.get("rows") or scan.get("noc_rows") or []
    if not isinstance(rows, list):
        rows = []
    ready = 0
    failed = 0
    signals = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("context_status") or "")
        if status == "SYMBOL_CONTEXT_READY":
            ready += 1
        reason = str(row.get("reject_reason") or row.get("context_reason") or "")
        isolated = str(row.get("failure_class") or "") == "SYMBOL_FAILURE"
        not_ready = bool(row.get("reject")) and status == "SYMBOL_CONTEXT_NOT_READY"
        named = reason in {
            "SYMBOL_TIMEOUT",
            "SYMBOL_UNAVAILABLE",
            "CYCLE_BUDGET_EXHAUSTED",
        }
        if isolated or not_ready or named:
            failed += 1
        if str(row.get("direction") or "").upper() in {"BUY", "SELL"}:
            signals += 1
    handoff = cycle.get("execution_handoff")
    if not isinstance(handoff, dict):
        diag = cycle.get("market_context_diagnostics")
        raw_h = diag.get("execution_handoff") if isinstance(diag, dict) else None
        handoff = raw_h if isinstance(raw_h, dict) else {}
    ticket = cycle.get("mt5_ticket") or cycle.get("broker_ticket")
    no_ticket = ticket in (None, "", 0, "0")
    forwarded = bool(cycle.get("forwarded_to_oms") or handoff.get("oms_forwarded"))
    risk_passed = bool(handoff.get("risk_passed"))
    risk_entered = bool(handoff.get("risk_entered"))
    oms_passed = bool(handoff.get("oms_forwarded") or handoff.get("oms_entered"))
    abort = str(cycle.get("abort_reason") or "") or None
    outcome = str(cycle.get("cycle_outcome") or "") or None
    return {
        "cycle_id": cycle_id,
        "cycle_start": cycle_start,
        "cycle_end": cycle_end,
        "symbols_targeted": int(
            scan.get("symbols_queued") or len(scan.get("universe") or []) or 0
        ),
        "symbols_evaluated": int(scan.get("symbols_evaluated") or 0),
        "symbols_ready": ready,
        "signals_found": int(scan.get("signals_found") or signals),
        "tradeable_count": int(scan.get("eligible_count") or 0),
        "risk_approved": 1 if risk_passed else 0,
        "risk_rejected": 1 if risk_entered and not risk_passed else 0,
        "oms_approved": 1 if bool(handoff.get("oms_forwarded")) else 0,
        "oms_rejected": (
            1 if oms_passed and not bool(handoff.get("oms_forwarded")) else 0
        ),
        "orders_attempted": 1 if forwarded else 0,
        "orders_submitted": 1 if forwarded else 0,
        "tickets_confirmed": 0 if no_ticket else 1,
        "positions_managed": int(positions_managed or 0),
        "symbols_failed": failed,
        "cycle_status": abort or outcome or "RUNNING",
        "mt5_ticket": None if no_ticket else ticket,
    }


def last_blocker_from_cycle(cycle: Any) -> tuple[str | None, str | None]:
    """Named blocker + stage. Never collapse to generic NO_TRADE."""
    if cycle is None:
        return None, None
    abort = str(getattr(cycle, "abort_reason", None) or "") or None
    outcome = str(getattr(cycle, "cycle_outcome", None) or "") or None
    detail = str(getattr(cycle, "detail", None) or "")
    if abort and abort not in {"NONE", "None"}:
        stage = outcome or "execution"
        if "SESSION" in abort or "BROKER_SESSION" in (detail or ""):
            stage = "session"
        elif "ORDER_CALC" in abort or "CALCULATION" in abort:
            stage = "calculation"
        elif "GATEWAY" in abort or "GATEWAY" in (detail or "").upper():
            stage = "gateway"
        elif "RISK" in abort or "MIN_LOT" in abort or "MIN_LOT" in (detail or ""):
            stage = "risk"
        elif "SAFETY" in abort:
            stage = "safety"
        elif abort == "CYCLE_TIMEOUT":
            diag = getattr(cycle, "market_context_diagnostics", None)
            if isinstance(diag, dict) and diag.get("timeout_stage"):
                stage = str(diag.get("timeout_stage"))
            else:
                stage = "timeout"
        return abort, stage
    if outcome in {"safety_blocked", "no_snapshot", "error"}:
        return (detail or outcome), outcome
    return None, outcome
