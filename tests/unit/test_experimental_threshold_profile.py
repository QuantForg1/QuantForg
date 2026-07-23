"""Unit tests — EXPERIMENTAL_75 profile (DEFAULT_ITE_CONFIG frozen)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.experimental_threshold_profile import (
    BADGE_LABEL,
    EVAL_TARGET,
    EXPERIMENTAL_CONFLUENCE,
    EXPERIMENTAL_QUALITY,
    activate_experimental_75,
    generate_experimental_threshold_report,
    get_experimental_threshold_store,
    observe_experimental_cycle,
    report_to_markdown,
    reset_experimental_threshold_store,
    rollback_experimental_to_production,
    status_payload,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.operations.models import OperatorIdentity


def _op() -> OperatorIdentity:
    return OperatorIdentity(
        user_id=uuid4(),
        role="owner",
        display_name="Experimental Tester",
    )


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_experimental_threshold_store()
    yield
    reset_experimental_threshold_store()


@pytest.mark.unit
def test_default_ite_config_frozen() -> None:
    assert DEFAULT_ITE_CONFIG.min_trade_quality_score == 80
    assert DEFAULT_ITE_CONFIG.min_confluence_score == 80


@pytest.mark.unit
def test_activate_requires_confirmation() -> None:
    with pytest.raises(ValueError, match="confirmation"):
        activate_experimental_75(
            operator=_op(),
            reason="enough_chars_here",
            confirmed=False,
        )


@pytest.mark.unit
def test_activate_and_rollback_audit() -> None:
    result = activate_experimental_75(
        operator=_op(),
        reason="test_activate_experimental_75",
        confirmed=True,
    )
    assert result["activated"] is True
    assert result["badge"] == BADGE_LABEL
    assert result["default_ite_config"]["quality"] == 80
    assert DEFAULT_ITE_CONFIG.min_trade_quality_score == 80

    status = status_payload()
    assert status["active"] is True
    assert status["badge"] == BADGE_LABEL
    assert status["badge_visible"] is True
    assert len(status["audit_trail"]) >= 1

    rb = rollback_experimental_to_production(
        operator=_op(),
        reason="test_rollback_to_80_80",
        confirmed=True,
    )
    assert rb["rolled_back"] is True
    assert rb["auto_rollback"] is False
    assert status_payload()["active"] is False
    assert DEFAULT_ITE_CONFIG.min_trade_quality_score == 80
    assert DEFAULT_ITE_CONFIG.min_confluence_score == 80


@pytest.mark.unit
def test_observe_builds_report_at_100() -> None:
    activate_experimental_75(
        operator=_op(),
        reason="test_monitor_100_evaluations",
        confirmed=True,
    )
    store = get_experimental_threshold_store()
    for i in range(EVAL_TARGET):
        # Mix: some pass 75/75 only, some pass 80/80
        q = 76 if i % 3 == 0 else 85
        c = 76 if i % 3 == 0 else 85
        observe_experimental_cycle(
            {
                "recorded_at": f"2026-07-23T12:00:{i:02d}Z",
                "quality": {"score": q},
                "confluence": {"total": c},
                "decision_action": "BUY",
                "executed": q >= 80,
                "rejected": False,
                "session": {"allowed": True},
            }
        )
    assert store.evaluations == EVAL_TARGET
    assert store.report_generated is True
    assert store.last_report is not None
    assert store.last_report["report_type"] == "EXPERIMENTAL_THRESHOLD_REPORT"
    assert store.last_report["recommendation"] in {"Keep 75/75", "Revert to 80/80"}
    assert store.last_report["never_auto_promotes"] is True
    assert store.last_report["default_ite_config_unchanged"] is True
    md = report_to_markdown(store.last_report)
    assert "EXPERIMENTAL_THRESHOLD_REPORT" in md
    assert "Recommendation" in md


@pytest.mark.unit
def test_off_hours_not_eligible() -> None:
    activate_experimental_75(
        operator=_op(),
        reason="test_session_filter_eligible",
        confirmed=True,
    )
    observe_experimental_cycle(
        {
            "quality": {"score": 90},
            "confluence": {"total": 90},
            "decision_action": "BUY",
            "session": {"allowed": False},
        }
    )
    assert get_experimental_threshold_store().evaluations == 0


@pytest.mark.unit
def test_gates_are_75() -> None:
    assert EXPERIMENTAL_QUALITY == 75
    assert EXPERIMENTAL_CONFLUENCE == 75
    report = generate_experimental_threshold_report()
    assert report["experimental"]["quality"] == 75
    assert report["default_baseline"]["quality"] == 80
