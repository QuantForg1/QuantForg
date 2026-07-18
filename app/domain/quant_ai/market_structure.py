"""Quant AI — explainable market structure from real OHLC only."""

from __future__ import annotations

from typing import Any


def _closes(candles: list[dict[str, Any]]) -> list[float]:
    out: list[float] = []
    for c in candles:
        try:
            out.append(float(c.get("close") or c.get("c") or 0))
        except (TypeError, ValueError):
            continue
    return out


def _ema(series: list[float], period: int) -> float | None:
    if len(series) < period or period < 1:
        return None
    k = 2 / (period + 1)
    ema = sum(series[:period]) / period
    for v in series[period:]:
        ema = v * k + ema * (1 - k)
    return ema


def _atr(candles: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    trs: list[float] = []
    for i in range(1, len(candles)):
        try:
            h = float(candles[i].get("high") or candles[i].get("h") or 0)
            low = float(candles[i].get("low") or candles[i].get("l") or 0)
            pc = float(candles[i - 1].get("close") or candles[i - 1].get("c") or 0)
        except (TypeError, ValueError):
            continue
        trs.append(max(h - low, abs(h - pc), abs(low - pc)))
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def analyze_symbol_structure(
    *,
    symbol: str,
    candles: list[dict[str, Any]],
    bid: float | None = None,
    ask: float | None = None,
    session: str | None = None,
) -> dict[str, Any]:
    """Trend / momentum / S/R / regime with human-readable reasons.

    Never invent quotes.
    """
    closes = _closes(candles)
    if len(closes) < 30:
        return {
            "status": "unavailable",
            "symbol": symbol.upper(),
            "reason": "Insufficient real OHLC history for structural analysis",
            "data_source": "mt5_candles",
            "autonomous_trading": False,
        }

    price = closes[-1]
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    ema200 = _ema(closes, min(200, len(closes)))
    atr = _atr(candles, 14)

    reasons: list[str] = []
    confidence = 0.45
    trend = "Neutral"

    if ema200 is not None:
        if price > ema200:
            trend = "Bullish"
            reasons.append(f"Price above {min(200, len(closes))}-period EMA")
            confidence += 0.12
        else:
            trend = "Bearish"
            reasons.append(f"Price below {min(200, len(closes))}-period EMA")
            confidence += 0.12

    recent = closes[-12:]
    higher_highs = all(
        recent[i] >= recent[i - 1] - 1e-12 for i in range(1, len(recent) // 2 + 1)
    )
    higher_lows = len(recent) >= 6 and recent[-1] > recent[-6]
    lower_highs = all(
        recent[i] <= recent[i - 1] + 1e-12 for i in range(1, len(recent) // 2 + 1)
    )

    if trend == "Bullish" and higher_lows:
        reasons.append("Higher lows on recent swings")
        confidence += 0.1
    if trend == "Bearish" and not higher_lows:
        reasons.append("Lower / flat recent swings")
        confidence += 0.08
    if higher_highs and trend == "Bullish":
        reasons.append("Sequence of higher highs")
        confidence += 0.08
    if lower_highs and trend == "Bearish":
        reasons.append("Sequence of lower highs")
        confidence += 0.08

    momentum = "Balanced"
    if ema20 is not None and ema50 is not None:
        if ema20 > ema50:
            momentum = "Strong up"
            reasons.append("20 EMA above 50 EMA (momentum alignment)")
            confidence += 0.08
        elif ema20 < ema50:
            momentum = "Strong down"
            reasons.append("20 EMA below 50 EMA (momentum alignment)")
            confidence += 0.08

    window = closes[-20:]
    vol_pct = (max(window) - min(window)) / price * 100 if price else 0
    if vol_pct > 1.5:
        volatility = "High"
        reasons.append(f"20-bar range {vol_pct:.2f}% of price")
    elif vol_pct < 0.35:
        volatility = "Low"
        reasons.append(f"Compressed 20-bar range {vol_pct:.2f}%")
    else:
        volatility = "Moderate"
        reasons.append(f"20-bar range {vol_pct:.2f}% of price")

    lookback = candles[-50:] if len(candles) >= 50 else candles
    highs = [float(c.get("high") or c.get("h") or 0) for c in lookback]
    lows = [float(c.get("low") or c.get("l") or 0) for c in lookback]
    resistance = max(highs) if highs else None
    support = min(lows) if lows else None

    spread = None
    spread_ok = None
    if bid is not None and ask is not None and ask >= bid:
        spread = ask - bid
        spread_ok = spread <= (atr * 0.15 if atr else spread)
        if spread_ok:
            reasons.append(f"Observed spread {spread:.5f} within ATR tolerance")
            confidence += 0.05
        else:
            reasons.append(f"Observed spread {spread:.5f} elevated vs ATR")
            confidence -= 0.05

    if session:
        reasons.append(f"Session context: {session}")

    risk = "Moderate"
    if volatility == "High" or (spread_ok is False):
        risk = "Elevated"
    elif volatility == "Low" and trend != "Neutral":
        risk = "Controlled"

    suggested_sl = None
    suggested_tp = None
    if atr and price:
        if trend == "Bullish":
            suggested_sl = round(price - 1.5 * atr, 5)
            suggested_tp = round(price + 2.5 * atr, 5)
        elif trend == "Bearish":
            suggested_sl = round(price + 1.5 * atr, 5)
            suggested_tp = round(price - 2.5 * atr, 5)

    confidence = max(0.05, min(0.95, confidence))

    return {
        "status": "available",
        "symbol": symbol.upper(),
        "trend": trend,
        "confidence": round(confidence, 4),
        "confidence_pct": round(confidence * 100, 1),
        "momentum": momentum,
        "volatility": volatility,
        "market_regime": (
            "Trending"
            if trend != "Neutral" and momentum.startswith("Strong")
            else "Range / mixed"
        ),
        "support": support,
        "resistance": resistance,
        "liquidity_zones": {
            "near_support": support,
            "near_resistance": resistance,
            "note": "Derived from recent swing extremes on real candles",
        },
        "session": session,
        "spread": spread,
        "atr": atr,
        "price": price,
        "ema": {"ema20": ema20, "ema50": ema50, "ema200": ema200},
        "risk": risk,
        "suggested_stop": suggested_sl,
        "suggested_tp": suggested_tp,
        "reasons": reasons,
        "why": {
            "summary": (
                f"{symbol.upper()} {trend.lower()} with "
                f"{round(confidence * 100)}% confidence"
            ),
            "supporting_factors": reasons,
        },
        "data_source": "mt5_candles|mt5_ticks",
        "autonomous_trading": False,
        "advisory_only": True,
    }
