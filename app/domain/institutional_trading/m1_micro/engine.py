"""Decide an M1 candidate. Never submits, sizes, or invents a stop."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.institutional_trading.m1_micro.config import m1_micro_enabled
from app.domain.institutional_trading.m1_micro.costs import (
    cost_cleared,
    round_trip_cost,
)
from app.domain.institutional_trading.m1_micro.exits import exit_reason, reentry_allowed
from app.domain.institutional_trading.m1_micro.signals import Bar, Setup, detect_setup
from app.domain.institutional_trading.owner_live_limits import (
    OWNER_MAX_OPEN_POSITIONS,
    OWNER_MAX_PLANNED_RISK_PCT,
)
from app.domain.institutional_trading.runtime_policy import active_max_open_positions

_COST_MULTIPLE = Decimal("1.50")


@dataclass(frozen=True, slots=True)
class M1Decision:
    action: str
    setup: str
    reason: str
    stop: Decimal | None = None
    target: Decimal | None = None
    cost: Decimal = Decimal("0")
    signal_id: str = ""


def evaluate_m1(
    bars: list[Bar],
    *,
    bid: Decimal,
    ask: Decimal,
    higher_timeframe_bias: str,
    open_positions: int = 0,
    planned_risk_pct: Decimal = Decimal("0"),
    open_planned_risk_pct: Decimal = Decimal("0"),
    open_risk_known: bool = True,
    slippage_points: Decimal = Decimal("0.05"),
    commission_points: Decimal = Decimal("0"),
    last_signal_id: str = "",
    thesis_open: bool = False,
    side_open: str = "",
    invalidation: Decimal | None = None,
    target_open: Decimal | None = None,
) -> M1Decision:
    """Return a decision. ``action`` is disabled, none, buy, sell, or exit.

    Lot size is intentionally absent. The existing risk engine remains the
    only sizer, and it still rejects anything above 9% of live equity.
    """
    if not m1_micro_enabled():
        return M1Decision(
            action="disabled",
            setup="",
            reason="M1_MICRO_DISABLED",
        )
    spread = Decimal(str(ask)) - Decimal(str(bid))
    if spread < 0 or Decimal(str(bid)) <= 0 or Decimal(str(ask)) <= 0:
        return M1Decision(action="none", setup="", reason="quote_unusable")
    if thesis_open and invalidation is not None and target_open is not None:
        why = exit_reason(
            side=side_open,
            bid=Decimal(str(bid)),
            ask=Decimal(str(ask)),
            invalidation=invalidation,
            target=target_open,
        )
        if why:
            return M1Decision(action="exit", setup="exit", reason=why)
        return M1Decision(action="none", setup="", reason="thesis_intact")
    if not open_risk_known:
        return M1Decision(
            action="none",
            setup="",
            reason="open_planned_risk_unmeasured",
        )
    if int(open_positions) >= min(
        active_max_open_positions(), OWNER_MAX_OPEN_POSITIONS
    ):
        return M1Decision(
            action="none",
            setup="",
            reason="shared_book_position_open",
        )
    combined_risk = Decimal(str(planned_risk_pct)) + Decimal(str(open_planned_risk_pct))
    if combined_risk > OWNER_MAX_PLANNED_RISK_PCT:
        return M1Decision(
            action="none",
            setup="",
            reason="combined_planned_risk_above_9_percent",
        )
    if Decimal(str(planned_risk_pct)) > OWNER_MAX_PLANNED_RISK_PCT:
        return M1Decision(
            action="none",
            setup="",
            reason="planned_risk_above_9_percent",
        )
    cost = round_trip_cost(
        spread=spread,
        slippage_points=slippage_points,
        commission_points=commission_points,
    )
    setup: Setup | None = detect_setup(
        bars,
        higher_timeframe_bias=higher_timeframe_bias,
        spread=spread,
    )
    if setup is None:
        return M1Decision(action="none", setup="", reason="no_setup", cost=cost)
    if not reentry_allowed(
        last_signal_id=last_signal_id,
        signal_id=setup.signal_id,
        thesis_open=thesis_open,
    ):
        return M1Decision(
            action="none",
            setup=setup.name,
            reason="duplicate_or_open_signal",
            cost=cost,
            signal_id=setup.signal_id,
        )
    distance = abs(setup.target - setup.stop)
    # The tradable distance is from the quote to the target, not from the stop.
    entry = Decimal(str(ask)) if setup.side == "BUY" else Decimal(str(bid))
    target_distance = abs(setup.target - entry)
    if not cost_cleared(
        target_distance=target_distance, cost=cost, multiple=_COST_MULTIPLE
    ):
        return M1Decision(
            action="none",
            setup=setup.name,
            reason="cost_not_cleared",
            stop=setup.stop,
            target=setup.target,
            cost=cost,
            signal_id=setup.signal_id,
        )
    if distance <= 0 or setup.stop <= 0 or setup.target <= 0:
        return M1Decision(action="none", setup=setup.name, reason="stop_missing")
    return M1Decision(
        action=setup.side.lower(),
        setup=setup.name,
        reason="setup_cleared_cost",
        stop=setup.stop,
        target=setup.target,
        cost=cost,
        signal_id=setup.signal_id,
    )
