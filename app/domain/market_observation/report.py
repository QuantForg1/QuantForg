"""Classify a market snapshot from supplied facts. Missing facts stay blank."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

SCHEMA_VERSION = "market-observation.v1"
STALE_QUOTE_SECONDS = 120
STRONG_MOMENTUM = Decimal("0.5")
INITIAL_SYMBOLS = frozenset({"XAUUSD"})

_TRENDS = frozenset({"up", "down", "flat"})
_VOLATILITY = frozenset({"high", "low", "normal"})
_NEWS = frozenset({"clear", "high_impact"})


@dataclass(frozen=True, slots=True)
class ObservationInput:
    """Facts already loaded by the caller. This module does not fetch."""

    symbol: str
    read_at: datetime
    quote_time: datetime | None = None
    bid: str | None = None
    ask: str | None = None
    spread: str | None = None
    trend: str | None = None
    momentum: str | None = None
    volatility: str | None = None
    liquidity: str | None = None
    news: str | None = None
    source: str = "none"
    quote_status: str = "unavailable"


def build_market_observation(spec: ObservationInput) -> dict[str, Any]:
    """Return a JSON-safe observation. Never an execution instruction."""
    symbol = (spec.symbol or "").strip().upper() or "UNKNOWN"
    read_at = _aware(spec.read_at)
    source = (spec.source or "").strip() or "none"
    observed = _iso(read_at)
    quote_time = _aware(spec.quote_time) if spec.quote_time else None
    age = None
    if quote_time is not None:
        age = int((read_at - quote_time).total_seconds())
    bid = _decimal(spec.bid)
    ask = _decimal(spec.ask)
    spread = _decimal(spec.spread)
    if spread is None and bid is not None and ask is not None and ask >= bid:
        spread = ask - bid
    fresh = _freshness(
        age=age,
        quote_status=spec.quote_status,
        has_quote=spread is not None,
    )
    trend = _choice(spec.trend, _TRENDS)
    momentum = _decimal(spec.momentum)
    volatility = _choice(spec.volatility, _VOLATILITY)
    news = _choice(spec.news, _NEWS)
    regime = _regime(
        fresh=fresh,
        has_quote=spread is not None,
        trend=trend,
        momentum=momentum,
        volatility=volatility,
    )
    suitability = _suitability(symbol=symbol, fresh=fresh, news=news, regime=regime)
    return {
        "schema_version": SCHEMA_VERSION,
        "places_orders": False,
        "modifies_positions": False,
        "changes_strategy_selection": False,
        "changes_risk_policy": False,
        "authoritative_for_execution": False,
        "symbol": symbol,
        "read_at": observed,
        "source": source,
        "initial_observation_set": sorted(INITIAL_SYMBOLS),
        "regime": _figure(
            regime,
            status=_regime_figure_status(fresh, regime),
            source=source,
            method="observation_rules_v1",
            observed_at=observed,
        ),
        "trend": _figure(
            trend,
            status="verified" if trend else "unavailable",
            source=source,
            method="caller_supplied_trend",
            observed_at=observed,
        ),
        "momentum": _figure(
            _money(momentum) if momentum is not None else None,
            status="verified" if momentum is not None else "unavailable",
            source=source,
            method="caller_supplied_signed_momentum",
            observed_at=observed,
        ),
        "volatility": _figure(
            volatility,
            status="verified" if volatility else "unavailable",
            source=source,
            method="caller_supplied_volatility",
            observed_at=observed,
        ),
        "spread": _figure(
            _money(spread) if spread is not None else None,
            status="verified" if spread is not None else "unavailable",
            source=source,
            method="ask_minus_bid_or_reported_spread",
            observed_at=_iso(quote_time),
        ),
        "spread_condition": _figure(
            None,
            status="unavailable",
            source=source,
            method="no_spread_limit_in_observation_mode",
            observed_at=observed,
        ),
        "liquidity": _figure(
            _text(spec.liquidity),
            status="verified" if _text(spec.liquidity) else "unavailable",
            source=source,
            method="caller_supplied_liquidity",
            observed_at=observed,
        ),
        "session": _session_figure(read_at, observed_at=observed),
        "news": _figure(
            news,
            status="verified" if news else "unavailable",
            source=source if news else "none",
            method="caller_supplied_news",
            observed_at=observed,
        ),
        "freshness": _figure(
            fresh,
            status="verified" if fresh != "unknown" else "unavailable",
            source=source,
            method=f"quote_age_versus_{STALE_QUOTE_SECONDS}s",
            observed_at=observed,
        ),
        "strategy_suitability": _figure(
            suitability,
            status="verified",
            source="market_observation",
            method="observation_only_no_order",
            observed_at=observed,
        ),
        "quote_age_seconds": age,
    }


def _regime_figure_status(fresh: str, regime: str) -> str:
    if fresh == "fresh" and regime != "uncertain":
        return "verified"
    return _regime_status(fresh, regime)


def _regime_status(fresh: str, regime: str) -> str:
    if regime == "market_unavailable" or fresh == "unknown":
        return "unavailable"
    if fresh == "delayed" or regime == "uncertain":
        return "partially_verified"
    return "verified"


def _freshness(*, age: int | None, quote_status: str, has_quote: bool) -> str:
    status = (quote_status or "").strip().lower()
    if not has_quote or status in {"", "unavailable", "error"}:
        return "unknown"
    if age is None:
        return "delayed" if status == "delayed" else "unknown"
    if age < 0 or age > STALE_QUOTE_SECONDS or status == "delayed":
        return "delayed"
    return "fresh"


def _regime(
    *,
    fresh: str,
    has_quote: bool,
    trend: str | None,
    momentum: Decimal | None,
    volatility: str | None,
) -> str:
    if not has_quote or fresh in {"unknown", "delayed"}:
        return "market_unavailable"
    if trend is None or momentum is None:
        return "uncertain"
    if trend == "flat" and volatility == "high":
        return "high_volatility"
    if trend == "flat" and volatility == "low":
        return "low_volatility"
    if trend == "flat":
        return "ranging"
    if trend == "up" and momentum >= STRONG_MOMENTUM:
        return "strong_bullish"
    if trend == "up" and momentum > 0:
        return "weak_bullish"
    if trend == "down" and momentum <= -STRONG_MOMENTUM:
        return "strong_bearish"
    if trend == "down" and momentum < 0:
        return "weak_bearish"
    return "uncertain"


def _suitability(*, symbol: str, fresh: str, news: str | None, regime: str) -> str:
    if symbol not in INITIAL_SYMBOLS:
        return "not_in_initial_observation_set"
    if regime == "market_unavailable" or fresh == "unknown":
        return "unavailable"
    if news == "high_impact" or fresh == "delayed":
        return "observation_only_caution"
    return "observation_only"


def _session_figure(read_at: datetime, *, observed_at: str | None) -> dict[str, Any]:
    hour = read_at.astimezone(UTC).hour
    if hour < 7:
        name = "asia"
    elif hour < 12:
        name = "london"
    elif hour < 16:
        name = "london_ny"
    elif hour < 21:
        name = "new_york"
    else:
        name = "quiet"
    return _figure(
        name,
        status="verified",
        source="utc_clock",
        method="approximate_fx_session_clock",
        observed_at=observed_at,
    )


def _figure(
    value: Any,
    *,
    status: str,
    source: str,
    method: str,
    observed_at: str | None,
) -> dict[str, Any]:
    if value is None and status == "verified":
        status = "unavailable"
    return {
        "value": value,
        "status": status,
        "source": source,
        "method": method,
        "observed_at": observed_at,
        "execution_instruction": False,
    }


def _text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _choice(value: str | None, allowed: frozenset[str]) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().lower().replace("-", "_").replace(" ", "_")
    return text if text in allowed else None


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool | float):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _money(value: Decimal) -> str:
    return format(value, "f")


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _aware(value).isoformat()
