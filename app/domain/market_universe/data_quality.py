"""Market-data quality states for the research universe.

Missing / stale data is never interpreted as opportunity=0, bearish, or
bullish. Status is explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.domain.market_universe.constants import (
    BAR_STALE_AFTER_S,
    DATA_STATES,
    MIN_HISTORY_BARS_RESEARCH,
    QUOTE_STALE_AFTER_S,
    UNKNOWN,
    DataState,
)


def _as_float(value: Any) -> float | None:
    if value is None or value == "" or value == UNKNOWN:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "" or value == UNKNOWN:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _age_seconds(
    *,
    last_ts: Any,
    now: datetime | None = None,
    age_seconds: Any = None,
) -> float | None:
    direct = _as_float(age_seconds)
    if direct is not None and direct >= 0:
        return direct
    if last_ts in (None, "", UNKNOWN, 0, "0"):
        return None
    current = now or datetime.now(UTC)
    if isinstance(last_ts, datetime):
        ts = last_ts if last_ts.tzinfo else last_ts.replace(tzinfo=UTC)
        return max(0.0, (current - ts).total_seconds())
    if isinstance(last_ts, (int, float)):
        n = float(last_ts)
        if n > 1e12:
            n = n / 1000.0
        try:
            ts = datetime.fromtimestamp(n, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
        return max(0.0, (current - ts).total_seconds())
    text = str(last_ts).strip()
    if not text:
        return None
    try:
        ts = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return max(0.0, (current - ts).total_seconds())
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class DataQuality:
    state: DataState
    quote_freshness: str
    bar_freshness: str
    quote_age_seconds: float | None
    bar_age_seconds: float | None
    missing_bars: int | None
    history_depth: int | None
    spread: float | None
    tick_frequency: float | None | str
    volume: float | None | str
    session_status: str
    symbol_available: bool
    reason: str
    opportunity_score: str | int

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "quote_freshness": self.quote_freshness,
            "bar_freshness": self.bar_freshness,
            "quote_age_seconds": self.quote_age_seconds,
            "bar_age_seconds": self.bar_age_seconds,
            "missing_bars": self.missing_bars
            if self.missing_bars is not None
            else UNKNOWN,
            "history_depth": self.history_depth
            if self.history_depth is not None
            else UNKNOWN,
            "spread": self.spread if self.spread is not None else UNKNOWN,
            "tick_frequency": self.tick_frequency
            if self.tick_frequency is not None
            else UNKNOWN,
            "volume": self.volume if self.volume is not None else UNKNOWN,
            "session_status": self.session_status,
            "symbol_available": self.symbol_available,
            "reason": self.reason,
            "opportunity_score": self.opportunity_score,
            "unavailable_is_not_zero_opportunity": True,
        }


def evaluate_data_quality(
    *,
    bid: Any = None,
    ask: Any = None,
    last_quote_ts: Any = None,
    quote_age_seconds: Any = None,
    last_bar_ts: Any = None,
    bar_age_seconds: Any = None,
    history_bars: Any = None,
    missing_bars: Any = None,
    spread: Any = None,
    tick_frequency: Any = None,
    volume: Any = None,
    trade_mode: Any = None,
    market_open: Any = None,
    disabled: bool = False,
    unsupported: bool = False,
    crypto_24_7: bool = False,
    fetch_error: bool = False,
    unknown: bool = False,
    now: datetime | None = None,
) -> DataQuality:
    """Map quote/bar facts onto an explicit data state.

    ``opportunity_score`` is UNKNOWN whenever data cannot support analysis.
    Never returns 0 as a substitute for missing data.
    """
    quote_age = _age_seconds(
        last_ts=last_quote_ts, now=now, age_seconds=quote_age_seconds
    )
    bar_age = _age_seconds(last_ts=last_bar_ts, now=now, age_seconds=bar_age_seconds)
    depth = _as_int(history_bars)
    miss = _as_int(missing_bars)
    spr = _as_float(spread)
    bid_n = _as_float(bid)
    ask_n = _as_float(ask)
    has_quote = bid_n is not None and ask_n is not None and bid_n > 0 and ask_n > 0
    quote_freshness = (
        UNKNOWN
        if quote_age is None
        else ("STALE" if quote_age > QUOTE_STALE_AFTER_S else "LIVE")
    )
    bar_freshness = (
        UNKNOWN
        if bar_age is None
        else ("STALE" if bar_age > BAR_STALE_AFTER_S else "LIVE")
    )

    mode_text = str(trade_mode or "").strip().lower()
    mode_closed = mode_text in {"0", "disabled", "closeonly", "3"}
    open_flag = market_open
    if isinstance(open_flag, str):
        open_flag = open_flag.strip().lower() in {"1", "true", "yes", "open"}

    session_status = UNKNOWN
    if crypto_24_7:
        session_status = "24/7"
    elif open_flag is False or mode_closed:
        session_status = "MARKET_CLOSED"
    elif open_flag is True or has_quote:
        session_status = "OPEN"

    if unknown:
        state = "UNKNOWN"
        reason = "quality not evaluated"
    elif fetch_error:
        state = "ERROR"
        reason = "symbol probe failed; other instruments continue"
    elif disabled:
        state: DataState = "DISABLED"
        reason = "operator or policy disabled"
    elif unsupported:
        state = "UNSUPPORTED"
        reason = "instrument is not in the research-supported set"
    elif mode_closed and not crypto_24_7:
        state = "MARKET_CLOSED"
        reason = f"trade_mode={trade_mode!r}"
    elif open_flag is False and not crypto_24_7:
        state = "MARKET_CLOSED"
        reason = "broker market_open=false"
    elif not has_quote:
        state = "NO_DATA"
        reason = "no bid/ask"
    elif quote_freshness == "STALE" or bar_freshness == "STALE":
        state = "STALE"
        reason = f"quote_age={quote_age} bar_age={bar_age}"
    elif depth is not None and depth < MIN_HISTORY_BARS_RESEARCH:
        state = "INSUFFICIENT_HISTORY"
        reason = f"history_bars={depth} < {MIN_HISTORY_BARS_RESEARCH}"
    else:
        state = "LIVE"
        reason = "quote present and fresh"

    opp: str | int = UNKNOWN
    return DataQuality(
        state=state,
        quote_freshness=quote_freshness,
        bar_freshness=bar_freshness,
        quote_age_seconds=quote_age,
        bar_age_seconds=bar_age,
        missing_bars=miss,
        history_depth=depth,
        spread=spr,
        tick_frequency=tick_frequency if tick_frequency not in (None, "") else UNKNOWN,
        volume=volume if volume not in (None, "") else UNKNOWN,
        session_status=session_status,
        symbol_available=has_quote
        and state not in {"DISABLED", "UNSUPPORTED", "NO_DATA", "ERROR", "UNKNOWN"},
        reason=reason,
        opportunity_score=opp,
    )


def evaluate_timeframe_quality(
    frames: dict[str, dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Per-timeframe research quality. Missing frames stay UNKNOWN."""
    from app.domain.market_universe.constants import RESEARCH_TIMEFRAMES

    out: dict[str, Any] = {}
    for tf in RESEARCH_TIMEFRAMES:
        raw = (frames or {}).get(tf) if isinstance(frames, dict) else None
        if not isinstance(raw, dict) or not raw:
            out[tf] = {
                "state": "UNKNOWN",
                "bar_count": UNKNOWN,
                "latest_bar_timestamp": UNKNOWN,
                "data_age_seconds": UNKNOWN,
                "missing_bars": UNKNOWN,
                "continuity": UNKNOWN,
                "opportunity_score": UNKNOWN,
            }
            continue
        dq = evaluate_data_quality(
            last_bar_ts=raw.get("latest_bar_timestamp") or raw.get("time"),
            bar_age_seconds=raw.get("data_age_seconds"),
            history_bars=raw.get("bar_count") or raw.get("bars"),
            missing_bars=raw.get("missing_bars"),
            fetch_error=bool(raw.get("error")),
            bid=raw.get("bid", 1),
            ask=raw.get("ask", 1),
            now=now,
        )
        payload = dq.to_dict()
        payload["bar_count"] = raw.get("bar_count") or raw.get("bars") or UNKNOWN
        payload["latest_bar_timestamp"] = (
            raw.get("latest_bar_timestamp") or raw.get("time") or UNKNOWN
        )
        payload["continuity"] = raw.get("continuity") or UNKNOWN
        out[tf] = payload
    return out


def assert_known_state(state: str) -> DataState:
    if state not in DATA_STATES:
        raise ValueError(f"unknown data state {state!r}")
    return state  # type: ignore[return-value]
