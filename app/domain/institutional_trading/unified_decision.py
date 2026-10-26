"""One entry decision for the primary strategy and the M1 engine.

The primary ``TradeDecision`` already folds the live ITE stack: confluence,
market context, eligibility, and the registered scalping strategies (SMC,
trend continuation, breakout, range mean-reversion, and momentum). M1 adds
its own cost-checked setups (momentum continuation, pullback continuation,
range breakout, confirmed micro-reversal) plus a volatility screen.

This module does not score those strategies again and it does not send
orders. It only decides which single entry, if any, may be handed to the
existing OMS:

- A source may submit only with a buy or sell direction and a protective
  stop above zero. M1 without that stop is ignored.
- A primary buy or sell still counts as directional intent when its stop
  zone is missing. The existing OMS and gateway reject that order. It must
  not be joined by an opposite M1 order.
- Opposite buy and sell produce no order. Confidence and higher-timeframe
  bias do not break that tie. There is no hedge and no flip.
- The same direction never sums confidence and never creates two orders.
  When the primary is the executable order for this cycle, it owns the
  entry and M1 is confirmation. When the primary did not take the entry,
  M1 may submit that same direction once.
- No actionable signal waits. Nothing here forces a trade.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class NormalizedSignal:
    """One strategy view, already reduced to a single direction."""

    source: str
    direction: str
    confidence: Decimal | None = None
    timeframe: str = ""
    invalidation: Decimal | None = None
    holding_period: str = ""
    direction_counts_without_stop: bool = False


@dataclass(frozen=True, slots=True)
class UnifiedPlan:
    """The only entry this cycle may attempt. ``wait`` attempts none."""

    action: str
    reason: str
    owner: str
    submit_primary: bool
    submit_m1: bool
    confidence: Decimal | None
    timeframe: str
    invalidation: Decimal | None
    holding_period: str
    sources: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "reason": self.reason,
            "owner": self.owner,
            "submit_primary": self.submit_primary,
            "submit_m1": self.submit_m1,
            "confidence": (
                str(self.confidence) if self.confidence is not None else None
            ),
            "timeframe": self.timeframe,
            "invalidation": (
                str(self.invalidation) if self.invalidation is not None else None
            ),
            "holding_period": self.holding_period,
            "sources": list(self.sources),
        }


def resolve_unified(
    primary: NormalizedSignal | None,
    m1: NormalizedSignal | None,
    *,
    primary_executable: bool,
    higher_timeframe_bias: str | None = None,
) -> UnifiedPlan:
    """Pick one owner or wait.

    ``higher_timeframe_bias`` is accepted so callers can show that the
    higher timeframe was considered upstream. It cannot choose a side.
    """
    _ = higher_timeframe_bias
    primary_side = _intent(primary)
    m1_side = _intent(m1)
    if primary_side and m1_side and primary_side != m1_side:
        return UnifiedPlan(
            action="wait",
            reason="direction_conflict",
            owner="",
            submit_primary=False,
            submit_m1=False,
            confidence=None,
            timeframe="",
            invalidation=None,
            holding_period="",
            sources=("primary", "m1"),
        )
    if (
        primary_side
        and m1_side
        and primary_side == m1_side
        and primary is not None
        and m1 is not None
    ):
        if primary_executable:
            return _owned(
                primary,
                m1,
                side=primary_side,
                owner="primary",
                reason="primary_owns_order",
                submit_primary=True,
                submit_m1=False,
            )
        return _owned(
            primary,
            m1,
            side=m1_side,
            owner="m1",
            reason="m1_same_direction_after_primary_block",
            submit_primary=False,
            submit_m1=True,
        )
    if primary_side and primary_executable and primary is not None:
        return UnifiedPlan(
            action=primary_side,
            reason="primary_only",
            owner="primary",
            submit_primary=True,
            submit_m1=False,
            confidence=primary.confidence,
            timeframe=primary.timeframe,
            invalidation=_protective_stop(primary.invalidation),
            holding_period=primary.holding_period,
            sources=("primary",),
        )
    if m1_side and m1 is not None:
        return UnifiedPlan(
            action=m1_side,
            reason="m1_only",
            owner="m1",
            submit_primary=False,
            submit_m1=True,
            confidence=m1.confidence,
            timeframe=m1.timeframe,
            invalidation=_protective_stop(m1.invalidation),
            holding_period=m1.holding_period,
            sources=("m1",),
        )
    if primary_side:
        return _wait("primary_not_submitted")
    return _wait("no_actionable_signal")


def signal_from_decision(decision: object) -> NormalizedSignal:
    """Normalize the primary decision. A missing stop stays missing."""
    action = getattr(decision, "action", "")
    zone = getattr(decision, "stop_zone", None)
    raw_stop = None
    if zone is not None:
        raw_stop = getattr(zone, "mid", None)
        if raw_stop is None:
            raw_stop = getattr(zone, "low", None)
    return NormalizedSignal(
        source="primary",
        direction=str(getattr(action, "value", action) or ""),
        confidence=_decimal_or_none(getattr(decision, "confidence", None)),
        timeframe="primary",
        invalidation=_protective_stop(_decimal_or_none(raw_stop)),
        holding_period=str(getattr(decision, "expected_duration", "") or ""),
        direction_counts_without_stop=True,
    )


def signal_from_m1_note(note: Mapping[str, object]) -> NormalizedSignal:
    """Normalize an M1 note. Only a cost-cleared entry with a stop counts."""
    stop = None
    if bool(note.get("entry_valid")):
        stop = _protective_stop(_decimal_or_none(note.get("stop")))
    return NormalizedSignal(
        source="m1",
        direction=str(note.get("action") or ""),
        confidence=None,
        timeframe="M1",
        invalidation=stop,
        holding_period="m1",
    )


def _owned(
    primary: NormalizedSignal,
    m1: NormalizedSignal,
    *,
    side: str,
    owner: str,
    reason: str,
    submit_primary: bool,
    submit_m1: bool,
) -> UnifiedPlan:
    selected = primary if owner == "primary" else m1
    return UnifiedPlan(
        action=side,
        reason=reason,
        owner=owner,
        submit_primary=submit_primary,
        submit_m1=submit_m1,
        confidence=selected.confidence,
        timeframe=selected.timeframe,
        invalidation=_protective_stop(selected.invalidation),
        holding_period=selected.holding_period,
        sources=("primary", "m1"),
    )


def _wait(reason: str) -> UnifiedPlan:
    return UnifiedPlan(
        action="wait",
        reason=reason,
        owner="",
        submit_primary=False,
        submit_m1=False,
        confidence=None,
        timeframe="",
        invalidation=None,
        holding_period="",
        sources=(),
    )


def _intent(signal: NormalizedSignal | None) -> str:
    if signal is None:
        return ""
    side = _side(signal.direction)
    if not side:
        return ""
    if _protective_stop(signal.invalidation) is not None:
        return side
    if signal.direction_counts_without_stop:
        return side
    return ""


def _side(direction: str) -> str:
    text = str(direction or "").strip().lower()
    if text in {"buy", "sell"}:
        return text
    return ""


def _protective_stop(value: Decimal | None) -> Decimal | None:
    if value is None or value <= 0:
        return None
    return value


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        return None
