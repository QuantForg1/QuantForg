"""Autonomous cycle evidence + below_min_lot rejection logging."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.application.services.cycle_evidence import (
    log_trade_rejection,
    record_cycle_evidence,
    reset_cycle_evidence_path_for_tests,
)
from app.application.services.live_auto_trade_certification import (
    seed_certified_demo_report_for_tests,
)
from app.application.services.strategy_diagnostics import (
    StrategyDiagnosticsStore,
    reason_label,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.sizing import calculate_scalping_lots
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.models import (
    OperatorIdentity,
    OpsExecutionMode,
)
from app.domain.institutional_trading.session_policy import TRADABLE_SESSION_NAMES


def _op() -> OperatorIdentity:
    return OperatorIdentity(
        user_id=uuid4(),
        role="owner",
        display_name="Autonomy Tester",
    )


@pytest.mark.unit
class TestAutonomousCycleEvidence:
    def test_below_min_lot_includes_required_fields(self) -> None:
        sized = calculate_scalping_lots(
            equity=Decimal("181.53"),
            stop_distance=Decimal("150.00"),
            risk_pct=Decimal("1.0"),
            contract_size=Decimal("100"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
        )
        assert sized.valid is False
        assert sized.method in {"below_min_lot", "min_lot_exceeds_risk_budget"}
        detail = sized.below_min_lot_detail()
        assert Decimal(detail["calculated_lot"]) > 0
        assert detail["broker_minimum"] == "0.01"
        assert detail["account_balance"] == "181.53"
        assert "calculated_lot=" in sized.reason or "MIN_LOT_EXCEEDS" in sized.reason

    def test_record_cycle_evidence_persists_jsonl(self, tmp_path: Path) -> None:
        path = tmp_path / "ite_cycle_evidence.jsonl"
        reset_cycle_evidence_path_for_tests(path)
        try:
            row = record_cycle_evidence(
                cycle_outcome="no_trade",
                decision_action="NO_TRADE",
                reasons=["quality_below_threshold"],
                abort_reason="quality_below_threshold",
                session="tokyo",
                session_stars=2,
                quality_score=66,
                confluence_score=70,
                forwarded_to_oms=False,
                trace_id="trace-1",
            )
            assert row["rejected"] is True
            assert row["autonomous"] is True
            assert row["forced_trade"] is False
            assert row["quality_thresholds_reduced"] is False
            assert path.is_file()
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == 1
            loaded = json.loads(lines[0])
            assert loaded["primary_reason"] == "quality_below_threshold"
            assert loaded["session"] == "tokyo"
        finally:
            reset_cycle_evidence_path_for_tests(None)

    def test_below_min_lot_reject_log_structured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[dict[str, object]] = []

        def _capture(event: str, **kwargs: object) -> None:
            captured.append({"event": event, **kwargs})

        monkeypatch.setattr(
            "app.application.services.cycle_evidence.logger.warning",
            _capture,
        )
        log_trade_rejection(
            reasons=["below_min_lot calculated_lot=0.002"],
            stage="lot_sizing",
            code="below_min_lot",
            session="tokyo",
            sizing={
                "calculated_lot": "0.0025",
                "broker_minimum": "0.01",
                "account_balance": "181.53",
                "risk_percentage": "1.0",
            },
        )
        assert captured
        assert captured[0]["event"] == "Rejected because: below_min_lot"
        assert captured[0]["calculated_lot"] == "0.0025"
        assert captured[0]["broker_minimum"] == "0.01"
        assert captured[0]["account_balance"] == "181.53"
        assert captured[0]["risk_percentage"] == "1.0"

    def test_diagnostics_record_writes_cycle_evidence(self, tmp_path: Path) -> None:
        path = tmp_path / "ite_cycle_evidence.jsonl"
        reset_cycle_evidence_path_for_tests(path)
        try:
            store = StrategyDiagnosticsStore()
            store.record_from_artefacts(
                snapshot=None,
                decision=None,
                cycle_outcome="safety_blocked",
                decision_action="NO_TRADE",
                abort_reason="SAFETY_BLOCKED",
                decision_reasons=("Auto Trading Disabled",),
                market_context_diagnostics={
                    "equity": "181.53",
                    "risk_pct": "1.0",
                    "raw_lots": "0.002",
                    "broker_min_lot": "0.01",
                    "sizing_status": "below_min_lot",
                },
                forwarded_to_oms=False,
                trace_id="t-safe",
            )
            assert path.is_file()
            line = path.read_text(encoding="utf-8").strip().splitlines()[0]
            loaded = json.loads(line)
            assert loaded["cycle_outcome"] == "safety_blocked"
            assert loaded["rejected"] is True
            assert "SAFETY_BLOCKED" in loaded["reasons"]
        finally:
            reset_cycle_evidence_path_for_tests(None)

    def test_quality_thresholds_unchanged(self) -> None:
        assert DEFAULT_ITE_CONFIG.min_trade_quality_score == 80
        assert DEFAULT_ITE_CONFIG.min_confluence_score == 80
        assert DEFAULT_AI_SCALPING_CONFIG.require_session_quality is False

    def test_control_plane_expands_sessions_to_24_7(self) -> None:
        seed_certified_demo_report_for_tests()
        plane = OperationsControlPlane()
        op = _op()
        plane.transition_mode(
            op, OpsExecutionMode.CANARY, reason="canary", confirmed=True
        )
        plane.transition_mode(op, OpsExecutionMode.LIVE, reason="live", confirmed=True)
        policy = plane.update_auto_trade_controls(
            op,
            enabled=True,
            allowed_sessions=("london", "new_york"),
            reason="partial sessions",
        )
        assert set(TRADABLE_SESSION_NAMES).issubset(set(policy.allowed_sessions))
        assert "tokyo" in policy.allowed_sessions
        assert "sydney" in policy.allowed_sessions

    def test_below_min_lot_reason_label(self) -> None:
        assert "broker minimum" in reason_label("below_min_lot").lower()
