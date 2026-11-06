"""Position-specific exit context builders.

Pure helpers used by shadow observation and, when
``live_reversal_exits_enabled`` / ``QUANTFORG_LIVE_REVERSAL_EXITS`` allow it,
to feed confirmed classifications into the LIVE PME planner. Pullbacks and
false M1 noise never set ``structure_broken``.
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
    classification: str = "none"
    # temporary_m1_pullback | genuine_momentum_change |
    # confirmed_structure_reversal | htf_trend_reversal |
    # false_reversal_noise | none


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
    - One M1 candle / LTF-only noise never produces structure_broken.
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
            classification="none",
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
            classification="none",
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
            classification="temporary_m1_pullback",
        )
    # LTF BOS without HTF = noise / false reversal, not an exit.
    if (bos_against or choch_against) and not htf_agrees_against:
        return ReversalExitProposal(
            structure_broken=False,
            trend_reversed=False,
            confidence="low",
            reason="ltf structure without htf confirmation — false reversal risk",
            against_side=against,
            is_retracement=True,
            stale_data=False,
            classification="false_reversal_noise",
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
            classification=("temporary_m1_pullback" if ltf_only_noise else "none"),
        )
    if structure and choch_against and htf_agrees_against:
        classification = "htf_trend_reversal"
        reason = "confirmed choch with htf agreement"
    elif structure:
        classification = "confirmed_structure_reversal"
        reason = "confirmed structural reversal"
    else:
        classification = "genuine_momentum_change"
        reason = "AI confidence fade with momentum deterioration"
    conf = "high" if structure and htf_agrees_against else "medium"
    return ReversalExitProposal(
        structure_broken=structure,
        trend_reversed=trend,
        confidence=conf,
        reason=reason,
        against_side=against,
        is_retracement=False,
        stale_data=False,
        classification=classification,
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
        "shadow_classification": proposal.classification,
    }
