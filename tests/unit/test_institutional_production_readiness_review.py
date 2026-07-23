"""Unit tests — Institutional Production Readiness Review (read-only)."""

from __future__ import annotations

import time

import pytest

from app.application.services.institutional_production_readiness_review import (
    build_institutional_production_readiness_review,
    prr_to_markdown,
    score_readiness,
)

pytestmark = pytest.mark.unit


class TestInstitutionalPrr:
    def test_build_payload_shape_and_flags(self) -> None:
        payload = build_institutional_production_readiness_review(write_report=False)
        assert payload["mutates_engines"] is False
        assert payload["analytics_only"] is True
        assert payload["advisory_only"] is True
        assert payload[
            "never_modifies_strategy_risk_safety_oms_execution_auto_trading_thresholds"
        ] is True
        sections = payload["sections"]
        for key in (
            "architecture",
            "security",
            "reliability",
            "trading",
            "data_integrity",
            "performance",
            "operations",
            "production_checklist",
            "risk_register",
            "executive_summary",
        ):
            assert key in sections

        checklist = sections["production_checklist"]
        assert isinstance(checklist, list)
        assert len(checklist) >= 10
        for row in checklist:
            assert row["status"] in {"PASS", "WARNING", "FAIL"}

        score = payload["overall_production_readiness_score"]
        assert 0 <= score <= 100
        assert payload["recommendation"] in {
            "NOT READY",
            "CONDITIONALLY READY",
            "READY FOR CONTROLLED LIVE",
            "READY FOR INSTITUTIONAL PRODUCTION",
        }

        risks = sections["risk_register"]
        for level in ("critical", "high", "medium", "low"):
            assert level in risks
            assert isinstance(risks[level], list)

    def test_markdown_export(self) -> None:
        payload = build_institutional_production_readiness_review(write_report=False)
        md = prr_to_markdown(payload)
        assert "Institutional Production Readiness Review" in md
        assert "Risk Register" in md

    def test_score_readiness_helpers(self) -> None:
        score, rec, _ = score_readiness(
            [
                {"status": "PASS", "section": "architecture"},
                {"status": "PASS", "section": "security"},
                {"status": "WARNING", "section": "operations"},
            ]
        )
        assert score > 70
        assert rec in {
            "CONDITIONALLY READY",
            "READY FOR CONTROLLED LIVE",
            "READY FOR INSTITUTIONAL PRODUCTION",
        }

    def test_performance_budget(self) -> None:
        t0 = time.perf_counter()
        payload = build_institutional_production_readiness_review(write_report=False)
        elapsed = time.perf_counter() - t0
        assert payload["elapsed_ms"] is not None
        assert elapsed < 15.0
