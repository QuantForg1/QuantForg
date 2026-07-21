"""Canonical MT5 XAUUSD (Gold) instrument specifications.

QuantForg trades XAUUSD only. All risk, margin, exposure, spread, and
sizing math must use these specs — never FX-major (100000 / 0.0001) defaults.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL

# --- Identity -----------------------------------------------------------------
SYMBOL = GOLD_SYMBOL  # "XAUUSD"
BASE_CURRENCY = "XAU"
PROFIT_CURRENCY = "USD"

# --- MT5 symbol properties (Weltrade / standard gold CFD) ----------------------
DIGITS = 2
POINT = Decimal("0.01")
TICK_SIZE = Decimal("0.01")
# Tick value ≈ contract_size * tick_size = $1.00 per 0.01 move per 1.00 lot
TICK_VALUE = Decimal("1.00")
CONTRACT_SIZE = Decimal("100")  # ounces per 1.00 lot
VOLUME_MIN = Decimal("0.01")
VOLUME_MAX = Decimal("10")
VOLUME_STEP = Decimal("0.01")

# --- Desk policy (absolute price units, not FX pips) ---------------------------
# Live XAU spreads are typically ~0.20–0.60 USD. FX ceilings like 0.00050
# are invalid for gold and must never be applied.
MAX_SPREAD = Decimal("2.00")
MAX_SPREAD_TIGHT = Decimal("0.50")  # full confluence score
# Any configured ceiling below this is treated as FX inheritance → coerce.
MIN_VALID_SPREAD_CEILING = Decimal("0.05")

# Weltrade gold accounts commonly run 1:1000. Cap matches broker, not FX 1:500.
MAX_LEVERAGE = Decimal("1000")
# Safer fallback when account.leverage is missing (never use FX 100k path).
EXPOSURE_LEVERAGE_FALLBACK = Decimal("1000")

# Whitelist — platform is single-instrument.
SYMBOL_WHITELIST: frozenset[str] = frozenset({SYMBOL})


def is_fx_scale_spread_ceiling(value: Decimal) -> bool:
    """True when a spread ceiling looks like FX pips, not gold price units."""
    return value < MIN_VALID_SPREAD_CEILING


def coerce_max_spread(value: Decimal | None) -> Decimal:
    """Normalize operator/env spread ceilings to XAUUSD absolute price units."""
    if value is None or value <= 0 or is_fx_scale_spread_ceiling(value):
        return MAX_SPREAD
    return value


def margin_required(
    *,
    volume: Decimal,
    price: Decimal,
    leverage: Decimal,
    contract_size: Decimal = CONTRACT_SIZE,
) -> Decimal:
    """MT5-style required margin: volume × contract_size × price / leverage."""
    lev = leverage if leverage > 0 else EXPOSURE_LEVERAGE_FALLBACK
    return (volume * contract_size * price / lev).quantize(Decimal("0.01"))


def notional_value(
    *,
    volume: Decimal,
    price: Decimal,
    contract_size: Decimal = CONTRACT_SIZE,
) -> Decimal:
    """Full contract notional (not margin)."""
    return (volume * contract_size * price).quantize(Decimal("0.01"))


def exposure_pct_of_equity(
    *,
    volume: Decimal,
    price: Decimal,
    equity: Decimal,
    leverage: Decimal,
    contract_size: Decimal = CONTRACT_SIZE,
) -> Decimal:
    """Margin exposure as % of equity (desk exposure metric)."""
    if equity <= 0:
        return Decimal("0")
    margin = margin_required(
        volume=volume, price=price, leverage=leverage, contract_size=contract_size
    )
    return (margin / equity * Decimal("100")).quantize(Decimal("0.01"))


def point_value_per_lot() -> Decimal:
    """USD value of one point (0.01) move for 1.00 lot."""
    return CONTRACT_SIZE * POINT


def specs_dict() -> dict[str, object]:
    return {
        "symbol": SYMBOL,
        "digits": DIGITS,
        "point": str(POINT),
        "tick_size": str(TICK_SIZE),
        "tick_value": str(TICK_VALUE),
        "contract_size": str(CONTRACT_SIZE),
        "volume_min": str(VOLUME_MIN),
        "volume_max": str(VOLUME_MAX),
        "volume_step": str(VOLUME_STEP),
        "max_spread": str(MAX_SPREAD),
        "max_leverage": str(MAX_LEVERAGE),
        "point_value_per_lot": str(point_value_per_lot()),
    }
