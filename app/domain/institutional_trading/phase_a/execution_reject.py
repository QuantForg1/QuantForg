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
        "DECISION_HASH_UNVERIFIED",
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


def should_count_execution_reject(
    oms_result: Any | None,
    *,
    abort_reason: Any = None,
    oms_submit_called: bool = False,
) -> bool:
    """True only after OMS submit and a genuine downstream execution failure."""
    if not oms_submit_called and oms_result is None:
        return False
    return classify_downstream_execution_reject(
        oms_result, abort_reason=abort_reason
    ) is not None


def execution_observability(
    *,
    oms_result: Any | None = None,
    abort_reason: Any = None,
    forwarded_to_oms: bool = False,
    oms_submit_called: bool = False,
    gateway_status: str | None = None,
    reject_reason: str | None = None,
    reject_timestamp: str | None = None,
) -> dict[str, Any]:
    """Operator flags. Never labels Risk/Safety/WAIT as a broker reject."""
    abort = _abort_token(abort_reason)
    raw: dict[str, Any] = {}
    if oms_result is not None:
        maybe = getattr(oms_result, "raw", None)
        if isinstance(maybe, dict):
            raw = maybe
    gw = str(
        gateway_status
        or (getattr(oms_result, "gateway_status", "") if oms_result is not None else "")
        or ""
    ).lower()
    order_send = bool(raw.get("order_send_reached")) or "order_send" in gw
    order_check = bool(raw.get("order_check_reached")) or "order_check" in gw
    oms_reached = bool(
        oms_submit_called
        or oms_result is not None
        or raw.get("oms_reached")
    )
    if abort in _PRE_OMS_ABORTS and not oms_submit_called and oms_result is None:
        oms_reached = False
    broker_reached = bool(order_check or order_send)
    mt5_reached = bool(order_send)
    execution_attempted = bool(order_send)
    retcode = getattr(oms_result, "retcode", None) if oms_result is not None else None
    mt5_retcode = None
    broker_retcode = None
    if retcode is not None and (mt5_reached or order_send):
        try:
            rc = int(retcode)
        except (TypeError, ValueError):
            rc = None
        else:
            broker_retcode = rc
            if 10000 <= rc < 20000:
                mt5_retcode = rc
    stage = None
    if oms_result is not None or oms_submit_called:
        stage = classify_downstream_execution_reject(
            oms_result, abort_reason=abort
        )
    if stage:
        reject_source = stage
    elif oms_reached and not execution_attempted:
        reject_source = "OMS_APPLICATION"
    elif abort in {EXECUTION_REJECT_BURST, "SELF_PROTECTION"} or "REJECT_BURST" in abort:
        reject_source = EXECUTION_REJECT_BURST
    elif abort:
        reject_source = abort
    else:
        reject_source = None
    message = reject_reason
    if not message and oms_result is not None:
        message = str(getattr(oms_result, "message", "") or "") or None
    return {
        "execution_attempted": bool(execution_attempted),
        "oms_reached": bool(oms_reached),
        "broker_reached": bool(broker_reached),
        "mt5_reached": bool(mt5_reached),
        "broker_retcode": broker_retcode,
        "mt5_retcode": mt5_retcode,
        "reject_source": reject_source,
        "reject_reason": message,
        "reject_timestamp": reject_timestamp,
        "counted_toward_reject_burst": stage is not None,
    }


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
