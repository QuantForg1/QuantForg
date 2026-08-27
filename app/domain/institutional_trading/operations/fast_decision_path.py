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
from datetime import UTC, datetime
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
    MARKET_CONTEXT_NOT_READY = "MARKET_CONTEXT_NOT_READY"
    FOCUS_FORMING = "FOCUS_FORMING"
    WAITING = "WAITING"
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
    NO_ELIGIBLE_SETUP = "NO_ELIGIBLE_SETUP"
    NO_EXECUTABLE_FOCUS = "NO_EXECUTABLE_FOCUS"


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
    NO_EXECUTABLE_FOCUS = "NO_EXECUTABLE_FOCUS"
    MARKET_CONTEXT_NOT_READY = "MARKET_CONTEXT_NOT_READY"
    SETUP_NOT_READY = "SETUP_NOT_READY"
    WAIT = "WAIT"
    RISK_ASSESSMENT = "RISK_ASSESSMENT"


NO_CURRENT_BLOCK = "NO_CURRENT_BLOCK"
NO_CURRENT_BLOCKING_GATE = "NO_CURRENT_BLOCKING_GATE"
SAFETY_NOT_REACHED = "NOT_REACHED"
OPTIMIZER_NOT_RUN = "NOT_RUN"


def _stage_flag(classification: dict[str, Any], name: str) -> bool:
    stages = classification.get("stages")
    if not isinstance(stages, dict):
        return False
    return str(stages.get(name) or "").upper() == "PASS"


# Snapshot ATR used by the scanner quality gate (pipeline DEFAULT_ITE_CONFIG).
SCAN_ATR_TIMEFRAME = "M15"
SCAN_ATR_PERIOD = 14


def _norm(text: str) -> str:
    raw = str(text or "").lower()
    for ch in ("_", "-", ":", "/", ".", ",", "(", ")", "[", "]"):
        raw = raw.replace(ch, " ")
    return " ".join(raw.split())


_ROTATE_NEEDLES: tuple[str, ...] = (
    "min lot",
    "min_lot_constraint",
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


def is_ignored_action_value(value: Any) -> bool:
    """True for the OMS NO_TRADE abort token — not a current trading fault."""
    raw = str(value or "").strip()
    if not raw:
        return False
    lowered = raw.lower().replace("-", "_")
    if lowered == "ignored_action" or lowered.startswith("ignored_action "):
        return True
    hay = _norm(raw)
    return hay == "ignored action" or hay.startswith("ignored action ")


def _is_valid_wait_focus(symbol: str | None) -> bool:
    focus = str(symbol or "").strip().upper() or None
    if not focus:
        return False
    try:
        from app.domain.trading.gold_only import gold_only_enabled, is_gold_symbol

        if gold_only_enabled():
            return bool(is_gold_symbol(focus))
    except Exception:
        pass
    return True


def coherent_next_action(
    *,
    current_focus: str | None,
    next_action: str | None,
) -> str:
    """WAIT_SAME_FOCUS is valid only while Gold focus is still active."""
    action = str(next_action or "").strip() or CandidateAction.NO_EXECUTABLE_FOCUS.value
    if is_ignored_action_value(action):
        return CandidateAction.NO_EXECUTABLE_FOCUS.value
    if action == CandidateAction.WAIT_SAME_FOCUS.value and not _is_valid_wait_focus(
        current_focus
    ):
        return CandidateAction.NO_EXECUTABLE_FOCUS.value
    return action


def sanitize_blocking_gate(
    value: str | None,
    *,
    fallback: str = NO_CURRENT_BLOCKING_GATE,
) -> str:
    raw = str(value or "").strip()
    if not raw or is_ignored_action_value(raw):
        return fallback
    return raw


def sanitize_fault_code(
    value: str | None,
    *,
    blocking_gate: str | None = None,
) -> str:
    raw = str(value or "").strip()
    gate = sanitize_blocking_gate(blocking_gate) if blocking_gate is not None else None
    if not raw or is_ignored_action_value(raw):
        if not gate or gate == NO_CURRENT_BLOCKING_GATE:
            return NO_CURRENT_BLOCK
        return blocking_gate_fault_code(gate)
    upper = raw.upper()
    if upper in {"WAIT_SAME_FOCUS", "NO_TRADE", "WATCH", "NONE", "IGNORED_ACTION"}:
        if not gate or gate == NO_CURRENT_BLOCKING_GATE:
            return NO_CURRENT_BLOCK
        return blocking_gate_fault_code(gate)
    return raw


def _should_count_as_blocker(code: str) -> bool:
    if is_ignored_action_value(code):
        return False
    upper = str(code or "").strip().upper()
    return upper not in {
        "",
        "NONE",
        "NO_TRADE",
        "WATCH",
        "WAIT_SAME_FOCUS",
        NO_CURRENT_BLOCK,
        NO_CURRENT_BLOCKING_GATE,
        CandidateAction.NO_EXECUTABLE_FOCUS.value,
        CandidateAction.MARKET_CONTEXT_NOT_READY.value,
    }


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

    if "leverage" in hay and "exceeds" in hay:
        return {
            "decision_state": DecisionState.HARD_BLOCK.value,
            "fault_class": FaultClass.HARD_BLOCK.value,
            "fault_code": "LEVERAGE_POLICY_EXCEEDED",
            "fault_reason": abort or "; ".join(reasons) or "LEVERAGE_POLICY_EXCEEDED",
            "retryable": False,
            "candidate_action": CandidateAction.FAIL_CLOSED.value,
            "next_action": CandidateAction.FAIL_CLOSED.value,
            "blocking_stage": "SAFETY",
            "skip_idle_sleep": False,
            "release_entry_budget": False,
        }

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

    if is_ignored_action_value(abort) or is_ignored_action_value(outcome):
        return {
            "decision_state": DecisionState.SETUP_NOT_READY.value,
            "fault_class": FaultClass.WAIT.value,
            "fault_code": NO_CURRENT_BLOCK,
            "fault_reason": NO_CURRENT_BLOCKING_GATE,
            "retryable": True,
            "candidate_action": CandidateAction.NO_EXECUTABLE_FOCUS.value,
            "next_action": CandidateAction.NO_EXECUTABLE_FOCUS.value,
            "blocking_stage": "DECISION",
            "skip_idle_sleep": False,
            "release_entry_budget": True,
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

    if (
        "gateway market data unavailable" in hay
        or "trade mode lookup failed" in hay
        or "trade mode unknown" in hay
        or "symbol unavailable" in hay
        or "no full mode gold symbol" in hay
        or "gold only symbol rejected" in hay
        or "unsuffixed gold" in hay
        or abort.strip().upper().startswith("GATEWAY_MARKET_DATA_UNAVAILABLE")
    ):
        return {
            "decision_state": DecisionState.HARD_BLOCK.value,
            "fault_class": FaultClass.CANDIDATE_BLOCK.value,
            "fault_code": "SYMBOL_ROUTING_BLOCK",
            "fault_reason": abort or "; ".join(reasons) or "SYMBOL_ROUTING_BLOCK",
            "retryable": False,
            "candidate_action": CandidateAction.NO_EXECUTABLE_FOCUS.value,
            "next_action": CandidateAction.NO_EXECUTABLE_FOCUS.value,
            "blocking_stage": "MARKET",
            "skip_idle_sleep": False,
            "release_entry_budget": True,
        }

    if (
        abort.strip().upper() == "NO_MARKET_CONTEXT"
        or "no market context" in hay
        or "market data load failed" in hay
        or "cloudflare origin unreachable" in hay
        or "symbol catalogue resolution failed" in hay
    ):
        return {
            "decision_state": DecisionState.HARD_BLOCK.value,
            "fault_class": FaultClass.HARD_BLOCK.value,
            "fault_code": abort.strip().upper() or "NO_MARKET_CONTEXT",
            "fault_reason": abort or "; ".join(reasons) or outcome or "NO_MARKET_CONTEXT",
            "retryable": False,
            "candidate_action": CandidateAction.FAIL_CLOSED.value,
            "next_action": CandidateAction.FAIL_CLOSED.value,
            "blocking_stage": "GATEWAY",
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
        if (
            "min_lot_constraint" in hay
            or "min lot" in hay
            or "minimum lot" in hay
        ):
            code = "MIN_LOT_CONSTRAINT"
        elif "tradable" in hay or "closeonly" in hay or "allowlist" in hay:
            code = "SYMBOL_NOT_TRADEABLE"
        elif "market closed" in hay:
            code = "MARKET_CLOSED"
        else:
            code = abort or (reasons[0] if reasons else "CANDIDATE_BLOCK")
        rotate = CandidateAction.ROTATE_FOCUS.value
        wait_same = CandidateAction.WAIT_SAME_FOCUS.value
        try:
            from app.domain.trading.gold_only import gold_only_enabled

            if gold_only_enabled():
                rotate = wait_same
        except Exception:
            pass
        return {
            "decision_state": DecisionState.CANDIDATE_BLOCK.value,
            "fault_class": FaultClass.CANDIDATE_BLOCK.value,
            "fault_code": code,
            "fault_reason": abort or "; ".join(reasons) or outcome,
            "retryable": False,
            "candidate_action": rotate,
            "next_action": rotate,
            "blocking_stage": "RISK"
            if (
                "min_lot_constraint" in hay
                or "min lot" in hay
                or "minimum lot" in hay
            )
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
        spread_wait = "spread" in hay
        next_action = (
            CandidateAction.WAIT_SAME_FOCUS.value
            if spread_wait
            else CandidateAction.NO_EXECUTABLE_FOCUS.value
        )
        fault_code = abort or (reasons[0] if reasons else "")
        if not fault_code or is_ignored_action_value(fault_code) or fault_code == "WAIT_SAME_FOCUS":
            fault_code = "NO_ELIGIBLE_SETUP" if setup else NO_CURRENT_BLOCK
        fault_reason = abort or "; ".join(reasons) or outcome or action or "NO_TRADE"
        if is_ignored_action_value(fault_reason):
            fault_reason = NO_CURRENT_BLOCKING_GATE
        return {
            "decision_state": DecisionState.SETUP_NOT_READY.value
            if setup and not spread_wait
            else DecisionState.WAITING.value,
            "fault_class": FaultClass.WAIT.value,
            "fault_code": fault_code,
            "fault_reason": fault_reason,
            "retryable": True,
            "candidate_action": next_action,
            "next_action": next_action,
            "blocking_stage": "STRATEGY" if setup else "OPTIMIZER",
            "skip_idle_sleep": False,
            "release_entry_budget": True,
        }

    fallback_code = abort or outcome or "NO_TRADE"
    if is_ignored_action_value(fallback_code) or fallback_code in {"NO_TRADE", "WATCH"}:
        fallback_code = NO_CURRENT_BLOCK
    fallback_reason = abort or outcome or "NO_TRADE"
    if is_ignored_action_value(fallback_reason):
        fallback_reason = NO_CURRENT_BLOCKING_GATE
    return {
        "decision_state": DecisionState.NO_TRADE.value,
        "fault_class": FaultClass.WAIT.value,
        "fault_code": fallback_code,
        "fault_reason": fallback_reason,
        "retryable": True,
        "candidate_action": CandidateAction.NO_EXECUTABLE_FOCUS.value,
        "next_action": CandidateAction.NO_EXECUTABLE_FOCUS.value,
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
    try:
        from app.domain.trading.gold_only import (
            filter_autonomous_symbols,
            gold_only_enabled,
            is_gold_symbol,
        )

        if gold_only_enabled():
            eligible = list(filter_autonomous_symbols(eligible))
            if hold and not is_gold_symbol(hold):
                hold = None
            if nxt and not is_gold_symbol(nxt):
                nxt = None
            if hold and hold in eligible:
                return hold, "WAIT_SAME_FOCUS"
            if nxt and nxt in eligible:
                return nxt, "FOCUS_SELECTED"
            if eligible:
                return eligible[0], "FOCUS_SELECTED"
            return None, "NO_EXECUTABLE_FOCUS"
    except Exception:
        pass
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
    return None, "NO_EXECUTABLE_FOCUS"


@dataclass
class _WindowState:
    started_mono: float | None = None
    first_fill_at: float | None = None
    first_fill_symbol: str | None = None
    focus_symbol: str | None = None
    focus_reason: str = "FOCUS_FORMING"
    last_classification: dict[str, Any] = field(default_factory=dict)
    current_scan: dict[str, Any] = field(default_factory=dict)
    snapshot_seq: int = 0
    snapshot_id: str | None = None
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
    cycle_id: int = 0
    last_tracker_state: str | None = None
    last_tracker_mono: float | None = None
    dwell_ms: dict[str, float] = field(default_factory=dict)
    cycle_events: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=120)
    )
    oms_ready: int = 0
    broker_ready: int = 0
    soft_waits: int = 0
    scan_published_mono: float | None = None


_LOCK = threading.RLock()
_WINDOW = _WindowState()


def reset_fast_decision_path() -> None:
    """Test helper."""
    global _WINDOW
    with _LOCK:
        _WINDOW = _WindowState()
    try:
        from app.domain.institutional_trading.operations.system_coherence import (
            reset_system_coherence,
        )

        reset_system_coherence()
    except Exception:
        pass


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
        why = str(reason or "")
        try:
            from app.domain.trading.gold_only import (
                gold_only_enabled,
                is_gold_symbol,
            )

            if gold_only_enabled() and nxt and not is_gold_symbol(nxt):
                nxt = None
                why = "NO_EXECUTABLE_FOCUS"
        except Exception:
            pass
        _WINDOW.focus_symbol = nxt
        _WINDOW.focus_reason = why
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
    now = time.monotonic()
    with _LOCK:
        _WINDOW.last_classification = dict(classification)
        _WINDOW.cycle_id += 1
        cycle_id = int(_WINDOW.cycle_id)
        _WINDOW.candidates_evaluated += 1
        code = str(classification.get("fault_code") or "NONE")
        if _should_count_as_blocker(code):
            _WINDOW.blocker_counts[code] = int(_WINDOW.blocker_counts.get(code) or 0) + 1
        fc = str(classification.get("fault_class") or "")
        if fc == FaultClass.HARD_BLOCK.value or fc == FaultClass.SYSTEM_BLOCK.value:
            _WINDOW.hard_blocks += 1
        elif fc == FaultClass.CANDIDATE_BLOCK.value:
            _WINDOW.candidate_blocks += 1
        elif fc == FaultClass.WAIT.value:
            _WINDOW.soft_waits += 1
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
            _WINDOW.oms_ready += 1
            if _WINDOW.first_fill_at is None and fill_symbol:
                _WINDOW.first_fill_at = now
                _WINDOW.first_fill_symbol = str(fill_symbol).upper()
        if state == DecisionState.ORDER_UNKNOWN.value:
            _WINDOW.unknown_orders += 1
        if cycle_ms is not None:
            _WINDOW.cycle_ms.append(float(cycle_ms))
        event = {
            "cycle_id": cycle_id,
            "timestamp": _iso_now(),
            "decision_state": state,
            "fault_class": fc,
            "fault_code": code,
            "fault_reason": classification.get("fault_reason"),
            "blocking_stage": classification.get("blocking_stage"),
            "next_action": classification.get("next_action"),
            "cycle_latency_ms": cycle_ms,
            "forwarded_to_oms": bool(forwarded_to_oms),
            "market_ready": _stage_flag(classification, "MARKET"),
            "strategy_ready": _stage_flag(classification, "STRATEGY"),
            "decision_ready": _stage_flag(classification, "DECISION"),
            "safety_ready": _stage_flag(classification, "SAFETY"),
            "risk_ready": _stage_flag(classification, "RISK"),
            "sizing_ready": _stage_flag(classification, "SIZING"),
            "portfolio_ready": _stage_flag(classification, "PORTFOLIO"),
            "optimizer_ready": _stage_flag(classification, "OPTIMIZER"),
            "oms_ready": _stage_flag(classification, "OMS"),
            "broker_ready": _stage_flag(classification, "BROKER"),
            "execution_readiness": classification.get("execution_readiness"),
            "first_authoritative_blocker": classification.get(
                "first_authoritative_blocker"
            ),
        }
        _WINDOW.cycle_events.append(event)


def _percentile(samples: list[float], p: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    if len(ordered) == 1:
        return round(ordered[0], 1)
    idx = min(len(ordered) - 1, max(0, int(round((p / 100.0) * (len(ordered) - 1)))))
    return round(ordered[idx], 1)


def _iso_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _window_setup_state(
    *,
    current_focus: str | None,
    eligible_count: int,
    execution_ready: bool,
    fault_class: str | None,
    next_action: str | None,
    has_current_scan: bool,
) -> str:
    if not has_current_scan:
        return DecisionState.MARKET_CONTEXT_NOT_READY.value
    if execution_ready:
        return DecisionState.EXECUTION_READY.value
    fc = str(fault_class or "")
    nxt = str(next_action or "")
    if nxt == CandidateAction.FAIL_CLOSED.value or fc in {
        FaultClass.HARD_BLOCK.value,
        FaultClass.SYSTEM_BLOCK.value,
    }:
        return DecisionState.HARD_BLOCK.value
    if _is_valid_wait_focus(current_focus) and nxt == CandidateAction.WAIT_SAME_FOCUS.value:
        return DecisionState.WAITING.value
    if int(eligible_count or 0) == 0 or not current_focus:
        return DecisionState.SETUP_NOT_READY.value
    return DecisionState.FOCUS_FORMING.value


def _cohere_opportunity_fields(
    *,
    current_focus: str | None,
    next_action: str | None,
    fault_code: str | None,
    fault_reason: str | None,
    blocking_gate: str | None,
) -> dict[str, Any]:
    focus = str(current_focus or "").strip().upper() or None
    nxt = coherent_next_action(current_focus=focus, next_action=next_action)
    gate = sanitize_blocking_gate(blocking_gate or fault_reason)
    code = sanitize_fault_code(fault_code, blocking_gate=gate)
    reason = sanitize_blocking_gate(fault_reason, fallback=gate)
    if is_ignored_action_value(code) or is_ignored_action_value(nxt) or is_ignored_action_value(gate):
        code = NO_CURRENT_BLOCK
        gate = NO_CURRENT_BLOCKING_GATE
        reason = NO_CURRENT_BLOCKING_GATE
        if nxt == CandidateAction.WAIT_SAME_FOCUS.value and not _is_valid_wait_focus(focus):
            nxt = CandidateAction.NO_EXECUTABLE_FOCUS.value
    if gate == NO_CURRENT_BLOCKING_GATE and code == NO_CURRENT_BLOCK:
        if nxt not in {
            CandidateAction.FAIL_CLOSED.value,
            CandidateAction.RECONCILE.value,
            CandidateAction.WAIT_SAME_FOCUS.value,
            CandidateAction.HOLD_FOCUS.value,
            CandidateAction.MARKET_CONTEXT_NOT_READY.value,
        }:
            nxt = coherent_next_action(
                current_focus=focus,
                next_action=nxt or CandidateAction.NO_EXECUTABLE_FOCUS.value,
            )
    return {
        "current_focus": focus,
        "next_action": nxt,
        "fault_code": code,
        "fault_reason": reason,
        "blocking_gate": gate,
        "first_blocking_gate": gate,
    }


def opportunity_window_snapshot(
    *,
    now_mono: float | None = None,
    current_scan: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        stored_scan = dict(_WINDOW.current_scan) if _WINDOW.current_scan else {}
        snapshot_id = _WINDOW.snapshot_id
        snapshot_seq = int(_WINDOW.snapshot_seq)
        focus_symbol = _WINDOW.focus_symbol
        focus_reason = _WINDOW.focus_reason
        event_counts = sorted(
            (
                (k, v)
                for k, v in _WINDOW.blocker_counts.items()
                if _should_count_as_blocker(str(k))
            ),
            key=lambda kv: (-kv[1], kv[0]),
        )
        window_meta = {
            "window": "FIRST_TRADE_OPPORTUNITY_WINDOW",
            "duration_seconds": WINDOW_SECONDS,
            "active": active,
            "remaining_seconds": round(remaining, 1) if remaining is not None else None,
            "started": started is not None,
            "candidates_evaluated": _WINDOW.candidates_evaluated,
            "focus_rotations": _WINDOW.focus_rotations,
            "hard_blocks": _WINDOW.hard_blocks,
            "candidate_blocks": _WINDOW.candidate_blocks,
            "advisory_degradations": _WINDOW.advisory_degradations,
            "execution_ready": _WINDOW.execution_ready,
            "orders_submitted": _WINDOW.orders_submitted,
            "unknown_orders": _WINDOW.unknown_orders,
            "oms_ready": _WINDOW.oms_ready,
            "broker_ready": _WINDOW.broker_ready,
            "soft_waits": _WINDOW.soft_waits,
            "cycle_id": int(_WINDOW.cycle_id),
            "first_natural_trade": bool(_WINDOW.first_fill_symbol),
            "first_fill_symbol": _WINDOW.first_fill_symbol,
            "dwell_ms": dict(_WINDOW.dwell_ms),
            "recent_events": list(_WINDOW.cycle_events)[-12:],
            "cycle_event_counts": [
                {"fault_code": k, "count": v} for k, v in event_counts[:8]
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

    current = (
        dict(current_scan)
        if isinstance(current_scan, dict) and current_scan.get("label") == "CURRENT_SCAN"
        else stored_scan
    )
    has_current_scan = bool(current)
    if has_current_scan:
        symbol = str(current.get("symbol") or current.get("current_scan_symbol") or "").strip().upper() or None
        try:
            from app.domain.trading.gold_only import gold_only_enabled, is_gold_symbol

            if gold_only_enabled() and symbol and not is_gold_symbol(symbol):
                symbol = None
        except Exception:
            pass
        if "executable_focus" in current:
            focus = current.get("executable_focus")
        else:
            focus = focus_symbol
        try:
            from app.domain.trading.gold_only import gold_only_enabled, is_gold_symbol

            if gold_only_enabled() and focus and not is_gold_symbol(str(focus)):
                focus = None
        except Exception:
            pass
        eligible_count = int(current.get("eligible_count") or 0)
        best = current.get("best_candidate")
        if isinstance(best, dict):
            best_symbol = str(best.get("symbol") or "").strip().upper() or None
        else:
            best_symbol = str(current.get("current_scan_symbol") or symbol or "").strip().upper() or None
        try:
            from app.domain.trading.gold_only import gold_only_enabled, is_gold_symbol

            if gold_only_enabled() and best_symbol and not is_gold_symbol(best_symbol):
                best_symbol = None
        except Exception:
            pass
        coherent = _cohere_opportunity_fields(
            current_focus=str(focus or "").strip().upper() or None,
            next_action=str(current.get("next_action") or ""),
            fault_code=str(current.get("fault_code") or ""),
            fault_reason=str(current.get("fault_reason") or current.get("first_blocking_gate") or ""),
            blocking_gate=str(current.get("first_blocking_gate") or current.get("fault_reason") or ""),
        )
        execution_ready = bool(current.get("execution_ready"))
        safety_state = str(current.get("safety_state") or SAFETY_NOT_REACHED)
        optimizer_state = str(current.get("optimizer_state") or OPTIMIZER_NOT_RUN)
        as_of = str(current.get("as_of") or "") or _iso_now()
        snap_id = snapshot_id or f"current-scan-{snapshot_seq or 0}"
        blocking_stage = current.get("blocking_stage") or "SCANNER"
        fault_class = current.get("fault_class") or FaultClass.WAIT.value
        setup_state = _window_setup_state(
            current_focus=coherent["current_focus"],
            eligible_count=eligible_count,
            execution_ready=execution_ready,
            fault_class=str(fault_class),
            next_action=coherent["next_action"],
            has_current_scan=True,
        )
        if (
            coherent["fault_code"] == NO_CURRENT_BLOCK
            and coherent["blocking_gate"] == NO_CURRENT_BLOCKING_GATE
            and not coherent["current_focus"]
            and coherent["next_action"]
            not in {
                CandidateAction.FAIL_CLOSED.value,
                CandidateAction.RECONCILE.value,
                CandidateAction.MARKET_CONTEXT_NOT_READY.value,
            }
        ):
            coherent["next_action"] = CandidateAction.NO_EXECUTABLE_FOCUS.value
    else:
        try:
            from app.domain.trading.gold_only import gold_only_enabled, is_gold_symbol

            focus = focus_symbol
            if gold_only_enabled() and focus and not is_gold_symbol(str(focus)):
                focus = None
        except Exception:
            focus = focus_symbol
        coherent = _cohere_opportunity_fields(
            current_focus=str(focus or "").strip().upper() or None,
            next_action=CandidateAction.MARKET_CONTEXT_NOT_READY.value,
            fault_code=NO_CURRENT_BLOCK,
            fault_reason=NO_CURRENT_BLOCKING_GATE,
            blocking_gate=NO_CURRENT_BLOCKING_GATE,
        )
        symbol = None
        best_symbol = None
        eligible_count = 0
        execution_ready = False
        safety_state = SAFETY_NOT_REACHED
        optimizer_state = OPTIMIZER_NOT_RUN
        as_of = _iso_now()
        snap_id = snapshot_id or "current-scan-0"
        blocking_stage = "SCANNER"
        fault_class = FaultClass.WAIT.value
        setup_state = DecisionState.MARKET_CONTEXT_NOT_READY.value
        focus_reason = "NO_CURRENT_SCAN"

    from app.domain.institutional_trading.operations.gold_execution_readiness import (
        bottleneck_report,
        build_readiness_matrix,
        parse_as_of_age_seconds,
        production_feature_inventory,
        resolve_tracker_state,
    )

    scan_age = parse_as_of_age_seconds(as_of if has_current_scan else None)
    named_reject = None
    if has_current_scan:
        named_reject = str(
            current.get("fault_reason")
            or current.get("first_blocking_gate")
            or coherent["fault_reason"]
            or ""
        ).strip() or None
        if named_reject in {NO_CURRENT_BLOCKING_GATE, NO_CURRENT_BLOCK, "NONE"}:
            named_reject = None
    last_cls = {}
    with _LOCK:
        last_cls = dict(_WINDOW.last_classification) if _WINDOW.last_classification else {}
        last_tracker = _WINDOW.last_tracker_state
        last_tracker_mono = _WINDOW.last_tracker_mono
    overlay_cls = last_cls if eligible_count > 0 else {}
    forwarded = bool(overlay_cls.get("decision_state") == DecisionState.ORDER_SUBMITTED.value)
    readiness = build_readiness_matrix(
        has_current_scan=has_current_scan,
        eligible_count=eligible_count,
        execution_ready=execution_ready,
        blocking_stage=str(overlay_cls.get("blocking_stage") or blocking_stage),
        fault_class=str(overlay_cls.get("fault_class") or fault_class),
        next_action=coherent["next_action"],
        named_reject=named_reject,
        last_classification=overlay_cls or None,
        scan_age_seconds=scan_age,
        forwarded_to_oms=forwarded,
    )
    tracker_state = resolve_tracker_state(
        has_current_scan=has_current_scan,
        eligible_count=eligible_count,
        execution_ready=execution_ready,
        current_focus=coherent["current_focus"],
        next_action=coherent["next_action"],
        fault_class=str(overlay_cls.get("fault_class") or fault_class),
        decision_state=str(overlay_cls.get("decision_state") or setup_state),
        named_reject=named_reject,
        window_active=bool(window_meta.get("active")),
        window_started=bool(window_meta.get("started")),
        first_natural_trade=bool(window_meta.get("first_natural_trade")),
        forwarded_to_oms=forwarded,
    )
    now_mono = ts
    dwell = dict(window_meta.get("dwell_ms") or {})
    with _LOCK:
        if last_tracker_mono is not None:
            elapsed = max(0.0, (now_mono - float(last_tracker_mono)) * 1000.0)
            key = last_tracker or tracker_state
            dwell[key] = round(float(dwell.get(key) or 0.0) + elapsed, 1)
        _WINDOW.dwell_ms = dwell
        _WINDOW.last_tracker_state = tracker_state
        _WINDOW.last_tracker_mono = now_mono
    window_meta["dwell_ms"] = dwell
    bottleneck = None
    if (not window_meta.get("active") and window_meta.get("started")) or tracker_state == "TIMEOUT_NO_TRADE":
        bottleneck = bottleneck_report(
            tracker_state=tracker_state,
            readiness=readiness,
            window=window_meta,
            named_reject=named_reject,
            first_blocking_gate=coherent["first_blocking_gate"],
            dwell_ms=dwell,
        )

    return {
        **window_meta,
        "snapshot_id": snap_id,
        "as_of": as_of,
        "symbol": symbol,
        "current_focus": coherent["current_focus"],
        "focus_reason": focus_reason,
        "best_candidate": best_symbol,
        "current_best_candidate": best_symbol,
        "eligible_count": eligible_count,
        "setup_state": setup_state,
        "decision_state": setup_state,
        "tracker_state": tracker_state,
        "blocking_stage": overlay_cls.get("blocking_stage") or blocking_stage,
        "fault_class": overlay_cls.get("fault_class") or fault_class,
        "fault_code": coherent["fault_code"],
        "fault_reason": coherent["fault_reason"],
        "blocking_gate": coherent["blocking_gate"],
        "first_blocking_gate": coherent["first_blocking_gate"],
        "next_action": coherent["next_action"],
        "safety_state": safety_state,
        "optimizer_state": optimizer_state,
        "execution_ready": execution_ready,
        "execution_readiness": overlay_cls.get("execution_readiness")
        or ("EXECUTION_READY" if execution_ready else "NOT_READY"),
        "first_authoritative_blocker": overlay_cls.get("first_authoritative_blocker")
        or coherent["first_blocking_gate"],
        "all_failed_conditions": overlay_cls.get("all_failed_conditions") or [],
        "execute_now_required": False,
        "readiness_matrix": readiness,
        "production_features": production_feature_inventory(),
        "bottleneck_report": bottleneck,
        "scan_age_seconds": readiness.get("scan_age_seconds"),
        "primary_blockers": [],
    }


def blocking_gate_fault_code(reason: str | None) -> str:
    """Map a scanner reject string to a stable observability code.

    Does not change Safety / Risk / OMS. Observability only.
    """
    if is_ignored_action_value(reason):
        return NO_CURRENT_BLOCK
    hay = _norm(reason or "")
    if "opportunity_score_below" in hay or "opportunity score" in hay:
        return "OPPORTUNITY_SCORE_BELOW_THRESHOLD"
    if "volatility unavailable" in hay:
        return "VOLATILITY_UNAVAILABLE"
    if "invalid volatility" in hay or "atr% ≤ 0" in hay or "atr% <=" in hay:
        return "VOLATILITY_INVALID"
    if "volatility too compressed" in hay:
        return "VOLATILITY_COMPRESSED"
    if "below hard minimum" in hay or "dead tape floor" in hay:
        return "VOLATILITY_HARD_MIN"
    if "portfolio" in hay:
        return "PORTFOLIO_RISK_LIMIT"
    if "no eligible" in hay:
        return "NO_ELIGIBLE_SETUP"
    if not hay:
        return "NO_ELIGIBLE_SETUP"
    classified = classify_candidate_outcome(
        abort_reason=reason,
        failed_reasons=(str(reason),) if reason else (),
        cycle_outcome="no_eligible_setup",
        decision_action="NO_TRADE",
    )
    code = str(classified.get("fault_code") or "NO_ELIGIBLE_SETUP")
    if is_ignored_action_value(code):
        return NO_CURRENT_BLOCK
    return code


def scan_ineligible_abort_reason(scan: dict[str, Any] | None) -> str:
    """Abort code when Gold was scanned but is not an executable candidate.

    Observability only. Does not change Risk / Safety / OMS gates.
    Distinguishes 'no eligible setup' from a true routing NO_EXECUTABLE_SYMBOL.
    """
    if not isinstance(scan, dict):
        return "NO_ELIGIBLE_SETUP"
    trace = scan.get("eligibility_trace") if isinstance(scan.get("eligibility_trace"), dict) else None
    if trace:
        code = str(trace.get("first_failed_code") or trace.get("eligibility_reason") or "")
        if code and code not in {NO_CURRENT_BLOCK, "NONE", "SCALP_ELIGIBLE", "PASS"}:
            return str(code)
    current = scan.get("current_scan")
    nested = current if isinstance(current, dict) else {}
    gate = str(
        nested.get("first_blocking_gate")
        or scan.get("first_blocking_gate")
        or nested.get("blocking_gate")
        or scan.get("blocking_gate")
        or ""
    )
    code = blocking_gate_fault_code(gate) if gate else ""
    if code and code not in {NO_CURRENT_BLOCK, "NONE", ""}:
        return str(code)
    ranked = scan.get("opportunity_ranked") or nested.get("opportunity_ranked") or []
    if isinstance(ranked, list):
        for row in ranked:
            if not isinstance(row, dict):
                continue
            score = row.get("opportunity_score")
            threshold = row.get("opportunity_threshold")
            try:
                if score is not None and int(score) < int(threshold or 70):
                    return "OPPORTUNITY_SCORE_BELOW_THRESHOLD"
            except (TypeError, ValueError):
                continue
            reject = str(row.get("reject_reason") or row.get("blocking_gate") or "")
            if reject:
                mapped = blocking_gate_fault_code(reject)
                if mapped and mapped not in {NO_CURRENT_BLOCK, "NONE"}:
                    return str(mapped)
            break
    if scan.get("no_eligible_setup") or nested.get("no_eligible_setup"):
        return "NO_ELIGIBLE_SETUP"
    return "NO_ELIGIBLE_SETUP"


def _row_symbol(row: Any) -> str | None:
    if not isinstance(row, dict):
        return None
    return str(row.get("symbol") or "").strip().upper() or None


def _scan_eligible_symbols(scan: dict[str, Any]) -> list[str]:
    raw = scan.get("eligible_symbols") if isinstance(scan, dict) else None
    out: list[str] = []
    seen: set[str] = set()
    for item in raw or []:
        sym = str(item or "").strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


_GENERIC_SCAN_GATES = frozenset(
    {
        "NO_ELIGIBLE_SETUP",
        NO_CURRENT_BLOCKING_GATE,
        NO_CURRENT_BLOCK,
        "NONE",
        "IGNORED_ACTION",
        "WAIT_SAME_FOCUS",
        "NO_TRADE",
        "WATCH",
    }
)


def _is_generic_scan_gate(value: str | None) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return True
    if is_ignored_action_value(raw):
        return True
    return raw.upper() in _GENERIC_SCAN_GATES


def named_reject_reasons(*sources: Any) -> list[str]:
    """First-authoritative reject list from a scored / ranked scan row.

    Observability only. Does not change SCALPING_V1 floors or eligibility.
    """
    out: list[str] = []
    seen: set[str] = set()

    def _push(text: str) -> None:
        item = str(text or "").strip()
        if not item or _is_generic_scan_gate(item):
            return
        key = item.casefold()
        if key in seen:
            return
        seen.add(key)
        out.append(item)

    for source in sources:
        if isinstance(source, dict):
            raw = source.get("reject_reasons") or source.get("failed_gates")
            if isinstance(raw, (list, tuple)):
                for item in raw:
                    _push(str(item))
                if out:
                    return out
            joined = str(
                source.get("reject_reason")
                or source.get("blocking_gate")
                or source.get("first_blocking_gate")
                or ""
            ).strip()
            if joined and not _is_generic_scan_gate(joined):
                for part in joined.split(";"):
                    _push(part)
                if out:
                    return out
        elif isinstance(source, (list, tuple)):
            for item in source:
                _push(str(item))
            if out:
                return out
        else:
            joined = str(source or "").strip()
            if joined and not _is_generic_scan_gate(joined):
                for part in joined.split(";"):
                    _push(part)
                if out:
                    return out
    return out


def _iter_scan_rows(scan: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("opportunity_ranked", "rows", "ranked", "noc_rows"):
        blob = scan.get(key)
        if not isinstance(blob, list):
            continue
        rows.extend(r for r in blob if isinstance(r, dict))
    for key in ("best_candidate", "best", "best_eligible_candidate"):
        blob = scan.get(key)
        if isinstance(blob, dict):
            rows.append(blob)
    return rows


def _merge_scan_rows(*rows: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key, value in row.items():
            if value is None or value == "":
                continue
            if isinstance(value, (list, tuple)) and not value:
                continue
            merged[key] = value
    reasons = named_reject_reasons(*rows)
    if reasons:
        merged["reject_reasons"] = reasons
    return merged


def _find_gold_scan_row(
    scan: dict[str, Any], preferred: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Locate a scored Gold row even when catalogue spelling differs (XAUUSD vs XAUUSD_I)."""
    try:
        from app.domain.trading.gold_only import is_gold_symbol
    except Exception:
        return dict(preferred) if isinstance(preferred, dict) else {}

    matches: list[dict[str, Any]] = []
    if isinstance(preferred, dict) and is_gold_symbol(_row_symbol(preferred) or ""):
        matches.append(preferred)
    for row in _iter_scan_rows(scan):
        if is_gold_symbol(_row_symbol(row) or ""):
            matches.append(row)
    if not matches:
        return {}
    return _merge_scan_rows(*matches)


def _best_candidate_row(scan: dict[str, Any]) -> dict[str, Any]:
    cand = scan.get("best_candidate")
    if isinstance(cand, dict) and _row_symbol(cand):
        return dict(cand)
    ranked = scan.get("opportunity_ranked")
    if isinstance(ranked, list) and ranked:
        first = ranked[0]
        if isinstance(first, dict):
            return dict(first)
    best = scan.get("best")
    if isinstance(best, dict) and _row_symbol(best):
        return dict(best)
    return {}


def _row_for_symbol(scan: dict[str, Any], symbol: str | None) -> dict[str, Any]:
    want = str(symbol or "").strip().upper()
    if not want:
        return {}
    for row in _iter_scan_rows(scan):
        if _row_symbol(row) == want:
            return dict(row)
    return {}


def _volatility_fields(
    scan: dict[str, Any],
    symbol: str | None,
    row_hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    looked = _row_for_symbol(scan, symbol)
    hint = dict(row_hint) if isinstance(row_hint, dict) else {}
    row = {**hint, **looked} if looked else hint
    if not isinstance(row.get("volatility_decision"), dict) and isinstance(
        hint.get("volatility_decision"), dict
    ):
        row = {**row, "volatility_decision": hint.get("volatility_decision")}
    if row.get("atr_pct") is None and hint.get("atr_pct") is not None:
        row = {**row, "atr_pct": hint.get("atr_pct")}
    vol = row.get("volatility_decision") if isinstance(row.get("volatility_decision"), dict) else {}
    thresholds = row.get("thresholds") if isinstance(row.get("thresholds"), dict) else {}
    atr_pct = vol.get("atr_pct") if vol.get("atr_pct") is not None else row.get("atr_pct")
    hard_min = vol.get("hard_min_pct")
    if hard_min is None:
        hard_min = thresholds.get("hard_min_pct")
    band = vol.get("band") or thresholds.get("band")
    return {
        "atr_pct": str(atr_pct) if atr_pct is not None else None,
        "hard_min_pct": str(hard_min) if hard_min is not None else None,
        "band": str(band) if band else None,
        "atr_source_timeframe": SCAN_ATR_TIMEFRAME,
        "atr_source_period": SCAN_ATR_PERIOD,
        "volatility_reason": vol.get("reason") or row.get("reject_reason") or row.get("blocking_gate"),
    }


def build_current_scan_decision(scan: dict[str, Any] | None) -> dict[str, Any]:
    """CURRENT SCAN snapshot — never copies last ITE Safety / Optimizer.

    Observability only. Does not authorize trades or bypass Safety.
    Best Candidate may be a rejected row; only eligible symbols are executable.
    """
    payload = dict(scan or {})
    eligible = _scan_eligible_symbols(payload)
    try:
        from app.domain.trading.gold_only import (
            filter_autonomous_symbols,
            gold_only_enabled,
        )

        if gold_only_enabled():
            eligible = list(filter_autonomous_symbols(eligible))
            payload["eligible_symbols"] = eligible
    except Exception:
        pass
    best_row = _best_candidate_row(payload)
    scan_symbol = _row_symbol(best_row)
    if scan_symbol:
        best_row = _merge_scan_rows(best_row, _row_for_symbol(payload, scan_symbol))
    try:
        from app.domain.trading.gold_only import gold_only_enabled, is_gold_symbol

        if gold_only_enabled():
            gold_row = _find_gold_scan_row(payload, best_row)
            if gold_row:
                best_row = gold_row
                scan_symbol = _row_symbol(gold_row)
            elif scan_symbol and not is_gold_symbol(scan_symbol):
                scan_symbol = None
                best_row = {}
    except Exception:
        pass
    named = named_reject_reasons(
        best_row,
        payload.get("reject_reasons"),
        payload.get("first_blocking_gate"),
        payload.get("reject_reason"),
    )
    gate = named[0] if named else None
    trace = (
        payload.get("eligibility_trace")
        if isinstance(payload.get("eligibility_trace"), dict)
        else None
    )
    if not eligible:
        named_elig = str((trace or {}).get("first_failed_code") or "").strip()
        gate = named_elig or gate or "NO_ELIGIBLE_SETUP"
    vol = _volatility_fields(payload, scan_symbol, best_row)
    as_of = payload.get("as_of")
    scores = {
        str(r.get("symbol") or "").upper(): float(r.get("opportunity_score") or 0)
        for r in (payload.get("opportunity_ranked") or [])
        if isinstance(r, dict) and str(r.get("symbol") or "").strip()
    }
    proposed = str(payload.get("best_symbol") or "").upper() or None
    prior_focus = None
    try:
        prior_focus = (
            str(opportunity_window_snapshot().get("current_focus") or "").upper() or None
        )
    except Exception:
        prior_focus = None
    held, focus_why = apply_focus_hysteresis(
        current_focus=prior_focus,
        eligible_symbols=eligible,
        scores=scores,
        proposed=proposed,
    )
    classified = classify_candidate_outcome(
        abort_reason=gate,
        failed_reasons=(gate,) if gate else (),
        cycle_outcome="no_eligible_setup" if not eligible else payload.get("note"),
        decision_action="NO_TRADE" if not eligible else "",
    )
    if not eligible:
        state = DecisionState.NO_ELIGIBLE_SETUP.value
        next_action = CandidateAction.NO_EXECUTABLE_FOCUS.value
        executable_focus = None
        focus_why = "NO_EXECUTABLE_FOCUS"
        fault_class = str(classified.get("fault_class") or FaultClass.WAIT.value)
        if classified.get("next_action") == CandidateAction.ROTATE_FOCUS.value:
            try:
                from app.domain.trading.gold_only import gold_only_enabled

                if gold_only_enabled():
                    next_action = CandidateAction.NO_EXECUTABLE_FOCUS.value
                    focus_why = "NO_EXECUTABLE_FOCUS"
                else:
                    fault_class = FaultClass.CANDIDATE_BLOCK.value
            except Exception:
                fault_class = FaultClass.CANDIDATE_BLOCK.value
        elif "volatility" in _norm(gate or ""):
            fault_class = FaultClass.WAIT.value
        decision_state = DecisionState.NO_EXECUTABLE_FOCUS.value
        blocking_stage = "SCANNER"
        safety_state = SAFETY_NOT_REACHED
        optimizer_state = OPTIMIZER_NOT_RUN
    else:
        state = "ELIGIBLE_PRESENT"
        executable_focus = held
        next_action = (
            CandidateAction.WAIT_SAME_FOCUS.value
            if focus_why in {"HOLD_FOCUS", "WAIT_SAME_FOCUS"}
            else (
                CandidateAction.ROTATE_FOCUS.value
                if "ROTATE" in focus_why
                else CandidateAction.HOLD_FOCUS.value
            )
        )
        try:
            from app.domain.trading.gold_only import gold_only_enabled

            if gold_only_enabled() and next_action == CandidateAction.ROTATE_FOCUS.value:
                next_action = (
                    CandidateAction.WAIT_SAME_FOCUS.value
                    if _is_valid_wait_focus(executable_focus)
                    else CandidateAction.NO_EXECUTABLE_FOCUS.value
                )
        except Exception:
            pass
        next_action = coherent_next_action(
            current_focus=executable_focus,
            next_action=next_action,
        )
        fault_class = FaultClass.NONE.value
        decision_state = DecisionState.FOCUS_FORMING.value
        blocking_stage = None
        safety_state = SAFETY_NOT_REACHED
        optimizer_state = OPTIMIZER_NOT_RUN
        gate = None

    if is_ignored_action_value(gate):
        gate = "NO_ELIGIBLE_SETUP" if not eligible else NO_CURRENT_BLOCKING_GATE
    fault_code = blocking_gate_fault_code(gate) if gate else None
    if is_ignored_action_value(fault_code) or str(fault_code or "") in {
        "WAIT_SAME_FOCUS",
        "NO_TRADE",
        "WATCH",
    }:
        fault_code = NO_CURRENT_BLOCK if not gate else blocking_gate_fault_code(gate)
    next_action = coherent_next_action(
        current_focus=executable_focus,
        next_action=next_action,
    )
    best_eligible = payload.get("best_eligible_candidate")
    if not isinstance(best_eligible, dict):
        best_eligible = None
    all_reasons = named if (not eligible and named) else []
    try:
        from app.domain.institutional_trading.operations.system_coherence import (
            symbol_identity,
        )
    except Exception:
        def symbol_identity(sym: str) -> tuple[str, str]:
            u = str(sym or "").upper()
            return u, u

    if scan_symbol:
        logical, canonical = symbol_identity(scan_symbol)
    else:
        logical, canonical = "", ""
    opp_score = best_row.get("opportunity_score") if best_row else None
    opp_threshold = (
        best_row.get("opportunity_threshold") if best_row else None
    ) or 70
    score_band = best_row.get("score_band") if best_row else None
    score_breakdown = (
        best_row.get("score_breakdown")
        or best_row.get("opportunity_components")
        or {}
    )
    direction = (best_row.get("direction") if best_row else None) or None
    row_eligible = bool(
        (best_row.get("eligible") if best_row else False)
        or (best_row.get("opportunity_eligible") if best_row else False)
    )
    try:
        opp_i = int(opp_score) if opp_score is not None else None
    except (TypeError, ValueError):
        opp_i = None
    if opp_i is not None:
        from app.domain.institutional_trading.operations.probability_selector import (
            score_band_for,
        )

        score_band = score_band or score_band_for(opp_i, threshold=int(opp_threshold))
        if opp_i < int(opp_threshold):
            row_eligible = False
            if _is_generic_scan_gate(gate):
                state = DecisionState.SETUP_NOT_READY.value
                next_action = CandidateAction.WAIT.value
                blocking_stage = "PROBABILITY"
                fault_class = FaultClass.WAIT.value
                fault_code = "OPPORTUNITY_SCORE_BELOW_THRESHOLD"
                gate = "OPPORTUNITY_SCORE_BELOW_THRESHOLD"
                decision_state = DecisionState.SETUP_NOT_READY.value
            else:
                next_action = next_action or CandidateAction.WAIT.value
        elif str(direction or "").upper() not in {"BUY", "SELL"}:
            row_eligible = False
            if _is_generic_scan_gate(gate):
                next_action = CandidateAction.WAIT.value
                blocking_stage = "DECISION"
                fault_code = "DIRECTION_NONE"
                gate = "DIRECTION_NONE"
        elif row_eligible and eligible:
            next_action = CandidateAction.RISK_ASSESSMENT.value
            blocking_stage = None
            fault_code = None
            gate = None
            state = "ELIGIBLE_PRESENT"
            decision_state = DecisionState.FOCUS_FORMING.value
    trade_class = "NO_TRADE"
    trade_class_reason = "No classified opportunity on this scan."
    try:
        from app.domain.institutional_trading.operations.trade_classifier import (
            classify_trade,
        )

        trade_classified = classify_trade(
            opportunity_score=int(opp_i or 0),
            direction=str(direction or "NONE"),
            confidence=(
                (best_row.get("confidence") or best_row.get("ai_confidence"))
                if best_row
                else None
            ),
            structure=(
                (best_row.get("structure") or best_row.get("structure_score"))
                if best_row
                else None
            ),
            risk_reward=best_row.get("expected_rr") if best_row else None,
            regime=best_row.get("market_regime") if best_row else None,
            mtf_alignment=best_row.get("mtf") if best_row else None,
            execution_quality=(
                best_row.get("spread_score") if best_row else None
            ),
            cycle_id=str(payload.get("cycle_id") or "") or None,
            snapshot_id=str(payload.get("snapshot_id") or "") or None,
        )
        trade_class = trade_classified.trade_class.value
        trade_class_reason = trade_classified.reason
    except Exception:
        pass
    return {
        "label": "CURRENT_SCAN",
        "state": state,
        "decision_state": decision_state,
        "symbol": scan_symbol,
        "logical_symbol": logical or None,
        "canonical_symbol": canonical or None,
        "cycle_id": payload.get("cycle_id"),
        "snapshot_id": payload.get("snapshot_id"),
        "current_scan_symbol": scan_symbol,
        "direction": direction,
        "trade_class": trade_class,
        "trade_class_reason": trade_class_reason,
        "opportunity_score": opp_i,
        "opportunity_threshold": int(opp_threshold),
        "score_band": score_band,
        "score_breakdown": dict(score_breakdown) if isinstance(score_breakdown, dict) else {},
        "eligible": bool(row_eligible and eligible),
        "best_candidate": {
            "symbol": scan_symbol,
            "eligible": bool(row_eligible),
            "blocking_gate": gate,
            "reject_reasons": list(all_reasons),
            "direction": direction,
            "quality": (
                (best_row.get("quality") or best_row.get("trade_quality"))
                if best_row
                else None
            ),
            "confidence": (
                (best_row.get("confidence") or best_row.get("ai_confidence"))
                if best_row
                else None
            ),
            "opportunity_score": opp_i,
            "opportunity_threshold": int(opp_threshold),
            "score_band": score_band,
            "score_breakdown": dict(score_breakdown) if isinstance(score_breakdown, dict) else {},
        }
        if scan_symbol
        else None,
        "best_eligible": best_eligible,
        "eligible_count": len(eligible),
        "eligible_symbols": list(eligible),
        "executable_focus": executable_focus,
        "focus_reason": focus_why,
        "first_blocking_gate": gate,
        "all_reject_reasons": list(all_reasons),
        "blocking_stage": blocking_stage or classified.get("blocking_stage") or "SCANNER",
        "fault_class": fault_class,
        "fault_code": fault_code,
        "fault_reason": gate,
        "next_action": next_action,
        "safety_state": safety_state,
        "optimizer_state": optimizer_state,
        "as_of": as_of,
        "atr_pct": vol.get("atr_pct"),
        "hard_min_pct": vol.get("hard_min_pct"),
        "band": vol.get("band"),
        "atr_source_timeframe": vol.get("atr_source_timeframe"),
        "atr_source_period": vol.get("atr_source_period"),
        "volatility_reason": vol.get("volatility_reason"),
        "scanner_duration_ms": payload.get("scanner_duration_ms"),
        "forces_trades": False,
        "execution_ready": bool(eligible) and bool(payload.get("best_symbol")),
        "eligibility_trace": dict(trace) if trace else payload.get("eligibility_trace"),
        "eligibility_status": (
            (trace or {}).get("eligibility_status")
            or payload.get("eligibility_status")
        ),
        "eligibility_reason": (
            (trace or {}).get("eligibility_reason")
            or payload.get("eligibility_reason")
        ),
        "failed_predicates": list(
            (trace or {}).get("failed_predicates")
            or payload.get("failed_predicates")
            or []
        ),
        "passed_predicates": list(
            (trace or {}).get("passed_predicates")
            or payload.get("passed_predicates")
            or []
        ),
        "optimizer_status": payload.get("optimizer_status") or optimizer_state,
        "optimizer_reason": payload.get("optimizer_reason"),
        "config_profile": payload.get("config_profile") or "SCALPING_V1",
    }


def publish_current_scan_decision(scan_or_decision: dict[str, Any] | None) -> dict[str, Any]:
    """Push CURRENT SCAN into the observability window. Never order_send."""
    blob = dict(scan_or_decision or {})
    decision = blob if blob.get("label") == "CURRENT_SCAN" else build_current_scan_decision(blob)
    classification = {
        "decision_state": decision.get("decision_state") or decision.get("state"),
        "fault_class": decision.get("fault_class"),
        "fault_code": decision.get("fault_code"),
        "fault_reason": decision.get("fault_reason"),
        "next_action": decision.get("next_action"),
        "blocking_stage": decision.get("blocking_stage"),
        "current_scan_symbol": decision.get("current_scan_symbol"),
        "eligible_count": decision.get("eligible_count"),
        "retryable": True,
        "candidate_action": decision.get("next_action"),
        "skip_idle_sleep": False,
        "release_entry_budget": True,
    }
    set_focus(decision.get("executable_focus"), reason=str(decision.get("focus_reason") or ""))
    with _LOCK:
        _WINDOW.snapshot_seq += 1
        _WINDOW.snapshot_id = f"current-scan-{_WINDOW.snapshot_seq}"
        _WINDOW.current_scan = dict(decision)
        _WINDOW.current_scan["snapshot_id"] = _WINDOW.snapshot_id
        _WINDOW.scan_published_mono = time.monotonic()
    try:
        from app.domain.institutional_trading.operations.system_coherence import (
            Plane,
            get_coherence_store,
            sanitize_next_action,
        )

        decision["next_action"] = sanitize_next_action(
            focus=str(decision.get("executable_focus") or decision.get("symbol") or ""),
            next_action=str(decision.get("next_action") or ""),
            direction=str(
                (decision.get("best_candidate") or {}).get("direction") or ""
            ),
        )
        published = get_coherence_store().publish(
            Plane.CURRENT_SCAN.value,
            dict(decision),
            sequence=_WINDOW.snapshot_seq,
            source="fast_decision_path.publish_current_scan",
            event_type="CURRENT_SCAN",
        )
        if published.get("accepted"):
            decision["cycle_id"] = published.get("cycle_id")
            decision["snapshot_id"] = published.get("snapshot_id")
            decision["sequence"] = published.get("sequence")
            decision["logical_symbol"] = published.get("logical_symbol")
            decision["canonical_symbol"] = published.get("canonical_symbol")
            with _LOCK:
                _WINDOW.current_scan.update(
                    {
                        "cycle_id": decision["cycle_id"],
                        "snapshot_id": decision["snapshot_id"],
                        "sequence": decision["sequence"],
                        "logical_symbol": decision["logical_symbol"],
                        "canonical_symbol": decision["canonical_symbol"],
                        "next_action": decision["next_action"],
                    }
                )
    except Exception:
        pass
    record_cycle_classification(classification)
    return decision


def build_last_pipeline_snapshot(last_cycle: dict[str, Any] | None) -> dict[str, Any] | None:
    """LAST COMPLETED ITE CYCLE — separate from CURRENT SCAN.

    Does not mutate Safety / Risk / OMS. Read-only projection.
    """
    if not isinstance(last_cycle, dict) or not last_cycle:
        return None
    diag = last_cycle.get("market_context_diagnostics")
    if not isinstance(diag, dict):
        diag = {}
    symbol = (
        str(diag.get("symbol") or diag.get("broker_symbol_resolved") or "").upper()
        or None
    )
    outcome = str(last_cycle.get("cycle_outcome") or "").lower()
    abort = str(last_cycle.get("abort_reason") or "").upper()
    safety_reasons = [
        str(r)
        for r in (last_cycle.get("safety_failed_reasons") or ())
        if str(r).strip()
    ]
    if outcome == "no_snapshot" or abort == "NO_MARKET_CONTEXT":
        safety_state = "NOT_REACHED"
    elif outcome == "safety_blocked" or abort == "SAFETY_BLOCKED" or safety_reasons:
        safety_state = "FAIL"
    elif outcome in {
        "forwarded",
        "execution_deferred",
        "no_trade",
        "aborted",
        "shadow",
    }:
        safety_state = "PASS"
    else:
        safety_state = "NOT_REACHED"
    opt = diag.get("execution_optimizer")
    if isinstance(opt, dict) and str(opt.get("final_state") or "").strip():
        optimizer_state = str(opt.get("final_state"))
        optimizer_symbol = str(opt.get("symbol") or "").upper() or symbol
        optimizer_result = dict(opt)
    else:
        optimizer_state = "NOT_RUN"
        optimizer_symbol = None
        optimizer_result = None
    forwarded = bool(last_cycle.get("forwarded_to_oms"))
    if forwarded:
        oms_state = "FORWARDED"
    elif last_cycle.get("oms_message"):
        oms_state = "MESSAGE"
    else:
        oms_state = "NOT_REACHED"
    autonomous_valid = True
    try:
        from app.domain.trading.gold_only import gold_only_enabled, is_gold_symbol

        if gold_only_enabled():
            autonomous_valid = bool(symbol and is_gold_symbol(symbol))
    except Exception:
        autonomous_valid = True
    snap = {
        "label": "LAST_COMPLETED_ITE_CYCLE",
        "symbol": symbol if autonomous_valid else None,
        "last_pipeline_symbol": symbol if autonomous_valid else None,
        "last_pipeline_raw_symbol": symbol,
        "autonomous_valid": autonomous_valid,
        "last_safety_symbol": symbol if safety_state != "NOT_REACHED" else None,
        "last_optimizer_symbol": optimizer_symbol,
        "cycle_outcome": last_cycle.get("cycle_outcome"),
        "abort_reason": last_cycle.get("abort_reason"),
        "safety_state": safety_state,
        "safety_failed_reasons": safety_reasons,
        "optimizer_state": optimizer_state,
        "optimizer_result": optimizer_result,
        "oms_state": oms_state,
        "decision_action": last_cycle.get("decision_action"),
        "forwarded_to_oms": forwarded,
        "timestamp": diag.get("as_of") or last_cycle.get("timestamp"),
        "as_of": diag.get("as_of") or last_cycle.get("timestamp"),
        "detail": last_cycle.get("detail"),
    }
    try:
        from app.domain.institutional_trading.operations.system_coherence import (
            Plane,
            get_coherence_store,
            symbol_identity,
        )

        logical, canonical = symbol_identity(snap.get("symbol"))
        snap["logical_symbol"] = logical
        snap["canonical_symbol"] = canonical
        get_coherence_store().publish(
            Plane.LAST_PIPELINE.value,
            dict(snap),
            source="fast_decision_path.last_pipeline",
            event_type="LAST_COMPLETED_ITE_CYCLE",
        )
    except Exception:
        pass
    return snap
