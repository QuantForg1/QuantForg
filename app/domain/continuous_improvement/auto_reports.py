"""Automatic operational reports from production evidence only."""

from __future__ import annotations

import contextlib
from typing import Any

from app.domain.continuous_improvement.persistence import (
    JsonDocumentStore,
    new_id,
    utc_iso,
)

_store = JsonDocumentStore("auto_reports.json", "reports")


def _pack(
    period: str,
    *,
    validation: dict[str, Any],
    trading: dict[str, Any],
    learning: dict[str, Any],
    release: dict[str, Any],
    scorecard: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": f"ci_rpt_{period}",
        "period": period,
        "as_of": utc_iso(),
        "validation_overall": validation.get("overall"),
        "validation_ok": validation.get("ok_count"),
        "validation_targets": validation.get("target_count"),
        "trading": {
            "signals_generated": trading.get("signals_generated"),
            "signals_rejected": trading.get("signals_rejected"),
            "signals_approved": trading.get("signals_approved"),
            "trades_opened": trading.get("trades_opened"),
            "trades_closed": trading.get("trades_closed"),
            "win_rate": trading.get("win_rate"),
            "profit_factor": trading.get("profit_factor"),
            "expectancy": trading.get("expectancy"),
            "measured_count": trading.get("measured_count"),
        },
        "learning": {
            "success_patterns": len(learning.get("top_success_patterns") or []),
            "failure_patterns": len(learning.get("top_failure_patterns") or []),
            "blocking_gates": len(learning.get("most_common_blocking_gates") or []),
            "recommendations": len(learning.get("recommendations") or []),
        },
        "release_confidence": release.get("confidence"),
        "scorecard_overall": scorecard.get("overall_score"),
        "fabricated": False,
        "observe_only": True,
        "evidence_only": True,
    }


def _upsert(pack: dict[str, Any]) -> None:
    doc_id = str(pack.get("id") or new_id("rpt"))

    def mutator(_row: dict[str, Any]) -> dict[str, Any]:
        updated = dict(pack)
        updated["id"] = doc_id
        return updated

    if _store.get(doc_id) is None:
        _store.append({**pack, "id": doc_id})
    else:
        _store.upsert(doc_id, mutator)


def build_auto_reports(
    *,
    validation: dict[str, Any],
    trading: dict[str, Any],
    learning: dict[str, Any],
    release: dict[str, Any],
    scorecard: dict[str, Any],
) -> dict[str, Any]:
    daily = _pack(
        "daily_production_summary",
        validation=validation,
        trading=trading,
        learning=learning,
        release=release,
        scorecard=scorecard,
    )
    weekly = _pack(
        "weekly_executive_summary",
        validation=validation,
        trading=trading,
        learning=learning,
        release=release,
        scorecard=scorecard,
    )
    monthly = _pack(
        "monthly_platform_review",
        validation=validation,
        trading=trading,
        learning=learning,
        release=release,
        scorecard=scorecard,
    )
    quarterly = _pack(
        "quarterly_operational_review",
        validation=validation,
        trading=trading,
        learning=learning,
        release=release,
        scorecard=scorecard,
    )
    for pack in (daily, weekly, monthly, quarterly):
        with contextlib.suppress(Exception):
            _upsert(pack)

    return {
        "as_of": utc_iso(),
        "daily_production_summary": daily,
        "weekly_executive_summary": weekly,
        "monthly_platform_review": monthly,
        "quarterly_operational_review": quarterly,
        "history": list(reversed(_store.list(limit=40))),
        "fabricated": False,
        "evidence_only": True,
    }
