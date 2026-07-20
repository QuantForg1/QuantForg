"""Phase H certification platform façade."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.certification.acceptance_gate import (
    LiveAcceptanceGate,
)
from app.domain.institutional_trading.certification.canary import CanaryValidator
from app.domain.institutional_trading.certification.certificate import (
    CertificateIssuer,
)
from app.domain.institutional_trading.certification.dashboard import (
    CertificationDashboard,
)
from app.domain.institutional_trading.certification.e2e import EndToEndCertifier
from app.domain.institutional_trading.certification.failure_injection import (
    FailureInjector,
)
from app.domain.institutional_trading.certification.go_nogo import GoNoGoEngine
from app.domain.institutional_trading.certification.models import (
    CERTIFICATION_PIPELINE,
    CanaryMetrics,
    CertificationEvidence,
    CertificationReport,
    GoNoGoStatus,
    PipelineStage,
)
from app.domain.institutional_trading.certification.stress import StressTester

OPERATOR_CHECKLIST: tuple[str, ...] = (
    "Confirm Phases A-G unit suites green in CI",
    "Confirm Shadow mode ran ≥14 calendar days (or accept canary-only path)",
    "Confirm canary trade count and execution metrics from OMS journal (read-only)",
    "Confirm gateway uptime ≥99.9% from reliability probes",
    "Confirm zero duplicate executions and zero open CRITICAL incidents",
    "Run certification report (POST /ite/certification/run)",
    "Review Go/No-Go failed requirements — do not promote if NOT_READY",
    "Operator sign-off on Production Certificate before LIVE mode change",
    "LIVE mode change remains via Phase F ops control plane (human action)",
    "Do not enable AutoTrading until certificate shows READY_FOR_LIVE",
)


@dataclass
class CertificationPlatform:
    e2e: EndToEndCertifier = field(default_factory=EndToEndCertifier)
    canary: CanaryValidator = field(default_factory=CanaryValidator)
    gate: LiveAcceptanceGate = field(default_factory=LiveAcceptanceGate)
    stress: StressTester = field(default_factory=StressTester)
    failures: FailureInjector = field(default_factory=FailureInjector)
    dashboard: CertificationDashboard = field(default_factory=CertificationDashboard)
    go_nogo: GoNoGoEngine = field(default_factory=GoNoGoEngine)
    certificates: CertificateIssuer = field(default_factory=CertificateIssuer)
    _last_report: CertificationReport | None = field(default=None, repr=False)
    _approvals: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def load_canary(self, metrics: CanaryMetrics) -> CanaryMetrics:
        return self.canary.load(metrics)

    def run(
        self,
        evidence: CertificationEvidence,
        *,
        operator_approval: str | None = None,
        run_stress: bool = True,
        run_failures: bool = True,
        now: datetime | None = None,
    ) -> CertificationReport:
        """Generate one full certification report. Never trades."""
        moment = now or datetime.now(UTC)
        # Prefer canary store if evidence.canary is empty but store has data
        if evidence.canary.total_trades == 0 and self.canary.snapshot().total_trades:
            evidence = CertificationEvidence(
                shadow_days=evidence.shadow_days,
                canary=self.canary.snapshot(),
                gateway_uptime_pct=evidence.gateway_uptime_pct,
                critical_incidents=evidence.critical_incidents,
                stage_ok=evidence.stage_ok,
                stage_latency_ms=evidence.stage_latency_ms,
                reliability_score=evidence.reliability_score,
                execution_score=evidence.execution_score,
                research_score=evidence.research_score,
                risk_score=evidence.risk_score,
                operations_score=evidence.operations_score,
                git_commit=evidence.git_commit,
                strategy_version=evidence.strategy_version,
                config_version=evidence.config_version,
                engine_version=evidence.engine_version,
                known_limitations=evidence.known_limitations,
            )

        # Default missing stages to False unless provided
        stage_ok = dict(evidence.stage_ok)
        for stage in CERTIFICATION_PIPELINE:
            stage_ok.setdefault(stage.value, False)
        evidence = CertificationEvidence(
            shadow_days=evidence.shadow_days,
            canary=evidence.canary,
            gateway_uptime_pct=evidence.gateway_uptime_pct,
            critical_incidents=evidence.critical_incidents,
            stage_ok=stage_ok,
            stage_latency_ms=dict(evidence.stage_latency_ms),
            reliability_score=evidence.reliability_score,
            execution_score=evidence.execution_score,
            research_score=evidence.research_score,
            risk_score=evidence.risk_score,
            operations_score=evidence.operations_score,
            git_commit=evidence.git_commit,
            strategy_version=evidence.strategy_version,
            config_version=evidence.config_version,
            engine_version=evidence.engine_version,
            known_limitations=evidence.known_limitations,
        )

        stage_checks = self.e2e.validate(evidence)
        gate_reqs = self.gate.evaluate(evidence)
        stress_results = self.stress.run_standard_suite() if run_stress else []
        failure_results = self.failures.run_suite() if run_failures else []
        scorecard = self.dashboard.score(
            evidence,
            stage_checks=stage_checks,
            gate=gate_reqs,
            stress=stress_results,
            failures=failure_results,
        )
        status, failed = self.go_nogo.evaluate(
            stage_checks=stage_checks,
            gate=gate_reqs,
            stress=stress_results,
            failures=failure_results,
            evidence=evidence,
        )

        passed_tests = [f"pipeline:{s.stage.value}" for s in stage_checks if s.passed]
        passed_tests.extend(
            f"stress:{s.batch_size}" for s in stress_results if s.passed
        )
        passed_tests.extend(
            f"failure:{f.scenario.value}" for f in failure_results if f.graceful
        )
        passed_tests.extend(f"gate:{g.name}" for g in gate_reqs if g.passed)

        cert = self.certificates.issue(
            evidence=evidence,
            go_nogo=status,
            passed_tests=passed_tests,
            operator_approval=operator_approval,
            now=moment,
        )

        report = CertificationReport(
            report_id=uuid4(),
            generated_at=moment,
            stage_checks=stage_checks,
            canary=evidence.canary,
            gate_requirements=gate_reqs,
            stress=stress_results,
            failures=failure_results,
            scorecard=scorecard,
            go_nogo=status,
            failed_requirements=failed,
            certificate=cert,
        )
        with self._lock:
            self._last_report = report
        return report

    def last_report(self) -> CertificationReport | None:
        with self._lock:
            return self._last_report

    def approve(
        self,
        *,
        operator: str,
        note: str = "",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        moment = now or datetime.now(UTC)
        entry = {
            "operator": operator,
            "note": note,
            "at": moment.isoformat(),
        }
        with self._lock:
            self._approvals.append(entry)
            if self._last_report and self._last_report.certificate:
                self._last_report.certificate.operator_approval = operator
        return entry

    def dashboard_payload(self) -> dict[str, Any]:
        report = self.last_report()
        return {
            "has_report": report is not None,
            "scorecard": report.scorecard.to_dict() if report else None,
            "go_nogo": report.go_nogo.value if report else GoNoGoStatus.NOT_READY.value,
            "failed_requirements": report.failed_requirements if report else [],
            "production_ready": (
                report.scorecard.production_ready if report else False
            ),
            "certificate": (
                report.certificate.to_dict() if report and report.certificate else None
            ),
            "canary": self.canary.summary(),
            "operator_checklist": [
                {"step": i + 1, "text": t, "done": False}
                for i, t in enumerate(OPERATOR_CHECKLIST)
            ],
            "pipeline_stages": [s.value for s in PipelineStage],
            "approvals": list(self._approvals),
        }


_PLATFORM: CertificationPlatform | None = None
_PLAT_LOCK = Lock()


def get_certification_platform() -> CertificationPlatform:
    global _PLATFORM
    with _PLAT_LOCK:
        if _PLATFORM is None:
            _PLATFORM = CertificationPlatform()
        return _PLATFORM


def reset_certification_platform_for_tests() -> CertificationPlatform:
    global _PLATFORM
    with _PLAT_LOCK:
        _PLATFORM = CertificationPlatform()
        return _PLATFORM
