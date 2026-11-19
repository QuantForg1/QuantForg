"""QuantForg AI Assistant — grounded chat with optional chart screenshots.

Truthfulness rules:
* Every live number the model sees is computed here from the platform's
  market feed (tick, M15/H1/H4 candles) — the model is told never to invent
  prices or levels that are not in the snapshot or visible in the image.
* When a feed is unavailable the snapshot says so, and the model must say so.
* Advisory only: the assistant cannot place, modify or close trades.
* Secrets never enter the prompt; images are passed through, never stored.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

MAX_HISTORY_TURNS = 12
MAX_MESSAGE_CHARS = 4000
MAX_IMAGES = 3
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
RATE_LIMIT_MESSAGES = 30
RATE_LIMIT_WINDOW_S = 600.0

_DATA_URL_RE = re.compile(r"^data:(image/[a-z+.-]+);base64,([A-Za-z0-9+/=\s]+)$")


class AssistantError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


# ---------------------------------------------------------------- validation


@dataclass(frozen=True, slots=True)
class ChatTurn:
    role: str  # "user" | "assistant"
    content: str


def validate_image(data_url: str) -> str:
    """Return a normalised data URL or raise AssistantError."""
    m = _DATA_URL_RE.match((data_url or "").strip())
    if not m:
        raise AssistantError("invalid_image", "Attach a PNG, JPEG, WebP or GIF image.")
    mime = m.group(1).lower()
    if mime == "image/jpg":
        mime = "image/jpeg"
    if mime not in ALLOWED_IMAGE_TYPES:
        raise AssistantError("invalid_image", "Attach a PNG, JPEG, WebP or GIF image.")
    payload = re.sub(r"\s+", "", m.group(2))
    try:
        raw = base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise AssistantError("invalid_image", "The image could not be read.") from exc
    if len(raw) > MAX_IMAGE_BYTES:
        raise AssistantError("image_too_large", "Images must be 5 MB or smaller.", 413)
    if not raw:
        raise AssistantError("invalid_image", "The image is empty.")
    return f"data:{mime};base64,{payload}"


def clean_history(turns: list[ChatTurn]) -> list[ChatTurn]:
    out: list[ChatTurn] = []
    for t in turns[-MAX_HISTORY_TURNS:]:
        role = "assistant" if t.role == "assistant" else "user"
        text = (t.content or "").strip()[:MAX_MESSAGE_CHARS]
        if text:
            out.append(ChatTurn(role, text))
    return out


# --------------------------------------------------------------- rate limits


@dataclass
class _Bucket:
    hits: deque[float] = field(default_factory=deque)


_BUCKETS: dict[str, _Bucket] = {}


def check_rate_limit(user_key: str, *, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    bucket = _BUCKETS.setdefault(user_key, _Bucket())
    while bucket.hits and now - bucket.hits[0] > RATE_LIMIT_WINDOW_S:
        bucket.hits.popleft()
    if len(bucket.hits) >= RATE_LIMIT_MESSAGES:
        raise AssistantError(
            "rate_limited",
            "You've reached the assistant limit for now. Try again in a few minutes.",
            429,
        )
    bucket.hits.append(now)


def reset_rate_limits_for_tests() -> None:
    _BUCKETS.clear()


# ---------------------------------------------------------------- indicators


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None  # NaN guard


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = values[i] - values[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    avg_g, avg_l = gains / period, losses / period
    for i in range(period + 1, len(values)):
        d = values[i] - values[i - 1]
        avg_g = (avg_g * (period - 1) + max(d, 0.0)) / period
        avg_l = (avg_l * (period - 1) + max(-d, 0.0)) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100.0 - 100.0 / (1.0 + rs)


def atr(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> float | None:
    n = len(closes)
    if n <= period:
        return None
    trs = [
        max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        for i in range(1, n)
    ]
    a = sum(trs[:period]) / period
    for tr in trs[period:]:
        a = (a * (period - 1) + tr) / period
    return a


def summarize_candles(candles: list[Any], timeframe: str) -> dict[str, Any]:
    """Deterministic, compact stats for one timeframe. No invented values."""
    rows: list[tuple[Any, float, float, float, float]] = []
    for c in candles:
        o = _f(getattr(c, "open", None))
        h = _f(getattr(c, "high", None))
        lo = _f(getattr(c, "low", None))
        cl = _f(getattr(c, "close", None))
        if o is None or h is None or lo is None or cl is None:
            continue
        rows.append((getattr(c, "open_time", None), o, h, lo, cl))
    if len(rows) < 5:
        return {"timeframe": timeframe, "available": False}
    closes = [r[4] for r in rows]
    highs = [r[2] for r in rows]
    lows = [r[3] for r in rows]
    last = closes[-1]
    e20, e50 = ema(closes, 20), ema(closes, 50)
    look = rows[-20:]
    trend = "unclear"
    if e20 is not None and e50 is not None:
        if last > e20 > e50:
            trend = "up (price above EMA20 above EMA50)"
        elif last < e20 < e50:
            trend = "down (price below EMA20 below EMA50)"
        else:
            trend = "mixed / ranging"

    def r2(x: float | None) -> float | None:
        return None if x is None else round(x, 2)

    recent = [
        {
            "t": t.isoformat() if isinstance(t, datetime) else str(t),
            "o": r2(o),
            "h": r2(h),
            "l": r2(lo),
            "c": r2(cl),
        }
        for (t, o, h, lo, cl) in rows[-12:]
    ]
    return {
        "timeframe": timeframe,
        "available": True,
        "bars": len(rows),
        "last_close": r2(last),
        "change_last_20_bars_pct": (
            r2((last / closes[-21] - 1) * 100) if len(closes) > 20 else None
        ),
        "ema20": r2(e20),
        "ema50": r2(e50),
        "rsi14": r2(rsi(closes, 14)),
        "atr14": r2(atr(highs, lows, closes, 14)),
        "high_last_20": r2(max(r[2] for r in look)),
        "low_last_20": r2(min(r[3] for r in look)),
        "trend": trend,
        "recent_bars": recent,
    }


# ------------------------------------------------------------------ snapshot


# ---------------------------------------------------------- levels & regime


def _rows(candles: list[Any]) -> list[tuple[float, float, float, float]]:
    out: list[tuple[float, float, float, float]] = []
    for c in candles:
        o = _f(getattr(c, "open", None))
        h = _f(getattr(c, "high", None))
        lo = _f(getattr(c, "low", None))
        cl = _f(getattr(c, "close", None))
        if o is not None and h is not None and lo is not None and cl is not None:
            out.append((o, h, lo, cl))
    return out


def swing_levels(
    candles: list[Any], price: float, *, wing: int = 3, limit: int = 3
) -> dict[str, list[float]]:
    """Nearest swing-high resistances above and swing-low supports below.

    A swing high is a bar whose high is the highest of ``wing`` bars on each
    side (fractal). Levels closer than 0.25 ATR are merged. Pure price data.
    """
    rows = _rows(candles)
    if len(rows) < 2 * wing + 5:
        return {"supports": [], "resistances": []}
    highs = [r[1] for r in rows]
    lows = [r[2] for r in rows]
    closes = [r[3] for r in rows]
    a = atr(highs, lows, closes, 14) or 0.0
    piv_hi: list[float] = []
    piv_lo: list[float] = []
    for i in range(wing, len(rows) - wing):
        window_h = highs[i - wing : i + wing + 1]
        window_l = lows[i - wing : i + wing + 1]
        if highs[i] == max(window_h):
            piv_hi.append(highs[i])
        if lows[i] == min(window_l):
            piv_lo.append(lows[i])
    # Most recent extremes also count as levels.
    piv_hi.append(max(highs[-20:]))
    piv_lo.append(min(lows[-20:]))

    def merge(levels: list[float]) -> list[float]:
        merged: list[float] = []
        for lv in sorted(levels):
            if merged and a and abs(lv - merged[-1]) < 0.25 * a:
                merged[-1] = round((merged[-1] + lv) / 2, 2)
            else:
                merged.append(round(lv, 2))
        return merged

    res = [x for x in merge(piv_hi) if x > price]
    sup = [x for x in merge(piv_lo) if x < price]
    return {
        "resistances": sorted(res)[:limit],
        "supports": sorted(sup, reverse=True)[:limit],
    }


def volatility_regime(candles: list[Any]) -> dict[str, Any]:
    rows = _rows(candles)
    if len(rows) < 40:
        return {"state": "unknown"}
    highs = [r[1] for r in rows]
    lows = [r[2] for r in rows]
    closes = [r[3] for r in rows]
    cur = atr(highs, lows, closes, 14)
    trs = [
        max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        for i in range(1, len(rows))
    ]
    base = sum(trs[-100:]) / len(trs[-100:])
    if not cur or not base:
        return {"state": "unknown"}
    ratio = cur / base
    state = "high" if ratio >= 1.4 else "low" if ratio <= 0.7 else "normal"
    return {"state": state, "atr_vs_average": round(ratio, 2)}


def trading_session(now: datetime) -> str:
    """Gold session by UTC hour (FX week: Sun 22:00 → Fri 21:00 UTC)."""
    wd, h = now.weekday(), now.hour
    if wd == 5 or (wd == 6 and h < 22) or (wd == 4 and h >= 21):
        return "closed (weekend)"
    if 12 <= h < 16:
        return "London-New York overlap"
    if 7 <= h < 12:
        return "London"
    if 16 <= h < 21:
        return "New York"
    if h >= 22 or h < 7:
        return "Asia"
    return "rollover / thin liquidity"


def overall_bias(timeframes: list[dict[str, Any]]) -> dict[str, Any]:
    ups = sum(1 for t in timeframes if str(t.get("trend", "")).startswith("up"))
    downs = sum(1 for t in timeframes if str(t.get("trend", "")).startswith("down"))
    n = sum(1 for t in timeframes if t.get("available"))
    if n == 0:
        return {"direction": "unknown", "aligned": 0, "of": 0}
    if ups > downs:
        direction = "bullish"
    elif downs > ups:
        direction = "bearish"
    else:
        direction = "neutral"
    return {"direction": direction, "aligned": max(ups, downs), "of": n}


# ------------------------------------------------------------------ snapshot


async def _safe(coro: Any, limit_s: float) -> Any:
    try:
        return await asyncio.wait_for(coro, timeout=limit_s)
    except Exception as exc:  # feeds are optional; record absence, not errors
        logger.info(
            "assistant_snapshot_part_unavailable", error_type=type(exc).__name__
        )
        return None


def _event_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


async def build_market_snapshot(
    *,
    feed: Any,
    news: Any | None,
    symbol: str = "XAUUSD",
    risk_settings: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    tick_b, m15, h1, h4 = await asyncio.gather(
        _safe(feed.tick(symbol=symbol), 6),
        _safe(feed.candles(symbol=symbol, timeframe="M15", count=120), 8),
        _safe(feed.candles(symbol=symbol, timeframe="H1", count=150), 8),
        _safe(feed.candles(symbol=symbol, timeframe="H4", count=120), 8),
    )
    snap: dict[str, Any] = {
        "generated_at_utc": now.replace(microsecond=0).isoformat(),
        "symbol": symbol,
        "session": trading_session(now),
    }
    tick = getattr(tick_b, "tick", None) if tick_b is not None else None
    price: float | None = None
    if tick is not None:
        bid, ask = _f(getattr(tick, "bid", None)), _f(getattr(tick, "ask", None))
        if bid is not None and ask is not None:
            price = (bid + ask) / 2
        snap["quote"] = {
            "bid": bid,
            "ask": ask,
            "spread": (
                round(ask - bid, 2) if bid is not None and ask is not None else None
            ),
            "source": getattr(tick_b, "source", ""),
            "status": getattr(tick_b, "status", ""),
            "market_open": getattr(tick_b, "market_open", None),
            # Broker tick clocks are not UTC; the fetch time is what we know.
            "fetched_at_utc": snap["generated_at_utc"],
        }
    else:
        snap["quote"] = {
            "available": False,
            "note": "Live quote unavailable right now.",
        }

    bundles = ((m15, "M15"), (h1, "H1"), (h4, "H4"))
    snap["timeframes"] = [
        (
            summarize_candles(list(getattr(b, "candles", []) or []), tf)
            if b is not None
            else {"timeframe": tf, "available": False}
        )
        for b, tf in bundles
    ]
    if price is None:
        for t in snap["timeframes"]:
            if t.get("available"):
                price = float(t["last_close"])
                break
    snap["bias"] = overall_bias(snap["timeframes"])
    h1_candles = list(getattr(h1, "candles", []) or []) if h1 is not None else []
    h4_candles = list(getattr(h4, "candles", []) or []) if h4 is not None else []
    if price is not None and h1_candles:
        snap["key_levels_h1"] = swing_levels(h1_candles, price)
    if price is not None and h4_candles:
        snap["key_levels_h4"] = swing_levels(h4_candles, price)
    if h1_candles:
        snap["volatility_h1"] = volatility_regime(h1_candles)

    if news is not None:
        try:
            snap["news"] = [
                {
                    "title": n.title,
                    "source": n.source,
                    "published_at": str(n.published_at),
                }
                for n in news.news(limit=6)
            ]
        except Exception:
            snap["news"] = "unavailable"
        try:
            events = []
            for e in news.economic_events(limit=12):
                at = _event_time(e.scheduled_at)
                events.append(
                    {
                        "title": e.title,
                        "country": e.country,
                        "impact": e.impact,
                        "scheduled_at_utc": (
                            at.isoformat() if at else str(e.scheduled_at)
                        ),
                        "minutes_from_now": (
                            round((at - now).total_seconds() / 60) if at else None
                        ),
                        "forecast": e.forecast,
                        "previous": e.previous,
                        "actual": e.actual,
                    }
                )
            snap["economic_calendar"] = events
        except Exception:
            snap["economic_calendar"] = "unavailable"
    if risk_settings:
        snap["user_risk_settings"] = risk_settings
    return snap


_SNAPSHOT_TTL_S = 15.0
_SNAPSHOT_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_SNAPSHOT_LOCK = asyncio.Lock()


async def cached_market_snapshot(
    *, feed: Any, news: Any | None, symbol: str = "XAUUSD"
) -> dict[str, Any]:
    """Shared snapshot (no per-user data), refreshed at most every 15 s."""
    hit = _SNAPSHOT_CACHE.get(symbol)
    if hit and time.monotonic() - hit[0] < _SNAPSHOT_TTL_S:
        return dict(hit[1])
    async with _SNAPSHOT_LOCK:
        hit = _SNAPSHOT_CACHE.get(symbol)
        if hit and time.monotonic() - hit[0] < _SNAPSHOT_TTL_S:
            return dict(hit[1])
        snap = await build_market_snapshot(feed=feed, news=news, symbol=symbol)
        _SNAPSHOT_CACHE[symbol] = (time.monotonic(), snap)
        return dict(snap)


def clear_snapshot_cache_for_tests() -> None:
    _SNAPSHOT_CACHE.clear()


# ------------------------------------------------------- trade conditions


def _cond(key: str, label: str, status: str, detail: str) -> dict[str, str]:
    return {"key": key, "label": label, "status": status, "detail": detail}


def trade_conditions(snap: dict[str, Any]) -> dict[str, Any]:
    """Deterministic checklist: is this a reasonable moment to trade gold?

    Each item is good / caution / avoid with the measured reason. This is a
    conditions read, not a signal: it never says buy or sell.
    """
    items: list[dict[str, str]] = []
    tfs = {t.get("timeframe"): t for t in snap.get("timeframes", [])}
    h1 = tfs.get("H1") or {}
    m15 = tfs.get("M15") or {}
    bias = snap.get("bias") or {}

    # 1. Trend alignment
    of = int(bias.get("of") or 0)
    aligned = int(bias.get("aligned") or 0)
    direction = str(bias.get("direction") or "unknown")
    if of == 0:
        items.append(
            _cond("trend", "Trend alignment", "caution", "Trend data unavailable.")
        )
    elif direction in {"bullish", "bearish"} and aligned == of:
        items.append(
            _cond(
                "trend", "Trend alignment", "good", f"All {of} timeframes {direction}."
            )
        )
    elif direction in {"bullish", "bearish"}:
        items.append(
            _cond(
                "trend",
                "Trend alignment",
                "caution",
                f"{aligned} of {of} timeframes {direction}; the rest disagree.",
            )
        )
    else:
        items.append(
            _cond(
                "trend",
                "Trend alignment",
                "avoid",
                "Timeframes conflict; no clear trend.",
            )
        )

    # 2. Momentum (H1 RSI)
    r = _f(h1.get("rsi14"))
    if r is None:
        items.append(
            _cond("momentum", "Momentum (H1 RSI)", "caution", "RSI unavailable.")
        )
    elif r >= 70 or r <= 30:
        side = "overbought" if r >= 70 else "oversold"
        items.append(
            _cond(
                "momentum",
                "Momentum (H1 RSI)",
                "caution",
                f"RSI {r:.1f} is {side}; chasing here risks a snap-back.",
            )
        )
    else:
        items.append(
            _cond(
                "momentum", "Momentum (H1 RSI)", "good", f"RSI {r:.1f}, not stretched."
            )
        )

    # 3. Room to the next level in the bias direction (in H1 ATR units)
    a = _f(h1.get("atr14"))
    price = _f(h1.get("last_close"))
    q = snap.get("quote") or {}
    bid, ask = _f(q.get("bid")), _f(q.get("ask"))
    if bid is not None and ask is not None:
        price = (bid + ask) / 2
    levels = snap.get("key_levels_h1") or {}
    target = None
    if direction == "bullish" and levels.get("resistances"):
        target = levels["resistances"][0]
    elif direction == "bearish" and levels.get("supports"):
        target = levels["supports"][0]
    if a and price is not None and target is not None:
        room = abs(float(target) - price) / a
        status = "good" if room >= 1.5 else "caution" if room >= 0.75 else "avoid"
        items.append(
            _cond(
                "room",
                "Room to next level",
                status,
                f"{room:.1f}x ATR to {float(target):.2f}.",
            )
        )
    else:
        items.append(
            _cond(
                "room",
                "Room to next level",
                "caution",
                "No clear level in the trend direction.",
            )
        )

    # 4. Volatility regime
    vol = snap.get("volatility_h1") or {}
    vstate = str(vol.get("state") or "unknown")
    vratio = vol.get("atr_vs_average")
    if vstate == "normal":
        items.append(
            _cond(
                "volatility", "Volatility", "good", f"Normal ({vratio}x average ATR)."
            )
        )
    elif vstate == "high":
        items.append(
            _cond(
                "volatility",
                "Volatility",
                "caution",
                f"High ({vratio}x average ATR); widen stops or size down.",
            )
        )
    elif vstate == "low":
        items.append(
            _cond(
                "volatility",
                "Volatility",
                "caution",
                f"Low ({vratio}x average ATR); breakouts may fail.",
            )
        )
    else:
        items.append(
            _cond("volatility", "Volatility", "caution", "Volatility unavailable.")
        )

    # 5. Spread cost vs M15 range
    spread = _f(q.get("spread"))
    m15_atr = _f(m15.get("atr14"))
    if spread is not None and m15_atr:
        pct = spread / m15_atr * 100
        status = "good" if pct < 10 else "caution" if pct < 25 else "avoid"
        items.append(
            _cond(
                "spread",
                "Spread cost",
                status,
                f"Spread {spread:.2f} = {pct:.0f}% of the M15 ATR.",
            )
        )
    else:
        items.append(_cond("spread", "Spread cost", "caution", "Spread unavailable."))

    # 6. High-impact news
    cal = snap.get("economic_calendar")
    upcoming = []
    if isinstance(cal, list):
        for e in cal:
            mins = e.get("minutes_from_now")
            if (
                isinstance(mins, int)
                and -15 <= mins <= 240
                and str(e.get("impact", "")).lower() in {"high", "3", "red"}
            ):
                upcoming.append((mins, str(e.get("title"))))
    if not isinstance(cal, list):
        items.append(
            _cond("news", "High-impact news", "caution", "Calendar unavailable.")
        )
    elif not upcoming:
        items.append(
            _cond(
                "news",
                "High-impact news",
                "good",
                "No high-impact event in the next 4 h.",
            )
        )
    else:
        mins, title = min(upcoming)
        when = "now" if mins <= 0 else f"in {mins} min"
        status = "avoid" if mins <= 60 else "caution"
        items.append(_cond("news", "High-impact news", status, f"{title} {when}."))

    # 7. Session liquidity
    session = str(snap.get("session") or "")
    if session.startswith("closed"):
        items.append(_cond("session", "Session", "avoid", "Market closed."))
    elif session in {"London-New York overlap", "London", "New York"}:
        items.append(_cond("session", "Session", "good", f"{session}: deep liquidity."))
    else:
        items.append(
            _cond("session", "Session", "caution", f"{session}: thinner liquidity.")
        )

    avoid = sum(1 for i in items if i["status"] == "avoid")
    caution = sum(1 for i in items if i["status"] == "caution")
    if avoid:
        verdict, tone = "Stand aside for now", "avoid"
    elif caution >= 2:
        verdict, tone = "Trade only with extra caution", "caution"
    elif caution:
        verdict, tone = "Conditions mostly supportive", "good"
    else:
        verdict, tone = "Conditions supportive", "good"
    good = sum(1 for i in items if i["status"] == "good")
    return {
        "verdict": verdict,
        "tone": tone,
        "score": round(good / len(items) * 100),
        "bias": direction,
        "items": items,
    }


# ------------------------------------------------------------------- prompt

INSTRUCTIONS = "\n".join(
    [
        "You are QuantForg AI, the market analyst inside QuantForg, an automated",
        "XAUUSD (gold) trading platform on MetaTrader 5. You talk to traders.",
        "",
        "DATA AND TRUTH",
        "- Live prices, indicators, levels, news and calendar come ONLY from the",
        "  LIVE_DATA JSON in the user's message, or from what is clearly visible",
        "  in an attached image. Never invent a number, level, event or headline.",
        "  If something is missing, say plainly that it is not available.",
        "- Copy numbers exactly and say which timeframe they come from.",
        "- All times in LIVE_DATA are UTC. Write times as e.g. 19:22 UTC.",
        "- Facts come first; label your interpretation as interpretation.",
        "  Markets are uncertain: no promises, no guaranteed outcomes.",
        "- You cannot see the user's account or trades unless they are in",
        "  LIVE_DATA. Never claim to have placed or changed a trade.",
        "- Never mention 'LIVE_DATA', 'JSON' or 'snapshot' to the user;",
        "  say 'live data' or 'the current market'.",
        "",
        "FORMAT (rendered as markdown)",
        "- Start with a one-line answer in bold (the bottom line).",
        "- Then 2-4 short sections with '### ' headings.",
        "- Bullets: one idea per bullet, max ~20 words. Nest at most one level",
        "  (indent sub-bullets with two spaces).",
        "- Use bold only for key numbers or labels, never for whole sentences.",
        "- No tables, no code blocks, no emojis, no filler.",
        "- Simple questions: answer in 2-5 lines, no headings.",
        "- Price questions: lead with price, trend, key support and resistance.",
        "",
        "CHART SCREENSHOTS",
        "When an image is attached, cover: instrument and timeframe (if",
        "readable), structure and trend, key levels visible on the chart,",
        "indicators shown, price action at the latest candle, a bullish and a",
        "bearish scenario each with what invalidates it, and where a stop would",
        "logically sit. If the chart is gold, compare it with the live price and",
        "say if the screenshot looks older than the live data.",
        "",
        "LANGUAGE",
        "Reply in the language of the user's latest message (Kinyarwanda,",
        "English, French, Swahili, ...). Keep trading terms (support,",
        "resistance, stop loss, RSI) in English when that is clearer.",
        "",
        "Trade ideas end with one short line: not financial advice.",
        "Never ask for or repeat passwords, keys or broker logins.",
    ]
)


def build_input(
    *,
    history: list[ChatTurn],
    message: str,
    images: list[str],
    snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for t in history:
        items.append(
            {
                "role": t.role,
                "content": [
                    {
                        "type": (
                            "output_text" if t.role == "assistant" else "input_text"
                        ),
                        "text": t.content,
                    }
                ],
            }
        )
    parts: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": "LIVE_DATA:\n"
            + json.dumps(snapshot, default=str, separators=(",", ":")),
        },
        {"type": "input_text", "text": message or "Analyze the attached chart."},
    ]
    for url in images:
        parts.append({"type": "input_image", "image_url": url, "detail": "high"})
    items.append({"role": "user", "content": parts})
    return items


# --------------------------------------------------------------------- chat


def assistant_client(settings: Any) -> Any | None:
    """OpenAI client for the assistant, or None when no key is configured."""
    import os

    from app.infrastructure.ai.openai_responses import OpenAIResponsesClient

    secret = getattr(settings, "openai_api_key", None)
    getter = getattr(secret, "get_secret_value", None)
    key = str(getter() if callable(getter) else (secret or "")).strip()
    if not key:
        return None
    model = (
        os.environ.get("OPENAI_ASSISTANT_MODEL")
        or getattr(settings, "openai_model", "")
        or "gpt-5.4-mini"
    )
    return OpenAIResponsesClient(
        api_key=key,
        model=model,
        base_url=getattr(settings, "openai_base_url", "")
        or "https://api.openai.com/v1",
        timeout_seconds=60.0,
        max_retries=1,
    )


_PROVIDER_MESSAGES = {
    "insufficient_quota": (
        "The AI provider account has no remaining credits. Please contact support."
    ),
    "auth_failed": "The AI provider rejected the platform key. Please contact support.",
    "rate_limited": "The AI service is busy. Please try again in a moment.",
    "timeout": "The AI took too long to answer. Please try again.",
}


def provider_message(code: str) -> str:
    return _PROVIDER_MESSAGES.get(
        code, "The AI service is unavailable right now. Please try again."
    )


def reasoning_for(images: list[str]) -> str:
    """Low effort for chat keeps answers fast; charts get more thought."""
    return "medium" if images else "low"


def snapshot_meta(snapshot: dict[str, Any]) -> dict[str, Any]:
    q = snapshot.get("quote") or {}
    return {
        "as_of_utc": snapshot.get("generated_at_utc"),
        "bid": q.get("bid"),
        "ask": q.get("ask"),
        "source": q.get("source"),
        "session": snapshot.get("session"),
        "bias": (snapshot.get("bias") or {}).get("direction"),
    }


async def chat(
    *,
    client: Any | None,
    history: list[ChatTurn],
    message: str,
    images: list[str],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    from app.infrastructure.ai.openai_responses import (
        OpenAIProviderError,
        extract_output_text,
    )

    if client is None:
        raise AssistantError(
            "assistant_unavailable", "The AI assistant is not configured yet.", 503
        )
    items = build_input(
        history=history, message=message, images=images, snapshot=snapshot
    )
    started = time.monotonic()
    try:
        payload = await client.create_response(
            input_text=items,
            instructions=INSTRUCTIONS,
            timeout_seconds=90.0 if images else 60.0,
            max_output_tokens=3000,
        )
    except OpenAIProviderError as exc:
        logger.warning("assistant_provider_error", code=exc.code)
        raise AssistantError(
            f"provider_{exc.code}", provider_message(exc.code), 503
        ) from exc
    text = extract_output_text(payload)
    logger.info(
        "assistant_answered",
        model=getattr(client, "model", ""),
        images=len(images),
        model_ms=round((time.monotonic() - started) * 1000),
        chars=len(text),
    )
    if not text:
        raise AssistantError(
            "empty_answer", "The AI returned no answer. Please try again.", 502
        )
    return {
        "answer": text,
        "model": getattr(client, "model", ""),
        "snapshot_at": snapshot.get("generated_at_utc"),
        "live_quote": snapshot.get("quote"),
        "meta": snapshot_meta(snapshot),
        "advisory_only": True,
    }


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def stream_chat(
    *,
    client: Any | None,
    history: list[ChatTurn],
    message: str,
    images: list[str],
    snapshot: dict[str, Any],
    streamer: Any | None = None,
) -> Any:
    """Server-sent events: ``meta`` → many ``delta`` → ``done`` (or ``error``)."""
    import httpx

    from app.infrastructure.ai.openai_responses import (
        OpenAIProviderError,
        stream_output_text,
    )

    yield _sse(
        "meta", {**snapshot_meta(snapshot), "model": getattr(client, "model", "")}
    )
    if client is None:
        yield _sse(
            "error",
            {
                "code": "assistant_unavailable",
                "message": "The AI assistant is not configured yet.",
            },
        )
        return
    stream = streamer or stream_output_text
    started = time.monotonic()
    first_ms: int | None = None
    chars = 0
    try:
        async for delta in stream(
            client,
            input_items=build_input(
                history=history, message=message, images=images, snapshot=snapshot
            ),
            instructions=INSTRUCTIONS,
            max_output_tokens=3000,
            reasoning_effort=reasoning_for(images),
            timeout_seconds=120.0 if images else 90.0,
        ):
            if first_ms is None:
                first_ms = round((time.monotonic() - started) * 1000)
            chars += len(delta)
            yield _sse("delta", {"text": delta})
    except OpenAIProviderError as exc:
        logger.warning("assistant_provider_error", code=exc.code)
        yield _sse(
            "error",
            {"code": f"provider_{exc.code}", "message": provider_message(exc.code)},
        )
        return
    except httpx.TimeoutException:
        yield _sse(
            "error",
            {"code": "provider_timeout", "message": provider_message("timeout")},
        )
        return
    except httpx.HTTPError:
        yield _sse(
            "error", {"code": "provider_outage", "message": provider_message("outage")}
        )
        return
    total_ms = round((time.monotonic() - started) * 1000)
    logger.info(
        "assistant_streamed",
        model=getattr(client, "model", ""),
        images=len(images),
        first_token_ms=first_ms,
        model_ms=total_ms,
        chars=chars,
    )
    if chars == 0:
        yield _sse(
            "error",
            {
                "code": "empty_answer",
                "message": "The AI returned no answer. Please try again.",
            },
        )
        return
    yield _sse("done", {"model": getattr(client, "model", ""), "ms": total_ms})
