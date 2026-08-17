"""Change isolation — smallest-change principle for alpha promotions."""

from __future__ import annotations

from typing import Any


ALLOWED_CHANGE_KINDS = frozenset(
    {
        "strategy",
        "model",
        "threshold",
        "feature",
        "parameter",
        "ranking_logic",
    }
)


def validate_change_isolation(change: dict[str, Any]) -> dict[str, Any]:
    kinds = change.get("kinds") or change.get("changed") or []
    if isinstance(kinds, str):
        kinds = [kinds]
    kinds_t = tuple(str(k) for k in kinds)
    unknown = [k for k in kinds_t if k not in ALLOWED_CHANGE_KINDS]
    unrelated = bool(change.get("includes_unrelated_refactor"))
    ok = bool(kinds_t) and not unknown and not unrelated
    return {
        "ok": ok,
        "kinds": list(kinds_t),
        "unknown_kinds": unknown,
        "includes_unrelated_refactor": unrelated,
        "why_blocked": None
        if ok
        else (
            "unrelated_refactor"
            if unrelated
            else ("missing_kinds" if not kinds_t else "unknown_kinds")
        ),
    }
