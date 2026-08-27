"""Classify events that may increment the Phase A reject-burst latch.

The latch is an execution-path circuit breaker. It must increment only when
OMS actually submitted and the broker/MT5 received a request that failed.

Strategy WAIT, Risk/Safety holds before OMS, capacity, daily-loss, and
min-lot rejections are not execution failures and must not arm REJECT_BURST.

Recovery is the configured cooldown (default 300s). A fill is not required.
This module does not disable the breaker, lower thresholds, or force TAKE.
"""

from __future__ import annotations

from typing import Any

# Operator-facing first-blocker tokens. Do not label OMS/Broker/MT5 unless
# that stage was actually reached.
RISK_REJECTED = "RISK_REJECTED"
EXECUTION_REJECT_BURST = "EXECUTION_REJECT_BURST"
SAFETY_BLOCKED = "SAFETY_BLOCKED"
OMS_REJECTED = "OMS_REJECTED"
BROKER_REJECTED = "BROKER_REJECTED"
MT5_REJECTED = "MT5_REJECTED"
GATEWAY = "GATEWAY"

_WAIT_ACTIONS = frozenset({"WAIT", "NO_TRADE", "WATCH", "NONE", ""})
_PRE_OMS_ABORTS = frozenset(
    {
        "IGNORED_ACTION",
        "ELIGIBILITY_FAILED",
        "DAILY_LOSS_BLOCK",
        "MISSING_LOTS",
        "MISSING_ZONES",
        "KILL_SWITCH",
        "AUTO_TRADING_BLOCKED",
        "SAFETY_BLOCKED",
        "EXECUTION_DISABLED",
        "HEALTH_DEGRADED",
        "SELF_PROTECTION",
        "CANARY_DAILY_CAP",
        "CANARY_LOT_LIMIT",
        "CANARY_POSITION_LIMIT",
        "DUPLICATE_DECISION",
        "DECISION_EXPIRED",
        "SESSION_INVALID",
        "MARKET_CLOSED",
        "SPREAD_UNACCEPTABLE",
        "SLIPPAGE_EXCESSIVE",
        "MIN_LOT_CONSTRAINT",
        "MIN_LOT_INFEASIBLE",
        "MAX_POSITIONS_REACHED",
        "CONTINUOUS_OPS_PAUSE_NEW_ENTRIES",
        "RISK_REJECTED",
        "RISK_BLOCK",
    }
)
_BURST_REASON_TOKENS = (
    "execution_reject_burst",
    "reject_burst",
    "phase_a:reject_burst",
    "phase_a:execution_reject_burst",
    "broker_rejection_burst",
    "execution_failure_burst",
    "ambiguous_order_burst",
    "entry_burst",
)


def _abort_token(abort_reason: Any) -> str:
    raw = getattr(abort_reason, "value", abort_reason)
    return str(raw or "").strip().upper()


def _status_token(status: Any) -> str:
    raw = getattr(status, "value", status)
    return str(raw or "").strip().upper()


def reasons_indicate_execution_reject_burst(
    reasons: tuple[str, ...] | list[str] | None,
) -> bool:
    hay = " ".join(str(r).lower() for r in (reasons or ()) if str(r).strip())
    return any(token in hay for token in _BURST_REASON_TOKENS)


def first_blocking_gate_from_reasons(
    reasons: tuple[str, ...] | list[str] | None,
    *,
    default: str = RISK_REJECTED,
) -> str:
    """Map pause / eligibility reasons to an operator first-blocker."""
    hay = " ".join(str(r).upper() for r in (reasons or ()) if str(r).strip())
    if reasons_indicate_execution_reject_burst(reasons):
        return EXECUTION_REJECT_BURST
    if any(
        tok in hay
        for tok in ("SAFETY_BLOCKED", "KILL_SWITCH", "AUTO_TRADING_BLOCKED")
    ):
        return SAFETY_BLOCKED
    if "OMS" in hay and "REJECT" in hay:
        return OMS_REJECTED
    if "MT5" in hay and "REJECT" in hay:
        return MT5_REJECTED
    if "BROKER" in hay and "REJECT" in hay:
        return BROKER_REJECTED
    return default


def burst_record_stage_for_cycle(
    *,
    decision_action: str | None,
    oms_submit_called: bool,
    abort_reason: Any = None,
    oms_result: Any | None = None,
) -> str | None:
    """Return the stage to record on the burst latch, or None to skip.

    None means this cycle must not increment reject-burst.
    """
    action = str(decision_action or "").strip().upper()
    if action in _WAIT_ACTIONS or action.startswith("WAIT"):
        return None
    if not oms_submit_called:
        return None
    abort = _abort_token(abort_reason)
    if abort in _PRE_OMS_ABORTS:
        return None
    if abort in {"GATEWAY_FAILURE", "GATEWAY"}:
        return GATEWAY
    return classify_downstream_execution_reject(oms_result, abort_reason=abort)


def classify_downstream_execution_reject(
    oms_result: Any | None,
    *,
    abort_reason: Any = None,
) -> str | None:
    """Genuine broker/MT5 reject stage, or None if broker never received."""
    abort = _abort_token(abort_reason)
    raw: dict[str, Any] = {}
    if oms_result is not None:
        maybe = getattr(oms_result, "raw", None)
        if isinstance(maybe, dict):
            raw = maybe
    order_send = bool(raw.get("order_send_reached"))
    gateway_status = ""
    retcode = None
    if oms_result is not None:
        gateway_status = str(getattr(oms_result, "gateway_status", "") or "").lower()
        retcode = getattr(oms_result, "retcode", None)
    if "order_send" in gateway_status:
        order_send = True

    mt5_retcode = False
    if retcode is not None:
        try:
            rc = int(retcode)
        except (TypeError, ValueError):
            rc = None
        else:
            # MT5 trade retcodes. order_check TRADE_RETCODE_DONE (0) is not a send.
            mt5_retcode = 10000 <= rc < 20000

    if abort in {"GATEWAY_FAILURE", "GATEWAY"}:
        return GATEWAY
    if order_send or mt5_retcode:
        if abort in {"MT5_REJECTION"} or mt5_retcode:
            return MT5_REJECTED
        return BROKER_REJECTED
    # OMS pipeline ran (validation / Risk / Safety) but broker never received.
    if abort in {"OMS_FAILURE", "OMS_REJECTED"} or abort.endswith("OMS_REJECTED"):
        return None
    return None


def apply_oms_outcome_to_burst(
    burst: Any,
    *,
    abort_reason: Any,
    status: Any,
    oms_result: Any | None = None,
    enabled: bool = True,
) -> Any:
    """Record latch events for a post-submit OMS outcome. Never submits orders."""
    if not enabled or burst is None:
        return None
    abort = _abort_token(abort_reason)
    status_u = _status_token(status)
    if abort in {"GATEWAY_FAILURE", "GATEWAY"}:
        burst.record_ambiguous(stage=GATEWAY)
        return burst.record_execution_failure(stage=GATEWAY)
    if status_u in {"OMS_SUCCESS", "SUCCESS"}:
        return burst.record_entry_attempt()
    stage = classify_downstream_execution_reject(
        oms_result, abort_reason=abort
    )
    if stage is None:
        return None
    burst.record_broker_reject(stage=stage)
    return burst.record_execution_failure(stage=stage)


def burst_clear_condition(*, cooldown_s: float) -> str:
    return (
        f"autonomous cooldown {float(cooldown_s):.0f}s "
        "(fill not required; windowed rejects expire with the window)"
    )
