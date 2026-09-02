"""Dynamic position sizing — risk%, equity, SL distance, broker lot constraints."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)


@dataclass(frozen=True, slots=True)
class LotSizingResult:
    lots: Decimal
    risk_amount: Decimal
    stop_distance: Decimal
    method: str
    reason: str
    valid: bool
    # Structured fields for reject evidence (especially below_min_lot)
    calculated_lot: Decimal = Decimal("0")
    broker_min_lot: Decimal = Decimal("0")
    broker_lot_step: Decimal = Decimal("0")
    broker_max_lot: Decimal = Decimal("0")
    account_balance: Decimal = Decimal("0")
    risk_percentage: Decimal = Decimal("0")
    normalized_lot: Decimal = Decimal("0")
    estimated_risk_amount: Decimal = Decimal("0")
    risk_budget: Decimal = Decimal("0")
    sizing_status: str = ""
    block_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "lots": str(self.lots),
            "risk_amount": str(self.risk_amount),
            "stop_distance": str(self.stop_distance),
            "method": self.method,
            "reason": self.reason,
            "valid": self.valid,
            "calculated_lot": str(self.calculated_lot),
            "broker_min_lot": str(self.broker_min_lot),
            "broker_minimum": str(self.broker_min_lot),
            "broker_lot_step": str(self.broker_lot_step),
            "broker_max_lot": str(self.broker_max_lot),
            "account_balance": str(self.account_balance),
            "equity": str(self.account_balance),
            "risk_percentage": str(self.risk_percentage),
            "risk_pct": str(self.risk_percentage),
            "raw_lots": str(self.calculated_lot),
            "normalized_lot": str(self.normalized_lot),
            "estimated_risk_amount": str(
                self.estimated_risk_amount or self.risk_amount
            ),
            "risk_budget": str(self.risk_budget or self.risk_amount),
            "sizing_status": self.sizing_status,
            "block_reason": self.block_reason,
        }

    def below_min_lot_detail(self) -> dict[str, str]:
        return {
            "calculated_lot": str(self.calculated_lot),
            "broker_minimum": str(self.broker_min_lot),
            "account_balance": str(self.account_balance),
            "risk_percentage": str(self.risk_percentage),
        }


def _quantize_lot(
    raw: Decimal, *, step: Decimal, min_lot: Decimal, max_lot: Decimal
) -> Decimal:
    if step <= 0 or min_lot <= 0 or max_lot <= 0:
        return Decimal("0")
    steps = (raw / step).to_integral_value(rounding=ROUND_DOWN)
    lots = steps * step
    if lots < min_lot:
        return Decimal("0")
    if lots > max_lot:
        lots = max_lot
    return lots.quantize(step)


def calculate_scalping_lots(
    *,
    equity: Decimal,
    stop_distance: Decimal | None,
    atr: Decimal | None = None,
    risk_pct: Decimal | None = None,
    contract_size: Decimal | None = None,
    min_lot: Decimal | None = None,
    lot_step: Decimal | None = None,
    compounding_enabled: bool = False,
    peak_equity: Decimal | None = None,
    daily_exposure_used_pct: Decimal = Decimal("0"),
    session_risk_multiplier: Decimal | None = None,
    tick_size: Decimal | None = None,
    tick_value: Decimal | None = None,
    config: AiScalpingConfig | None = None,
) -> LotSizingResult:
    """Size lots from risk% — never martingale / grid / invalid broker lots."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    if cfg.allow_martingale or cfg.allow_grid or cfg.allow_unlimited_averaging:
        return LotSizingResult(
            lots=Decimal("0"),
            risk_amount=Decimal("0"),
            stop_distance=Decimal("0"),
            method="blocked",
            reason="Unsafe sizing modes are permanently disabled",
            valid=False,
            account_balance=equity,
            risk_percentage=risk_pct or cfg.risk_per_trade_pct,
            broker_min_lot=min_lot or cfg.broker_min_lot,
        )

    base_risk = risk_pct if risk_pct is not None else cfg.risk_per_trade_pct
    if compounding_enabled or cfg.compounding_enabled:
        # Compound only with account growth vs peak — never after losses.
        ref = peak_equity if peak_equity and peak_equity > 0 else equity
        if ref > 0 and equity > ref:
            growth = (equity - ref) / ref
            base_risk = base_risk * (Decimal("1") + min(growth, Decimal("0.25")))
        # No increase when underwater vs peak
        elif peak_equity and equity < peak_equity:
            base_risk = base_risk

    if daily_exposure_used_pct >= cfg.max_daily_exposure_pct:
        return LotSizingResult(
            lots=Decimal("0"),
            risk_amount=Decimal("0"),
            stop_distance=stop_distance or Decimal("0"),
            method="exposure_cap",
            reason=(
                f"Daily exposure {daily_exposure_used_pct}% at max "
                f"{cfg.max_daily_exposure_pct}%"
            ),
            valid=False,
            account_balance=equity,
            risk_percentage=base_risk,
            broker_min_lot=min_lot or cfg.broker_min_lot,
        )

    remaining_exposure = cfg.max_daily_exposure_pct - daily_exposure_used_pct
    if remaining_exposure < base_risk:
        base_risk = max(Decimal("0"), remaining_exposure)

    # Optional volatility-adjusted sizing — may REDUCE risk only, never raise
    method_suffix = ""
    if cfg.volatility_adjusted_sizing and atr is not None and atr > 0:
        if (
            stop_distance
            and stop_distance > 0
            and atr >= stop_distance * Decimal("1.5")
        ):
            base_risk = (base_risk * cfg.high_vol_risk_scale).quantize(
                Decimal("0.0001")
            )
            method_suffix = "+high_vol_scale"
        elif (
            stop_distance
            and stop_distance > 0
            and atr <= stop_distance * Decimal("0.5")
        ):
            scale = min(Decimal("1"), cfg.low_vol_risk_scale)
            base_risk = (base_risk * scale).quantize(Decimal("0.0001"))
            method_suffix = "+low_vol_scale"
        if base_risk > cfg.risk_per_trade_pct:
            base_risk = cfg.risk_per_trade_pct

    # Session soft risk weight — may REDUCE only, never increase above base
    if session_risk_multiplier is not None:
        sess_scale = min(Decimal("1"), max(Decimal("0"), session_risk_multiplier))
        if sess_scale < Decimal("1"):
            base_risk = (base_risk * sess_scale).quantize(Decimal("0.0001"))
            method_suffix += "+session_risk_scale"
        if risk_pct is not None and base_risk > risk_pct:
            base_risk = risk_pct
        elif risk_pct is None and base_risk > cfg.risk_per_trade_pct:
            base_risk = cfg.risk_per_trade_pct

    dist = stop_distance
    if dist is None or dist <= 0:
        if atr is not None and atr > 0:
            dist = atr * cfg.stop_atr_mult
        else:
            return LotSizingResult(
                lots=Decimal("0"),
                risk_amount=Decimal("0"),
                stop_distance=Decimal("0"),
                method="no_stop",
                reason="Stop distance unavailable — refusing fixed lots",
                valid=False,
                account_balance=equity,
                risk_percentage=base_risk,
                broker_min_lot=min_lot or cfg.broker_min_lot,
            )

    cs = (
        contract_size
        if contract_size is not None and contract_size > 0
        else Decimal("100")
    )
    broker_min = min_lot if min_lot is not None and min_lot > 0 else cfg.broker_min_lot
    broker_step = (
        lot_step if lot_step is not None and lot_step > 0 else cfg.broker_lot_step
    )

    if equity <= 0 or base_risk <= 0 or cs <= 0:
        return LotSizingResult(
            lots=Decimal("0"),
            risk_amount=Decimal("0"),
            stop_distance=dist,
            method="invalid_inputs",
            reason="Equity / risk% / contract size invalid",
            valid=False,
            account_balance=equity,
            risk_percentage=base_risk,
            broker_min_lot=broker_min,
        )

    risk_amount = (equity * base_risk / Decimal("100")).quantize(Decimal("0.01"))
    from app.domain.institutional_trading.config import (
        MAX_PLANNED_SL_RISK_USD,
        MIN_PLANNED_RISK_USD,
        TARGET_PLANNED_RISK_USD,
    )
    from app.domain.institutional_trading.operations.min_lot_feasibility import (
        CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
        STATUS_EXCEEDS_BUDGET,
        STATUS_NORMALIZED_TO_MIN,
        lot_dollar_risk,
        normalize_lots_against_broker,
        resolve_target_risk_budget_usd,
    )

    usd_target = Decimal(
        str(
            getattr(cfg, "target_risk_per_trade_usd", TARGET_PLANNED_RISK_USD)
            or TARGET_PLANNED_RISK_USD
        )
    )
    min_floor = Decimal(
        str(
            getattr(cfg, "min_planned_risk_usd", MIN_PLANNED_RISK_USD)
            or MIN_PLANNED_RISK_USD
        )
    )
    per_trade_max = Decimal(
        str(
            getattr(cfg, "max_planned_sl_risk_usd", MAX_PLANNED_SL_RISK_USD)
            or MAX_PLANNED_SL_RISK_USD
        )
    )
    if usd_target > 0:
        usd_budget = resolve_target_risk_budget_usd(
            equity=equity, target_usd=usd_target
        )
        if cfg.risk_per_trade_pct > 0 and base_risk < cfg.risk_per_trade_pct:
            usd_budget = (usd_budget * base_risk / cfg.risk_per_trade_pct).quantize(
                Decimal("0.01")
            )
            if usd_budget > 0 and min_floor > 0 and usd_budget < min_floor:
                usd_budget = min_floor
        risk_amount = usd_budget
    per_lot = lot_dollar_risk(
        Decimal("1"),
        stop_distance=dist,
        contract_size=cs,
        tick_size=tick_size,
        tick_value=tick_value,
    )
    raw = risk_amount / per_lot if per_lot > 0 else Decimal("0")

    broker_max = cfg.broker_max_lot
    norm = normalize_lots_against_broker(
        calculated_lot=raw,
        min_lot=broker_min,
        lot_step=broker_step,
        max_lot=broker_max,
        equity=equity,
        stop_distance=dist,
        contract_size=cs,
        risk_budget=risk_amount,
        tick_size=tick_size,
        tick_value=tick_value,
        min_planned_risk=min_floor,
        max_planned_sl_risk=per_trade_max,
    )
    if not norm.approved:
        method = (
            "min_lot_exceeds_risk_budget"
            if norm.sizing_status == STATUS_EXCEEDS_BUDGET
            else "below_min_lot"
        )
        detail = (
            f"{norm.block_reason or method} calculated_lot={raw} "
            f"broker_minimum={broker_min} broker_lot_step={broker_step} "
            f"account_balance={equity} risk_percentage={base_risk} "
            f"estimated_risk_amount={norm.estimated_risk_amount} "
            f"risk_budget={risk_amount}"
        )
        if norm.block_reason == CODE_MIN_LOT_EXCEEDS_RISK_BUDGET:
            detail = (
                f"{CODE_MIN_LOT_EXCEEDS_RISK_BUDGET}: min_lot {broker_min} "
                f"estimated_risk_amount={norm.estimated_risk_amount} exceeds "
                f"hard_max={norm.hard_max_risk_pct}% "
                f"(calculated_lot={raw} risk_budget={risk_amount})"
            )
        return LotSizingResult(
            lots=Decimal("0"),
            risk_amount=norm.estimated_risk_amount or risk_amount,
            stop_distance=dist,
            method=method,
            reason=detail,
            valid=False,
            calculated_lot=raw,
            broker_min_lot=broker_min,
            broker_lot_step=broker_step,
            broker_max_lot=broker_max,
            account_balance=equity,
            risk_percentage=base_risk,
            normalized_lot=norm.normalized_lot,
            estimated_risk_amount=norm.estimated_risk_amount,
            risk_budget=risk_amount,
            sizing_status=norm.sizing_status,
            block_reason=norm.block_reason,
        )
    method = f"percentage_risk{method_suffix}"
    risk_pct_out = base_risk
    if norm.sizing_status == STATUS_NORMALIZED_TO_MIN:
        method = "micro_conditional_min_lot"
        risk_pct_out = norm.needed_pct or base_risk
    return LotSizingResult(
        lots=norm.normalized_lot,
        risk_amount=norm.estimated_risk_amount or risk_amount,
        stop_distance=dist,
        method=method,
        reason=(
            f"risk={base_risk}% equity={equity} stop={dist} "
            f"→ lots={norm.normalized_lot} (min={broker_min} step={broker_step} "
            f"status={norm.sizing_status})"
        ),
        valid=True,
        calculated_lot=raw,
        broker_min_lot=broker_min,
        broker_lot_step=broker_step,
        broker_max_lot=broker_max,
        account_balance=equity,
        risk_percentage=risk_pct_out,
        normalized_lot=norm.normalized_lot,
        estimated_risk_amount=norm.estimated_risk_amount,
        risk_budget=risk_amount,
        sizing_status=norm.sizing_status,
        block_reason=None,
    )
