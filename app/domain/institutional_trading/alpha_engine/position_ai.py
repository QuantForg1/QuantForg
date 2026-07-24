"""AI-driven adaptive profit / exposure management for open positions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.institutional_trading.alpha_engine.config import (
    DEFAULT_ALPHA_CONFIG,
    InstitutionalAlphaConfig,
)
from app.domain.institutional_trading.management.config import PositionManagementConfig
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    PositionLifecycleState,
    PositionManageContext,
)
from app.domain.institutional_trading.management.policies import PlannedAction
from app.domain.institutional_trading.management.r_math import (
    is_stop_improvement,
    partial_close_volume,
    signed_r,
    trail_distance,
    trail_stop_price,
    volatility_regime,
)


@dataclass(frozen=True, slots=True)
class AiManageHints:
    """Live AI re-evaluation inputs for an open position."""

    entry_confidence: int
    current_confidence: int
    momentum: int = 50
    volatility: int = 50
    liquidity: int = 50
    trend_strength: int = 50

    def to_dict(self) -> dict[str, object]:
        return {
            "entry_confidence": self.entry_confidence,
            "current_confidence": self.current_confidence,
            "momentum": self.momentum,
            "volatility": self.volatility,
            "liquidity": self.liquidity,
            "trend_strength": self.trend_strength,
            "confidence_delta": self.current_confidence - self.entry_confidence,
        }


def plan_ai_position_action(
    position: ManagedPosition,
    context: PositionManageContext,
    *,
    hints: AiManageHints,
    pme_config: PositionManagementConfig,
    alpha: InstitutionalAlphaConfig | None = None,
) -> PlannedAction | None:
    """Return an AI-driven PlannedAction or None to fall through to default PME."""
    cfg = alpha or DEFAULT_ALPHA_CONFIG
    drop = hints.entry_confidence - hints.current_confidence
    r = signed_r(position, context.current_price)

    # Significant confidence collapse → exit
    if drop >= cfg.confidence_drop_exit and hints.current_confidence < cfg.let_profits_run_min_confidence:
        return PlannedAction(
            ManageActionKind.EMERGENCY_EXIT,
            (
                f"AI confidence drop {drop} "
                f"({hints.entry_confidence}→{hints.current_confidence}) — exit"
            ),
            volume=position.remaining_volume,
            target_state=PositionLifecycleState.EXITED,
        )

    # Moderate drop → reduce exposure once
    if (
        drop >= cfg.confidence_drop_reduce
        and not position.partial_done
        and position.remaining_volume > pme_config.min_volume
    ):
        # Reuse partial sizing helper with temporary pct override via volume calc
        vol = (position.remaining_volume * (cfg.reduce_pct / Decimal("100"))).quantize(
            pme_config.volume_step
        )
        if vol < pme_config.min_volume:
            vol = pme_config.min_volume
        if vol >= position.remaining_volume:
            vol = position.remaining_volume - pme_config.min_volume
        if vol >= pme_config.min_volume:
            return PlannedAction(
                ManageActionKind.PARTIAL_CLOSE,
                (
                    f"AI confidence drop {drop} — reduce {cfg.reduce_pct}% "
                    f"(mom={hints.momentum} trend={hints.trend_strength})"
                ),
                volume=vol,
                target_state=PositionLifecycleState.PARTIAL,
            )

    # Adaptive trailing: let profits run while confidence high; tighten when weak
    mid = context.mid_price or context.current_price
    regime = volatility_regime(context.atr, mid, pme_config)
    if r >= pme_config.trail_after_r and position.state in {
        PositionLifecycleState.BE_MOVED,
        PositionLifecycleState.PARTIAL,
        PositionLifecycleState.TRAILING,
        PositionLifecycleState.OPEN,
    }:
        if hints.current_confidence >= cfg.let_profits_run_min_confidence:
            # Wider trail — let profits run
            dist = context.atr * cfg.trail_atr_mult_strong
            reason = (
                f"AI let-profits-run trail (conf={hints.current_confidence}) "
                f"dist={dist} at {r}R"
            )
        elif hints.current_confidence <= cfg.tighten_trail_confidence:
            dist = context.atr * cfg.trail_atr_mult_weak
            reason = (
                f"AI tighten trail (conf={hints.current_confidence}) "
                f"dist={dist} at {r}R"
            )
        else:
            dist = trail_distance(context.atr, regime, pme_config)
            reason = f"AI ATR trail ({regime.value}) dist={dist} at {r}R"

        new_sl = trail_stop_price(position, context.current_price, dist)
        if is_stop_improvement(position, new_sl):
            return PlannedAction(
                ManageActionKind.TRAIL,
                reason,
                new_sl=new_sl,
                new_tp=position.current_tp if position.current_tp > 0 else None,
                target_state=PositionLifecycleState.TRAILING,
            )

    _ = partial_close_volume  # available for future AI partial ladders
    return None
