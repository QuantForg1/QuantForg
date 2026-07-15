"""Research Lab — market regime classification from live structure + context."""

from __future__ import annotations

from typing import Any


def classify_regime(
    *,
    structure: dict[str, Any] | None,
    market_context: dict[str, Any] | None = None,
    news_risk: str | None = None,
) -> dict[str, Any]:
    """Classify regime from real analysis inputs — never invents quotes."""
    structure = structure or {}
    market_context = market_context or {}
    if structure.get("status") == "unavailable":
        return {
            "status": "unavailable",
            "reason": "Insufficient structure for regime classification",
            "regimes": [],
        }

    regimes: list[str] = []
    evidence: list[str] = []

    mr = str(structure.get("market_regime") or "")
    trend = str(structure.get("trend") or "Neutral")
    vol = str(structure.get("volatility") or "")
    momentum = str(structure.get("momentum") or "")

    if mr.startswith("Trending") or (
        trend in {"Bullish", "Bearish"} and momentum.startswith("Strong")
    ):
        regimes.append("Trending")
        evidence.append(f"Structure regime/trend={mr or trend}")
    if mr.startswith("Range") or trend == "Neutral":
        regimes.append("Range")
        evidence.append("Neutral / mixed structure")
    if vol == "High":
        regimes.append("High Volatility")
        evidence.append("High 20-bar volatility")
    if vol == "Low":
        regimes.append("Low Volatility")
        evidence.append("Compressed volatility")
    if news_risk in {"high", "moderate"}:
        regimes.append("News Driven")
        evidence.append(f"News risk={news_risk}")
    if "mean" in momentum.lower() or (vol == "Low" and trend == "Neutral"):
        regimes.append("Mean Reversion")
        evidence.append("Mean-reversion friendly tape")

    # Session context enrichment (not a regime alone)
    session = market_context.get("session")
    if session:
        evidence.append(f"Session={session}")

    # Deduplicate preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for r in regimes:
        if r not in seen:
            seen.add(r)
            ordered.append(r)

    primary = ordered[0] if ordered else "Unknown"
    return {
        "status": "available" if ordered else "unavailable",
        "primary": primary,
        "regimes": ordered,
        "evidence": evidence,
        "advisory_only": True,
    }


def strategy_regime_fit(
    strategy: dict[str, Any], regime: dict[str, Any]
) -> dict[str, Any]:
    best = list(strategy.get("best_regimes") or [])
    active = list(regime.get("regimes") or [])
    overlap = [
        r
        for r in best
        if any(r.lower() in a.lower() or a.lower() in r.lower() for a in active)
    ]
    score = round(len(overlap) / max(len(best), 1), 4) if best else None
    return {
        "strategy_key": strategy.get("key"),
        "best_regimes": best,
        "active_regimes": active,
        "overlap": overlap,
        "fit_score": score,
        "suitable": bool(overlap),
    }
