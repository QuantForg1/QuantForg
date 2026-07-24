"""Dynamic position sizing — risk%, equity, SL distance, broker lot constraints."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from app.domain.institutional_trading.ai_scalping.config import (
    AiScalpingConfig,
    DEFAULT_AI_SCALPING_CONFIG,
)


@dataclass(frozen=True, slots=True)
class LotSizingResult:
    lots: Decimal
    risk_amount: Decimal
    stop_distance: Decimal
    method: str
    reason: str
    valid: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "lots": str(self.lots),
            "risk_amount": str(self.risk_amount),
            "stop_distance": str(self.stop_distance),
            "method": self.method,
            "reason": self.reason,
            "valid": self.valid,
        }


def _quantize_lot(raw: Decimal, *, step: Decimal, min_lot: Decimal, max_lot: Decimal) -> Decimal:
    if step <= 0:
        step = Decimal("0.01")
    steps = (raw / step).to_integral_value(rounding=ROUND_DOWN)
    lots = steps * step
    if lots < min_lot:
        return Decimal("0")
    if lots > max_lot:
        return max_lot
    return lots.quantize(step)


def calculate_scalping_lots(
    *,
    equity: Decimal,
    stop_distance: Decimal | None,
    atr: Decimal | None = None,
    risk_pct: Decimal | None = None,
    contract_size: Decimal = Decimal("100"),
    compounding_enabled: bool = False,
    peak_equity: Decimal | None = None,
    daily_exposure_used_pct: Decimal = Decimal("0"),
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
        )

    remaining_exposure = cfg.max_daily_exposure_pct - daily_exposure_used_pct
    if remaining_exposure < base_risk:
        base_risk = max(Decimal("0"), remaining_exposure)

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
            )

    if equity <= 0 or base_risk <= 0 or contract_size <= 0:
        return LotSizingResult(
            lots=Decimal("0"),
            risk_amount=Decimal("0"),
            stop_distance=dist,
            method="invalid_inputs",
            reason="Equity / risk% / contract size invalid",
            valid=False,
        )

    risk_amount = (equity * base_risk / Decimal("100")).quantize(Decimal("0.01"))
    # XAU: risk ≈ lots * contract_size * stop_distance
    raw = risk_amount / (contract_size * dist)
    lots = _quantize_lot(
        raw,
        step=cfg.broker_lot_step,
        min_lot=cfg.broker_min_lot,
        max_lot=cfg.broker_max_lot,
    )
    if lots <= 0:
        return LotSizingResult(
            lots=Decimal("0"),
            risk_amount=risk_amount,
            stop_distance=dist,
            method="below_min_lot",
            reason=(
                f"Calculated lot below broker min {cfg.broker_min_lot} "
                f"(raw={raw})"
            ),
            valid=False,
        )
    return LotSizingResult(
        lots=lots,
        risk_amount=risk_amount,
        stop_distance=dist,
        method="percentage_risk",
        reason=(
            f"risk={base_risk}% equity={equity} stop={dist} "
            f"→ lots={lots} (min={cfg.broker_min_lot} step={cfg.broker_lot_step})"
        ),
        valid=True,
    )
