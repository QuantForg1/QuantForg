"""Close-then-reverse sequence evaluator — shadow-safe by default.

This module never talks to the broker or OMS. Callers may only act on
``submit_close`` / ``submit_opposite`` when the corresponding LIVE flags are
explicitly enabled by the owner after validation. Until then every plan stays
observe-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.institutional_trading.management.exit_context import (
    ReversalExitProposal,
)


@dataclass(frozen=True, slots=True)
class CloseThenReversePlan:
    """Explainable close-then-reverse stage. Defaults never submit."""

    stage: str
    allowed: bool
    reason: str
    submit_close: bool
    submit_opposite: bool
    classification: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "allowed": self.allowed,
            "reason": self.reason,
            "submit_close": self.submit_close,
            "submit_opposite": self.submit_opposite,
            "classification": self.classification,
            "never_opens_before_broker_confirm": True,
            "never_reverses_to_recover_loss": True,
        }


def evaluate_close_then_reverse(
    *,
    proposal: ReversalExitProposal,
    position_open_broker: bool,
    close_request_sent: bool = False,
    close_broker_confirmed: bool = False,
    close_uncertain: bool = False,
    close_rejected: bool = False,
    opposite_eligible: bool = False,
    concurrent_positions: int = 1,
    reverse_cooldown_active: bool = False,
    loss_recovery_motive: bool = False,
    live_reversal_enabled: bool = False,
    live_reverse_entry_enabled: bool = False,
) -> CloseThenReversePlan:
    """Gate the close → confirm → opposite-entry sequence.

    Hard rules encoded here:
    - Never open the opposite side before broker-confirmed close.
    - Never treat a close request as a confirmed close.
    - Never reverse solely to recover a loss.
    - Never submit when LIVE flags are off (shadow observe only).
    """
    classification = proposal.classification

    if loss_recovery_motive:
        return CloseThenReversePlan(
            stage="reject",
            allowed=False,
            reason="loss_recovery_motive_forbidden",
            submit_close=False,
            submit_opposite=False,
            classification=classification,
        )
    if reverse_cooldown_active:
        return CloseThenReversePlan(
            stage="reject",
            allowed=False,
            reason="reverse_cooldown_active",
            submit_close=False,
            submit_opposite=False,
            classification=classification,
        )
    if proposal.stale_data:
        return CloseThenReversePlan(
            stage="reject",
            allowed=False,
            reason="stale_market_data",
            submit_close=False,
            submit_opposite=False,
            classification=classification,
        )
    if proposal.is_retracement or classification in {
        "temporary_m1_pullback",
        "false_reversal_noise",
    }:
        return CloseThenReversePlan(
            stage="observe",
            allowed=False,
            reason="not_a_confirmed_reversal",
            submit_close=False,
            submit_opposite=False,
            classification=classification,
        )
    if not (proposal.structure_broken or proposal.trend_reversed):
        return CloseThenReversePlan(
            stage="observe",
            allowed=False,
            reason="no_confirmed_reversal_signal",
            submit_close=False,
            submit_opposite=False,
            classification=classification,
        )

    # Confirmed opposing thesis exists — still observe unless LIVE close is on.
    if position_open_broker and not close_broker_confirmed:
        if close_rejected:
            return CloseThenReversePlan(
                stage="reject",
                allowed=False,
                reason="close_rejected_no_opposite",
                submit_close=False,
                submit_opposite=False,
                classification=classification,
            )
        if close_uncertain:
            return CloseThenReversePlan(
                stage="await_broker_confirm",
                allowed=False,
                reason="close_uncertain_hold",
                submit_close=False,
                submit_opposite=False,
                classification=classification,
            )
        if close_request_sent:
            return CloseThenReversePlan(
                stage="await_broker_confirm",
                allowed=False,
                reason="close_request_pending_broker_confirm",
                submit_close=False,
                submit_opposite=False,
                classification=classification,
            )
        # May propose a close only when LIVE reversal exits are owner-enabled.
        return CloseThenReversePlan(
            stage="request_close" if live_reversal_enabled else "observe",
            allowed=bool(live_reversal_enabled),
            reason=(
                "confirmed_reversal_live_close_eligible"
                if live_reversal_enabled
                else "confirmed_reversal_shadow_observe_only"
            ),
            submit_close=bool(live_reversal_enabled),
            submit_opposite=False,
            classification=classification,
        )

    # Broker confirms the old position is gone.
    if not close_broker_confirmed:
        return CloseThenReversePlan(
            stage="await_broker_confirm",
            allowed=False,
            reason="broker_close_not_confirmed",
            submit_close=False,
            submit_opposite=False,
            classification=classification,
        )
    if position_open_broker:
        return CloseThenReversePlan(
            stage="await_broker_confirm",
            allowed=False,
            reason="position_still_open_after_close_claim",
            submit_close=False,
            submit_opposite=False,
            classification=classification,
        )
    if concurrent_positions > 0:
        return CloseThenReversePlan(
            stage="reject",
            allowed=False,
            reason="concurrent_position_still_present",
            submit_close=False,
            submit_opposite=False,
            classification=classification,
        )
    if not opposite_eligible:
        return CloseThenReversePlan(
            stage="evaluate_opposite",
            allowed=False,
            reason="opposite_failed_quality_risk_or_oms",
            submit_close=False,
            submit_opposite=False,
            classification=classification,
        )
    if not live_reverse_entry_enabled:
        return CloseThenReversePlan(
            stage="evaluate_opposite",
            allowed=False,
            reason="opposite_shadow_only_live_entry_disabled",
            submit_close=False,
            submit_opposite=False,
            classification=classification,
        )
    return CloseThenReversePlan(
        stage="submit_opposite",
        allowed=True,
        reason="broker_confirmed_close_opposite_eligible",
        submit_close=False,
        submit_opposite=True,
        classification=classification,
    )
