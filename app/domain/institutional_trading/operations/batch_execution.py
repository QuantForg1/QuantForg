"""Submit one authorized position plan through the EXISTING OMS bridge.

Loops ExecutionBridge.handle. Never opens a second order_send path.
UNKNOWN legs stop the remainder and require reconciliation — no retry.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import replace
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.decision_models import TradeDecision
from app.domain.institutional_trading.execution.models import (
    BridgeAbortReason,
    ExecutionBridgeContext,
    ExecutionBridgeResult,
)
from app.domain.institutional_trading.operations.position_plan import (
    BatchFillTally,
    PositionPlan,
    apply_tally,
    cycle_already_executed,
    mark_cycle_executed,
)

_HARD_ABORTS = frozenset(
    {
        BridgeAbortReason.KILL_SWITCH,
        BridgeAbortReason.EXECUTION_DISABLED,
        BridgeAbortReason.ELIGIBILITY_FAILED,
        BridgeAbortReason.AUTO_TRADING_BLOCKED,
        BridgeAbortReason.MARKET_CLOSED,
        BridgeAbortReason.DECISION_EXPIRED,
        BridgeAbortReason.SELF_PROTECTION,
        BridgeAbortReason.HEALTH_DEGRADED,
        BridgeAbortReason.SPREAD_UNACCEPTABLE,
    }
)

_SUCCESS_OUTCOMES = frozenset(
    {"success", "filled", "done", "accepted", "oms_success"}
)
_UNKNOWN_OUTCOMES = frozenset(
    {"unknown", "timeout", "ambiguous", "reconciliation_required"}
)

SubmitFn = Callable[
    [TradeDecision, ExecutionBridgeContext],
    ExecutionBridgeResult,
]


def classify_leg_outcome(result: Any) -> str:
    """accepted | rejected | unknown | hard_block — never retries."""
    abort = getattr(result, "abort_reason", None)
    abort_enum = abort if isinstance(abort, BridgeAbortReason) else None
    if abort_enum in _HARD_ABORTS:
        return "hard_block"
    oms = getattr(result, "oms_result", None)
    outcome = str(getattr(oms, "outcome", "") or "").strip().lower()
    forwarded = bool(getattr(result, "forwarded_to_oms", False))
    aborted = bool(getattr(result, "aborted", False))
    if outcome in _UNKNOWN_OUTCOMES:
        return "unknown"
    if forwarded and not aborted and outcome in _SUCCESS_OUTCOMES:
        return "accepted"
    if forwarded and oms is None:
        return "unknown"
    if forwarded and outcome in _SUCCESS_OUTCOMES:
        return "accepted"
    status = str(getattr(getattr(result, "journal_entry", None), "status", "") or "")
    if status.lower() in {"oms_success", "forwarded"} and forwarded:
        return "accepted"
    return "rejected"


def submit_position_plan_batch(
    *,
    plan: PositionPlan,
    decision: TradeDecision,
    context: ExecutionBridgeContext,
    submit: SubmitFn,
    trade_class: str,
) -> tuple[PositionPlan, BatchFillTally, ExecutionBridgeResult | None]:
    """Submit every authorized leg in THIS cycle. Duplicate cycle is a no-op."""
    tally = BatchFillTally(requested_count=int(plan.effective_count))
    last: ExecutionBridgeResult | None = None
    existing = cycle_already_executed(plan.cycle_id, plan.snapshot_id)
    if existing and existing != plan.position_plan_id:
        tally.state = "SOFT_REJECT"
        tally.reasons.append("duplicate_cycle_blocked")
        return apply_tally(plan, tally), tally, None
    if not mark_cycle_executed(
        plan.cycle_id, plan.snapshot_id, plan.position_plan_id
    ):
        tally.state = "SOFT_REJECT"
        tally.reasons.append("duplicate_cycle_blocked")
        return apply_tally(plan, tally), tally, None

    live_account = context.account
    live_ctx = context
    for leg in plan.legs:
        duration = "scalp" if str(trade_class).upper() == "SCALP" else "hold"
        leg_decision = replace(
            decision,
            id=uuid4(),
            input_hash=leg.input_hash,
            approved_lots=leg.lots,
            expected_duration=duration,
            reasons=(
                *decision.reasons,
                f"trade_class={trade_class}",
                f"position_plan_id={plan.position_plan_id}",
                f"cycle_id={plan.cycle_id}",
                f"snapshot_id={plan.snapshot_id}",
                f"leg={leg.leg_index + 1}/{plan.effective_count}",
            ),
        )
        live_ctx = replace(
            live_ctx,
            expected_input_hash=leg.input_hash,
            account=live_account,
            request_id=f"{context.request_id or 'batch'}:leg:{leg.leg_index}",
        )
        last = submit(leg_decision, live_ctx)
        tally.submitted_count += 1
        kind = classify_leg_outcome(last)
        if kind == "accepted":
            tally.accepted_count += 1
            with suppress(Exception):
                live_account = replace(
                    live_account,
                    open_positions=int(live_account.open_positions) + 1,
                    already_in_trade=True,
                )
        elif kind == "unknown":
            tally.unknown_count += 1
            tally.reasons.append("UNKNOWN_ORDER")
            tally.state = "RECONCILIATION_REQUIRED"
            break
        elif kind == "hard_block":
            tally.rejected_count += 1
            abort = getattr(last, "abort_reason", None)
            tally.reasons.append(str(getattr(abort, "value", abort) or "hard_block"))
            tally.state = "HARD_BLOCK"
            break
        else:
            tally.rejected_count += 1

    if tally.unknown_count:
        tally.state = "RECONCILIATION_REQUIRED"
    elif tally.accepted_count == tally.requested_count and tally.requested_count:
        tally.state = "FULL_FILL"
    elif tally.accepted_count > 0:
        tally.state = "PARTIAL_FILL"
    return apply_tally(plan, tally), tally, last
