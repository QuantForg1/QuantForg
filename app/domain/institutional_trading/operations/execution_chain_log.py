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
        return "OMS"
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
    if any(tok in abort for tok in ("KILL", "SAFETY", "HEALTH", "SELF_PROTECTION")):
        return "SAFETY"
    if any(tok in abort for tok in ("OPTIMIZER", "DEFER")):
        return "OPTIMIZER"
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
    return "OMS"


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
