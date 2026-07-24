"""Unit tests — Threshold Sensitivity Report (statistics only)."""

from __future__ import annotations

import pytest

from app.application.services.threshold_sensitivity import (
    build_threshold_sensitivity_report,
    normalize_score_rows,
    sweep_confluence_gates,
    sweep_quality_gates,
)


@pytest.mark.unit
class TestThresholdSensitivity:
    def test_quality_sweep_execution_pct(self) -> None:
        rows = normalize_score_rows(
            [
                {"quality": 82, "confluence": 85},
                {"quality": 76, "confluence": 81},
                {"quality": 70, "confluence": 90},
                {"quality": 64, "confluence": 80},
                {"quality": 58, "confluence": 80},
            ]
        )
        # Confluence held at 80 → all 5 pass confluence.
        sweep = sweep_quality_gates(rows)
        by_gate = {r["gate"]: r for r in sweep}
        assert by_gate[80]["would_execute_count"] == 1  # only 82
        assert by_gate[80]["execution_pct"] == 20.0
        assert by_gate[75]["would_execute_count"] == 2  # 82, 76
        assert by_gate[70]["would_execute_count"] == 3
        assert by_gate[65]["would_execute_count"] == 3  # 64 fails (>=65? 64 < 65)
        assert by_gate[60]["would_execute_count"] == 4  # 58 fails

    def test_confluence_sweep(self) -> None:
        rows = normalize_score_rows(
            [
                {"quality": 90, "confluence": 82},
                {"quality": 90, "confluence": 74},
                {"quality": 90, "confluence": 60},
            ]
        )
        sweep = sweep_confluence_gates(rows)
        by_gate = {r["gate"]: r for r in sweep}
        assert by_gate[80]["would_execute_count"] == 1
        assert by_gate[75]["would_execute_count"] == 1
        assert by_gate[70]["would_execute_count"] == 2
        assert by_gate[60]["would_execute_count"] == 3

    def test_report_locks(self) -> None:
        report = build_threshold_sensitivity_report(
            [{"quality": 70, "confluence": 70}]
        )
        assert report["never_modifies_thresholds"] is True
        assert report["never_modifies_live_engine"] is True
        assert report["statistics_only"] is True
        assert len(report["quality_gate_sensitivity"]) == 5
        assert len(report["confluence_gate_sensitivity"]) == 5
