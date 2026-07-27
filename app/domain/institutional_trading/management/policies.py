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


def _pick_trail_stop(
    position: ManagedPosition,
    context: PositionManageContext,
    config: PositionManagementConfig,
    *,
    regime_label: str,
) -> tuple[Decimal | None, str]:
    """Prefer structure → liquidity → ATR when respective flags are on.

    Among improving candidates, honor mode priority first; then pick the
    tightest stop within the same priority tier.
    """
    tiers: list[tuple[int, Decimal, str]] = []
    if config.structure_trail_enabled and context.structure_stop is not None:
        tiers.append((0, context.structure_stop, "structure trail"))
    if config.liquidity_trail_enabled and context.liquidity_stop is not None:
        tiers.append((1, context.liquidity_stop, "liquidity trail"))
    if config.atr_trail_enabled:
        dist = trail_distance(
            context.atr,
            volatility_regime(
                context.atr, context.mid_price or context.current_price, config
            ),
            config,
        )
        atr_sl = trail_stop_price(position, context.current_price, dist)
        tiers.append((2, atr_sl, f"ATR trail ({regime_label}) dist={dist}"))

    best: Decimal | None = None
    best_reason = "No trail mode enabled"
    best_tier = 99
    for tier, stop, reason in tiers:
        if not is_stop_improvement(position, stop):
            continue
        if best is None or tier < best_tier:
            best, best_reason, best_tier = stop, reason, tier
            continue
        if tier > best_tier:
            continue
        # Same tier — prefer tighter improving stop
        if position.side.lower() == "buy":
            if stop > best:
                best, best_reason = stop, reason
        elif stop < best:
            best, best_reason = stop, reason
    return best, best_reason


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

    # --- Institutional Alpha AI position management (configurable) ---
    if (
        context.ai_entry_confidence is not None
        and context.ai_current_confidence is not None
    ):
        try:
            from app.domain.institutional_trading.alpha_engine.position_ai import (
                AiManageHints,
                plan_ai_position_action,
            )

            ai_action = plan_ai_position_action(
                position,
                context,
                hints=AiManageHints(
                    entry_confidence=int(context.ai_entry_confidence),
                    current_confidence=int(context.ai_current_confidence),
                    momentum=int(context.ai_momentum or 50),
                    volatility=int(context.ai_volatility or 50),
                    liquidity=int(context.ai_liquidity or 50),
                    trend_strength=int(context.ai_trend_strength or 50),
                ),
                pme_config=config,
            )
            if ai_action is not None:
                return ai_action
        except Exception:  # noqa: S110  # best-effort optional path
            pass

    hold_minutes = (context.now - position.opened_at).total_seconds() / 60.0

    # --- Absolute max hold (scalping) — never keep trades open unnecessarily ---
    if (
        config.absolute_max_hold_minutes > 0
        and hold_minutes >= config.absolute_max_hold_minutes
    ):
        return PlannedAction(
            ManageActionKind.TIME_STOP,
            (
                f"Absolute max hold {config.absolute_max_hold_minutes}m reached "
                f"(held {hold_minutes:.1f}m) — flatten scalp"
            ),
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )

    # --- Time stop (weak R within window) ---
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

    # --- Momentum fade — exit quickly when edge disappears (scalping) ---
    fade_threshold = int(config.momentum_fade_threshold)
    if (
        config.momentum_fade_exit
        and context.ai_momentum is not None
        and int(context.ai_momentum) < fade_threshold
        and r < Decimal("0.8")
        and hold_minutes >= 1.0
    ):
        return PlannedAction(
            ManageActionKind.EMERGENCY_EXIT,
            f"Momentum faded ({context.ai_momentum}<{fade_threshold}) — exit scalping trade",
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )

    # --- Volatility collapse — statistical edge disappears ---
    vol_threshold = int(getattr(config, "volatility_collapse_threshold", 25) or 25)
    if (
        getattr(config, "volatility_collapse_exit", True)
        and context.ai_volatility is not None
        and int(context.ai_volatility) < vol_threshold
        and r < Decimal("0.5")
        and hold_minutes >= 2.0
    ):
        return PlannedAction(
            ManageActionKind.EMERGENCY_EXIT,
            (
                f"Volatility collapsed ({context.ai_volatility}<{vol_threshold}) "
                "— flatten scalp"
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
        if not config.partial_tp_enabled:
            # Advance lifecycle so trail can run without taking partial
            return PlannedAction(
                ManageActionKind.PARTIAL_CLOSE,
                "Partial disabled — advance to PARTIAL for trailing",
                volume=Decimal("0"),
                target_state=PositionLifecycleState.PARTIAL,
            )
        vol = partial_close_volume(position, config)
        if vol > 0:
            return PlannedAction(
                ManageActionKind.PARTIAL_CLOSE,
                f"Partial close {config.partial_close_pct}% at {r}R",
                volume=vol,
                target_state=PositionLifecycleState.PARTIAL,
            )
        # Min-lot (e.g. 0.01): partial volume rounds to 0 — advance lifecycle
        # so trail can run. Does not change R thresholds or strategy knobs.
        return PlannedAction(
            ManageActionKind.PARTIAL_CLOSE,
            "Partial skipped — volume below broker min lot; advance to PARTIAL",
            volume=Decimal("0"),
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
        if not (
            config.atr_trail_enabled
            or config.structure_trail_enabled
            or config.liquidity_trail_enabled
        ):
            return PlannedAction(
                ManageActionKind.NOOP,
                "Trailing disabled by config",
            )
        new_sl, trail_reason = _pick_trail_stop(
            position, context, config, regime_label=regime.value
        )
        if new_sl is None:
            return PlannedAction(
                ManageActionKind.NOOP,
                f"Trail would not improve SL ({trail_reason})",
            )
        return PlannedAction(
            ManageActionKind.TRAIL,
            f"{trail_reason} at {r}R",
            new_sl=new_sl,
            new_tp=position.current_tp if position.current_tp > 0 else None,
            target_state=PositionLifecycleState.TRAILING,
        )

    return PlannedAction(
        ManageActionKind.NOOP, f"No action (R={r}, state={position.state.value})"
    )
