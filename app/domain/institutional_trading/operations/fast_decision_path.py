"""Fast decision path — classify cycle outcomes without changing Safety/Risk/OMS.

Removes advisory latency from operator interpretation and tells the scheduler
when a *candidate* block should rotate focus vs when a *hard* gate must stay
fail-closed.

Does not force trades. Does not retry order_send. Does not mutate SL/TP/volume.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.domain.institutional_trading.operations.execution_halt_policy import (
    HaltClass,
    classify_halt_condition,
)

WINDOW_SECONDS = 30 * 60
# Hold current eligible focus unless another eligible desk scores this much higher.
FOCUS_MATERIAL_DELTA = 12
_LATENCY_SAMPLES = 64


class DecisionState(StrEnum):
    SETUP_NOT_READY = "SETUP_NOT_READY"
    FOCUS_FORMING = "FOCUS_FORMING"
    WAIT_SAME_FOCUS = "WAIT_SAME_FOCUS"
    DEGRADED = "DEGRADED"
    CANDIDATE_BLOCK = "CANDIDATE_BLOCK"
    HARD_BLOCK = "HARD_BLOCK"
    SYSTEM_BLOCK = "SYSTEM_BLOCK"
    EXECUTION_READY = "EXECUTION_READY"
    EXECUTION_AUTHORIZED = "EXECUTION_AUTHORIZED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_UNKNOWN = "ORDER_UNKNOWN"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    POSITION_OPEN = "POSITION_OPEN"
    NO_TRADE = "NO_TRADE"


class FaultClass(StrEnum):
    ADVISORY = "ADVISORY"
    CANDIDATE_BLOCK = "CANDIDATE_BLOCK"
    HARD_BLOCK = "HARD_BLOCK"
    SYSTEM_BLOCK = "SYSTEM_BLOCK"
    WAIT = "WAIT"
    NONE = "NONE"


class CandidateAction(StrEnum):
    CONTINUE = "CONTINUE"
    HOLD_FOCUS = "HOLD_FOCUS"
    WAIT_SAME_FOCUS = "WAIT_SAME_FOCUS"
    ROTATE_FOCUS = "ROTATE_FOCUS"
    FAIL_CLOSED = "FAIL_CLOSED"
    RECONCILE = "RECONCILE"


def _norm(text: str) -> str:
    raw = str(text or "").lower()
    for ch in ("_", "-", ":", "/", ".", ",", "(", ")", "[", "]"):
        raw = raw.replace(ch, " ")
    return " ".join(raw.split())


_ROTATE_NEEDLES: tuple[str, ...] = (
    "min lot",
    "below min lot",
    "minimum lot causes risk",
    "min lot constraint",
    "min lot risk",
    "symbol not tradable",
    "symbol tradable",
    "not tradable",
    "closeonly",
    "close only",
    "trade mode disabled",
    "market closed",
    "symbol allowed",
    "not in allowlist",
    "allowlist",
    "execution infeasible",
    "portfolio conflict",
)

_WAIT_NEEDLES: tuple[str, ...] = (
    "spread too high",
    "unacceptable spread",
    "optimizer defer",
    "defer submit",
    "remaining wait",
    "setup not ready",
    "no eligible setup",
    "no trade",
    "watch",
    "session invalid",
    "trading session",
    "quote temporarily",
    "tick unavailable",
)

_SYSTEM_NEEDLES: tuple[str, ...] = (
    "kill switch",
    "emergency stop",
    "gateway unavailable",
    "gateway disconnected",
    "mt5 disconnected",
    "mt5 unavailable",
    "oms reject",
    "oms rejection",
    "cycle exception",
)

_UNKNOWN_NEEDLES: tuple[str, ...] = (
    "order unknown",
    "unknown order",
    "reconciliation required",
    "reconciliation unknown",
    "ambiguous",
)


def _hay(*parts: str) -> str:
    return _norm(" ".join(p for p in parts if p))


def classify_candidate_outcome(
    *,
    abort_reason: str | None = None,
    failed_reasons: tuple[str, ...] | list[str] = (),
    cycle_outcome: str | None = None,
    forwarded_to_oms: bool = False,
    decision_action: str | None = None,
) -> dict[str, Any]:
    """Map an existing cycle abort into decision state + next_action.

    Advisory halt-policy reasons never rotate or fail-closed.
    """
    action = str(decision_action or "").upper()
    abort = str(abort_reason or "")
    outcome = str(cycle_outcome or "")
    reasons = [str(r) for r in (failed_reasons or ()) if str(r).strip()]
    hay = _hay(abort, outcome, *reasons)

    if forwarded_to_oms and action in {"BUY", "SELL"}:
        return {
            "decision_state": DecisionState.ORDER_SUBMITTED.value,
            "fault_class": FaultClass.NONE.value,
            "fault_code": "OMS_AUTHORIZED",
            "fault_reason": abort or "forwarded_to_oms",
            "retryable": False,
            "candidate_action": CandidateAction.HOLD_FOCUS.value,
            "next_action": CandidateAction.HOLD_FOCUS.value,
            "blocking_stage": "OMS",
            "skip_idle_sleep": False,
            "release_entry_budget": False,
        }

    if any(n in hay for n in _UNKNOWN_NEEDLES):
        return {
            "decision_state": DecisionState.ORDER_UNKNOWN.value,
            "fault_class": FaultClass.HARD_BLOCK.value,
            "fault_code": "ORDER_UNKNOWN",
            "fault_reason": abort or "ORDER_UNKNOWN",
            "retryable": False,
            "candidate_action": CandidateAction.RECONCILE.value,
            "next_action": CandidateAction.RECONCILE.value,
            "blocking_stage": "RECONCILIATION",
            "skip_idle_sleep": False,
            "release_entry_budget": False,
        }

    halt = classify_halt_condition(hay)
    if halt is HaltClass.ADVISORY:
        return {
            "decision_state": DecisionState.DEGRADED.value,
            "fault_class": FaultClass.ADVISORY.value,
            "fault_code": "ADVISORY_DEGRADED",
            "fault_reason": abort or reasons[0] if reasons else "advisory",
            "retryable": True,
            "candidate_action": CandidateAction.CONTINUE.value,
            "next_action": CandidateAction.CONTINUE.value,
            "blocking_stage": "ADVISORY",
            "skip_idle_sleep": True,
            "release_entry_budget": True,
        }

    system_wide = any(n in hay for n in _SYSTEM_NEEDLES)
    if (
        any(n in hay for n in _ROTATE_NEEDLES)
        and not system_wide
    ):
        code = "CANDIDATE_BLOCK"
        if "min lot" in hay or "minimum lot" in hay:
            code = "MIN_LOT_RISK_INFEASIBLE"
        elif "tradable" in hay or "closeonly" in hay or "allowlist" in hay:
            code = "SYMBOL_NOT_TRADEABLE"
        elif "market closed" in hay:
            code = "MARKET_CLOSED"
        else:
            code = abort or (reasons[0] if reasons else "CANDIDATE_BLOCK")
        return {
            "decision_state": DecisionState.CANDIDATE_BLOCK.value,
            "fault_class": FaultClass.CANDIDATE_BLOCK.value,
            "fault_code": code,
            "fault_reason": abort or "; ".join(reasons) or outcome,
            "retryable": False,
            "candidate_action": CandidateAction.ROTATE_FOCUS.value,
            "next_action": CandidateAction.ROTATE_FOCUS.value,
            "blocking_stage": "SIZING"
            if ("min lot" in hay or "minimum lot" in hay)
            else "ELIGIBILITY",
            "skip_idle_sleep": True,
            "release_entry_budget": True,
        }

    if system_wide or halt is HaltClass.HARD_BLOCK:
        stage = "SAFETY"
        if "gateway" in hay or "mt5" in hay:
            stage = "GATEWAY"
        if "oms" in hay:
            stage = "OMS"
        if "reconcil" in hay:
            stage = "RECONCILIATION"
        return {
            "decision_state": DecisionState.SYSTEM_BLOCK.value
            if any(n in hay for n in ("gateway", "mt5", "cycle exception"))
            else DecisionState.HARD_BLOCK.value,
            "fault_class": FaultClass.SYSTEM_BLOCK.value
            if "gateway" in hay or "mt5 disconnected" in hay
            else FaultClass.HARD_BLOCK.value,
            "fault_code": abort or (reasons[0] if reasons else "HARD_BLOCK"),
            "fault_reason": abort or "; ".join(reasons) or outcome,
            "retryable": False,
            "candidate_action": CandidateAction.FAIL_CLOSED.value,
            "next_action": CandidateAction.FAIL_CLOSED.value,
            "blocking_stage": stage,
            "skip_idle_sleep": False,
            "release_entry_budget": False,
        }

    if any(n in hay for n in _WAIT_NEEDLES) or action in {"NO_TRADE", "WATCH", ""}:
        setup = "no eligible" in hay or "setup not ready" in hay or action in {
            "NO_TRADE",
            "WATCH",
            "",
        }
        return {
            "decision_state": DecisionState.SETUP_NOT_READY.value
            if setup and "spread" not in hay
            else DecisionState.WAIT_SAME_FOCUS.value,
            "fault_class": FaultClass.WAIT.value,
            "fault_code": abort or (reasons[0] if reasons else "WAIT_SAME_FOCUS"),
            "fault_reason": abort or "; ".join(reasons) or outcome or action or "NO_TRADE",
            "retryable": True,
            "candidate_action": CandidateAction.WAIT_SAME_FOCUS.value,
            "next_action": CandidateAction.WAIT_SAME_FOCUS.value,
            "blocking_stage": "STRATEGY" if setup else "OPTIMIZER",
            "skip_idle_sleep": False,
            "release_entry_budget": True,
        }

    return {
        "decision_state": DecisionState.NO_TRADE.value,
        "fault_class": FaultClass.WAIT.value,
        "fault_code": abort or outcome or "NO_TRADE",
        "fault_reason": abort or outcome or "NO_TRADE",
        "retryable": True,
        "candidate_action": CandidateAction.WAIT_SAME_FOCUS.value,
        "next_action": CandidateAction.WAIT_SAME_FOCUS.value,
        "blocking_stage": "DECISION",
        "skip_idle_sleep": False,
        "release_entry_budget": True,
    }


def apply_focus_hysteresis(
    *,
    current_focus: str | None,
    eligible_symbols: list[str],
    scores: dict[str, float],
    proposed: str | None,
    material_delta: int = FOCUS_MATERIAL_DELTA,
) -> tuple[str | None, str]:
    """Keep a still-eligible focus unless another candidate is materially better.

    Ranking still uses existing opportunity scores — no new indicators.
    """
    eligible = [str(s).strip().upper() for s in eligible_symbols if str(s).strip()]
    hold = str(current_focus or "").strip().upper() or None
    nxt = str(proposed or "").strip().upper() or None
    if hold and hold in eligible:
        hold_score = float(scores.get(hold) or 0.0)
        new_score = float(scores.get(nxt or "") or 0.0) if nxt else 0.0
        if nxt and nxt != hold and (new_score - hold_score) >= float(material_delta):
            return nxt, "ROTATE_MATERIAL_BETTER"
        return hold, "HOLD_FOCUS"
    if nxt and nxt in eligible:
        return nxt, "FOCUS_SELECTED"
    if eligible:
        return eligible[0], "FOCUS_SELECTED"
    return None, "FOCUS_FORMING"


@dataclass
class _WindowState:
    started_mono: float | None = None
    first_fill_at: float | None = None
    first_fill_symbol: str | None = None
    focus_symbol: str | None = None
    focus_reason: str = "FOCUS_FORMING"
    last_classification: dict[str, Any] = field(default_factory=dict)
    candidates_evaluated: int = 0
    focus_rotations: int = 0
    hard_blocks: int = 0
    candidate_blocks: int = 0
    advisory_degradations: int = 0
    execution_ready: int = 0
    orders_submitted: int = 0
    unknown_orders: int = 0
    cycle_ms: deque[float] = field(default_factory=lambda: deque(maxlen=_LATENCY_SAMPLES))
    blocker_counts: dict[str, int] = field(default_factory=dict)


_LOCK = threading.RLock()
_WINDOW = _WindowState()


def reset_fast_decision_path() -> None:
    """Test helper."""
    global _WINDOW
    with _LOCK:
        _WINDOW = _WindowState()


def ensure_opportunity_window(*, now_mono: float | None = None) -> None:
    """Start the 30-minute observability window once. Never forces a trade."""
    ts = float(now_mono if now_mono is not None else time.monotonic())
    with _LOCK:
        if _WINDOW.started_mono is None:
            _WINDOW.started_mono = ts


def set_focus(symbol: str | None, *, reason: str) -> None:
    with _LOCK:
        prev = _WINDOW.focus_symbol
        nxt = str(symbol or "").strip().upper() or None
        _WINDOW.focus_symbol = nxt
        _WINDOW.focus_reason = str(reason or "")
        if prev and nxt and prev != nxt:
            _WINDOW.focus_rotations += 1


def record_cycle_classification(
    classification: dict[str, Any],
    *,
    cycle_ms: float | None = None,
    forwarded_to_oms: bool = False,
    fill_symbol: str | None = None,
) -> None:
    ensure_opportunity_window()
    with _LOCK:
        _WINDOW.last_classification = dict(classification)
        _WINDOW.candidates_evaluated += 1
        code = str(classification.get("fault_code") or "NONE")
        _WINDOW.blocker_counts[code] = int(_WINDOW.blocker_counts.get(code) or 0) + 1
        fc = str(classification.get("fault_class") or "")
        if fc == FaultClass.HARD_BLOCK.value or fc == FaultClass.SYSTEM_BLOCK.value:
            _WINDOW.hard_blocks += 1
        elif fc == FaultClass.CANDIDATE_BLOCK.value:
            _WINDOW.candidate_blocks += 1
        elif fc == FaultClass.ADVISORY.value:
            _WINDOW.advisory_degradations += 1
        state = str(classification.get("decision_state") or "")
        if state in {
            DecisionState.EXECUTION_READY.value,
            DecisionState.EXECUTION_AUTHORIZED.value,
            DecisionState.ORDER_SUBMITTED.value,
        }:
            _WINDOW.execution_ready += 1
        if forwarded_to_oms:
            _WINDOW.orders_submitted += 1
            if _WINDOW.first_fill_at is None and fill_symbol:
                _WINDOW.first_fill_at = time.monotonic()
                _WINDOW.first_fill_symbol = str(fill_symbol).upper()
        if state == DecisionState.ORDER_UNKNOWN.value:
            _WINDOW.unknown_orders += 1
        if cycle_ms is not None:
            _WINDOW.cycle_ms.append(float(cycle_ms))


def _percentile(samples: list[float], p: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    if len(ordered) == 1:
        return round(ordered[0], 1)
    idx = min(len(ordered) - 1, max(0, int(round((p / 100.0) * (len(ordered) - 1)))))
    return round(ordered[idx], 1)


def opportunity_window_snapshot(*, now_mono: float | None = None) -> dict[str, Any]:
    ts = float(now_mono if now_mono is not None else time.monotonic())
    with _LOCK:
        started = _WINDOW.started_mono
        remaining = None
        active = False
        if started is not None:
            elapsed = max(0.0, ts - started)
            remaining = max(0.0, WINDOW_SECONDS - elapsed)
            active = remaining > 0
        samples = list(_WINDOW.cycle_ms)
        cls = dict(_WINDOW.last_classification)
        blockers = sorted(
            _WINDOW.blocker_counts.items(),
            key=lambda kv: (-kv[1], kv[0]),
        )
        return {
            "window": "FIRST_TRADE_OPPORTUNITY_WINDOW",
            "duration_seconds": WINDOW_SECONDS,
            "active": active,
            "remaining_seconds": round(remaining, 1) if remaining is not None else None,
            "started": started is not None,
            "current_focus": _WINDOW.focus_symbol,
            "focus_reason": _WINDOW.focus_reason,
            "decision_state": cls.get("decision_state") or DecisionState.FOCUS_FORMING.value,
            "blocking_stage": cls.get("blocking_stage"),
            "fault_class": cls.get("fault_class"),
            "fault_code": cls.get("fault_code"),
            "fault_reason": cls.get("fault_reason"),
            "next_action": cls.get("next_action"),
            "candidates_evaluated": _WINDOW.candidates_evaluated,
            "focus_rotations": _WINDOW.focus_rotations,
            "hard_blocks": _WINDOW.hard_blocks,
            "candidate_blocks": _WINDOW.candidate_blocks,
            "advisory_degradations": _WINDOW.advisory_degradations,
            "execution_ready": _WINDOW.execution_ready,
            "orders_submitted": _WINDOW.orders_submitted,
            "unknown_orders": _WINDOW.unknown_orders,
            "first_natural_trade": bool(_WINDOW.first_fill_symbol),
            "first_fill_symbol": _WINDOW.first_fill_symbol,
            "primary_blockers": [
                {"fault_code": k, "count": v} for k, v in blockers[:8]
            ],
            "cycle_latency_ms": {
                "n": len(samples),
                "p50": _percentile(samples, 50),
                "p95": _percentile(samples, 95),
                "p99": _percentile(samples, 99),
            },
            "forces_trades": False,
            "order_send_retries": False,
        }
