"""Unit tests — Candidate Validation decision rules (research only)."""

from __future__ import annotations

import pytest

from app.application.services.candidate_validation import decide_candidate


@pytest.mark.unit
class TestCandidateValidation:
    def test_keep_when_pf_not_improved(self) -> None:
        prod = {
            "profit_factor": 2.0,
            "expectancy": 1.0,
            "maximum_drawdown_pct": 10.0,
        }
        cand = {
            "profit_factor": 1.5,
            "expectancy": 1.5,
            "maximum_drawdown_pct": 9.0,
        }
        d = decide_candidate(production=prod, candidate=cand)
        assert d["recommend_candidate"] is False
        assert d["action"] == "keep_production"

    def test_keep_when_dd_materially_worse(self) -> None:
        prod = {
            "profit_factor": 2.0,
            "expectancy": 1.0,
            "maximum_drawdown_pct": 10.0,
        }
        cand = {
            "profit_factor": 3.0,
            "expectancy": 1.5,
            "maximum_drawdown_pct": 20.0,
        }
        d = decide_candidate(production=prod, candidate=cand)
        assert d["recommend_candidate"] is False

    def test_eligible_when_all_pass(self) -> None:
        prod = {
            "profit_factor": 2.0,
            "expectancy": 1.0,
            "maximum_drawdown_pct": 10.0,
        }
        cand = {
            "profit_factor": 2.5,
            "expectancy": 1.2,
            "maximum_drawdown_pct": 10.5,
        }
        d = decide_candidate(production=prod, candidate=cand)
        assert d["recommend_candidate"] is True
        assert d["never_modifies_production"] is True
        assert d["auto_applied"] is False
