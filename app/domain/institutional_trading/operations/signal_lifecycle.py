"""Per-cycle signal lifecycle — observe only.

A valid BUY/SELL may be rejected. It must not collapse into unexplained
NO_TRADE. This module does not authorize orders or change Risk/Safety.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

SIGNAL_FOUND = "SIGNAL_FOUND"
SIGNAL_ELIGIBLE = "SIGNAL_ELIGIBLE"
SIGNAL_BLOCKED_RISK = "SIGNAL_BLOCKED_RISK"
SIGNAL_BLOCKED_SAFETY = "SIGNAL_BLOCKED_SAFETY"
SIGNAL_BLOCKED_MIN_LOT = "SIGNAL_BLOCKED_MIN_LOT"
SIGNAL_BLOCKED_SAME_SYMBOL = "SIGNAL_BLOCKED_SAME_SYMBOL"
SIGNAL_BLOCKED_PORTFOLIO = "SIGNAL_BLOCKED_PORTFOLIO"
SIGNAL_BLOCKED_MARGIN = "SIGNAL_BLOCKED_MARGIN"
SIGNAL_BLOCKED_BROKER = "SIGNAL_BLOCKED_BROKER"
SIGNAL_EXECUTED = "SIGNAL_EXECUTED"
SIGNAL_MANAGED = "SIGNAL_MANAGED"
SIGNAL_CLOSED = "SIGNAL_CLOSED"

HIGH_QUALITY_MIN = 70

_BLOCKED = frozenset(
    {
        SIGNAL_BLOCKED_RISK,
        SIGNAL_BLOCKED_SAFETY,
        SIGNAL_BLOCKED_MIN_LOT,
        SIGNAL_BLOCKED_SAME_SYMBOL,
        SIGNAL_BLOCKED_PORTFOLIO,
        SIGNAL_BLOCKED_MARGIN,
        SIGNAL_BLOCKED_BROKER,
    }
)


def _hay(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).upper()


def is_high_quality_signal(
    *,
    direction: str | None,
    quality: Any = None,
    confidence: Any = None,
) -> bool:
    d = str(direction or "").strip().upper()
    if d not in {"BUY", "SELL"}:
        return False
    try:
        q = int(quality) if quality is not None else 0
    except (TypeError, ValueError):
        q = 0
    try:
        c = int(confidence) if confidence is not None else 0
    except (TypeError, ValueError):
        c = 0
    return q >= HIGH_QUALITY_MIN and c >= HIGH_QUALITY_MIN


def classify_signal_final_state(
    *,
    direction: str | None = None,
    forwarded_to_oms: bool = False,
    blocking_stage: str | None = None,
    fault_code: str | None = None,
    reasons: str | None = None,
    eligible: bool = False,
    closed: bool = False,
    managed: bool = False,
) -> str:
    """Map existing authoritative gates. Do not invent blockers."""
    if closed:
        return SIGNAL_CLOSED
    if managed:
        return SIGNAL_MANAGED
    if forwarded_to_oms:
        return SIGNAL_EXECUTED
    hay = _hay(blocking_stage, fault_code, reasons)
    stage = str(blocking_stage or "").strip().upper()
    if "MIN_LOT" in hay:
        return SIGNAL_BLOCKED_MIN_LOT
    if stage == "SAFETY" or "SAFETY_BLOCK" in hay or "KILL_SWITCH" in hay:
        return SIGNAL_BLOCKED_SAFETY
    if "SAME_SYMBOL" in hay or "QUANTFORG_SAME_SYMBOL" in hay:
        return SIGNAL_BLOCKED_SAME_SYMBOL
    if "PORTFOLIO" in hay:
        return SIGNAL_BLOCKED_PORTFOLIO
    if "MARGIN" in hay:
        return SIGNAL_BLOCKED_MARGIN
    if (
        stage in {"BROKER", "GATEWAY", "MARKET"}
        or "BROKER_SESSION" in hay
        or "GATEWAY" in hay
        or "SYMBOL_UNAVAILABLE" in hay
    ):
        return SIGNAL_BLOCKED_BROKER
    if stage == "RISK" or "RISK" in hay:
        return SIGNAL_BLOCKED_RISK
    d = str(direction or "").strip().upper()
    if eligible and d in {"BUY", "SELL"}:
        return SIGNAL_ELIGIBLE
    return SIGNAL_FOUND


def blocked_bucket(final_state: str) -> str | None:
    mapping = {
        SIGNAL_BLOCKED_RISK: "risk",
        SIGNAL_BLOCKED_SAFETY: "safety",
        SIGNAL_BLOCKED_MIN_LOT: "min_lot",
        SIGNAL_BLOCKED_SAME_SYMBOL: "same_symbol",
        SIGNAL_BLOCKED_PORTFOLIO: "portfolio",
        SIGNAL_BLOCKED_MARGIN: "margin",
        SIGNAL_BLOCKED_BROKER: "broker",
    }
    return mapping.get(final_state)


def build_signal_lifecycle_record(
    *,
    trace_id: str | None,
    cycle_id: str | None,
    snapshot_id: str | None,
    symbol: str | None,
    direction: str | None,
    confidence: Any = None,
    quality: Any = None,
    strategy_id: str | None = None,
    trade_class: str | None = None,
    approved_stop: Any = None,
    min_lot_feasibility: Any = None,
    risk_result: str | None = None,
    safety_result: str | None = None,
    portfolio_result: str | None = None,
    margin_result: str | None = None,
    broker_result: str | None = None,
    same_symbol_result: str | None = None,
    execution_allowed: bool = False,
    forwarded_to_oms: bool = False,
    blocking_stage: str | None = None,
    fault_code: str | None = None,
    reasons: str | None = None,
    eligible: bool = False,
    ticket: Any = None,
    closed: bool = False,
    managed: bool = False,
) -> dict[str, Any]:
    raw_dir = str(direction or "").strip().upper()
    d = raw_dir if raw_dir in {"BUY", "SELL"} else None
    final_state = classify_signal_final_state(
        direction=d,
        forwarded_to_oms=forwarded_to_oms,
        blocking_stage=blocking_stage,
        fault_code=fault_code,
        reasons=reasons,
        eligible=eligible,
        closed=closed,
        managed=managed,
    )
    hq = is_high_quality_signal(
        direction=d, quality=quality, confidence=confidence
    )
    submitted = bool(forwarded_to_oms)
    stale_attempt = (not submitted) and ticket not in (None, "", "None", "0")
    now = datetime.now(UTC).isoformat()
    return {
        "trace_id": str(trace_id or "") or None,
        "cycle_id": str(cycle_id or "") or None,
        "snapshot_id": str(snapshot_id or "") or None,
        "symbol": str(symbol or "") or None,
        "direction": d,
        "confidence": confidence,
        "quality": quality,
        "strategy_id": str(strategy_id or "") or None,
        "trade_class": str(trade_class or "") or None,
        "approved_stop": str(approved_stop) if approved_stop is not None else None,
        "min_lot_feasibility": (
            str(min_lot_feasibility) if min_lot_feasibility is not None else None
        ),
        "risk_result": risk_result,
        "safety_result": safety_result,
        "portfolio_result": portfolio_result,
        "margin_result": margin_result,
        "broker_result": broker_result,
        "same_symbol_result": same_symbol_result,
        "execution_allowed": bool(execution_allowed),
        "final_state": final_state,
        "final_blocker": (
            None
            if submitted or final_state in {SIGNAL_ELIGIBLE, SIGNAL_FOUND}
            else (str(fault_code or blocking_stage or "").strip() or None)
        ),
        "high_quality": hq,
        "forwarded_to_oms": submitted,
        "ticket": str(ticket) if submitted and ticket not in (None, "") else None,
        "stale_ticket_reused": False,
        "stale_ticket_attempt": stale_attempt,
        "signal_created_at": now,
        "signal_valid_until": "this_cycle",
        "freshness": "STALE_ATTEMPT" if stale_attempt else "FRESH",
        "timestamp": now,
        "blocked": final_state in _BLOCKED,
    }
