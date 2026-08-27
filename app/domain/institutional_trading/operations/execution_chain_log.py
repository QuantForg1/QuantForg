"""Post-AI execution-chain labels — observability only.

Does not submit, retry, or invent a second OMS path. A blocked cycle must
never inherit a prior ticket / retcode / PASS.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

NOT_ATTEMPTED = "NOT_ATTEMPTED"
CHAIN_PASS = "PASS"  # noqa: S105 — log label, not a secret
CHAIN_FAIL = "FAIL"


def bridge_abort_stage(abort_reason: str | None) -> str:
    """Map a bridge abort onto the pipeline stage that actually stopped.

    Eligibility / confluence / quality are Decision-layer — never Broker.
    """
    abort = str(abort_reason or "").strip().upper()
    if not abort or abort in {"NONE", "NULL"}:
        return "STRATEGY"
    if "MAX_POSITION" in abort or "POSITIONS PER SYMBOL" in abort:
        return "RISK"
    if "DAILY_LOSS" in abort or "DAILY LOSS" in abort:
        return "RISK"
    if any(
        tok in abort
        for tok in ("ELIGIBILITY", "CONFLUENCE", "QUALITY", "IGNORED_ACTION", "MISSING_ZONES")
    ):
        return "ELIGIBILITY"
    if any(tok in abort for tok in ("EXPIRED", "STALE", "INPUT_HASH")):
        return "DECISION"
    if any(tok in abort for tok in ("RISK", "MIN_LOT", "SIZING", "MISSING_LOTS")):
        return "RISK"
    if any(tok in abort for tok in ("KILL", "SAFETY", "SELF_PROTECTION")):
        return "SAFETY"
    if any(
        tok in abort
        for tok in ("EXECUTION_HEALTH", "HEALTH_DEGRADED", "HEALTH")
    ):
        return "EXECUTION_HEALTH"
    if any(tok in abort for tok in ("OPTIMIZER", "DEFER")):
        return "OPTIMIZER"
    if any(
        tok in abort
        for tok in (
            "NO_EXECUTABLE",
            "NO_ELIGIBLE",
            "OPPORTUNITY",
            "SETUP_NOT_READY",
            "DIRECTION_NONE",
            "WAITING_NEXT_CYCLE",
            "WAIT_NO_DIRECTIONAL",
            "NO CLEAR BUY/SELL",
            "NO EDGE",
            "BALANCED SCORES",
            "WAIT_SNIPER",
            "WAIT_CHASE",
            "WAIT_STALE",
            "WAIT_CONFLICT",
            "WAIT_NO_SNIPER",
        )
    ):
        return "STRATEGY"
    if any(
        tok in abort
        for tok in (
            "MT5",
            "GATEWAY",
            "BROKER",
            "MARKET_CLOSED",
            "SPREAD",
            "SLIPPAGE",
            "SESSION_INVALID",
        )
    ):
        return "BROKER"
    if any(
        tok in abort
        for tok in (
            "OMS",
            "DUPLICATE",
            "POSITION",
            "CANARY",
            "EXECUTION_DISABLED",
            "AUTO_TRADING",
        )
    ):
        return "OMS"
    return "STRATEGY"


def build_execution_handoff(
    *,
    take: bool,
    abort_reason: str | None = None,
    blocking_stage: str | None = None,
    forwarded_to_oms: bool = False,
    mt5_ticket: Any = None,
) -> dict[str, Any]:
    """Stage stamps for one cycle. TAKE is not a fill. Ticket required for EXECUTED."""
    abort = str(abort_reason or "").upper()
    stage = str(blocking_stage or bridge_abort_stage(abort_reason) or "").upper()
    ticket_ok = mt5_ticket is not None and str(mt5_ticket).strip() not in {
        "",
        "None",
        "0",
    }
    forwarded = bool(forwarded_to_oms)
    risk_block = stage == "RISK" or "DAILY_LOSS" in abort or "RISK" in abort
    safety_block = stage == "SAFETY" or (
        "SAFETY" in abort or "KILL" in abort or "AUTOTRADING" in abort
    )
    health_block = stage == "EXECUTION_HEALTH" or (
        "EXECUTION_HEALTH" in abort or "HEALTH_DEGRADED" in abort
    )
    oms_block = bool(take) and stage == "OMS" and not forwarded
    risk_entered = bool(take) or risk_block or safety_block or health_block or forwarded
    safety_entered = (
        (bool(take) and not risk_block) or safety_block or health_block or forwarded
    )
    optimizer_entered = (
        safety_entered and not safety_block and not health_block
    )
    oms_entered = forwarded or oms_block
    return {
        "decision_take": bool(take),
        "risk_entered": risk_entered,
        "risk_passed": bool(take) and not risk_block and (safety_entered or forwarded),
        "safety_entered": safety_entered,
        "safety_passed": safety_entered and not safety_block,
        "optimizer_entered": optimizer_entered,
        "optimizer_passed": optimizer_entered and (oms_entered or forwarded),
        "oms_entered": oms_entered,
        "oms_forwarded": forwarded,
        "broker_received": forwarded,
        "mt5_ticket": int(mt5_ticket) if ticket_ok else None,
        "execution_confirmed": bool(forwarded and ticket_ok),
        "terminal_reason": abort or ("EXECUTED" if forwarded and ticket_ok else None),
        "blocking_stage": stage or None,
    }


def execution_blocked_event(
    *,
    stage: str,
    reason_code: str,
    human_reason: str,
    correlation_id: str | None = None,
    symbol: str | None = None,
    direction: str | None = None,
    signal_id: str | None = None,
) -> dict[str, Any]:
    """Explicit EXECUTION_BLOCKED artefact. Never a silent drop."""
    return {
        "stage": str(stage or "UNKNOWN").upper(),
        "reason_code": str(reason_code or "UNKNOWN_EXECUTION_ERROR").upper(),
        "human_reason": str(human_reason or reason_code or "execution blocked"),
        "correlation_id": correlation_id,
        "symbol": symbol,
        "direction": direction,
        "signal_id": signal_id,
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }


def classify_post_ai_execution_chain(
    *,
    forwarded_to_oms: bool,
    may_submit_oms: bool | None = None,
    blocking_stage: str | None = None,
    ticket: Any = None,
    retcode: Any = None,
    this_cycle_forwarded: bool | None = None,
) -> dict[str, Any]:
    """Labels for OMS / Gateway / MT5 after AI Decision.

    If this cycle did not reach OMS, tickets from a prior fill are dropped.
    """
    forwarded = bool(forwarded_to_oms)
    if this_cycle_forwarded is False:
        forwarded = False
    stage = str(blocking_stage or "").strip().upper()
    blocked = (
        not forwarded
        or may_submit_oms is False
        or stage == "RISK"
    )
    if blocked:
        return {
            "oms_submit": NOT_ATTEMPTED,
            "submitting_order": False,
            "mt5_gateway": NOT_ATTEMPTED,
            "broker": NOT_ATTEMPTED,
            "mt5_accepted": False,
            "ticket": None,
            "retcode": None,
            "forwarded_to_oms": False,
        }
    ticket_ok = ticket is not None and str(ticket).strip() not in {"", "None", "0"}
    return {
        "oms_submit": CHAIN_PASS,
        "submitting_order": True,
        "mt5_gateway": CHAIN_PASS,
        "broker": CHAIN_PASS if ticket_ok else CHAIN_FAIL,
        "mt5_accepted": ticket_ok,
        "ticket": ticket if ticket_ok else None,
        "retcode": retcode,
        "forwarded_to_oms": True,
    }
