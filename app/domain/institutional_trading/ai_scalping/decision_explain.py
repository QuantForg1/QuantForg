"""Explainable decision taxonomy — normalize WHY labels (no behavior change)."""

from __future__ import annotations

from typing import Any, Literal

ExplainAction = Literal[
    "BUY",
    "SELL",
    "HOLD",
    "NO_TRADE",
    "CLOSE",
    "PARTIAL",
    "MOVE_SL",
    "UNKNOWN",
]


def classify_explain_action(
    *,
    direction: str | None = None,
    reject: bool = False,
    decision_action: str | None = None,
    manage_action: str | None = None,
) -> ExplainAction:
    m = str(manage_action or "").strip().lower()
    if m in {"close", "flatten", "exit", "close_all"}:
        return "CLOSE"
    if m in {"partial", "partial_close", "scale_out"}:
        return "PARTIAL"
    if m in {"move_sl", "trail", "breakeven", "break_even", "modify_sl"}:
        return "MOVE_SL"
    d = str(decision_action or direction or "").strip().upper()
    if reject or d in {"", "NONE", "NO_TRADE", "HOLD", "WATCH", "SKIP"}:
        if d == "HOLD":
            return "HOLD"
        return "NO_TRADE"
    if d == "BUY":
        return "BUY"
    if d == "SELL":
        return "SELL"
    return "UNKNOWN"


def explain_decision(
    *,
    direction: str | None = None,
    reject: bool = False,
    reject_reason: str | None = None,
    reasons: list[str] | tuple[str, ...] | None = None,
    decision_action: str | None = None,
    manage_action: str | None = None,
    manage_reason: str | None = None,
) -> dict[str, Any]:
    """Return a structured WHY explanation from existing artefacts."""
    action = classify_explain_action(
        direction=direction,
        reject=reject,
        decision_action=decision_action,
        manage_action=manage_action,
    )
    why: list[str] = []
    if manage_reason:
        why.append(str(manage_reason))
    if reject_reason:
        why.append(str(reject_reason))
    for r in reasons or ():
        s = str(r).strip()
        if s and s not in why:
            why.append(s)
    if not why:
        if action == "BUY":
            why.append("Institutional AI selected BUY — all quality gates passed")
        elif action == "SELL":
            why.append("Institutional AI selected SELL — all quality gates passed")
        elif action == "NO_TRADE":
            why.append("No eligible institutional setup — NO_TRADE")
        elif action == "HOLD":
            why.append("Hold — no new entry / wait for confirmation")
        else:
            why.append(f"Action={action}")
    return {
        "action": action,
        f"why_{action.lower()}": why[0] if why else None,
        "why": why,
        "reject": reject,
        "direction": direction,
        "decision_action": decision_action,
        "manage_action": manage_action,
    }
