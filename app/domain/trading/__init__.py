"""Trading domain helpers — XAUUSD-only platform."""

from app.domain.trading.gold_only import (
    GOLD_SYMBOL,
    default_trading_symbol,
    filter_gold_symbols,
    gold_only_enabled,
    is_gold_symbol,
    require_xauusd,
    resolve_trading_symbol,
)
from app.domain.trading.xauusd_specs import (
    CONTRACT_SIZE,
    MAX_LEVERAGE,
    MAX_SPREAD,
    SYMBOL,
    coerce_max_spread,
    exposure_pct_of_equity,
    margin_required,
    notional_value,
    specs_dict,
)

__all__ = [
    "CONTRACT_SIZE",
    "GOLD_SYMBOL",
    "MAX_LEVERAGE",
    "MAX_SPREAD",
    "SYMBOL",
    "coerce_max_spread",
    "default_trading_symbol",
    "exposure_pct_of_equity",
    "filter_gold_symbols",
    "gold_only_enabled",
    "is_gold_symbol",
    "margin_required",
    "notional_value",
    "require_xauusd",
    "resolve_trading_symbol",
    "specs_dict",
]
