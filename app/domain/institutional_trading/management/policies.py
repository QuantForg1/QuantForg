"""Policy helpers for BE / trail / partial / time / emergency / shutdown."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.institutional_trading.management.class_policy import (
    TRADE_CLASS_UNKNOWN,
    resolve_class_management,
)
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
        # Session-aware: soften trail distance in weak sessions (profit protection)
        if getattr(config, "session_aware_management", False):
            sess = str(getattr(context, "market_session", "") or "").lower()
            if sess in {"sydney", "tokyo", "asian"}:
                scale = Decimal(
                    str(getattr(config, "weak_session_trail_scale", "0.85") or "0.85")
                )
                dist = (dist * scale).quantize(Decimal("0.0001"))
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
        # Phase A durable halt: manage positions; do not auto-flatten solely
        # because halt mode is armed (fail-safe for orphaned risk via PME).
        suppress_flatten = False
        try:
            from app.domain.institutional_trading.phase_a import get_phase_a_plane

            suppress_flatten = bool(get_phase_a_plane().halt.suppress_auto_flatten())
        except Exception:
            suppress_flatten = False
        if not suppress_flatten:
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
    profile = resolve_class_management(getattr(position, "trade_class", ""))
    trade_class = profile.trade_class
    time_stop_minutes = int(profile.time_stop_minutes)
    abs_hold = int(profile.absolute_max_hold_minutes or 0)
    cfg_abs = int(config.absolute_max_hold_minutes or 0)
    if trade_class != "HOLD" and cfg_abs > 0:
        abs_hold = min(abs_hold, cfg_abs) if abs_hold > 0 else cfg_abs
    if trade_class == TRADE_CLASS_UNKNOWN:
        from core.logging import get_logger

        get_logger(__name__).warning(
            "pme_trade_class_unknown_fallback",
            ticket=getattr(position, "ticket", None),
            symbol=getattr(position, "symbol", None),
            cycle_id=getattr(position, "cycle_id", None),
            profile=profile.profile_name,
            break_even_at_r=str(profile.break_even_at_r),
            absolute_max_hold_minutes=abs_hold,
        )

    # --- Absolute max hold — SCALP tighter, HOLD longer, UNKNOWN safe ---
    if abs_hold > 0 and hold_minutes >= abs_hold:
        return PlannedAction(
            ManageActionKind.TIME_STOP,
            (
                f"Absolute max hold {abs_hold}m reached "
                f"(held {hold_minutes:.1f}m) — flatten {trade_class}"
            ),
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )

    # --- Time stop (weak R within window) ---
    if (
        hold_minutes >= time_stop_minutes
        and position.max_favorable_r < config.time_stop_min_r
        and r < config.time_stop_min_r
    ):
        return PlannedAction(
            ManageActionKind.TIME_STOP,
            (
                f"Time stop {time_stop_minutes}m — "
                f"max R {position.max_favorable_r} < {config.time_stop_min_r}"
            ),
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )

    # --- Momentum fade — exit quickly when edge disappears (scalping) ---
    fade_threshold = int(config.momentum_fade_threshold)
    if (
        profile.momentum_fade_exit
        and config.momentum_fade_exit
        and context.ai_momentum is not None
        and int(context.ai_momentum) < fade_threshold
        and r < Decimal("0.8")
        and hold_minutes >= 1.0
    ):
        return PlannedAction(
            ManageActionKind.EMERGENCY_EXIT,
            (
                f"Momentum faded ({context.ai_momentum}<{fade_threshold}) "
                "- exit scalping trade"
            ),
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )

    # --- Volatility collapse — statistical edge disappears ---
    vol_threshold = int(getattr(config, "volatility_collapse_threshold", 25) or 25)
    if (
        profile.volatility_collapse_exit
        and getattr(config, "volatility_collapse_exit", True)
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

    be_at = profile.break_even_at_r
    if (
        trade_class == "SCALP"
        and getattr(config, "session_aware_management", False)
    ):
        sess = str(getattr(context, "market_session", "") or "").lower()
        if sess in {"sydney", "tokyo", "asian"}:
            # Earlier break-even timing in thin sessions (SCALP only).
            protect = Decimal(
                str(getattr(config, "session_profit_protect_at_r", "1.5") or "1.5")
            )
            if protect < be_at:
                be_at = protect
            else:
                be_at = (be_at * Decimal("0.8")).quantize(Decimal("0.01"))

    if (
        position.state is PositionLifecycleState.OPEN
        and not position.be_moved
        and r >= be_at
    ):
        from dataclasses import replace as _replace

        be_cfg = _replace(
            config,
            break_even_at_r=profile.break_even_at_r,
            break_even_offset_r=profile.break_even_offset_r,
        )
        new_sl = break_even_stop(position, be_cfg)
        preserved_tp = position.current_tp if position.current_tp > 0 else None
        if not is_stop_improvement(position, new_sl):
            # Stop already at/better than BE — still advance so partial/trail run.
            return PlannedAction(
                ManageActionKind.BREAK_EVEN,
                (
                    f"Break-even already protected at {r}R "
                    f"(candidate {new_sl} does not improve "
                    f"{position.current_stop}) — advance BE_MOVED "
                    f"class={trade_class}"
                ),
                new_sl=None,
                new_tp=preserved_tp,
                target_state=PositionLifecycleState.BE_MOVED,
            )
        return PlannedAction(
            ManageActionKind.BREAK_EVEN,
            (
                f"Break-even at {r}R (+{profile.break_even_offset_r}R offset) "
                f"class={trade_class} trigger={be_at}R"
            ),
            new_sl=new_sl,
            new_tp=preserved_tp,
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

    # Second scale-out rung (optional) — after first partial, still in PARTIAL
    if (
        position.state is PositionLifecycleState.PARTIAL
        and position.partial_done
        and not bool(getattr(position, "second_partial_done", False))
        and bool(getattr(config, "second_partial_enabled", False))
        and r >= Decimal(str(getattr(config, "second_partial_at_r", "3.0") or "3.0"))
    ):
        pct = Decimal(
            str(getattr(config, "second_partial_close_pct", "25") or "25")
        )
        # Reuse partial_close_volume math with temporary pct via remaining * pct/100
        vol = (position.remaining_volume * pct / Decimal("100")).quantize(
            config.volume_step
        )
        if vol >= config.min_volume:
            return PlannedAction(
                ManageActionKind.PARTIAL_CLOSE,
                f"Second partial {pct}% at {r}R (scale-out)",
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
        if not (
            config.atr_trail_enabled
            or config.structure_trail_enabled
            or config.liquidity_trail_enabled
        ):
            return PlannedAction(
                ManageActionKind.NOOP,
                "Trailing disabled by config",
            )
        trail_sl, trail_reason = _pick_trail_stop(
            position, context, config, regime_label=regime.value
        )
        if trail_sl is None:
            return PlannedAction(
                ManageActionKind.NOOP,
                f"Trail would not improve SL ({trail_reason})",
            )
        return PlannedAction(
            ManageActionKind.TRAIL,
            f"{trail_reason} at {r}R",
            new_sl=trail_sl,
            new_tp=position.current_tp if position.current_tp > 0 else None,
            target_state=PositionLifecycleState.TRAILING,
        )

    return PlannedAction(
        ManageActionKind.NOOP, f"No action (R={r}, state={position.state.value})"
    )
