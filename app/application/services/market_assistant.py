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


async def _safe(coro: Any, limit_s: float) -> Any:
    try:
        return await asyncio.wait_for(coro, timeout=limit_s)
    except Exception as exc:  # feeds are optional; record absence, not errors
        logger.info(
            "assistant_snapshot_part_unavailable", error_type=type(exc).__name__
        )
        return None


async def build_market_snapshot(
    *,
    feed: Any,
    news: Any | None,
    symbol: str = "XAUUSD",
    risk_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tick_b, m15, h1, h4 = await asyncio.gather(
        _safe(feed.tick(symbol=symbol), 6),
        _safe(feed.candles(symbol=symbol, timeframe="M15", count=120), 8),
        _safe(feed.candles(symbol=symbol, timeframe="H1", count=150), 8),
        _safe(feed.candles(symbol=symbol, timeframe="H4", count=120), 8),
    )
    snap: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "symbol": symbol,
    }
    tick = getattr(tick_b, "tick", None) if tick_b is not None else None
    if tick is not None:
        bid, ask = _f(getattr(tick, "bid", None)), _f(getattr(tick, "ask", None))
        snap["quote"] = {
            "bid": bid,
            "ask": ask,
            "spread": (
                round(ask - bid, 2) if bid is not None and ask is not None else None
            ),
            "source": getattr(tick_b, "source", ""),
            "status": getattr(tick_b, "status", ""),
            "as_of": getattr(tick_b, "as_of", ""),
            "market_open": getattr(tick_b, "market_open", None),
        }
    else:
        snap["quote"] = {
            "available": False,
            "note": "Live quote unavailable right now.",
        }

    snap["timeframes"] = [
        (
            summarize_candles(list(getattr(b, "candles", []) or []), tf)
            if b is not None
            else {"timeframe": tf, "available": False}
        )
        for b, tf in ((m15, "M15"), (h1, "H1"), (h4, "H4"))
    ]

    if news is not None:
        try:
            headlines = news.news(limit=6)
            snap["news"] = [
                {
                    "title": n.title,
                    "source": n.source,
                    "published_at": str(n.published_at),
                }
                for n in headlines
            ]
        except Exception:
            snap["news"] = "unavailable"
        try:
            events = news.economic_events(limit=8)
            snap["economic_calendar"] = [
                {
                    "title": e.title,
                    "country": e.country,
                    "impact": e.impact,
                    "scheduled_at": str(e.scheduled_at),
                    "forecast": e.forecast,
                    "previous": e.previous,
                    "actual": e.actual,
                }
                for e in events
            ]
        except Exception:
            snap["economic_calendar"] = "unavailable"
    if risk_settings:
        snap["user_risk_settings"] = risk_settings
    return snap


# ------------------------------------------------------------------- prompt

INSTRUCTIONS = "\n".join(
    [
        (
            "You are QuantForg AI, the trading assistant inside the QuantForg "
            "platform (an automated XAUUSD/gold trading robot on MetaTrader 5). You"
            " help traders understand the market, read charts, plan risk and use "
            "the platform."
        ),
        "",
        "TRUTHFULNESS (most important):",
        (
            "- Live prices, indicator values, news and calendar events come ONLY "
            "from the LIVE_SNAPSHOT JSON below or from what is clearly visible in "
            "an attached image. Never invent a price, level, indicator value, news "
            "item or event. If something is missing, say it is not available."
        ),
        (
            "- Quote numbers exactly as given; say which timeframe they come from. "
            "Mention the snapshot time when you talk about the current price."
        ),
        (
            "- If a chart screenshot conflicts with the live snapshot (e.g. older "
            "screenshot), say so and explain which is newer."
        ),
        (
            "- Separate facts (from data) from your interpretation. Express "
            "uncertainty honestly; markets are probabilistic. Never promise profit "
            "or guaranteed outcomes."
        ),
        (
            "- You cannot see the user's account, trades or the robot's internals "
            "unless they are in the snapshot. Do not pretend otherwise."
        ),
        "",
        "CHART SCREENSHOT ANALYSIS (when an image is attached):",
        (
            "1. Identify instrument, timeframe and visible time range if readable "
            "(say if not readable)."
        ),
        "2. Market structure and trend (higher highs/lows, ranges, breakouts).",
        (
            "3. Key support/resistance zones, liquidity areas and the levels "
            "visible on the chart."
        ),
        "4. Indicators visible on the chart and what they show.",
        "5. Candlestick/price-action context near the current price.",
        (
            "6. Scenarios: bullish case, bearish case, and what would invalidate "
            "each."
        ),
        (
            "7. Risk notes: where a stop would logically sit, approximate reward-"
            "to-risk, news risk."
        ),
        "Combine with LIVE_SNAPSHOT for the real current price when it is gold.",
        "",
        "STYLE:",
        (
            "- Reply in the user's language (Kinyarwanda, English, French, "
            "Swahili…). Match their language exactly."
        ),
        (
            "- Be clear and structured: short headings, bullets, key numbers in "
            "bold. Be concise for simple questions, thorough for analysis."
        ),
        (
            "- Educational/advisory only. You cannot place, modify or close trades,"
            " and you must not claim to. End trade-idea answers with one short line"
            " that this is not financial advice."
        ),
        (
            "- Never ask for or repeat passwords, API keys, broker logins or other "
            "credentials."
        ),
        "",
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
            "text": "LIVE_SNAPSHOT:\n"
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
    from app.infrastructure.ai.openai_responses import OpenAIResponsesClient

    secret = getattr(settings, "openai_api_key", None)
    getter = getattr(secret, "get_secret_value", None)
    key = str(getter() if callable(getter) else (secret or "")).strip()
    if not key:
        return None
    import os

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
    try:
        payload = await client.create_response(
            input_text=items,
            instructions=INSTRUCTIONS,
            timeout_seconds=90.0 if images else 60.0,
            max_output_tokens=2500,
        )
    except OpenAIProviderError as exc:
        logger.warning("assistant_provider_error", code=exc.code)
        raise AssistantError(
            f"provider_{exc.code}",
            _PROVIDER_MESSAGES.get(
                exc.code, "The AI service is unavailable right now. Please try again."
            ),
            503,
        ) from exc
    text = extract_output_text(payload)
    if not text:
        raise AssistantError(
            "empty_answer", "The AI returned no answer. Please try again.", 502
        )
    return {
        "answer": text,
        "model": getattr(client, "model", ""),
        "snapshot_at": snapshot.get("generated_at_utc"),
        "live_quote": snapshot.get("quote"),
        "advisory_only": True,
    }
