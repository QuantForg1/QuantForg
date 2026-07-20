"""ITE Production Validation & Certification API — Phase H."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.application.dto.auth import AuthUserDTO
from app.domain.enums.user import UserRole
from app.domain.institutional_trading.certification.models import (
    CERTIFICATION_PIPELINE,
    CanaryMetrics,
    CertificationEvidence,
)
from app.domain.institutional_trading.certification.platform import (
    get_certification_platform,
)
from app.presentation.dependencies.auth import require_roles

router = APIRouter(prefix="/ite/certification", tags=["ite-certification"])

OperatorUser = Annotated[
    AuthUserDTO,
    Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
]


class CanaryBody(BaseModel):
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


class EvidenceBody(BaseModel):
    shadow_days: float = 0.0
    canary: CanaryBody = Field(default_factory=CanaryBody)
    gateway_uptime_pct: float = 0.0
    critical_incidents: int = 0
    stage_ok: dict[str, bool] = Field(default_factory=dict)
    stage_latency_ms: dict[str, float] = Field(default_factory=dict)
    reliability_score: float = 80.0
    execution_score: float = 80.0
    research_score: float = 80.0
    risk_score: float = 80.0
    operations_score: float = 80.0
    git_commit: str = "unknown"
    strategy_version: str = "unset"
    config_version: str = "unset"
    engine_version: str = "1.0.0-ite"
    all_stages_ok: bool = False
    operator_approval: str | None = None
    run_stress: bool = True
    run_failures: bool = True


class ApproveBody(BaseModel):
    note: str = ""


def _to_evidence(body: EvidenceBody) -> CertificationEvidence:
    stage_ok = dict(body.stage_ok)
    if body.all_stages_ok:
        for s in CERTIFICATION_PIPELINE:
            stage_ok[s.value] = True
    c = body.canary
    return CertificationEvidence(
        shadow_days=body.shadow_days,
        canary=CanaryMetrics(
            total_trades=c.total_trades,
            wins=c.wins,
            profit_factor=c.profit_factor,
            expectancy=c.expectancy,
            max_drawdown_pct=c.max_drawdown_pct,
            execution_success=c.execution_success,
            execution_attempts=c.execution_attempts,
            oms_errors=c.oms_errors,
            gateway_errors=c.gateway_errors,
            mt5_errors=c.mt5_errors,
            duplicate_prevented=c.duplicate_prevented,
            duplicate_executions=c.duplicate_executions,
        ),
        gateway_uptime_pct=body.gateway_uptime_pct,
        critical_incidents=body.critical_incidents,
        stage_ok=stage_ok,
        stage_latency_ms=dict(body.stage_latency_ms),
        reliability_score=body.reliability_score,
        execution_score=body.execution_score,
        research_score=body.research_score,
        risk_score=body.risk_score,
        operations_score=body.operations_score,
        git_commit=body.git_commit,
        strategy_version=body.strategy_version,
        config_version=body.config_version,
        engine_version=body.engine_version,
    )


@router.get("/dashboard")
def dashboard(_user: OperatorUser) -> dict[str, Any]:
    return get_certification_platform().dashboard_payload()


@router.post("/run")
def run_certification(body: EvidenceBody, _user: OperatorUser) -> dict[str, Any]:
    report = get_certification_platform().run(
        _to_evidence(body),
        operator_approval=body.operator_approval,
        run_stress=body.run_stress,
        run_failures=body.run_failures,
    )
    return report.to_dict()


@router.get("/report")
def last_report(_user: OperatorUser) -> dict[str, Any]:
    report = get_certification_platform().last_report()
    if report is None:
        raise HTTPException(status_code=404, detail="no certification report yet")
    return report.to_dict()


@router.get("/go-nogo")
def go_nogo(_user: OperatorUser) -> dict[str, Any]:
    report = get_certification_platform().last_report()
    if report is None:
        return {
            "go_nogo": "NOT_READY",
            "failed_requirements": ["no certification report — run /ite/certification/run"],
            "production_ready": False,
        }
    return {
        "go_nogo": report.go_nogo.value,
        "failed_requirements": list(report.failed_requirements),
        "production_ready": report.scorecard.production_ready,
        "scorecard": report.scorecard.to_dict(),
    }


@router.get("/certificate")
def certificate(_user: OperatorUser) -> dict[str, Any]:
    report = get_certification_platform().last_report()
    if report is None or report.certificate is None:
        raise HTTPException(status_code=404, detail="no certificate yet")
    return report.certificate.to_dict()


@router.post("/canary")
def load_canary(body: CanaryBody, _user: OperatorUser) -> dict[str, Any]:
    metrics = CanaryMetrics(**body.model_dump())
    return get_certification_platform().load_canary(metrics).to_dict()


@router.get("/canary")
def get_canary(_user: OperatorUser) -> dict[str, Any]:
    return get_certification_platform().canary.summary()


@router.post("/approve")
def approve(body: ApproveBody, user: OperatorUser) -> dict[str, Any]:
    name = user.display_name or str(user.id)
    return get_certification_platform().approve(operator=name, note=body.note)


@router.get("/checklist")
def checklist(_user: OperatorUser) -> dict[str, Any]:
    return {
        "checklist": get_certification_platform().dashboard_payload()[
            "operator_checklist"
        ]
    }


@router.post("/stress")
def stress_only(_user: OperatorUser) -> dict[str, Any]:
    results = get_certification_platform().stress.run_standard_suite()
    return {"stress": [r.to_dict() for r in results]}


@router.post("/failures")
def failures_only(_user: OperatorUser) -> dict[str, Any]:
    results = get_certification_platform().failures.run_suite()
    return {"failures": [r.to_dict() for r in results]}
