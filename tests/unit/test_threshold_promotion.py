"""Unit tests — Threshold Promotion (operator-gated, never auto)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.threshold_promotion import (
    CANDIDATE_CONFLUENCE,
    CANDIDATE_QUALITY,
    PRODUCTION_CONFLUENCE,
    PRODUCTION_QUALITY,
    build_overlay,
    observe_cycle,
    promote_candidate,
    reset_threshold_promotion_store,
    rollback_to_production,
    status_payload,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.operations.models import OperatorIdentity


def _op() -> OperatorIdentity:
    return OperatorIdentity(
        user_id=uuid4(),
        role="owner",
        display_name="test-operator",
    )


@pytest.mark.unit
class TestThresholdPromotion:
    def setup_method(self) -> None:
        reset_threshold_promotion_store()

    def test_default_untouched_by_overlay(self) -> None:
        overlay = build_overlay(quality=70, confluence=75)
        assert overlay.min_trade_quality_score == 70
        assert DEFAULT_ITE_CONFIG.min_trade_quality_score == 80
        assert DEFAULT_ITE_CONFIG.min_confluence_score == 80

    def test_promote_requires_confirmation(self) -> None:
        with pytest.raises(ValueError, match="confirmation"):
            promote_candidate(
                operator=_op(),
                reason="enough characters here",
                confirmed=False,
            )
        assert DEFAULT_ITE_CONFIG.min_trade_quality_score == PRODUCTION_QUALITY

    def test_promote_and_rollback(self) -> None:
        result = promote_candidate(
            operator=_op(),
            reason="validated candidate Q70/C75 after review",
            confirmed=True,
            evidence_reference="candidate_validation_latest.json",
        )
        assert result["ok"] is True
        assert result["promoted"] is True
        assert result["active"]["quality"] == CANDIDATE_QUALITY
        assert result["active"]["confluence"] == CANDIDATE_CONFLUENCE
        assert result["rollback_point"]["quality"] == PRODUCTION_QUALITY
        record = result["record"]
        assert record["utc_timestamp"]
        assert record["operator"]
        assert record["previous_thresholds"]["quality"] == 80
        assert record["new_thresholds"]["quality"] == 70
        assert record["evidence_reference"]
        assert "commit_hash" in record

        status = status_payload()
        assert status["promoted"] is True
        assert status["never_auto_promotes"] is True
        assert status["never_auto_rollbacks"] is True

        # Monitor observes without auto-rollback
        for i in range(5):
            observe_cycle(
                {
                    "recorded_at": f"t{i}",
                    "executed": i % 2 == 0,
                    "rejected": i % 2 == 1,
                    "latency_ms": 12.0,
                }
            )
        mon = status_payload()["monitoring"]
        assert mon["never_auto_rollback"] is True
        assert mon["live"]["cycles_observed"] == 5

        rb = rollback_to_production(
            operator=_op(),
            reason="operator_rollback_to_80_80",
            confirmed=True,
        )
        assert rb["rolled_back"] is True
        assert rb["auto_rollback"] is False
        assert rb["active"]["quality"] == PRODUCTION_QUALITY
        assert rb["active"]["confluence"] == PRODUCTION_CONFLUENCE
        assert DEFAULT_ITE_CONFIG.min_trade_quality_score == 80
