"""Policy helpers for BE / trail / partial / time / emergency / shutdown."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.institutional_trading.management.config import PositionManagementConfig
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    PositionLifecycleState,
    PositionManageContext,
)
from app.domain.institutional_trading.management.r_math import (
    break_even_stop,
    is_stop_improvement,
    partial_close_volume,
    signed_r,
    trail_distance,
    trail_stop_price,
    volatility_regime,
)


@dataclass(frozen=True, slots=True)
class PlannedAction:
    kind: ManageActionKind
    reason: str
    new_sl: Decimal | None = None
    new_tp: Decimal | None = None
    volume: Decimal | None = None
    target_state: PositionLifecycleState | None = None


def plan_action(
    position: ManagedPosition,
    context: PositionManageContext,
    config: PositionManagementConfig,
) -> PlannedAction:
    """Deterministic priority planner — one action per evaluate tick."""
    if position.state is PositionLifecycleState.EXITED:
        return PlannedAction(ManageActionKind.SKIP, "Already exited")

    if not context.position_still_open:
        return PlannedAction(
            ManageActionKind.SKIP,
            "Position missing from book / manually closed — mark exited locally",
            target_state=PositionLifecycleState.EXITED,
        )

    # Sync volume from book when provided
    r = signed_r(position, context.current_price)

    # --- Daily shutdown (highest priority flatten) ---
    if context.daily_loss_exceeded:
        return PlannedAction(
            ManageActionKind.DAILY_SHUTDOWN,
            "Daily loss exceeded — flatten",
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )
    if context.kill_switch_armed:
        return PlannedAction(
            ManageActionKind.DAILY_SHUTDOWN,
            "Kill switch armed — flatten",
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )
    if context.news_requests_exit:
        return PlannedAction(
            ManageActionKind.DAILY_SHUTDOWN,
            "News protection requests exit — flatten",
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )

    # --- Emergency exit ---
    if context.structure_broken:
        return PlannedAction(
            ManageActionKind.EMERGENCY_EXIT,
            "Structure break — emergency exit",
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )
    if context.trend_reversed:
        return PlannedAction(
            ManageActionKind.EMERGENCY_EXIT,
            "Trend reverse — emergency exit",
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )
    if context.spread is not None and context.spread > config.emergency_spread_max:
        return PlannedAction(
            ManageActionKind.EMERGENCY_EXIT,
            f"Spread spike {context.spread} — emergency exit",
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )
    if not context.market_open:
        return PlannedAction(
            ManageActionKind.EMERGENCY_EXIT,
            "Market closed — emergency exit",
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )
    if not context.connection_stable:
        return PlannedAction(
            ManageActionKind.EMERGENCY_EXIT,
            "Connection unstable — emergency exit",
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )
    if context.risk_requests_exit:
        return PlannedAction(
            ManageActionKind.EMERGENCY_EXIT,
            "Risk engine requests exit",
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )

    # --- Time stop ---
    hold_minutes = (context.now - position.opened_at).total_seconds() / 60.0
    if (
        hold_minutes >= config.time_stop_minutes
        and position.max_favorable_r < config.time_stop_min_r
        and r < config.time_stop_min_r
    ):
        return PlannedAction(
            ManageActionKind.TIME_STOP,
            (
                f"Time stop {config.time_stop_minutes}m — "
                f"max R {position.max_favorable_r} < {config.time_stop_min_r}"
            ),
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )

    # --- Progressive management (never skip states) ---
    mid = context.mid_price or context.current_price
    regime = volatility_regime(context.atr, mid, config)

    if (
        position.state is PositionLifecycleState.OPEN
        and not position.be_moved
        and r >= config.break_even_at_r
    ):
        new_sl = break_even_stop(position, config)
        if not is_stop_improvement(position, new_sl):
            return PlannedAction(
                ManageActionKind.NOOP,
                "BE candidate does not improve stop",
            )
        return PlannedAction(
            ManageActionKind.BREAK_EVEN,
            f"Break-even at {r}R (+{config.break_even_offset_r}R offset)",
            new_sl=new_sl,
            new_tp=position.current_tp if position.current_tp > 0 else None,
            target_state=PositionLifecycleState.BE_MOVED,
        )

    if (
        position.state is PositionLifecycleState.BE_MOVED
        and not position.partial_done
        and r >= config.partial_at_r
    ):
        vol = partial_close_volume(position, config)
        if vol <= 0:
            return PlannedAction(ManageActionKind.NOOP, "Partial volume too small")
        return PlannedAction(
            ManageActionKind.PARTIAL_CLOSE,
            f"Partial close {config.partial_close_pct}% at {r}R",
            volume=vol,
            target_state=PositionLifecycleState.PARTIAL,
        )

    if (
        position.state
        in {
            PositionLifecycleState.PARTIAL,
            PositionLifecycleState.TRAILING,
        }
        and r >= config.trail_after_r
    ):
        dist = trail_distance(context.atr, regime, config)
        new_sl = trail_stop_price(position, context.current_price, dist)
        if not is_stop_improvement(position, new_sl):
            return PlannedAction(
                ManageActionKind.NOOP,
                f"Trail ({regime.value}) would not improve SL",
            )
        target = PositionLifecycleState.TRAILING
        return PlannedAction(
            ManageActionKind.TRAIL,
            f"ATR trail ({regime.value}) dist={dist} at {r}R",
            new_sl=new_sl,
            new_tp=position.current_tp if position.current_tp > 0 else None,
            target_state=target,
        )

    return PlannedAction(
        ManageActionKind.NOOP, f"No action (R={r}, state={position.state.value})"
    )
