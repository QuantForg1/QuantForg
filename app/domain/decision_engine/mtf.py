"""Decision Engine — multi-timeframe confirmation from real structure briefs."""

from __future__ import annotations

from typing import Any


REQUIRED_TFS = ("M5", "M15", "H1", "H4", "D1")


def summarize_mtf(frames: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Require bullish/bearish agreement across higher TFs before idea eligibility."""
    available: dict[str, dict[str, Any]] = {}
    for tf in REQUIRED_TFS:
        brief = frames.get(tf) or {}
        if brief.get("status") == "available":
            available[tf] = brief

    if len(available) < 3:
        return {
            "status": "insufficient",
            "aligned": False,
            "bias": "Neutral",
            "confirmations": 0,
            "required": 3,
            "frames": {tf: frames.get(tf, {}).get("trend") for tf in REQUIRED_TFS},
            "why": "Need at least 3 timeframes with real OHLC for confirmation",
        }

    trends = [str(available[tf].get("trend") or "Neutral") for tf in available]
    bullish = sum(1 for t in trends if t == "Bullish")
    bearish = sum(1 for t in trends if t == "Bearish")
    # Higher-TF weight: H1/H4/D1 must mostly agree
    higher = [str((available.get(tf) or {}).get("trend") or "Neutral") for tf in ("H1", "H4", "D1") if tf in available]
    higher_bull = sum(1 for t in higher if t == "Bullish")
    higher_bear = sum(1 for t in higher if t == "Bearish")

    bias = "Neutral"
    confirmations = 0
    if higher_bull >= 2 and bullish >= bearish:
        bias = "Bullish"
        confirmations = bullish
    elif higher_bear >= 2 and bearish >= bullish:
        bias = "Bearish"
        confirmations = bearish

    aligned = bias != "Neutral" and confirmations >= 3 and (
        (bias == "Bullish" and higher_bull >= 2) or (bias == "Bearish" and higher_bear >= 2)
    )

    return {
        "status": "available",
        "aligned": aligned,
        "bias": bias,
        "confirmations": confirmations,
        "required": 3,
        "higher_tf_agreement": {
            "bullish": higher_bull,
            "bearish": higher_bear,
            "sample": higher,
        },
        "frames": {
            tf: {
                "trend": (frames.get(tf) or {}).get("trend"),
                "momentum": (frames.get(tf) or {}).get("momentum"),
                "confidence_pct": (frames.get(tf) or {}).get("confidence_pct"),
                "status": (frames.get(tf) or {}).get("status"),
            }
            for tf in REQUIRED_TFS
        },
        "why": (
            f"MTF {bias.lower()} with {confirmations} confirmations"
            if aligned
            else "MTF not aligned — prefer WAIT"
        ),
    }
