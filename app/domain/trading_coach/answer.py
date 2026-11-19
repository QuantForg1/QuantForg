"""Answer a fixed question from supplied records. Missing numbers stay missing."""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "trading-coach.v1"

_QUESTIONS = {
    "open_risk": "aggregate_open_risk_pct",
    "week_pnl": "week_net_pnl",
    "largest_loss": "largest_loss",
    "last_rejection": "last_rejection_reason",
    "broker_health": "broker_session_connected",
}


def answer_question(
    question_id: str,
    records: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return one grounded answer. This function cannot change an account."""
    key = _QUESTIONS.get(question_id)
    base = {
        "schema_version": SCHEMA_VERSION,
        "places_orders": False,
        "changes_settings": False,
        "authoritative_for_execution": False,
        "question_id": question_id,
    }
    if key is None:
        return {
            **base,
            "status": "unavailable",
            "answer": None,
            "reason": "question_not_supported",
        }
    value = None if records is None else records.get(key)
    if value is None or value == "":
        return {
            **base,
            "status": "unavailable",
            "answer": None,
            "field": key,
            "reason": "record_missing",
        }
    return {
        **base,
        "status": "grounded",
        "answer": value,
        "field": key,
        "reason": "supplied_user_record",
        "historical_fact": True,
        "recommendation": False,
    }
