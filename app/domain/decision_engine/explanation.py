"""Decision Engine — explainable WHY / failure / invalidation."""

from __future__ import annotations

from typing import Any


def build_explanation(
    *,
    decision: str,
    score: dict[str, Any],
    mtf: dict[str, Any],
    structure: dict[str, Any],
    risk: dict[str, Any],
    news_risk: str,
) -> dict[str, Any]:
    why_exists = list(score.get("supporting_factors") or [])
    if mtf.get("aligned"):
        why_exists.append(str(mtf.get("why")))
    if structure.get("why"):
        why = structure["why"]
        if isinstance(why, dict):
            why_exists.extend(list(why.get("supporting_factors") or [])[:3])

    may_fail = list(score.get("penalties") or [])
    if news_risk != "low":
        may_fail.append("News headline shock can invalidate structure abruptly")
    if risk.get("warnings"):
        may_fail.extend([str(w) for w in risk["warnings"]])
    may_fail.append("Spread widening / liquidity vacuum around session rolls")

    invalidates = [
        "MTF alignment breaks (H1/H4/D1 diverge)",
        "Price closes beyond suggested stop distance",
        "High-impact calendar event enters window",
        "Portfolio heat turns hot or daily loss limit hit",
    ]
    if structure.get("support") and mtf.get("bias") == "Bullish":
        invalidates.append(f"Breakdown below support {structure.get('support')}")
    if structure.get("resistance") and mtf.get("bias") == "Bearish":
        invalidates.append(f"Break above resistance {structure.get('resistance')}")

    improves = [
        "Wait for higher-TF pullback into structure with tighter spread",
        "Confirm session liquidity (London/NY overlap preferred)",
        "Reduce correlated open exposure before adding risk",
        "Require confidence ≥ threshold with stable execution latency",
    ]
    if decision == "WAIT":
        improves.insert(
            0, "Do nothing until score and MTF gates clear — capital preservation"
        )

    return {
        "why_it_exists": why_exists or ["No strong constructive factors"],
        "why_it_may_fail": may_fail or ["Residual market uncertainty"],
        "what_invalidates_it": invalidates,
        "what_would_improve_it": improves,
        "summary": (
            "WAIT — insufficient edge / confirmations"
            if decision == "WAIT"
            else "TRADE_IDEA — advisory only; paper by default; never auto-sent"
        ),
    }
