"""Institutional Dynamic Position Sizing Engine v2.

Grows position size smoothly with equity using preferred lot-range targets,
while sizing every trade from live account/broker/risk/quality inputs.

Hard safety contracts:
- Never force trades
- Never force broker minimum lot (below_min_lot → reject)
- Never exceed configured maximum risk %
- Never weaken AI / spread / volatility / liquidity gates
- No fixed lot sizes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.ai_scalping.sizing import (
    LotSizingResult,
    _quantize_lot,
)
from app.domain.trading.xauusd_specs import (
    CONTRACT_SIZE,
    VOLUME_MAX,
    VOLUME_MIN,
    VOLUME_STEP,
    margin_required,
)
from core.logging import get_logger

logger = get_logger(__name__)

QualityBand = Literal["weak", "average", "high", "exceptional"]

# Equity → preferred lot range anchors (smooth interpolation between points)
_EQUITY_TIER_ANCHORS: tuple[tuple[Decimal, Decimal, Decimal], ...] = (
    (Decimal("50"), Decimal("0.01"), Decimal("0.01")),
    (Decimal("100"), Decimal("0.02"), Decimal("0.03")),
    (Decimal("400"), Decimal("0.05"), Decimal("0.10")),
    (Decimal("1000"), Decimal("0.20"), Decimal("0.50")),
    (Decimal("5000"), Decimal("0.50"), Decimal("1.00")),
)

# Quality → risk allocation vs configured max (never > 1.0)
_QUALITY_RISK_SCALE: dict[QualityBand, Decimal] = {
    "weak": Decimal("0"),
    "average": Decimal("0.55"),
    "high": Decimal("1.00"),
    "exceptional": Decimal("1.00"),  # max configured only — never above ceiling
}


@dataclass(frozen=True, slots=True)
class EquityTierPreference:
    equity: Decimal
    preferred_lot_lo: Decimal
    preferred_lot_hi: Decimal
    tier_label: str

    def to_dict(self) -> dict[str, object]:
        return {
            "equity": str(self.equity),
            "preferred_lot_lo": str(self.preferred_lot_lo),
            "preferred_lot_hi": str(self.preferred_lot_hi),
            "tier_label": self.tier_label,
        }


@dataclass(frozen=True, slots=True)
class DynamicSizingDecision:
    """Full audit record for every sizing decision."""

    valid: bool
    method: str
    reason: str
    balance: Decimal
    equity: Decimal
    free_margin: Decimal | None
    suggested_lot: Decimal
    calculated_lot: Decimal
    final_lot: Decimal
    stop_loss_distance: Decimal
    risk_pct: Decimal
    configured_max_risk_pct: Decimal
    quality_score: int | None
    quality_band: QualityBand
    quality_risk_scale: Decimal
    equity_tier: EquityTierPreference
    broker_min_lot: Decimal
    broker_lot_step: Decimal
    broker_max_lot: Decimal
    contract_size: Decimal
    margin_required: Decimal | None = None
    margin_usage_pct: Decimal | None = None
    portfolio_exposure_pct: Decimal | None = None
    symbol_exposure_pct: Decimal | None = None
    session_risk_multiplier: Decimal | None = None
    volatility_scale: Decimal | None = None
    liquidity_score: int | None = None
    spread_score: int | None = None
    trend_confidence: int | None = None
    rejection_reason: str | None = None
    extras: dict[str, object] = field(default_factory=dict)

    def to_lot_result(self) -> LotSizingResult:
        return LotSizingResult(
            lots=self.final_lot if self.valid else Decimal("0"),
            risk_amount=(
                (self.equity * self.risk_pct / Decimal("100")).quantize(Decimal("0.01"))
                if self.equity > 0 and self.risk_pct > 0
                else Decimal("0")
            ),
            stop_distance=self.stop_loss_distance,
            method=self.method,
            reason=self.rejection_reason or self.reason,
            valid=self.valid,
            calculated_lot=self.calculated_lot,
            broker_min_lot=self.broker_min_lot,
            account_balance=self.balance if self.balance > 0 else self.equity,
            risk_percentage=self.risk_pct,
        )

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "engine": "dynamic_sizing_v2",
            "valid": self.valid,
            "method": self.method,
            "reason": self.reason,
            "balance": str(self.balance),
            "equity": str(self.equity),
            "free_margin": (
                str(self.free_margin) if self.free_margin is not None else None
            ),
            "suggested_lot": str(self.suggested_lot),
            "calculated_lot": str(self.calculated_lot),
            "final_lot": str(self.final_lot),
            "stop_loss_distance": str(self.stop_loss_distance),
            "risk_pct": str(self.risk_pct),
            "risk_percentage": str(self.risk_pct),
            "configured_max_risk_pct": str(self.configured_max_risk_pct),
            "quality_score": self.quality_score,
            "quality_band": self.quality_band,
            "quality_risk_scale": str(self.quality_risk_scale),
            "equity_tier": self.equity_tier.to_dict(),
            "broker_min_lot": str(self.broker_min_lot),
            "broker_minimum": str(self.broker_min_lot),
            "broker_lot_step": str(self.broker_lot_step),
            "broker_max_lot": str(self.broker_max_lot),
            "contract_size": str(self.contract_size),
            "margin_required": (
                str(self.margin_required) if self.margin_required is not None else None
            ),
            "margin_usage_pct": (
                str(self.margin_usage_pct)
                if self.margin_usage_pct is not None
                else None
            ),
            "portfolio_exposure_pct": (
                str(self.portfolio_exposure_pct)
                if self.portfolio_exposure_pct is not None
                else None
            ),
            "symbol_exposure_pct": (
                str(self.symbol_exposure_pct)
                if self.symbol_exposure_pct is not None
                else None
            ),
            "session_risk_multiplier": (
                str(self.session_risk_multiplier)
                if self.session_risk_multiplier is not None
                else None
            ),
            "volatility_scale": (
                str(self.volatility_scale)
                if self.volatility_scale is not None
                else None
            ),
            "liquidity_score": self.liquidity_score,
            "spread_score": self.spread_score,
            "trend_confidence": self.trend_confidence,
            "rejection_reason": self.rejection_reason,
            "account_balance": str(self.balance if self.balance > 0 else self.equity),
        }
        if self.extras:
            payload["extras"] = dict(self.extras)
        return payload


def interpolate_equity_tier(equity: Decimal) -> EquityTierPreference:
    """Smooth preferred lot range from equity — no abrupt tier jumps."""
    eq = max(Decimal("0"), equity)
    anchors = _EQUITY_TIER_ANCHORS
    if eq <= anchors[0][0]:
        lo, hi = anchors[0][1], anchors[0][2]
        return EquityTierPreference(eq, lo, hi, f"eq<={anchors[0][0]}")
    if eq >= anchors[-1][0]:
        lo, hi = anchors[-1][1], anchors[-1][2]
        return EquityTierPreference(eq, lo, hi, f"eq>={anchors[-1][0]}")

    for i in range(len(anchors) - 1):
        e0, lo0, hi0 = anchors[i]
        e1, lo1, hi1 = anchors[i + 1]
        if e0 <= eq <= e1:
            # Smoothstep blend for gradual growth
            t = (eq - e0) / (e1 - e0)
            t_smooth = t * t * (Decimal("3") - Decimal("2") * t)
            lo = lo0 + (lo1 - lo0) * t_smooth
            hi = hi0 + (hi1 - hi0) * t_smooth
            lo = lo.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            hi = hi.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            return EquityTierPreference(eq, lo, hi, f"eq:{e0}-{e1}")
    lo, hi = anchors[-1][1], anchors[-1][2]
    return EquityTierPreference(eq, lo, hi, "eq:fallback")


def classify_quality_band(
    *,
    reject: bool,
    quality_score: int | None,
    confidence: int | None,
    min_quality: int,
    min_confidence: int,
    exceptional_quality: int = 92,
    exceptional_confidence: int = 90,
) -> QualityBand:
    """Map setup quality to risk allocation band (weak → reject)."""
    if reject:
        return "weak"
    q = int(quality_score) if quality_score is not None else 0
    c = int(confidence) if confidence is not None else 0
    if q < min_quality or c < min_confidence:
        return "weak"
    if q >= exceptional_quality and c >= exceptional_confidence:
        return "exceptional"
    # Average: passed floors but not strong
    mid_q = (min_quality + exceptional_quality) // 2
    mid_c = (min_confidence + exceptional_confidence) // 2
    if q < mid_q or c < mid_c:
        return "average"
    return "high"


def _clamp01(value: Decimal) -> Decimal:
    if value < 0:
        return Decimal("0")
    if value > 1:
        return Decimal("1")
    return value


def _dampen_lot_growth(
    *,
    candidate: Decimal,
    previous_lot: Decimal | None,
    max_step_pct: Decimal,
) -> Decimal:
    """Prevent abrupt lot jumps vs last sized trade (growth smooth only)."""
    if previous_lot is None or previous_lot <= 0 or candidate <= 0:
        return candidate
    if candidate <= previous_lot:
        return candidate
    # Cap increase to max_step_pct of previous (e.g. 35% per trade)
    cap = previous_lot * (Decimal("1") + max(Decimal("0"), max_step_pct))
    return min(candidate, cap)


def calculate_dynamic_lots_v2(
    *,
    equity: Decimal,
    stop_distance: Decimal | None,
    balance: Decimal | None = None,
    free_margin: Decimal | None = None,
    atr: Decimal | None = None,
    mid_price: Decimal | None = None,
    leverage: Decimal | None = None,
    risk_pct: Decimal | None = None,
    contract_size: Decimal | None = None,
    min_lot: Decimal | None = None,
    lot_step: Decimal | None = None,
    max_lot: Decimal | None = None,
    session_risk_multiplier: Decimal | None = None,
    daily_exposure_used_pct: Decimal = Decimal("0"),
    portfolio_exposure_pct: Decimal | None = None,
    symbol_open_risk_pct: Decimal | None = None,
    quality_score: int | None = None,
    confidence: int | None = None,
    liquidity_score: int | None = None,
    spread_score: int | None = None,
    trend_confidence: int | None = None,
    quality_reject: bool = False,
    previous_final_lot: Decimal | None = None,
    max_margin_usage_pct: Decimal = Decimal("30"),
    max_symbol_exposure_pct: Decimal | None = None,
    lot_growth_max_step_pct: Decimal | None = None,
    config: AiScalpingConfig | None = None,
    log: bool = True,
) -> DynamicSizingDecision:
    """Institutional dynamic lot sizing — quality-weighted, equity-tier aware."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    bal = balance if balance is not None and balance > 0 else equity
    configured_max = (
        risk_pct if risk_pct is not None and risk_pct > 0 else cfg.risk_per_trade_pct
    )
    # Never exceed configured ceiling (also respect config hard lock 0.75)
    hard_ceiling = min(configured_max, Decimal("0.75"))
    if configured_max > hard_ceiling:
        configured_max = hard_ceiling

    broker_min = min_lot if min_lot is not None and min_lot > 0 else cfg.broker_min_lot
    broker_step = (
        lot_step if lot_step is not None and lot_step > 0 else cfg.broker_lot_step
    )
    broker_max = (
        max_lot
        if max_lot is not None and max_lot > 0
        else min(cfg.broker_max_lot, VOLUME_MAX)
    )
    cs = (
        contract_size
        if contract_size is not None and contract_size > 0
        else CONTRACT_SIZE
    )
    tier = interpolate_equity_tier(equity)

    try:
        min_q = int(cfg.normal_vol.quality)
        min_c = int(cfg.normal_vol.confidence)
    except Exception:
        min_q, min_c = 80, 80

    band = classify_quality_band(
        reject=bool(quality_reject),
        quality_score=quality_score,
        confidence=confidence if confidence is not None else trend_confidence,
        min_quality=min_q,
        min_confidence=min_c,
    )
    q_scale = _QUALITY_RISK_SCALE[band]

    def _reject(
        method: str,
        reason: str,
        *,
        calculated: Decimal = Decimal("0"),
        suggested: Decimal = Decimal("0"),
        risk: Decimal = Decimal("0"),
        dist: Decimal | None = None,
    ) -> DynamicSizingDecision:
        decision = DynamicSizingDecision(
            valid=False,
            method=method,
            reason=reason,
            balance=bal,
            equity=equity,
            free_margin=free_margin,
            suggested_lot=suggested,
            calculated_lot=calculated,
            final_lot=Decimal("0"),
            stop_loss_distance=dist or (stop_distance or Decimal("0")),
            risk_pct=risk,
            configured_max_risk_pct=configured_max,
            quality_score=quality_score,
            quality_band=band,
            quality_risk_scale=q_scale,
            equity_tier=tier,
            broker_min_lot=broker_min,
            broker_lot_step=broker_step,
            broker_max_lot=broker_max,
            contract_size=cs,
            portfolio_exposure_pct=portfolio_exposure_pct,
            symbol_exposure_pct=symbol_open_risk_pct,
            session_risk_multiplier=session_risk_multiplier,
            liquidity_score=liquidity_score,
            spread_score=spread_score,
            trend_confidence=trend_confidence or confidence,
            rejection_reason=reason,
        )
        if log:
            logger.warning(
                "dynamic_sizing_v2_decision",
                **{k: v for k, v in decision.to_dict().items() if k != "extras"},
            )
        return decision

    if cfg.allow_martingale or cfg.allow_grid or cfg.allow_unlimited_averaging:
        return _reject(
            "blocked",
            "Unsafe sizing modes are permanently disabled",
            risk=configured_max,
        )

    if band == "weak" or q_scale <= 0:
        return _reject(
            "quality_weak",
            (
                f"Weak setup — sizing reject "
                f"(quality={quality_score} confidence={confidence})"
            ),
            risk=Decimal("0"),
        )

    # Soft quality scales on liquidity / spread / trend (reduce only)
    soft_scale = Decimal("1")
    if liquidity_score is not None:
        if liquidity_score < 50:
            soft_scale *= Decimal("0.70")
        elif liquidity_score < 70:
            soft_scale *= Decimal("0.85")
    if spread_score is not None:
        if spread_score < 40:
            soft_scale *= Decimal("0.65")
        elif spread_score < 70:
            soft_scale *= Decimal("0.85")
    trend_c = trend_confidence if trend_confidence is not None else confidence
    if trend_c is not None:
        if trend_c < 55:
            soft_scale *= Decimal("0.75")
        elif trend_c < 70:
            soft_scale *= Decimal("0.90")
    soft_scale = _clamp01(soft_scale)

    base_risk = (configured_max * q_scale * soft_scale).quantize(Decimal("0.0001"))

    # Daily / portfolio exposure remaining — reduce only
    max_daily = cfg.max_daily_exposure_pct
    if daily_exposure_used_pct >= max_daily:
        return _reject(
            "exposure_cap",
            f"Daily exposure {daily_exposure_used_pct}% at max {max_daily}%",
            risk=base_risk,
        )
    remaining = max_daily - daily_exposure_used_pct
    if remaining < base_risk:
        base_risk = max(Decimal("0"), remaining)

    if portfolio_exposure_pct is not None and portfolio_exposure_pct >= max_daily:
        return _reject(
            "portfolio_exposure_cap",
            (f"Portfolio exposure {portfolio_exposure_pct}% " f"at max {max_daily}%"),
            risk=base_risk,
        )

    sym_cap = (
        max_symbol_exposure_pct
        if max_symbol_exposure_pct is not None
        else configured_max * Decimal("2")
    )
    if symbol_open_risk_pct is not None and symbol_open_risk_pct >= sym_cap > 0:
        return _reject(
            "symbol_exposure_cap",
            (f"Symbol exposure {symbol_open_risk_pct}% " f"at max {sym_cap}%"),
            risk=base_risk,
        )

    vol_scale = Decimal("1")
    method_suffix = "+v2"
    dist = stop_distance
    if dist is None or dist <= 0:
        if atr is not None and atr > 0:
            dist = atr * cfg.stop_atr_mult
        else:
            return _reject(
                "no_stop",
                "Stop distance unavailable — refusing fixed lots",
                risk=base_risk,
            )

    if cfg.volatility_adjusted_sizing and atr is not None and atr > 0 and dist > 0:
        if atr >= dist * Decimal("1.5"):
            vol_scale = min(Decimal("1"), cfg.high_vol_risk_scale)
            method_suffix += "+high_vol_scale"
        elif atr <= dist * Decimal("0.5"):
            vol_scale = min(Decimal("1"), cfg.low_vol_risk_scale)
            method_suffix += "+low_vol_scale"
        base_risk = (base_risk * vol_scale).quantize(Decimal("0.0001"))

    if session_risk_multiplier is not None:
        sess = min(Decimal("1"), max(Decimal("0"), session_risk_multiplier))
        if sess < 1:
            base_risk = (base_risk * sess).quantize(Decimal("0.0001"))
            method_suffix += "+session_risk_scale"

    # Absolute ceiling — never exceed configured max
    if base_risk > configured_max:
        base_risk = configured_max

    if equity <= 0 or base_risk <= 0 or cs <= 0:
        return _reject(
            "invalid_inputs",
            "Equity / risk% / contract size invalid",
            risk=base_risk,
            dist=dist,
        )

    risk_amount = (equity * base_risk / Decimal("100")).quantize(Decimal("0.01"))
    raw = risk_amount / (cs * dist)

    # Equity-tier soft target: high/exceptional may approach preferred_hi,
    # but NEVER above risk-based raw and NEVER force up to preferred_lo.
    suggested = raw
    if band in {"high", "exceptional"} and raw > 0:
        # Blend toward preferred mid only when raw already supports growth
        pref_mid = (tier.preferred_lot_lo + tier.preferred_lot_hi) / Decimal("2")
        if raw >= tier.preferred_lot_lo:
            # Cap at preferred_hi to avoid abrupt oversizing vs equity tier
            suggested = min(raw, tier.preferred_lot_hi)
            method_suffix += "+equity_tier_cap"
        elif raw >= pref_mid * Decimal("0.5"):
            # Gradual approach — keep risk-based raw (no upsize)
            suggested = raw
            method_suffix += "+equity_tier_grow"
    else:
        # Average setups: stay strictly at risk-based, also respect preferred_hi
        suggested = min(raw, tier.preferred_lot_hi)
        method_suffix += "+avg_tier_cap"

    # Smooth growth vs previous lot
    growth_step = (
        lot_growth_max_step_pct
        if lot_growth_max_step_pct is not None
        else getattr(cfg, "lot_growth_max_step_pct", Decimal("0.35"))
    )
    suggested = _dampen_lot_growth(
        candidate=suggested,
        previous_lot=previous_final_lot,
        max_step_pct=growth_step,
    )

    # Broker max cap
    suggested = min(suggested, broker_max)

    # Margin affordability — reduce only
    margin_need: Decimal | None = None
    margin_usage: Decimal | None = None
    if (
        mid_price is not None
        and mid_price > 0
        and free_margin is not None
        and free_margin >= 0
    ):
        lev = leverage if leverage is not None and leverage > 0 else Decimal("1000")
        # Probe margin at suggested lot only — never inflate to broker min
        probe = suggested if suggested > 0 else Decimal("0")
        if probe > 0:
            margin_need = margin_required(
                volume=probe, price=mid_price, leverage=lev, contract_size=cs
            )
            if equity > 0:
                margin_usage = (margin_need / equity * Decimal("100")).quantize(
                    Decimal("0.01")
                )
            if free_margin > 0 and margin_need > free_margin:
                # Scale down to affordable
                afford = (free_margin * lev) / (cs * mid_price)
                suggested = min(suggested, afford)
                method_suffix += "+margin_scale"
                margin_need = margin_required(
                    volume=max(suggested, Decimal("0")),
                    price=mid_price,
                    leverage=lev,
                    contract_size=cs,
                )
            if (
                margin_usage is not None
                and max_margin_usage_pct > 0
                and margin_usage > max_margin_usage_pct
                and suggested > 0
            ):
                # Scale so margin_usage ~= max_margin_usage_pct
                target_margin = equity * max_margin_usage_pct / Decimal("100")
                afford2 = (target_margin * lev) / (cs * mid_price)
                if afford2 < suggested:
                    suggested = afford2
                    method_suffix += "+margin_usage_cap"

    final = _quantize_lot(
        suggested,
        step=broker_step,
        min_lot=broker_min,
        max_lot=broker_max,
    )

    if final <= 0:
        # Micro CONDITIONAL — same hard_max path as percentage-risk sizing.
        try:
            from app.domain.institutional_trading.micro_account_mode import (
                MicroAccountProfile,
            )

            profile = MicroAccountProfile()
            min_loss = (broker_min * cs * dist).quantize(Decimal("0.01"))
            if equity > 0 and min_loss > 0 and equity <= Decimal("500"):
                needed_pct = (min_loss / equity * Decimal("100")).quantize(
                    Decimal("0.01")
                )
                if needed_pct <= profile.hard_max_risk_pct:
                    return DynamicSizingDecision(
                        valid=True,
                        method=f"dynamic_v2_micro_conditional{method_suffix}",
                        reason=(
                            f"micro hard_max: min_lot risk {needed_pct}% "
                            f"<= {profile.hard_max_risk_pct}% "
                            f"(raw={raw})"
                        ),
                        balance=bal,
                        equity=equity,
                        free_margin=free_margin,
                        suggested_lot=broker_min,
                        calculated_lot=raw,
                        final_lot=broker_min,
                        stop_loss_distance=dist,
                        risk_pct=needed_pct,
                        configured_max_risk_pct=configured_max,
                        quality_score=quality_score,
                        quality_band=band,
                        quality_risk_scale=q_scale,
                        equity_tier=tier,
                        broker_min_lot=broker_min,
                        broker_lot_step=broker_step,
                        broker_max_lot=broker_max,
                        contract_size=cs,
                        margin_required=None,
                        margin_usage_pct=None,
                        session_risk_multiplier=session_risk_multiplier,
                        rejection_reason=None,
                    )
        except Exception:
            pass
        detail = (
            "below_min_lot "
            f"calculated_lot={raw} suggested_lot={suggested} "
            f"broker_minimum={broker_min} account_balance={bal} "
            f"equity={equity} risk_percentage={base_risk} "
            f"quality_band={band} equity_tier={tier.tier_label}"
        )
        return _reject(
            "below_min_lot",
            detail,
            calculated=raw,
            suggested=suggested,
            risk=base_risk,
            dist=dist,
        )

    # Recompute margin at final lot
    if mid_price is not None and mid_price > 0:
        lev = leverage if leverage is not None and leverage > 0 else Decimal("1000")
        margin_need = margin_required(
            volume=final, price=mid_price, leverage=lev, contract_size=cs
        )
        if equity > 0:
            margin_usage = (margin_need / equity * Decimal("100")).quantize(
                Decimal("0.01")
            )

    decision = DynamicSizingDecision(
        valid=True,
        method=f"dynamic_v2{method_suffix}",
        reason=(
            f"v2 risk={base_risk}% band={band} equity={equity} "
            f"tier={tier.preferred_lot_lo}-{tier.preferred_lot_hi} "
            f"raw={raw} final={final}"
        ),
        balance=bal,
        equity=equity,
        free_margin=free_margin,
        suggested_lot=suggested,
        calculated_lot=raw,
        final_lot=final,
        stop_loss_distance=dist,
        risk_pct=base_risk,
        configured_max_risk_pct=configured_max,
        quality_score=quality_score,
        quality_band=band,
        quality_risk_scale=q_scale,
        equity_tier=tier,
        broker_min_lot=broker_min,
        broker_lot_step=broker_step,
        broker_max_lot=broker_max,
        contract_size=cs,
        margin_required=margin_need,
        margin_usage_pct=margin_usage,
        portfolio_exposure_pct=portfolio_exposure_pct,
        symbol_exposure_pct=symbol_open_risk_pct,
        session_risk_multiplier=session_risk_multiplier,
        volatility_scale=vol_scale,
        liquidity_score=liquidity_score,
        spread_score=spread_score,
        trend_confidence=trend_confidence or confidence,
        rejection_reason=None,
        extras={
            "soft_scale": str(soft_scale),
            "preferred_lot_lo": str(tier.preferred_lot_lo),
            "preferred_lot_hi": str(tier.preferred_lot_hi),
            "volume_min_default": str(VOLUME_MIN),
            "volume_step_default": str(VOLUME_STEP),
        },
    )
    if log:
        logger.info(
            "dynamic_sizing_v2_decision",
            **{k: v for k, v in decision.to_dict().items() if k != "extras"},
        )
    return decision


def check_portfolio_sizing_limits(
    *,
    open_positions: int,
    max_open_positions: int,
    daily_loss_pct: Decimal,
    max_daily_loss_pct: Decimal,
    exposure_pct: Decimal,
    max_exposure_pct: Decimal,
    margin_usage_pct: Decimal | None = None,
    max_margin_usage_pct: Decimal = Decimal("30"),
    symbol_exposure_pct: Decimal | None = None,
    max_symbol_exposure_pct: Decimal | None = None,
    correlated_exposure_pct: Decimal | None = None,
    max_correlated_exposure_pct: Decimal = Decimal("40"),
) -> tuple[bool, str | None]:
    """Portfolio / symbol / margin / correlation caps for multi-order scalping."""
    if open_positions >= max_open_positions:
        return True, (
            f"Max open positions reached ({open_positions}>={max_open_positions})"
        )
    if daily_loss_pct >= max_daily_loss_pct > 0:
        return True, (f"Daily loss limit ({daily_loss_pct}% >= {max_daily_loss_pct}%)")
    if exposure_pct >= max_exposure_pct > 0:
        return True, (
            f"Portfolio exposure limit ({exposure_pct}% >= {max_exposure_pct}%)"
        )
    if (
        margin_usage_pct is not None
        and max_margin_usage_pct > 0
        and margin_usage_pct >= max_margin_usage_pct
    ):
        return True, (
            f"Margin usage limit ({margin_usage_pct}% >= {max_margin_usage_pct}%)"
        )
    if (
        symbol_exposure_pct is not None
        and max_symbol_exposure_pct is not None
        and max_symbol_exposure_pct > 0
        and symbol_exposure_pct >= max_symbol_exposure_pct
    ):
        return True, (
            f"Symbol exposure limit "
            f"({symbol_exposure_pct}% >= {max_symbol_exposure_pct}%)"
        )
    if (
        correlated_exposure_pct is not None
        and max_correlated_exposure_pct > 0
        and correlated_exposure_pct >= max_correlated_exposure_pct
    ):
        return True, (
            f"Correlation exposure limit "
            f"({correlated_exposure_pct}% >= {max_correlated_exposure_pct}%)"
        )
    return False, None
