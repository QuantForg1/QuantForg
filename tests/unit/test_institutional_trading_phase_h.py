"""Phase H unit tests — production validation & certification."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.institutional_trading.certification.acceptance_gate import (
    LiveAcceptanceGate,
)
from app.domain.institutional_trading.certification.canary import CanaryValidator
from app.domain.institutional_trading.certification.models import (
    CERTIFICATION_PIPELINE,
    CanaryMetrics,
    CertificationEvidence,
    GoNoGoStatus,
    PipelineStage,
)
from app.domain.institutional_trading.certification.platform import (
    CertificationPlatform,
    reset_certification_platform_for_tests,
)
from app.domain.institutional_trading.certification.stress import StressTester


def _full_stages() -> dict[str, bool]:
    return {s.value: True for s in CERTIFICATION_PIPELINE}


def _live_ready_evidence(**over: object) -> CertificationEvidence:
    base = dict(  # noqa: C408
        shadow_days=14.0,
        canary=CanaryMetrics(
            total_trades=100,
            wins=55,
            profit_factor=1.4,
            expectancy=0.2,
            max_drawdown_pct=4.0,
            execution_success=99,
            execution_attempts=100,
            duplicate_executions=0,
            duplicate_prevented=3,
        ),
        gateway_uptime_pct=99.95,
        critical_incidents=0,
        stage_ok=_full_stages(),
        stage_latency_ms={s.value: 2.0 for s in CERTIFICATION_PIPELINE},
        reliability_score=95.0,
        execution_score=95.0,
        research_score=90.0,
        risk_score=92.0,
        operations_score=93.0,
        git_commit="abc123",
        strategy_version="v1.0.0",
        config_version="cfg-7",
        engine_version="1.0.0-ite",
    )
    base.update(over)
    return CertificationEvidence(**base)  # type: ignore[arg-type]


@pytest.fixture()
def platform() -> CertificationPlatform:
    return reset_certification_platform_for_tests()


@pytest.mark.unit
class TestEndToEndCertification:
    def test_all_pipeline_stages(self, platform: CertificationPlatform) -> None:
        report = platform.run(
            _live_ready_evidence(), run_stress=True, run_failures=True
        )
        stages = [c.stage for c in report.stage_checks]
        assert stages == list(CERTIFICATION_PIPELINE)
        assert all(c.passed for c in report.stage_checks)
        assert report.to_dict()["pipeline_passed"] is True


@pytest.mark.unit
class TestCanaryValidator:
    def test_tracks_metrics(self) -> None:
        v = CanaryValidator()
        v.record(trade=True, win=True, execution_ok=True)
        v.record(trade=True, win=False, execution_ok=True, oms_error=True)
        v.record(duplicate_prevented=True)
        s = v.snapshot()
        assert s.total_trades == 2
        assert s.wins == 1
        assert s.win_rate_pct == 50.0
        assert s.oms_errors == 1
        assert s.duplicate_prevented == 1
        assert s.execution_success_pct == 100.0


@pytest.mark.unit
class TestLiveAcceptanceGate:
    def test_blocks_insufficient_shadow(self) -> None:
        gate = LiveAcceptanceGate()
        reqs = gate.evaluate(_live_ready_evidence(shadow_days=7.0))
        by_name = {r.name: r for r in reqs}
        assert by_name["shadow_days"].passed is False
        assert gate.passed(_live_ready_evidence()) is True


@pytest.mark.unit
class TestStressTesting:
    def test_standard_batches(self) -> None:
        results = StressTester().run_standard_suite(sizes=(100, 500))
        assert [r.batch_size for r in results] == [100, 500]
        assert all(r.passed for r in results)
        assert all(r.recovery_ok for r in results)


@pytest.mark.unit
class TestFailureInjection:
    def test_suite_graceful(self, platform: CertificationPlatform) -> None:
        results = platform.failures.run_suite()
        assert len(results) == 6
        assert all(r.graceful for r in results)


@pytest.mark.unit
class TestGoNoGoAndCertificate:
    def test_ready_for_live(self, platform: CertificationPlatform) -> None:
        report = platform.run(
            _live_ready_evidence(),
            operator_approval="ops-lead",
            now=datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
        )
        assert report.go_nogo == GoNoGoStatus.READY_FOR_LIVE
        assert report.failed_requirements == []
        assert report.certificate is not None
        assert report.certificate.operator_approval == "ops-lead"
        assert report.certificate.git_commit == "abc123"
        assert report.scorecard.production_ready is True

    def test_ready_for_canary_when_gate_fails(
        self, platform: CertificationPlatform
    ) -> None:
        report = platform.run(
            _live_ready_evidence(shadow_days=3.0, canary=CanaryMetrics(total_trades=10))
        )
        assert report.go_nogo == GoNoGoStatus.READY_FOR_CANARY
        assert any("live_gate:" in f for f in report.failed_requirements)

    def test_not_ready_when_pipeline_incomplete(
        self, platform: CertificationPlatform
    ) -> None:
        report = platform.run(
            CertificationEvidence(
                stage_ok={PipelineStage.DECISION.value: True},
                reliability_score=50,
                execution_score=50,
                research_score=50,
                risk_score=50,
                operations_score=50,
            )
        )
        assert report.go_nogo == GoNoGoStatus.NOT_READY
        assert any(f.startswith("pipeline:") for f in report.failed_requirements)

    def test_dashboard_payload(self, platform: CertificationPlatform) -> None:
        platform.run(_live_ready_evidence())
        dash = platform.dashboard_payload()
        assert dash["go_nogo"] == GoNoGoStatus.READY_FOR_LIVE.value
        assert dash["production_ready"] is True
        assert len(dash["operator_checklist"]) >= 8
        assert (
            dash["certificate"]["title"] == "Institutional Trading Engine Certificate"
        )
