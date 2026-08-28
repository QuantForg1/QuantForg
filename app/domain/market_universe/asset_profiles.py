"""Asset profiles — research/configuration characteristics.

Profiles are NOT permission to bypass Risk / Safety / Opportunity 70 /
edge 5 / OMS. Empirical numbers that are not measured here stay
UNKNOWN / RESEARCH_REQUIRED / INSUFFICIENT_SAMPLE.
"""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.constants import (
    INSUFFICIENT_SAMPLE,
    RESEARCH_REQUIRED,
    UNKNOWN,
    AssetClassName,
)

_SHARED_WALL = {
    "weakens_risk": False,
    "weakens_safety": False,
    "weakens_opportunity_70": False,
    "weakens_edge_5": False,
    "authorizes_execution": False,
    "ALLOW_LIVE_PROMOTION": False,
}


def _profile(
    asset_class: AssetClassName,
    **fields: Any,
) -> dict[str, Any]:
    row = {
        "profile_id": f"{asset_class}_PROFILE",
        "asset_class": asset_class,
        "normal_volatility": UNKNOWN,
        "spread_characteristics": RESEARCH_REQUIRED,
        "trading_sessions": RESEARCH_REQUIRED,
        "liquidity_windows": RESEARCH_REQUIRED,
        "expected_atr_behavior": UNKNOWN,
        "gap_behavior": RESEARCH_REQUIRED,
        "weekend_behavior": RESEARCH_REQUIRED,
        "session_overlaps": RESEARCH_REQUIRED,
        "contract_specifics": RESEARCH_REQUIRED,
        "suitable_timeframes": RESEARCH_REQUIRED,
        "data_requirements": RESEARCH_REQUIRED,
        "empirical_sample": INSUFFICIENT_SAMPLE,
        "correlation_groups": RESEARCH_REQUIRED,
        "spread_tolerance": RESEARCH_REQUIRED,
        "volatility_normalization": RESEARCH_REQUIRED,
        "market_open_behavior": RESEARCH_REQUIRED,
        **_SHARED_WALL,
        **fields,
    }
    return row


ASSET_PROFILES: dict[str, dict[str, Any]] = {
    "FOREX": _profile(
        "FOREX",
        trading_sessions=("SYDNEY", "TOKYO", "LONDON", "LONDON-NY OVERLAP", "NEW YORK"),
        session_overlaps=("TOKYO-LONDON", "LONDON-NY OVERLAP"),
        weekend_behavior="TYPICALLY_CLOSED",
        gap_behavior="WEEKEND_GAP_POSSIBLE",
        suitable_timeframes=("M1", "M5", "M15", "H1"),
        data_requirements="QUOTE+OHLC; never treat missing bars as signal",
        liquidity_windows=("LONDON", "LONDON-NY OVERLAP"),
        spread_characteristics=RESEARCH_REQUIRED,
        contract_specifics="spot FX / CFD; point/digits from broker",
        correlation_groups=("USD_MAJORS", "EUR_CROSSES", "JPY_CROSSES"),
        market_open_behavior="SESSION_GATED",
    ),
    "CRYPTO": _profile(
        "CRYPTO",
        trading_sessions=("24/7",),
        weekend_behavior="24/7_CONTINUES",
        session_overlaps="NOT_APPLICABLE_24_7",
        gap_behavior="EXCHANGE_HALT_ONLY",
        suitable_timeframes=("M1", "M5", "M15", "H1"),
        data_requirements="24/7 quotes; weekend is not a close",
        liquidity_windows=RESEARCH_REQUIRED,
        spread_characteristics=RESEARCH_REQUIRED,
        contract_specifics="crypto CFD / synthetic USD; broker form may differ",
        correlation_groups=("BTC_BETA", "USD_CRYPTO"),
        market_open_behavior="24/7",
    ),
    "METALS": _profile(
        "METALS",
        trading_sessions=("SYDNEY", "TOKYO", "LONDON", "LONDON-NY OVERLAP", "NEW YORK"),
        weekend_behavior="TYPICALLY_CLOSED",
        gap_behavior="WEEKEND_GAP_POSSIBLE",
        session_overlaps=("LONDON-NY OVERLAP",),
        suitable_timeframes=("M1", "M5", "M15", "H1"),
        data_requirements="QUOTE+OHLC; gold live path remains XAUUSD_i",
        liquidity_windows=("LONDON", "NEW YORK"),
        spread_characteristics=RESEARCH_REQUIRED,
        contract_specifics="spot metal CFD; XAUUSD_i is the live reference",
        notes="Live gold execution is unchanged. Research metadata only.",
        correlation_groups=("METALS_GOLD", "USD_METALS"),
        market_open_behavior="SESSION_GATED",
    ),
    "INDICES": _profile(
        "INDICES",
        trading_sessions=("CASH_INDEX_HOURS", "FUTURES_HOURS_IF_OFFERED"),
        weekend_behavior="TYPICALLY_CLOSED",
        gap_behavior="CASH_OPEN_GAP_COMMON",
        session_overlaps=RESEARCH_REQUIRED,
        suitable_timeframes=("M5", "M15", "H1"),
        data_requirements="respect cash vs futures session; never assume FX hours",
        liquidity_windows=RESEARCH_REQUIRED,
        spread_characteristics=RESEARCH_REQUIRED,
        contract_specifics="index CFD; contract size/tick from broker",
        correlation_groups=("US_INDICES", "EU_INDICES"),
        market_open_behavior="CASH_OR_FUTURES_HOURS",
    ),
    "ENERGY": _profile(
        "ENERGY",
        trading_sessions=("ENERGY_CONTRACT_HOURS",),
        weekend_behavior="TYPICALLY_CLOSED",
        gap_behavior="CONTRACT_OPEN_GAP_COMMON",
        session_overlaps=RESEARCH_REQUIRED,
        suitable_timeframes=("M5", "M15", "H1"),
        data_requirements="respect energy contract hours; never assume London FX",
        liquidity_windows=RESEARCH_REQUIRED,
        spread_characteristics=RESEARCH_REQUIRED,
        contract_specifics="energy CFD (WTI/Brent/etc.); tick from broker",
        correlation_groups=("ENERGY_OIL", "USD_ENERGY"),
        market_open_behavior="CONTRACT_HOURS",
    ),
    "OTHER": _profile(
        "OTHER",
        trading_sessions=UNKNOWN,
        weekend_behavior=UNKNOWN,
        gap_behavior=UNKNOWN,
        notes="Known unsupported/stock-like. RESEARCH_REQUIRED before shadow.",
        correlation_groups=UNKNOWN,
    ),
    "UNKNOWN": _profile(
        "UNKNOWN",
        trading_sessions=UNKNOWN,
        weekend_behavior=UNKNOWN,
        gap_behavior=UNKNOWN,
        notes="Unclassified. Remain UNKNOWN rather than guessed.",
        correlation_groups=UNKNOWN,
    ),
}


def profile_for(asset_class: str | None) -> dict[str, Any]:
    key = str(asset_class or "UNKNOWN").strip().upper()
    return dict(ASSET_PROFILES.get(key) or ASSET_PROFILES["UNKNOWN"])
