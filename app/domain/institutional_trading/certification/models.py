"""Phase H — Production Validation & Certification contracts.

Measurement only. No order_send. No OMS / strategy / AI changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class GoNoGoStatus(StrEnum):
    NOT_READY = "NOT_READY"
    READY_FOR_CANARY = "READY_FOR_CANARY"
    READY_FOR_LIVE = "READY_FOR_LIVE"


class PipelineStage(StrEnum):
    DECISION = "decision"
    ELIGIBILITY = "eligibility"
    EXECUTION_BRIDGE = "execution_bridge"
    OMS = "oms"
    GATEWAY = "gateway"
    MT5 = "mt5"
    PME = "pme"
    JOURNAL = "journal"
    RESEARCH = "research"
    OPERATIONS = "operations"
    RELIABILITY = "reliability"


class FailureScenario(StrEnum):
    GATEWAY_DOWN = "gateway_down"
    MT5_DOWN = "mt5_down"
    TUNNEL_DOWN = "tunnel_down"
    DATABASE_DOWN = "database_down"
    SUPABASE_SLOW = "supabase_slow"
    RAILWAY_SLOW = "railway_slow"


# Live acceptance thresholds (locked Phase H)
SHADOW_MIN_DAYS = 14
CANARY_MIN_TRADES = 100
GATEWAY_UPTIME_MIN_PCT = 99.9
EXECUTION_SUCCESS_MIN_PCT = 99.0
DUPLICATE_EXECUTIONS_MAX = 0
CRITICAL_INCIDENTS_MAX = 0

STRESS_BATCH_SIZES: tuple[int, ...] = (100, 500, 1000, 5000)

CERTIFICATION_PIPELINE: tuple[PipelineStage, ...] = (
    PipelineStage.DECISION,
    PipelineStage.ELIGIBILITY,
    PipelineStage.EXECUTION_BRIDGE,
    PipelineStage.OMS,
    PipelineStage.GATEWAY,
    PipelineStage.MT5,
    PipelineStage.PME,
    PipelineStage.JOURNAL,
    PipelineStage.RESEARCH,
    PipelineStage.OPERATIONS,
    PipelineStage.RELIABILITY,
)


@dataclass(frozen=True, slots=True)
class StageCheck:
    stage: PipelineStage
    passed: bool
    detail: str
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "passed": self.passed,
            "detail": self.detail,
            "latency_ms": round(self.latency_ms, 3),
        }


@dataclass(frozen=True, slots=True)
class CanaryMetrics:
    total_trades: int = 0
    wins: int = 0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    max_drawdown_pct: float = 0.0
    execution_success: int = 0
    execution_attempts: int = 0
    oms_errors: int = 0
    gateway_errors: int = 0
    mt5_errors: int = 0
    duplicate_prevented: int = 0
    duplicate_executions: int = 0

    @property
    def win_rate_pct(self) -> float:
        if self.total_trades <= 0:
            return 0.0
        return round(100.0 * self.wins / self.total_trades, 4)

    @property
    def execution_success_pct(self) -> float:
        if self.execution_attempts <= 0:
            return 100.0
        return round(100.0 * self.execution_success / self.execution_attempts, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "win_rate_pct": self.win_rate_pct,
            "wins": self.wins,
            "profit_factor": round(self.profit_factor, 4),
            "expectancy": round(self.expectancy, 6),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "execution_success_pct": self.execution_success_pct,
            "execution_success": self.execution_success,
            "execution_attempts": self.execution_attempts,
            "oms_errors": self.oms_errors,
            "gateway_errors": self.gateway_errors,
            "mt5_errors": self.mt5_errors,
            "duplicate_prevented": self.duplicate_prevented,
            "duplicate_executions": self.duplicate_executions,
        }


@dataclass(frozen=True, slots=True)
class GateRequirement:
    name: str
    required: str
    actual: str
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "required": self.required,
            "actual": self.actual,
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class StressBatchResult:
    batch_size: int
    elapsed_ms: float
    decisions_per_sec: float
    peak_memory_kb: float
    queue_depth: int
    recovery_ok: bool
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_size": self.batch_size,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "decisions_per_sec": round(self.decisions_per_sec, 2),
            "peak_memory_kb": round(self.peak_memory_kb, 2),
            "queue_depth": self.queue_depth,
            "recovery_ok": self.recovery_ok,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class FailureInjectionResult:
    scenario: FailureScenario
    degraded: bool
    graceful: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario.value,
            "degraded": self.degraded,
            "graceful": self.graceful,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class Scorecard:
    overall: float
    reliability: float
    execution: float
    research: float
    risk: float
    operations: float
    production_ready: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": round(self.overall, 2),
            "reliability": round(self.reliability, 2),
            "execution": round(self.execution, 2),
            "research": round(self.research, 2),
            "risk": round(self.risk, 2),
            "operations": round(self.operations, 2),
            "production_ready": self.production_ready,
        }


@dataclass
class ProductionCertificate:
    version: str
    git_commit: str
    strategy_version: str
    config_version: str
    promotion_status: str
    passed_tests: list[str]
    known_limitations: list[str]
    operator_approval: str | None
    timestamp: datetime
    go_nogo: GoNoGoStatus
    certificate_id: UUID = field(default_factory=uuid4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "certificate_id": str(self.certificate_id),
            "title": "Institutional Trading Engine Certificate",
            "version": self.version,
            "git_commit": self.git_commit,
            "strategy_version": self.strategy_version,
            "config_version": self.config_version,
            "promotion_status": self.promotion_status,
            "passed_tests": list(self.passed_tests),
            "known_limitations": list(self.known_limitations),
            "operator_approval": self.operator_approval,
            "timestamp": self.timestamp.isoformat(),
            "go_nogo": self.go_nogo.value,
        }


@dataclass
class CertificationReport:
    report_id: UUID
    generated_at: datetime
    stage_checks: list[StageCheck]
    canary: CanaryMetrics
    gate_requirements: list[GateRequirement]
    stress: list[StressBatchResult]
    failures: list[FailureInjectionResult]
    scorecard: Scorecard
    go_nogo: GoNoGoStatus
    failed_requirements: list[str]
    certificate: ProductionCertificate | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": str(self.report_id),
            "generated_at": self.generated_at.isoformat(),
            "stage_checks": [s.to_dict() for s in self.stage_checks],
            "pipeline_passed": all(s.passed for s in self.stage_checks),
            "canary": self.canary.to_dict(),
            "gate_requirements": [g.to_dict() for g in self.gate_requirements],
            "gate_passed": all(g.passed for g in self.gate_requirements),
            "stress": [s.to_dict() for s in self.stress],
            "failures": [f.to_dict() for f in self.failures],
            "scorecard": self.scorecard.to_dict(),
            "go_nogo": self.go_nogo.value,
            "failed_requirements": list(self.failed_requirements),
            "certificate": self.certificate.to_dict() if self.certificate else None,
        }


@dataclass(frozen=True, slots=True)
class CertificationEvidence:
    """Operator / probe inputs — measurement only, never triggers trades."""

    shadow_days: float = 0.0
    canary: CanaryMetrics = field(default_factory=CanaryMetrics)
    gateway_uptime_pct: float = 0.0
    critical_incidents: int = 0
    stage_ok: dict[str, bool] = field(default_factory=dict)
    stage_latency_ms: dict[str, float] = field(default_factory=dict)
    reliability_score: float = 0.0
    execution_score: float = 0.0
    research_score: float = 0.0
    risk_score: float = 0.0
    operations_score: float = 0.0
    git_commit: str = "unknown"
    strategy_version: str = "unset"
    config_version: str = "unset"
    engine_version: str = "1.0.0-ite"
    known_limitations: tuple[str, ...] = (
        "Live MT5 canary under AutoTrading is operator-gated",
        "In-memory certification store must be flushed to SQL for durability",
        "No AI on hot path (by design)",
    )
