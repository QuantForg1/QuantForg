"""Market-universe research constants.

Observational only. These labels never authorize OMS / MT5 execution and
never override Opportunity 70, directional edge 5, Risk, or Safety.
"""

from __future__ import annotations

from typing import Literal

UNKNOWN = "UNKNOWN"
RESEARCH_REQUIRED = "RESEARCH_REQUIRED"
INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"

AssetClassName = Literal[
    "FOREX",
    "CRYPTO",
    "METALS",
    "INDICES",
    "ENERGY",
    "STOCKS",
    "COMMODITIES",
    "OTHER",
    "UNKNOWN",
]

ASSET_CLASSES: tuple[AssetClassName, ...] = (
    "FOREX",
    "CRYPTO",
    "METALS",
    "INDICES",
    "ENERGY",
    "STOCKS",
    "COMMODITIES",
    "OTHER",
    "UNKNOWN",
)

ClassificationSource = Literal[
    "BROKER_METADATA",
    "SYMBOL_RULE",
    "MANUAL_OVERRIDE",
]

DataState = Literal[
    "LIVE",
    "STALE",
    "NO_DATA",
    "MARKET_CLOSED",
    "DISABLED",
    "INSUFFICIENT_HISTORY",
    "UNSUPPORTED",
    "ERROR",
    "UNKNOWN",
]

DATA_STATES: tuple[DataState, ...] = (
    "LIVE",
    "STALE",
    "NO_DATA",
    "MARKET_CLOSED",
    "DISABLED",
    "INSUFFICIENT_HISTORY",
    "UNSUPPORTED",
    "ERROR",
    "UNKNOWN",
)

ClassificationConfidence = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]

PROMOTION_STATUSES: tuple[str, ...] = (
    "DISCOVERED",
    "DATA_READY",
    "ANALYZED",
    "QUALIFIED",
    "SHADOW",
    "INSUFFICIENT_SAMPLE",
    "MEANINGFUL_RESEARCH",
    "PROMOTION_CANDIDATE",
    "HUMAN_REVIEW_REQUIRED",
    "LIVE_ELIGIBLE",
)

PROMOTION_CHAIN: tuple[str, ...] = (
    "GLOBAL_DISCOVERY",
    "DATA_READY",
    "ANALYSIS",
    "QUALIFIED",
    "SHADOW",
    "RESEARCH",
    "BACKTEST",
    "WALK_FORWARD",
    "OOS",
    "RISK_REVIEW",
    "SAFETY_REVIEW",
    "HUMAN_APPROVAL",
    "LIVE_ELIGIBILITY",
    "EXISTING_OMS",
    "EXISTING_MT5_EXECUTION",
)

RESEARCH_TIMEFRAMES: tuple[str, ...] = ("M1", "M5", "M15", "H1")
CONTEXT_TIMEFRAMES: tuple[str, ...] = ("H4", "D1")
# Public catalogue_source contract: LIVE_BROKER | INJECTED | UNAVAILABLE | ERROR.
# MOCK is a diagnostic adapter_kind only — never a LIVE_BROKER label.
CATALOGUE_LIVE_BROKER = "LIVE_BROKER"
CATALOGUE_UNAVAILABLE = "UNAVAILABLE"
CATALOGUE_ERROR = "ERROR"
CATALOGUE_INJECTED = "INJECTED"
CATALOGUE_MOCK = "MOCK"
CATALOGUE_CACHE = "CACHE"
CATALOGUE_TTL_S = 60.0

MAX_RESEARCH_WORKERS = 4
MAX_HISTORY_PROBE_SYMBOLS = 8
HISTORY_PROBE_BARS = 80
HISTORY_CONTEXT_BARS = 40
RESEARCH_RETRY_BACKOFF_S = 2.0

# Research display tiers only. Live Opportunity threshold remains 70.
OPPORTUNITY_TIER_EXTREME = "EXTREME"
OPPORTUNITY_TIER_VERY_HIGH = "VERY_HIGH"
OPPORTUNITY_TIER_HIGH = "HIGH"
OPPORTUNITY_TIER_MODERATE = "MODERATE"
OPPORTUNITY_TIER_LOW = "LOW"

PROMOTION_N_EARLY = 20
PROMOTION_N_REVIEW = 50
PROMOTION_N_STRONG = 100

RESEARCH_REGIME_LABELS: tuple[str, ...] = (
    "TREND",
    "RANGE",
    "BREAKOUT",
    "REVERSAL",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "NEWS_VOLATILITY",
    "UNKNOWN",
)

LAYER_CORE = "CORE"
LAYER_RESEARCH = "RESEARCH"
LAYER_EXPANSION = "EXPANSION"
# Investigation hints ONLY — never inserted unless the broker returned them.
COVERAGE_OBSERVATION_HINTS: tuple[str, ...] = (
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "BTCUSD",
    "ETHUSD",
    "XAUUSD",
    "XAGUSD",
    "NAS100",
    "US30",
    "SPX500",
    "USOIL",
    "UKOIL",
)

# Frozen live contracts — copied for audit/display only. Do not use these
# to retune scoring. Authoritative values live in probability_selector /
# SCALPING_V1 / sniper.
FROZEN_OPPORTUNITY_THRESHOLD = 70
FROZEN_DIRECTIONAL_EDGE = 5
FROZEN_MIN_RR = "1.20"

# Research data-freshness heuristic (seconds). Not a trading gate.
QUOTE_STALE_AFTER_S = 30.0
BAR_STALE_AFTER_S = 180.0
MIN_HISTORY_BARS_RESEARCH = 50

ADVISORY_ONLY = True
ALLOW_LIVE_PROMOTION = False
RESEARCH_MAY_EXECUTE = False
RESEARCH_UNIVERSE_IS_NOT_EXECUTION_UNIVERSE = True
SHADOW_ONLY = True
