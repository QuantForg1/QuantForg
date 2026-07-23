"""IRL promotion policy — Research Passed / Failed ONLY.

NEVER auto-promotes into production. Governance workflow remains external.
"""

from __future__ import annotations

from typing import Any

from app.domain.institutional_research_lab.models import ResearchVerdict


DEFAULT_GATES: dict[str, Any] = {
    "min_trades": 20,
    "min_profit_factor": 1.2,
    "min_expectancy": 0.0,
    "max_drawdown_pct": 20.0,
    "min_consistency": 45.0,
    "min_walk_forward": 45.0,
    "min_confidence": 40.0,
}


def evaluate_research_verdict(
    *,
    statistics: dict[str, Any] | None,
    significance: dict[str, Any] | None,
    gates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    g = {**DEFAULT_GATES, **(gates or {})}
    stats = statistics or {}
    sig = significance or {}
    fails: list[str] = []

    trades = int(stats.get("total_trades") or 0)
    if trades < int(g["min_trades"]):
        fails.append("insufficient sample size")
    pf = stats.get("profit_factor")
    if pf is None or float(pf) < float(g["min_profit_factor"]):
        fails.append("profit factor below research gate")
    exp = stats.get("expectancy")
    if exp is None or float(exp) < float(g["min_expectancy"]):
        fails.append("expectancy below research gate")
    dd = stats.get("maximum_drawdown_pct")
    if dd is not None and float(dd) > float(g["max_drawdown_pct"]):
        fails.append("drawdown above research gate")
    if float(sig.get("consistency_score") or 0) < float(g["min_consistency"]):
        fails.append("consistency below research gate")
    if float(sig.get("walk_forward_score") or 0) < float(g["min_walk_forward"]):
        fails.append("walk-forward below research gate")
    if float(sig.get("confidence") or 0) < float(g["min_confidence"]):
        fails.append("confidence below research gate")

    passed = len(fails) == 0 and trades > 0
    return {
        "verdict": (
            ResearchVerdict.RESEARCH_PASSED.value
            if passed
            else ResearchVerdict.RESEARCH_FAILED.value
        ),
        "passed": passed,
        "fails": fails,
        "gates": g,
        "never_auto_promotes": True,
        "promotion_requires_governance_workflow": True,
        "note": (
            "Even when Research Passed, promotion continues only through "
            "the existing governance workflow — IRL never applies live thresholds."
        ),
    }
