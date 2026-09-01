"""Shadow aggressive compounding — auditable advice, zero live mutation."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    may_add_scalping_trade,
)
from app.domain.institutional_trading.ai_scalping.opportunity_ranking import (
    compute_opportunity_score,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.compounding.models import (
    BROKER_MIN_LOT,
    HARD_MAX_RISK_PCT,
    LIVE_ACTIVATION,
    CompoundingInputs,
    CompoundingMode,
    CompoundingObservation,
    ConvictionResult,
    CountPlan,
    DrawdownState,
    ScaleInAdvice,
    SizingAdvice,
)
from app.domain.institutional_trading.operations.position_plan import (
    class_position_cap,
    margin_allowed_count,
    remaining_quantforg_capacity,
    risk_allowed_count_from_lots,
    split_aggregate_lots,
    strategy_target_count,
)
from app.domain.trading.xauusd_specs import VOLUME_STEP

# Must match dynamic_sizing_v2._QUALITY_RISK_SCALE — never above 1.0 (Risk cap).
_QUALITY_RISK_SCALE = {
    "weak": Decimal("0"),
    "average": Decimal("0.55"),
    "high": Decimal("1.00"),
    "exceptional": Decimal("1.00"),
}

_PCT = Decimal("100")


def _dec(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except Exception:
        return Decimal(default)


def _clamp_int(n: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(n)))


def classify_drawdown(inputs: CompoundingInputs) -> tuple[DrawdownState, tuple[str, ...]]:
    """Reuse ITE daily-loss / weekly-drawdown ceilings. Do not invent live limits."""
    notes: list[str] = []
    max_daily = _dec(
        inputs.max_daily_loss_pct, str(DEFAULT_ITE_CONFIG.max_daily_loss_pct)
    )
    max_week = _dec(
        inputs.max_weekly_drawdown_pct,
        str(DEFAULT_ITE_CONFIG.max_weekly_drawdown_pct),
    )
    daily = inputs.daily_loss_pct
    if daily is None and inputs.equity and inputs.daily_pnl is not None:
        if inputs.equity > 0 and inputs.daily_pnl < 0:
            daily = (abs(inputs.daily_pnl) / inputs.equity * _PCT)
        else:
            daily = Decimal("0")
    if daily is None:
        notes.append("drawdown_inputs_unknown")
        return "CAUTION", tuple(notes)

    weekly = Decimal("0")
    if inputs.peak_equity and inputs.equity and inputs.peak_equity > 0:
        if inputs.equity < inputs.peak_equity:
            weekly = (
                (inputs.peak_equity - inputs.equity) / inputs.peak_equity * _PCT
            )

    if daily >= max_daily or weekly >= max_week:
        notes.append(
            f"CAPITAL_PRESERVATION daily_loss={daily}% "
            f"max_daily={max_daily}% peak_dd={weekly}% max_week={max_week}%"
        )
        return "CAPITAL_PRESERVATION", tuple(notes)
    if daily >= (max_daily * Decimal("0.50")):
        notes.append(f"DEFENSIVE daily_loss={daily}% >= 50% of {max_daily}%")
        return "DEFENSIVE", tuple(notes)
    if daily >= (max_daily * Decimal("0.25")):
        notes.append(f"CAUTION daily_loss={daily}% >= 25% of {max_daily}%")
        return "CAUTION", tuple(notes)
    notes.append(f"GREEN daily_loss={daily}%")
    return "GREEN", tuple(notes)


def compute_conviction(inputs: CompoundingInputs) -> ConvictionResult:
    """Conviction = existing Probability Center score minus auditable penalties."""
    score_row = dict(inputs.score or {})
    if inputs.quality is not None and "trade_quality" not in score_row:
        score_row["trade_quality"] = inputs.quality
    if inputs.confidence is not None and "ai_confidence" not in score_row:
        score_row["ai_confidence"] = inputs.confidence
    if inputs.expected_rr is not None and "expected_rr" not in score_row:
        score_row["expected_rr"] = str(inputs.expected_rr)
    if inputs.news_blocked:
        score_row["news_blocked"] = True

    opp = compute_opportunity_score(score_row)
    base = int(opp.get("opportunity_score") or 0)
    components = dict(opp.get("components") or {})
    reasons: list[str] = []
    penalties: list[str] = []
    deduct = 0

    for key, label in (
        ("structure_quality", "structure/BOS/CHOCH"),
        ("fvg_quality", "FVG"),
        ("order_block_quality", "order_block"),
        ("liquidity", "liquidity_sweep"),
        ("trend_strength", "momentum"),
        ("mtf_alignment", "multi_timeframe"),
        ("session_quality", "session"),
        ("spread_quality", "spread/liquidity"),
        ("risk_reward", "expected_R"),
        ("ai_quality", "signal_quality"),
        ("confidence", "strategy_confidence"),
    ):
        val = int(components.get(key) or 0)
        if val >= 70:
            reasons.append(f"{label}={val}")

    dd_state, _dd_notes = classify_drawdown(inputs)
    if dd_state == "CAPITAL_PRESERVATION":
        deduct += 40
        penalties.append("drawdown_capital_preservation-40")
    elif dd_state == "DEFENSIVE":
        deduct += 20
        penalties.append("drawdown_defensive-20")
    elif dd_state == "CAUTION":
        deduct += 8
        penalties.append("drawdown_caution-8")

    if inputs.exposure_pct is not None and inputs.exposure_pct >= Decimal("8"):
        deduct += 10
        penalties.append(f"portfolio_exposure={inputs.exposure_pct}-10")
    if inputs.news_blocked:
        deduct += 20
        penalties.append("news_blocked-20")
    spread_q = int(components.get("spread_quality") or 50)
    if spread_q < 40:
        deduct += 10
        penalties.append(f"spread_quality={spread_q}-10")
    if not inputs.candidate_allowed or inputs.same_symbol_blocked:
        deduct += 15
        penalties.append("same_symbol_or_capacity_blocked-15")

    conviction = _clamp_int(base - deduct)
    conf = int(inputs.confidence if inputs.confidence is not None else components.get("confidence") or 0)
    conf = _clamp_int(conf)
    adjusted = _clamp_int(round(0.55 * conviction + 0.45 * conf))

    if conviction >= 90:
        regime = "exceptional"
    elif conviction >= 80:
        regime = "strong"
    elif conviction >= 70:
        regime = "normal"
    elif conviction >= 40:
        regime = "weak"
    else:
        regime = "blocked"

    if not reasons:
        reasons.append(f"opportunity_score={base}")

    return ConvictionResult(
        conviction_score=conviction,
        confidence_adjusted_score=adjusted,
        conviction_regime=regime,
        conviction_reasons=tuple(reasons),
        conviction_penalties=tuple(penalties),
        opportunity_score=base,
        components=components,
    )


def select_mode(
    *,
    conviction: ConvictionResult,
    drawdown_state: DrawdownState,
    drawdown_known: bool,
) -> CompoundingMode:
    """Observational mode. Never raises live risk. Unknown drawdown cannot attack."""
    if drawdown_state == "CAPITAL_PRESERVATION":
        return "DEFENSIVE"
    if drawdown_state == "DEFENSIVE":
        return "DEFENSIVE"
    if not drawdown_known:
        return "NORMAL"
    score = conviction.conviction_score
    adj = conviction.confidence_adjusted_score
    if (
        drawdown_state == "GREEN"
        and score >= 95
        and adj >= 90
        and conviction.conviction_regime == "exceptional"
    ):
        return "CAPITAL_ATTACK"
    if drawdown_state == "GREEN" and score >= 90:
        return "HIGH_CONVICTION"
    if drawdown_state in {"GREEN", "CAUTION"} and score >= 80:
        return "AGGRESSIVE"
    if score < 60:
        return "DEFENSIVE"
    return "NORMAL"


def _mode_count_cap(mode: CompoundingMode, class_cap: int) -> int:
    if mode == "DEFENSIVE":
        return max(0, min(1, class_cap))
    if mode == "NORMAL":
        return max(0, min(class_cap, 5 if class_cap >= 5 else class_cap))
    return max(0, class_cap)


def compute_counts(
    inputs: CompoundingInputs,
    *,
    conviction: ConvictionResult,
    mode: CompoundingMode,
    suggested_aggregate: Decimal,
) -> CountPlan:
    trade_class = inputs.trade_class or "SCALP"
    class_cap = class_position_cap(trade_class)
    target = strategy_target_count(
        trade_class=trade_class,
        opportunity_score=conviction.opportunity_score,
        confidence=conviction.confidence_adjusted_score,
    )
    conviction_n = strategy_target_count(
        trade_class=trade_class,
        opportunity_score=conviction.conviction_score,
        confidence=conviction.confidence_adjusted_score,
    )
    mode_cap = _mode_count_cap(mode, class_cap)
    min_lot = inputs.min_lot if inputs.min_lot > 0 else BROKER_MIN_LOT
    risk_n = risk_allowed_count_from_lots(
        aggregate_lots=suggested_aggregate,
        min_lot=min_lot,
        cap=class_cap,
    )
    configured = max(0, int(inputs.configured_max_open))
    remaining = (
        int(inputs.remaining_capacity)
        if inputs.remaining_capacity is not None
        else remaining_quantforg_capacity(
            current_count=int(inputs.quantforg_open_count),
            configured_max=configured,
            class_cap=class_cap,
        )
    )
    portfolio_n = remaining
    broker_n = class_cap
    if inputs.max_lot is not None and inputs.max_lot > 0 and min_lot > 0:
        broker_n = min(class_cap, max(0, int(inputs.max_lot // min_lot)))

    _, per_leg = split_aggregate_lots(
        aggregate_lots=suggested_aggregate,
        count=max(1, min(target, conviction_n, risk_n, remaining, mode_cap) or 1),
        min_lot=min_lot,
        lot_step=inputs.lot_step or VOLUME_STEP,
        max_lot=inputs.max_lot or suggested_aggregate,
    )
    margin_n = margin_allowed_count(
        free_margin=inputs.free_margin,
        per_position_lots=per_leg if per_leg > 0 else min_lot,
        margin_per_lot=inputs.margin_per_lot,
        requested=class_cap,
    )

    reductions: list[str] = []
    effective = min(
        target,
        conviction_n,
        risk_n,
        portfolio_n,
        margin_n,
        broker_n,
        remaining,
        mode_cap,
    )
    if configured > 0 and remaining <= 0:
        effective = 0
        reductions.append("max_open_trades_is_cap_not_permission")
    if risk_n < target:
        reductions.append("risk_allowed_count")
    if conviction_n < target:
        reductions.append("conviction_count")
    if mode_cap < target:
        reductions.append(f"mode_cap={mode}")
    if remaining < target:
        reductions.append("remaining_capacity")
    if effective < 0:
        effective = 0

    return CountPlan(
        strategy_target_count=target,
        conviction_count=conviction_n,
        risk_allowed_count=risk_n,
        portfolio_allowed_count=portfolio_n,
        margin_allowed_count=margin_n,
        broker_allowed_count=broker_n,
        remaining_capacity=remaining,
        mode_count_cap=mode_cap,
        effective_count=effective,
        reductions=tuple(reductions),
    )


def _quality_band(conviction: int) -> str:
    if conviction < 70:
        return "weak"
    if conviction < 80:
        return "average"
    if conviction < 90:
        return "high"
    return "exceptional"


def compute_sizing(
    inputs: CompoundingInputs,
    *,
    conviction: ConvictionResult,
    effective_count: int,
) -> SizingAdvice:
    approved = inputs.risk_approved_volume
    if approved is None:
        approved = Decimal("0")
    if approved < 0:
        approved = Decimal("0")
    band = _quality_band(conviction.conviction_score)
    mult = _QUALITY_RISK_SCALE[band]  # type: ignore[index]
    # Never exceed Risk-approved volume. Aggressive = use more of the
    # already-approved budget, not a higher cap.
    suggested = (approved * mult).quantize(VOLUME_STEP)
    if suggested > approved:
        suggested = approved
    capped = suggested < approved and band != "exceptional"
    n = max(0, int(effective_count))
    per_leg = Decimal("0")
    if n > 0 and suggested > 0:
        n2, per_leg = split_aggregate_lots(
            aggregate_lots=suggested,
            count=n,
            min_lot=inputs.min_lot or BROKER_MIN_LOT,
            lot_step=inputs.lot_step or VOLUME_STEP,
        )
        if n2 <= 0:
            per_leg = Decimal("0")
    return SizingAdvice(
        quality_multiplier=mult,
        risk_approved_volume=approved,
        suggested_volume=suggested,
        per_leg_volume=per_leg,
        approved_aggregate_volume=suggested,
        capped_by_risk=capped or suggested <= approved,
    )


def compute_scale_in(inputs: CompoundingInputs) -> ScaleInAdvice:
    """Winner-only. Live sequential add-on stays OFF unless already authorized."""
    live_on = bool(inputs.sequential_scale_in_live_enabled)
    # Scanner still blocks QUANTFORG_SAME_SYMBOL_OPEN; live pyramid is not
    # auto-enabled by this shadow layer.
    if inputs.same_symbol_blocked or not inputs.candidate_allowed:
        shadow = may_add_scalping_trade(
            open_positions=max(1, int(inputs.quantforg_open_count or inputs.open_positions)),
            max_open=max(1, int(inputs.configured_max_open)),
            new_confidence=int(inputs.confidence or 0),
            best_open_confidence=None,
            new_direction=str(inputs.direction or ""),
            open_directions=inputs.open_directions,
            entry=inputs.entry,
            open_entries=inputs.open_entries,
            require_improvement=False,
            min_confidence_delta=0,
            open_profits=inputs.open_profits,
            require_unrealized_profit=True,
            same_direction_profits=inputs.open_profits,
        )
        reason = "SCANNER_SAME_SYMBOL_BLOCKS_BEFORE_PYRAMID"
        if not shadow.allow:
            reason = shadow.reason
        return ScaleInAdvice(
            scale_in_allowed=False,
            scale_in_live_enabled=False,
            shadow_eligible=bool(shadow.allow) and not live_on,
            scale_in_block_reason=reason
            if not shadow.allow
            else "SEQUENTIAL_SCALE_IN_LIVE_DISABLED",
            winners_only=True,
        )

    if int(inputs.quantforg_open_count or inputs.open_positions) <= 0:
        return ScaleInAdvice(
            scale_in_allowed=False,
            scale_in_live_enabled=False,
            shadow_eligible=False,
            scale_in_block_reason="NO_OPEN_LEG_TO_SCALE",
            winners_only=True,
        )

    decision = may_add_scalping_trade(
        open_positions=int(inputs.quantforg_open_count or inputs.open_positions),
        max_open=max(1, int(inputs.configured_max_open)),
        new_confidence=int(inputs.confidence or 0),
        best_open_confidence=None,
        new_direction=str(inputs.direction or ""),
        open_directions=inputs.open_directions,
        entry=inputs.entry,
        open_entries=inputs.open_entries,
        require_improvement=False,
        min_confidence_delta=0,
        open_profits=inputs.open_profits,
        require_unrealized_profit=True,
        same_direction_profits=inputs.open_profits,
    )
    if live_on:
        # Even if a caller sets the flag, this shadow engine will not flip
        # live authorization. Explicit second approval is required.
        return ScaleInAdvice(
            scale_in_allowed=False,
            scale_in_live_enabled=False,
            shadow_eligible=bool(decision.allow),
            scale_in_block_reason="SEQUENTIAL_SCALE_IN_LIVE_DISABLED",
            winners_only=True,
        )
    return ScaleInAdvice(
        scale_in_allowed=False,
        scale_in_live_enabled=False,
        shadow_eligible=bool(decision.allow),
        scale_in_block_reason=(
            decision.reason
            if not decision.allow
            else "SEQUENTIAL_SCALE_IN_LIVE_DISABLED"
        ),
        winners_only=True,
    )


def compounding_bias(
    *,
    drawdown_state: DrawdownState,
    daily_pnl: Decimal | None,
) -> str:
    if drawdown_state in {"DEFENSIVE", "CAPITAL_PRESERVATION"}:
        return "DE_RISK"
    if daily_pnl is not None and daily_pnl < 0:
        return "DE_RISK"
    if daily_pnl is not None and daily_pnl > 0 and drawdown_state == "GREEN":
        return "SCALE_UP_WITHIN_RISK"
    return "HOLD_CAPACITY"


def evaluate_compounding_shadow(inputs: CompoundingInputs) -> CompoundingObservation:
    """Pure function. Callers must not feed this into OMS."""
    dd_state, dd_notes = classify_drawdown(inputs)
    drawdown_known = "drawdown_inputs_unknown" not in dd_notes
    conviction = compute_conviction(inputs)
    mode = select_mode(
        conviction=conviction,
        drawdown_state=dd_state,
        drawdown_known=drawdown_known,
    )
    approved = inputs.risk_approved_volume or Decimal("0")
    if approved < 0:
        approved = Decimal("0")
    band = _quality_band(conviction.conviction_score)
    preview = (approved * _QUALITY_RISK_SCALE[band]).quantize(VOLUME_STEP)  # type: ignore[index]
    if preview > approved:
        preview = approved
    counts = compute_counts(
        inputs,
        conviction=conviction,
        mode=mode,
        suggested_aggregate=preview,
    )
    sizing = compute_sizing(
        inputs, conviction=conviction, effective_count=counts.effective_count
    )
    assert sizing.suggested_volume <= sizing.risk_approved_volume
    scale = compute_scale_in(inputs)
    notes = (
        "SHADOW_ONLY_NO_LIVE_MUTATION",
        "RISK_REMAINS_AUTHORITATIVE",
        f"HARD_MAX_RISK_PCT={HARD_MAX_RISK_PCT}",
        "BROKER_MIN_LOT=0.01",
        *dd_notes,
    )
    return CompoundingObservation(
        live_activation=LIVE_ACTIVATION,
        mutates_engines=False,
        mode=mode,
        drawdown_state=dd_state,
        compounding_bias=compounding_bias(
            drawdown_state=dd_state, daily_pnl=inputs.daily_pnl
        ),
        conviction=conviction,
        counts=counts,
        sizing=sizing,
        scale_in=scale,
        equity=str(inputs.equity) if inputs.equity is not None else None,
        risk_budget_pct=str(DEFAULT_ITE_CONFIG.risk_per_trade_pct),
        portfolio_exposure_pct=(
            str(inputs.exposure_pct) if inputs.exposure_pct is not None else None
        ),
        expected_r=str(inputs.expected_rr) if inputs.expected_rr is not None else None,
        signal_quality=inputs.quality,
        signal_confidence=inputs.confidence,
        min_lot_classification=inputs.min_lot_classification,
        live_hard_max_risk_pct=str(HARD_MAX_RISK_PCT),
        live_min_lot=str(BROKER_MIN_LOT),
        cycle_id=inputs.cycle_id,
        notes=notes,
    )
