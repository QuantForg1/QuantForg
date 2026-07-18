"""Performance Coach — advisory review from supplied trade records only."""

from __future__ import annotations

from typing import Any


def coach_from_trades(
    trades: list[dict[str, Any]], *, limit: int = 100
) -> dict[str, Any]:
    """Review up to last N trades — never invents fills or bypasses Decision Engine."""
    sample = list(trades)[:limit]
    if not sample:
        return {
            "status": "unavailable",
            "reason": "No paper/journal trades available for coaching",
            "sample_size": 0,
            "advisory_only": True,
            "never_auto_submits": True,
            "decision_engine_gatekeeper": True,
        }

    wins = 0
    losses = 0
    pnls: list[float] = []
    emotions_bad = 0
    no_lesson = 0
    skipped_de = 0
    tags_miss: dict[str, int] = {}

    for t in sample:
        pnl = t.get("pnl")
        try:
            p = float(pnl) if pnl is not None else None
        except (TypeError, ValueError):
            p = None
        if p is not None:
            pnls.append(p)
            if p > 0:
                wins += 1
            elif p < 0:
                losses += 1
        emo = str(t.get("emotion") or "").lower()
        if emo in {"fear", "revenge", "fomo", "tilt"}:
            emotions_bad += 1
        if not (t.get("lessons_learned") or "").strip():
            no_lesson += 1
        if t.get("decision_engine_score") is None:
            skipped_de += 1
        for tag in t.get("tags") or []:
            tags_miss[str(tag)] = tags_miss.get(str(tag), 0) + 1

    n = len(sample)
    wr = round(100.0 * wins / n, 1) if n else None
    mistakes: list[str] = []
    habits: list[str] = []
    weaknesses: list[str] = []
    suggestions: list[str] = []

    if emotions_bad >= max(2, n // 10):
        mistakes.append(
            f"Emotional markers on {emotions_bad}/{n} reviews — pause after losses"
        )
        weaknesses.append("Tilt / FOMO risk under stress")
        suggestions.append("Add playbook checklist: wait 5 minutes after a loss")
    if no_lesson >= max(3, n // 5):
        mistakes.append(f"{no_lesson} entries missing lessons learned")
        suggestions.append("Require a one-line lesson before closing the journal card")
    if skipped_de >= max(3, n // 4):
        mistakes.append(f"{skipped_de}/{n} trades lack Decision Engine score linkage")
        suggestions.append(
            "Only size risk when Decision Engine allows PAPER TRADE_IDEA "
            "— never bypass"
        )
    else:
        habits.append(
            "Decision Engine scores frequently attached — good gatekeeper hygiene"
        )

    if wr is not None and wr >= 55:
        habits.append(f"Win rate {wr}% across coached sample")
    elif wr is not None and wr < 40:
        weaknesses.append(f"Win rate {wr}% — edge must come from RR / selection")
        suggestions.append("Review Research Lab candidates before increasing size")

    if wins + losses >= 10 and losses > wins * 1.5:
        weaknesses.append("Loss frequency dominates sample")
        suggestions.append("Tighten session playbook — fewer setups, higher quality")

    if not habits:
        habits.append(
            "Continuing to journal is a productive habit — keep tagging session"
        )
    if not mistakes:
        mistakes.append("No acute pattern from available fields — keep sample growing")
    if not suggestions:
        suggestions.append(
            "Maintain paper-first validation via Research Lab + Decision Engine"
        )

    return {
        "status": "available",
        "sample_size": n,
        "win_rate_pct": wr,
        "wins": wins,
        "losses": losses,
        "common_mistakes": mistakes,
        "good_habits": habits,
        "weaknesses": weaknesses,
        "improvement_suggestions": suggestions,
        "top_tags": sorted(tags_miss.items(), key=lambda x: -x[1])[:8],
        "advisory_only": True,
        "never_auto_submits": True,
        "never_bypasses_decision_engine": True,
        "autonomous_trading": False,
    }
