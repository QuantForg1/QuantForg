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
    return None, "NO_EXECUTABLE_FOCUS"


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
            "current_best_candidate": cls.get("current_scan_symbol"),
            "eligible_count": cls.get("eligible_count"),
            "first_blocking_gate": cls.get("fault_reason"),
        }


def blocking_gate_fault_code(reason: str | None) -> str:
    """Map a scanner reject string to a stable observability code.

    Does not change Safety / Risk / OMS. Observability only.
    """
    hay = _norm(reason or "")
    if "volatility below hard" in hay or "dead tape" in hay:
        return "VOLATILITY_HARD_MIN"
    if "volatility unavailable" in hay:
        return "VOLATILITY_UNAVAILABLE"
    if "invalid volatility" in hay or "atr% ≤ 0" in hay or "atr% <=" in hay:
        return "VOLATILITY_INVALID"
    if "volatility too compressed" in hay:
        return "VOLATILITY_COMPRESSED"
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
    return str(classified.get("fault_code") or "NO_ELIGIBLE_SETUP")


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
    for key in ("rows", "opportunity_ranked", "ranked", "noc_rows"):
        blob = scan.get(key)
        if not isinstance(blob, list):
            continue
        for row in blob:
            if _row_symbol(row) == want and isinstance(row, dict):
                return dict(row)
    cand = scan.get("best_candidate")
    if isinstance(cand, dict) and _row_symbol(cand) == want:
        return dict(cand)
    return {}


def _volatility_fields(scan: dict[str, Any], symbol: str | None) -> dict[str, Any]:
    row = _row_for_symbol(scan, symbol)
    vol = row.get("volatility_decision") if isinstance(row.get("volatility_decision"), dict) else {}
    thresholds = row.get("thresholds") if isinstance(row.get("thresholds"), dict) else {}
    atr_pct = vol.get("atr_pct") if vol.get("atr_pct") is not None else row.get("atr_pct")
    hard_min = vol.get("hard_min_pct")
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
    best_row = _best_candidate_row(payload)
    scan_symbol = _row_symbol(best_row)
    gate = str(
        payload.get("first_blocking_gate")
        or best_row.get("blocking_gate")
        or best_row.get("reject_reason")
        or ""
    ).strip() or None
    if not eligible:
        gate = gate or "NO_ELIGIBLE_SETUP"
    vol = _volatility_fields(payload, scan_symbol)
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
            fault_class = FaultClass.CANDIDATE_BLOCK.value
        elif "volatility" in _norm(gate or ""):
            fault_class = FaultClass.WAIT.value
        decision_state = DecisionState.NO_EXECUTABLE_FOCUS.value
        blocking_stage = "SCANNER"
        safety_state = "NOT_REACHED"
        optimizer_state = "NOT_RUN"
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
        fault_class = FaultClass.NONE.value
        decision_state = DecisionState.FOCUS_FORMING.value
        blocking_stage = None
        safety_state = "NOT_REACHED"
        optimizer_state = "NOT_RUN"
        gate = None

    fault_code = blocking_gate_fault_code(gate) if gate else None
    best_eligible = payload.get("best_eligible_candidate")
    if not isinstance(best_eligible, dict):
        best_eligible = None
    return {
        "label": "CURRENT_SCAN",
        "state": state,
        "decision_state": decision_state,
        "symbol": scan_symbol,
        "current_scan_symbol": scan_symbol,
        "best_candidate": {
            "symbol": scan_symbol,
            "eligible": bool(best_row.get("eligible") or best_row.get("opportunity_eligible")),
            "blocking_gate": best_row.get("blocking_gate") or best_row.get("reject_reason") or gate,
            "direction": best_row.get("direction"),
            "quality": best_row.get("quality") or best_row.get("trade_quality"),
            "confidence": best_row.get("confidence") or best_row.get("ai_confidence"),
            "opportunity_score": best_row.get("opportunity_score"),
        }
        if scan_symbol
        else None,
        "best_eligible": best_eligible,
        "eligible_count": len(eligible),
        "eligible_symbols": list(eligible),
        "executable_focus": executable_focus,
        "focus_reason": focus_why,
        "first_blocking_gate": gate,
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
        "forces_trades": False,
        "execution_ready": bool(eligible) and bool(payload.get("best_symbol")),
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
    return {
        "label": "LAST_COMPLETED_ITE_CYCLE",
        "symbol": symbol,
        "last_pipeline_symbol": symbol,
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
        "detail": last_cycle.get("detail"),
    }
