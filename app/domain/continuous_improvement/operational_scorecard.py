"""Executive operational scorecard across seven categories."""

from __future__ import annotations

from typing import Any

from app.domain.continuous_improvement.models import SCORECARD_CATEGORIES
from app.domain.continuous_improvement.persistence import utc_iso


def _score_from_ratio(ratio: float | None) -> float | None:
    if ratio is None:
        return None
    return round(max(0.0, min(100.0, ratio * 100.0)), 1)


def _category(
    name: str,
    score: float | None,
    status: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "category": name,
        "score": score,
        "status": status,
        "evidence": evidence,
        "fabricated": False,
    }


def build_operational_scorecard(
    *,
    validation: dict[str, Any],
    trading: dict[str, Any],
    release: dict[str, Any],
    learning: dict[str, Any],
) -> dict[str, Any]:
    categories: dict[str, dict[str, Any]] = {}

    # Reliability / availability from validation ok ratio
    ok = validation.get("ok_count")
    total = validation.get("target_count") or 1
    try:
        ratio = float(ok) / float(total) if ok is not None else None
    except (TypeError, ValueError):
        ratio = None
    rel_score = _score_from_ratio(ratio)
    categories["reliability"] = _category(
        "reliability",
        rel_score,
        validation.get("overall") or "unknown",
        {"ok_count": ok, "target_count": total},
    )
    categories["availability"] = _category(
        "availability",
        rel_score,
        validation.get("overall") or "unknown",
        {"ok_ratio": ratio},
    )

    # Security — observe-only from sync security_ops (best-effort)
    try:
        from app.domain.production_reliability.security_ops import (
            build_security_ops,
        )

        sec = build_security_ops()
        alerts = int(sec.get("alert_count") or 0)
        sec_score = round(max(0.0, 100.0 - min(alerts, 20) * 5), 1)
        sec_status = "ok" if alerts == 0 else "watch"
        categories["security"] = _category(
            "security",
            sec_score,
            sec_status,
            {
                "alert_count": alerts,
                "failed_auth_count": sec.get("failed_auth_count"),
            },
        )
    except Exception:
        categories["security"] = _category(
            "security", None, "unknown", {"note": "unavailable"}
        )

    # Trading — only when measured fields exist
    measured = int(trading.get("measured_count") or 0)
    wr = trading.get("win_rate")
    pf = trading.get("profit_factor")
    trade_score: float | None = None
    if measured > 0:
        parts: list[float] = []
        if wr is not None:
            parts.append(max(0.0, min(100.0, float(wr) * 100.0)))
        if pf is not None:
            parts.append(max(0.0, min(100.0, min(float(pf), 3.0) / 3.0 * 100.0)))
        trade_score = round(sum(parts) / len(parts), 1) if parts else None
    categories["trading"] = _category(
        "trading",
        trade_score,
        "measured" if measured else "unmeasured",
        {
            "measured_count": measured,
            "win_rate": wr,
            "profit_factor": pf,
            "expectancy": trading.get("expectancy"),
        },
    )

    # Operations — release confidence + learning recommendations count
    conf = str(release.get("confidence") or "unknown")
    ops_map = {"high": 90.0, "medium": 65.0, "low": 35.0, "unknown": None}
    categories["operations"] = _category(
        "operations",
        ops_map.get(conf),
        conf,
        {
            "deployments": release.get("deployment_count"),
            "rollbacks": release.get("rollback_count"),
            "open_incidents": (release.get("production_incidents") or {}).get("open"),
        },
    )

    # Support — COP presence from validation component
    cop = (validation.get("components") or {}).get("customer_operations") or {}
    categories["support"] = _category(
        "support",
        80.0 if cop.get("ok") else None,
        str(cop.get("status") or "unknown"),
        {"customer_operations": cop.get("status")},
    )

    # Enterprise
    ent = (validation.get("components") or {}).get("enterprise_platform") or {}
    categories["enterprise"] = _category(
        "enterprise",
        80.0 if ent.get("ok") else None,
        str(ent.get("status") or "unknown"),
        {"enterprise_platform": ent.get("status")},
    )

    scores = [
        c["score"]
        for c in categories.values()
        if isinstance(c.get("score"), (int, float))
    ]
    overall = round(sum(scores) / len(scores), 1) if scores else None

    # Ensure all categories present
    for name in SCORECARD_CATEGORIES:
        categories.setdefault(
            name, _category(name, None, "unknown", {"note": "missing"})
        )

    return {
        "as_of": utc_iso(),
        "overall_score": overall,
        "categories": {k: categories[k] for k in SCORECARD_CATEGORIES},
        "learning_recommendation_count": len(learning.get("recommendations") or []),
        "fabricated": False,
        "observe_only": True,
    }
