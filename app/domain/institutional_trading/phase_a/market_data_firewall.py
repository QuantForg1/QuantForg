"""Phase A LIVE market-data freshness firewall — NEW ENTRIES only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class MarketDataState(str, Enum):
    MARKET_DATA_VALID = "MARKET_DATA_VALID"
    MARKET_DATA_DEGRADED = "MARKET_DATA_DEGRADED"
    MARKET_DATA_STALE = "MARKET_DATA_STALE"


@dataclass(frozen=True, slots=True)
class MarketDataVerdict:
    state: MarketDataState
    allow_new_entry: bool
    first_blocking_gate: str | None
    quote_age_ms: float | None
    required_max_age_ms: float
    detail: str
    symbol: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "allow_new_entry": self.allow_new_entry,
            "first_blocking_gate": self.first_blocking_gate,
            "quote_age_ms": self.quote_age_ms,
            "required_max_age_ms": self.required_max_age_ms,
            "detail": self.detail,
            "symbol": self.symbol,
        }


def evaluate_market_data_firewall(
    *,
    symbol: str,
    bid: float | None,
    ask: float | None,
    quote_time: datetime | None = None,
    quote_age_seconds: float | None = None,
    max_tick_age_seconds: float = 120.0,
    degraded_tick_age_seconds: float = 60.0,
    market_open: bool | None = True,
    symbol_valid: bool = True,
    candles_ok: bool = True,
    now: datetime | None = None,
) -> MarketDataVerdict:
    """Hard NO_NEW_ENTRY on stale/missing/malformed quotes.

    Does not manage positions — caller must not use this to stop PME.
    """
    required_ms = float(max_tick_age_seconds) * 1000.0
    sym = str(symbol or "").upper()

    if not symbol_valid or not sym:
        return MarketDataVerdict(
            state=MarketDataState.MARKET_DATA_STALE,
            allow_new_entry=False,
            first_blocking_gate="SYMBOL_IDENTITY_INVALID",
            quote_age_ms=None,
            required_max_age_ms=required_ms,
            detail="symbol identity invalid",
            symbol=sym,
        )
    if market_open is False:
        return MarketDataVerdict(
            state=MarketDataState.MARKET_DATA_STALE,
            allow_new_entry=False,
            first_blocking_gate="MARKET_CLOSED",
            quote_age_ms=None,
            required_max_age_ms=required_ms,
            detail="market session closed",
            symbol=sym,
        )
    if bid is None or ask is None:
        return MarketDataVerdict(
            state=MarketDataState.MARKET_DATA_STALE,
            allow_new_entry=False,
            first_blocking_gate="QUOTE_MISSING",
            quote_age_ms=None,
            required_max_age_ms=required_ms,
            detail="bid/ask missing",
            symbol=sym,
        )
    try:
        b = float(bid)
        a = float(ask)
    except Exception:
        return MarketDataVerdict(
            state=MarketDataState.MARKET_DATA_STALE,
            allow_new_entry=False,
            first_blocking_gate="QUOTE_MALFORMED",
            quote_age_ms=None,
            required_max_age_ms=required_ms,
            detail="bid/ask not numeric",
            symbol=sym,
        )
    if b <= 0 or a <= 0 or a < b:
        return MarketDataVerdict(
            state=MarketDataState.MARKET_DATA_STALE,
            allow_new_entry=False,
            first_blocking_gate="QUOTE_MALFORMED",
            quote_age_ms=None,
            required_max_age_ms=required_ms,
            detail="bid/ask non-positive or inverted",
            symbol=sym,
        )
    # Spread computable
    _ = a - b

    age_s: float | None = quote_age_seconds
    if age_s is None and quote_time is not None:
        moment = now or datetime.now(UTC)
        qt = quote_time
        if qt.tzinfo is None:
            qt = qt.replace(tzinfo=UTC)
        age_s = max(0.0, (moment - qt).total_seconds())
    if age_s is None:
        return MarketDataVerdict(
            state=MarketDataState.MARKET_DATA_STALE,
            allow_new_entry=False,
            first_blocking_gate="QUOTE_TIMESTAMP_MISSING",
            quote_age_ms=None,
            required_max_age_ms=required_ms,
            detail="quote timestamp / age unknown",
            symbol=sym,
        )

    age_ms = float(age_s) * 1000.0
    if not candles_ok:
        return MarketDataVerdict(
            state=MarketDataState.MARKET_DATA_STALE,
            allow_new_entry=False,
            first_blocking_gate="CANDLES_STALE_OR_INCOMPLETE",
            quote_age_ms=age_ms,
            required_max_age_ms=required_ms,
            detail="required candles missing or non-monotonic",
            symbol=sym,
        )
    if age_s > float(max_tick_age_seconds):
        return MarketDataVerdict(
            state=MarketDataState.MARKET_DATA_STALE,
            allow_new_entry=False,
            first_blocking_gate="STALE_MARKET_DATA",
            quote_age_ms=age_ms,
            required_max_age_ms=required_ms,
            detail=f"quote_age_s={age_s:.1f} > max={max_tick_age_seconds}",
            symbol=sym,
        )
    if age_s > float(degraded_tick_age_seconds):
        # Degraded still blocks new entries under Phase A (safe default)
        return MarketDataVerdict(
            state=MarketDataState.MARKET_DATA_DEGRADED,
            allow_new_entry=False,
            first_blocking_gate="DEGRADED_MARKET_DATA",
            quote_age_ms=age_ms,
            required_max_age_ms=required_ms,
            detail=f"quote_age_s={age_s:.1f} degraded band",
            symbol=sym,
        )
    return MarketDataVerdict(
        state=MarketDataState.MARKET_DATA_VALID,
        allow_new_entry=True,
        first_blocking_gate=None,
        quote_age_ms=age_ms,
        required_max_age_ms=required_ms,
        detail="ok",
        symbol=sym,
    )
