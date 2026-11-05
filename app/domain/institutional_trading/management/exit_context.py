"""Position-specific exit context builders — design / offline only.

LIVE ITE must not feed ``structure_broken`` / ``trend_reversed`` from these
helpers until the owner explicitly approves activation. Functions are pure and
deterministic for unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ReversalExitProposal:
    """Proposed exit flags — never applied automatically."""

    structure_broken: bool
    trend_reversed: bool
    confidence: str  # high | medium | low | none
    reason: str
    against_side: str  # buy|sell side that would be hurt
    is_retracement: bool
    stale_data: bool


def propose_reversal_exit(
    *,
    position_side: str,
    bos_against: bool = False,
    choch_against: bool = False,
    htf_agrees_against: bool = False,
    ltf_only_noise: bool = False,
    momentum: int | None = None,
    momentum_fade_threshold: int = 40,
    ai_entry_confidence: int | None = None,
    ai_current_confidence: int | None = None,
    confidence_drop: int = 25,
    data_age_seconds: float | None = None,
    max_fresh_seconds: float = 120.0,
    spread: float | None = None,
    emergency_spread: float = 5.0,
) -> ReversalExitProposal:
    """Distinguish genuine reversal vs retracement for offline validation.

    Rules (conservative):
    - Stale data → no exit proposal (stale_data=True).
    - Spread emergency is separate (caller handles via PME spread path).
    - Retracement: LTF noise without HTF/BOS/CHoCH confirmation.
    - Genuine: (BOS or CHoCH against) AND HTF agrees, or strong AI fade.
    """
    side = (position_side or "").lower()
    against = side  # flags are already "against position"
    if data_age_seconds is not None and data_age_seconds > max_fresh_seconds:
        return ReversalExitProposal(
            structure_broken=False,
            trend_reversed=False,
            confidence="none",
            reason="stale market data — no reversal exit",
            against_side=against,
            is_retracement=False,
            stale_data=True,
        )
    if spread is not None and spread > emergency_spread:
        return ReversalExitProposal(
            structure_broken=False,
            trend_reversed=False,
            confidence="none",
            reason="spread expansion — defer to PME spread path",
            against_side=against,
            is_retracement=False,
            stale_data=False,
        )
    if ltf_only_noise and not bos_against and not choch_against:
        return ReversalExitProposal(
            structure_broken=False,
            trend_reversed=False,
            confidence="low",
            reason="ltf noise / normal retracement",
            against_side=against,
            is_retracement=True,
            stale_data=False,
        )
    structure = bool(bos_against or choch_against) and bool(htf_agrees_against)
    trend = structure
    ai_fade = False
    if (
        ai_entry_confidence is not None
        and ai_current_confidence is not None
        and (ai_entry_confidence - ai_current_confidence) >= confidence_drop
        and momentum is not None
        and momentum < momentum_fade_threshold
    ):
        ai_fade = True
        trend = True
    if not structure and not ai_fade:
        return ReversalExitProposal(
            structure_broken=False,
            trend_reversed=False,
            confidence="none",
            reason="no confirmed reversal",
            against_side=against,
            is_retracement=bool(ltf_only_noise),
            stale_data=False,
        )
    conf = "high" if structure and htf_agrees_against else "medium"
    return ReversalExitProposal(
        structure_broken=structure,
        trend_reversed=trend,
        confidence=conf,
        reason=(
            "confirmed structural reversal"
            if structure
            else "AI confidence fade with momentum deterioration"
        ),
        against_side=against,
        is_retracement=False,
        stale_data=False,
    )


def shadow_log_fields(proposal: ReversalExitProposal) -> dict[str, Any]:
    """Fields safe to log without feeding LIVE exit booleans."""
    return {
        "shadow_structure_broken": proposal.structure_broken,
        "shadow_trend_reversed": proposal.trend_reversed,
        "shadow_confidence": proposal.confidence,
        "shadow_reason": proposal.reason,
        "shadow_is_retracement": proposal.is_retracement,
        "shadow_stale_data": proposal.stale_data,
    }
