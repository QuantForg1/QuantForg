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


def scheduler_is_stalled(
    *,
    last_cycle_finished_mono: float,
    now_mono: float,
    interval_seconds: float,
    started_mono: float,
    running: bool,
) -> bool:
    """True when the loop has not finished a cycle inside the healthy window.

    Closed-session manage-only cycles count as completed. Stall means the
    scheduler itself stopped ticking — not WAITING_SESSION.
    """
    if not running:
        return False
    if last_cycle_finished_mono <= 0:
        window = healthy_cycle_window_seconds(interval_seconds)
        return (now_mono - started_mono) > window
    age = now_mono - last_cycle_finished_mono
    return age > healthy_cycle_window_seconds(interval_seconds)


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
    if last_outcome == "error" and cycles > 0:
        return ERROR
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
        elif "RISK" in abort or "MIN_LOT" in (detail or ""):
            stage = "risk"
        elif "SAFETY" in abort:
            stage = "safety"
        return abort, stage
    if outcome in {"safety_blocked", "no_snapshot", "error"}:
        return (detail or outcome), outcome
    return None, outcome
