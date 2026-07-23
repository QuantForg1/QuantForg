"""ITE Operations Control Plane API — Phase F."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.application.dto.auth import AuthUserDTO
from app.domain.enums.user import UserRole
from app.domain.institutional_trading.auto_trading import AutoTradeLiveFacts
from app.domain.institutional_trading.operations.control_plane import (
    PermissionDenied,
    get_control_plane,
)
from app.domain.institutional_trading.operations.health import HealthInputs
from app.domain.institutional_trading.operations.models import (
    OperatorIdentity,
    OpsExecutionMode,
)
from app.presentation.dependencies.auth import require_roles
from core.config.settings import get_settings

router = APIRouter(prefix="/ite/ops", tags=["ite-operations"])

OperatorUser = Annotated[
    AuthUserDTO,
    Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
]


def _operator(
    user: AuthUserDTO,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> OperatorIdentity:
    ip = x_forwarded_for or (request.client.host if request.client else None)
    ua = request.headers.get("user-agent")
    return OperatorIdentity(
        user_id=user.id,
        role=str(user.role).lower(),
        display_name=user.display_name or user.email or str(user.id),
        ip=ip,
        user_agent=ua,
    )


class ConfirmBody(BaseModel):
    reason: str = Field(min_length=1)
    confirmed: bool = False


class ModeBody(ConfirmBody):
    target: str


class PromoteBody(ConfirmBody):
    config_version: str
    strategy_version: str
    risk_per_trade_pct: str | None = None
    max_daily_loss_pct: str | None = None
    max_open_trades: int | None = None


class RollbackBody(ConfirmBody):
    target_config_version: str


class ThresholdPromoteBody(ConfirmBody):
    evidence_reference: str | None = None


class ThresholdRollbackBody(BaseModel):
    reason: str = Field(default="operator_rollback_to_80_80", min_length=1)
    confirmed: bool = False


class ExperimentalActivateBody(BaseModel):
    reason: str = Field(min_length=8)
    confirmed: bool = False


class ExperimentalRollbackBody(BaseModel):
    reason: str = Field(
        default="operator_rollback_experimental_to_80_80", min_length=1
    )
    confirmed: bool = False


class RiskBody(ConfirmBody):
    risk_per_trade_pct: str
    max_daily_loss_pct: str
    max_open_trades: int


class AutoTradeControlsBody(ConfirmBody):
    enabled: bool | None = None
    run_state: str | None = None
    max_open_positions: int | None = None
    risk_per_trade_pct: str | None = None
    max_daily_loss_pct: str | None = None
    allowed_sessions: list[str] | None = None
    allowed_symbols: list[str] | None = None
    max_spread: str | None = None
    news_filter_enabled: bool | None = None


class AutoTradeEvaluateBody(BaseModel):
    gateway_connected: bool = False
    broker_connected: bool = False
    market_data_live: bool = False
    risk_engine_pass: bool = False
    risk_engine_reasons: list[str] = Field(default_factory=list)
    account_trading_enabled: bool = False
    mt5_autotrading_enabled: bool = False
    symbol: str = "XAUUSD"
    symbol_tradable: bool = False
    margin_available: bool = False
    no_broker_restrictions: bool = False
    open_positions: int = 0
    session: str = "off_hours"
    spread: str | None = None
    news_blocked: bool = False
    news_reason: str = ""
    daily_loss_exceeded: bool = False


class HealthBody(BaseModel):
    gateway_latency_ms: float = 0
    gateway_available: bool = True
    mt5_connected: bool = True
    cloudflare_tunnel_up: bool = True
    order_latency_ms: float = 0
    journal_latency_ms: float = 0
    research_queue_depth: int = 0
    simulation_queue_depth: int = 0
    oms_queue_depth: int = 0
    decision_throughput_per_min: float = 0


class AckBody(BaseModel):
    alert_id: str


@router.get("/control-center")
def control_center(_user: OperatorUser) -> dict[str, Any]:
    """Control center plus shared execution_state (same source as Auto Trading)."""
    from app.application.services.auto_trading_status import build_auto_trading_status

    plane = get_control_plane()
    settings = get_settings()
    cc = plane.control_center()
    snap = build_auto_trading_status(plane, settings=settings)
    cc["execution_enabled"] = snap.execution_state["execution_enabled"]
    cc["execution_state"] = snap.execution_state
    cc["primary_blocker"] = snap.primary_blocker
    cc["blocking_category"] = snap.blocking_category
    cc["gate_status"] = snap.safety.status
    return cc


@router.get("/launch-readiness")
def get_launch_readiness(_user: OperatorUser) -> dict[str, Any]:
    """OWNER Launch Readiness checklist — WHY + HOW TO RESOLVE per blocker."""
    from app.application.services.launch_readiness import build_launch_readiness

    plane = get_control_plane()
    settings = get_settings()
    # Caller already passed OWNER/ADMIN gate; POST still requires confirmed=true.
    report = build_launch_readiness(plane, settings=settings, owner_authorized=True)
    return report.to_dict()


class LaunchPromoteBody(ConfirmBody):
    activate_auto_trading: bool = True


@router.post("/launch-readiness/promote")
def promote_launch_readiness(
    body: LaunchPromoteBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    """Official SHADOW→CANARY→LIVE via state machine when launch locks clear.

    Never bypasses Risk/Safety. Never flips EXECUTION_ENABLED.
    Demo Certification is optional advisory — not required for LIVE.
    """
    from app.application.services.launch_readiness import promote_to_live_execution

    plane = get_control_plane()
    settings = get_settings()
    op = _operator(user, request, x_forwarded_for)
    result = promote_to_live_execution(
        plane,
        op,
        reason=body.reason,
        confirmed=body.confirmed,
        settings=settings,
        activate_auto_trading=body.activate_auto_trading,
    )
    if not body.confirmed:
        raise HTTPException(status_code=400, detail=result)
    return result


@router.get("/readiness")
def readiness(_user: OperatorUser) -> dict[str, Any]:
    return get_control_plane().readiness_dashboard()


@router.get("/services-health")
def services_health(_user: OperatorUser) -> dict[str, Any]:
    """Per-service status / uptime / latency / last error for operator desks."""
    import time
    from datetime import UTC, datetime

    from app.application.services.auto_trading_status import build_status_facts
    from app.application.services.institutional_ite_runtime import get_ite_runtime
    from app.application.services.institutional_live_probes import LiveProbeCollector
    from app.domain.institutional_trading.operations.production_alerts import (
        evaluate_production_alerts,
        inputs_from_probes,
    )
    from app.domain.institutional_trading.reliability.health import ProbeInputs

    plane = get_control_plane()
    settings = get_settings()
    t0 = time.perf_counter()
    facts, live = build_status_facts(plane, settings=settings)
    probe_ms = (time.perf_counter() - t0) * 1000.0

    runtime = get_ite_runtime()
    probes: ProbeInputs
    if runtime is not None:
        probes = runtime.probes.collect()
    else:
        probes = LiveProbeCollector(settings=settings).collect()

    evaluate_production_alerts(
        plane,
        inputs_from_probes(
            probes,
            plane=plane,
            extra={
                "ticks_fresh": bool(facts.market_data_live),
                "risk_locked": bool(plane.daily_loss_exceeded),
                "safety_locked": bool(plane.kill_switch_armed),
                "database_ok": bool(probes.supabase_up),
                "calendar_ok": True,
            },
        ),
    )

    health = plane.health.latest()
    now = datetime.now(UTC).isoformat()
    gateway_ok = bool(live.get("gateway_connected"))
    broker_ok = bool(live.get("broker_connected"))
    services = [
        {
            "name": "api",
            "status": "up",
            "uptime": "process",
            "heartbeat_at": now,
            "latency_ms": round(probe_ms, 2),
            "last_successful_operation": "services_health",
            "last_error": None,
            "reconnect_count": 0,
        },
        {
            "name": "mt5_gateway",
            "status": "up" if gateway_ok else "down",
            "uptime": "probe",
            "heartbeat_at": now,
            "latency_ms": live.get("gateway_latency_ms"),
            "last_successful_operation": "gateway_probe" if gateway_ok else None,
            "last_error": None if gateway_ok else "gateway offline",
            "reconnect_count": 0,
        },
        {
            "name": "mt5_terminal",
            "status": "up" if broker_ok else "down",
            "uptime": "probe",
            "heartbeat_at": now,
            "latency_ms": float(probes.gateway_latency_ms or 0.0),
            "last_successful_operation": "mt5_probe" if broker_ok else None,
            "last_error": None if broker_ok else "mt5 disconnected",
            "reconnect_count": 0,
        },
        {
            "name": "database",
            "status": "up" if probes.supabase_up else "down",
            "uptime": "probe",
            "heartbeat_at": now,
            "latency_ms": float(probes.database_latency_ms or 0.0),
            "last_successful_operation": "db_probe" if probes.supabase_up else None,
            "last_error": None if probes.supabase_up else "database unavailable",
            "reconnect_count": 0,
        },
        {
            "name": "ops_control_plane",
            "status": "halted" if plane.kill_switch_armed else "up",
            "uptime": "process",
            "heartbeat_at": now,
            "latency_ms": 0.0,
            "last_successful_operation": "control_center",
            "last_error": "kill switch armed" if plane.kill_switch_armed else None,
            "reconnect_count": 0,
            "execution_mode": plane.mode.value,
        },
    ]
    return {
        "as_of": now,
        "ops_health": health.to_dict() if health else None,
        "live": live,
        "services": services,
        "alerts": [a.to_dict() for a in plane.alerts.list(limit=50, unacked_only=True)],
    }


@router.post("/mode")
def set_mode(
    body: ModeBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        target = OpsExecutionMode(body.target.upper())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid mode") from exc
    try:
        result = plane.transition_mode(
            op, target, reason=body.reason, confirmed=body.confirmed
        )
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.message)
    return result.to_dict()


@router.post("/kill-switch/arm")
def arm_kill(
    body: ConfirmBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        plane.arm_kill_switch(op, reason=body.reason, confirmed=body.confirmed)
    except (PermissionDenied, ValueError) as exc:
        raise HTTPException(
            status_code=403 if isinstance(exc, PermissionDenied) else 400,
            detail=str(exc),
        ) from exc
    return {"kill_switch": True}


@router.post("/kill-switch/disarm")
def disarm_kill(
    body: ConfirmBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        plane.disarm_kill_switch(op, reason=body.reason, confirmed=body.confirmed)
    except (PermissionDenied, ValueError) as exc:
        raise HTTPException(
            status_code=403 if isinstance(exc, PermissionDenied) else 400,
            detail=str(exc),
        ) from exc
    return {"kill_switch": False}


@router.post("/config/promote")
def promote(
    body: PromoteBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmation required")
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        rec = plane.promote_config(
            op,
            config_version=body.config_version,
            strategy_version=body.strategy_version,
            reason=body.reason,
            risk_per_trade_pct=(
                Decimal(body.risk_per_trade_pct) if body.risk_per_trade_pct else None
            ),
            max_daily_loss_pct=(
                Decimal(body.max_daily_loss_pct) if body.max_daily_loss_pct else None
            ),
            max_open_trades=body.max_open_trades,
        )
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return rec.to_dict()


@router.post("/rollback")
def rollback(
    body: RollbackBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        rec = plane.rollback(
            op,
            target_config_version=body.target_config_version,
            reason=body.reason,
            confirmed=body.confirmed,
        )
    except (PermissionDenied, ValueError) as exc:
        raise HTTPException(
            status_code=403 if isinstance(exc, PermissionDenied) else 400,
            detail=str(exc),
        ) from exc
    return rec.to_dict()


@router.post("/risk")
def update_risk(
    body: RiskBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmation required")
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        plane.update_risk(
            op,
            risk_per_trade_pct=Decimal(body.risk_per_trade_pct),
            max_daily_loss_pct=Decimal(body.max_daily_loss_pct),
            max_open_trades=body.max_open_trades,
            reason=body.reason,
        )
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return cast("dict[str, Any]", plane.control_center()["risk"])


@router.post("/health")
def post_health(body: HealthBody, _user: OperatorUser) -> dict[str, Any]:
    plane = get_control_plane()
    plane.update_health(
        HealthInputs(
            gateway_latency_ms=body.gateway_latency_ms,
            gateway_available=body.gateway_available,
            mt5_connected=body.mt5_connected,
            cloudflare_tunnel_up=body.cloudflare_tunnel_up,
            order_latency_ms=body.order_latency_ms,
            journal_latency_ms=body.journal_latency_ms,
            research_queue_depth=body.research_queue_depth,
            simulation_queue_depth=body.simulation_queue_depth,
            oms_queue_depth=body.oms_queue_depth,
            decision_throughput_per_min=body.decision_throughput_per_min,
        )
    )
    snap = plane.health.latest()
    return snap.to_dict() if snap else {}


@router.get("/alerts")
def list_alerts(
    _user: OperatorUser,
    unacked_only: bool = False,
) -> dict[str, Any]:
    plane = get_control_plane()
    rows = plane.alerts.list(unacked_only=unacked_only)
    return {
        "alerts": [a.to_dict() for a in rows],
        "grouped": plane.alerts.grouped(unacked_only=unacked_only),
        "unacked_count": plane.alerts.unacked_count(),
    }


@router.post("/alerts/ack")
def ack_alert(
    body: AckBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        plane.acknowledge_alert(op, UUID(body.alert_id))
    except (PermissionDenied, ValueError) as exc:
        raise HTTPException(
            status_code=403 if isinstance(exc, PermissionDenied) else 400,
            detail=str(exc),
        ) from exc
    return {"ok": True}


@router.get("/audit")
def audit_log(_user: OperatorUser, limit: int = 200) -> dict[str, Any]:
    rows = get_control_plane().audit.list(limit=limit)
    return {
        "entries": [e.to_dict() for e in rows],
        "count": get_control_plane().audit.count(),
    }


@router.get("/configs")
def list_configs(_user: OperatorUser) -> dict[str, Any]:
    plane = get_control_plane()
    return {
        "active": (
            active.to_dict() if (active := plane.configs.active()) is not None else None
        ),
        "versions": [c.to_dict() for c in plane.configs.list()],
    }


@router.get("/runbooks")
def list_runbooks(_user: OperatorUser) -> dict[str, Any]:
    return {"runbooks": get_control_plane().runbooks.list()}


@router.post("/runbooks/{runbook_id}/execute")
def execute_runbook(
    runbook_id: str,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        return plane.execute_runbook(op, runbook_id)
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/auto-trading")
def get_auto_trading(_user: OperatorUser) -> dict[str, Any]:
    """Auto Trading status — live gateway probes (same source as Broker/Monitoring)."""
    from app.application.services.auto_trading_status import build_auto_trading_status
    from app.application.services.ops_state_persistence import ops_state_diagnostics

    plane = get_control_plane()
    settings = get_settings()
    snap = build_auto_trading_status(plane, settings=settings)
    safety = snap.safety
    orchestrator = None
    recent_attempts: list[dict[str, Any]] = []
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime

        runtime = get_ite_runtime()
        if runtime is not None:
            orchestrator = runtime.status()
            journal = getattr(runtime.execution.bridge, "journal", None)
            if journal is not None and hasattr(journal, "list"):
                recent_attempts = [
                    r.to_dict() if hasattr(r, "to_dict") else dict(r)
                    for r in journal.list(limit=20)
                ]
    except Exception:
        orchestrator = None
    return {
        "status": safety.status,
        "allowed": safety.allowed,
        "failed_reasons": list(safety.failed_reasons),
        "reason_groups": snap.reason_groups,
        "primary_blocker": snap.primary_blocker,
        "blocking_category": snap.blocking_category,
        "execution_state": snap.execution_state,
        "conditions": [c.to_dict() for c in safety.conditions],
        "policy": plane.auto_trade_policy().to_dict(),
        "emergency_stop": plane.kill_switch_armed,
        "execution_enabled": bool(snap.execution_state["execution_enabled"]),
        "ops_mode": plane.mode.value,
        "live": snap.live,
        "facts": {
            "gateway_connected": snap.facts.gateway_connected,
            "broker_connected": snap.facts.broker_connected,
            "market_data_live": snap.facts.market_data_live,
            "risk_engine_pass": snap.facts.risk_engine_pass,
            "risk_engine_evaluated": snap.facts.risk_engine_evaluated,
            "status_snapshot": snap.facts.status_snapshot,
        },
        "orchestrator": orchestrator,
        "recent_execution_attempts": recent_attempts,
        "persistence": ops_state_diagnostics(),
    }


@router.get("/witness-health")
def get_witness_health(_user: OperatorUser) -> dict[str, Any]:
    """Witness authentication vs trading execution health (read-only).

    Auth failures (HTTP 401) never alter Production Acceptance.
    """
    from app.application.services.witness_observability import dashboard_payload

    return dashboard_payload()


@router.get("/strategy-diagnostics")
def get_strategy_diagnostics(
    _user: OperatorUser,
    limit: int = 100,
) -> dict[str, Any]:
    """Operations → Strategy Diagnostics — why NO_TRADE (observation only).

    Never mutates strategy, risk, safety, OMS, or MT5. Never lowers thresholds
    or forces execution.
    """
    from app.application.services.strategy_diagnostics import (
        get_strategy_diagnostics_store,
    )

    window = max(1, min(int(limit or 100), 100))
    payload = get_strategy_diagnostics_store().snapshot(limit=window)
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime

        runtime = get_ite_runtime()
        if runtime is not None:
            payload["orchestrator_cycles"] = runtime.status().get("cycles")
            payload["orchestrator_last_cycle"] = runtime.status().get("last_cycle")
    except Exception:
        payload["orchestrator_cycles"] = None
        payload["orchestrator_last_cycle"] = None
    return payload


@router.get("/live-execution-explain")
def get_live_execution_explain(
    _user: OperatorUser,
    limit: int = 50,
) -> dict[str, Any]:
    """Operations → Live Execution Explain Mode (decision cards only).

    Never mutates Strategy, Thresholds, Risk, Safety, or OMS.
    """
    window = max(1, min(int(limit or 50), 100))
    from app.application.services.live_execution_explain import (
        explain_snapshot_from_diagnostics,
    )
    from app.application.services.strategy_diagnostics import (
        get_strategy_diagnostics_store,
    )

    diagnostics = get_strategy_diagnostics_store().snapshot(limit=window)
    return explain_snapshot_from_diagnostics(diagnostics)


@router.get("/adaptive-opportunity")
def get_adaptive_opportunity(
    _user: OperatorUser,
    limit: int = 50,
) -> dict[str, Any]:
    """Operations → Adaptive Opportunity Mode (gap analysis only).

    Never mutates Strategy, Thresholds, Risk, Safety, or OMS.
    Never lowers gates or forces trades.
    """
    window = max(1, min(int(limit or 50), 100))
    from app.application.services.adaptive_opportunity import (
        opportunity_snapshot_from_diagnostics,
    )
    from app.application.services.strategy_diagnostics import (
        get_strategy_diagnostics_store,
    )

    diagnostics = get_strategy_diagnostics_store().snapshot(limit=window)
    return opportunity_snapshot_from_diagnostics(diagnostics)


@router.get("/adaptive-opportunity-timeline")
def get_adaptive_opportunity_timeline(
    _user: OperatorUser,
    limit: int = 100,
) -> dict[str, Any]:
    """Operations → Adaptive Opportunity Timeline (history + prediction).

    Never mutates Strategy, Risk, Safety, Thresholds, or OMS.
    """
    window = max(1, min(int(limit or 100), 100))
    from app.application.services.adaptive_opportunity_timeline import (
        timeline_snapshot_from_diagnostics,
    )
    from app.application.services.strategy_diagnostics import (
        get_strategy_diagnostics_store,
    )

    diagnostics = get_strategy_diagnostics_store().snapshot(limit=window)
    return timeline_snapshot_from_diagnostics(diagnostics, limit=window)


@router.get("/strategy-intelligence-center")
def get_strategy_intelligence_center(
    _user: OperatorUser,
    days: int = 90,
) -> dict[str, Any]:
    """Operations → Strategy Intelligence Center (read-only post-trade IQ).

    Never mutates Strategy, Risk, Safety, OMS, Thresholds, or Auto Trading.
    Never auto-optimizes.
    """
    window_days = max(1, min(int(days or 90), 365))
    from app.application.services.strategy_intelligence_center import (
        build_strategy_intelligence_center,
    )

    return build_strategy_intelligence_center(days=window_days)


@router.get("/threshold-promotion")
def get_threshold_promotion(_user: OperatorUser) -> dict[str, Any]:
    """Operations → Threshold Promotion status (never auto-applies)."""
    from app.application.services.threshold_promotion import status_payload

    return status_payload()


@router.post("/threshold-promotion/promote")
def post_threshold_promote(
    body: ThresholdPromoteBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    """Explicit promote Q70/C75 — requires confirmed=true. Never automatic."""
    from app.application.services.threshold_promotion import promote_candidate

    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmation required")
    op = _operator(user, request, x_forwarded_for)
    try:
        return promote_candidate(
            operator=op,
            reason=body.reason,
            confirmed=body.confirmed,
            evidence_reference=body.evidence_reference,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/threshold-promotion/rollback")
def post_threshold_rollback(
    body: ThresholdRollbackBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    """Single-click rollback to Q80/C80. Never automatic."""
    from app.application.services.threshold_promotion import rollback_to_production

    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmation required")
    op = _operator(user, request, x_forwarded_for)
    try:
        return rollback_to_production(
            operator=op,
            reason=body.reason,
            confirmed=body.confirmed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/experimental-threshold")
def get_experimental_threshold(_user: OperatorUser) -> dict[str, Any]:
    """Operations → Experimental Threshold Profile (Q75/C75 overlay)."""
    from app.application.services.experimental_threshold_profile import status_payload

    return status_payload()


@router.post("/experimental-threshold/activate")
def post_experimental_activate(
    body: ExperimentalActivateBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    """Explicit activate EXPERIMENTAL_75 — requires confirmed=true."""
    from app.application.services.experimental_threshold_profile import (
        activate_experimental_75,
    )

    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmation required")
    op = _operator(user, request, x_forwarded_for)
    try:
        return activate_experimental_75(
            operator=op,
            reason=body.reason,
            confirmed=body.confirmed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/experimental-threshold/rollback")
def post_experimental_rollback(
    body: ExperimentalRollbackBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    """One-click rollback Experimental → Institutional Q80/C80."""
    from app.application.services.experimental_threshold_profile import (
        rollback_experimental_to_production,
    )

    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmation required")
    op = _operator(user, request, x_forwarded_for)
    try:
        return rollback_experimental_to_production(
            operator=op,
            reason=body.reason,
            confirmed=body.confirmed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/experimental-threshold/report")
def get_experimental_report(_user: OperatorUser) -> dict[str, Any]:
    """Latest EXPERIMENTAL_THRESHOLD_REPORT (empty until 100 evals)."""
    from app.application.services.experimental_threshold_profile import (
        generate_experimental_threshold_report,
        get_experimental_threshold_store,
        status_payload,
    )

    store = get_experimental_threshold_store()
    if store.last_report is not None:
        return store.last_report
    if store.evaluations > 0:
        return generate_experimental_threshold_report(store)
    return {
        "status": "empty",
        "message": "Report generates automatically after 100 eligible evaluations.",
        "evaluations": store.evaluations,
        "eval_target": 100,
        **{k: status_payload()[k] for k in ("profile_id", "active", "badge")},
    }


@router.post("/auto-trading")
def update_auto_trading(
    body: AutoTradeControlsBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmation required")
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        policy = plane.update_auto_trade_controls(
            op,
            enabled=body.enabled,
            run_state=body.run_state,
            max_open_positions=body.max_open_positions,
            risk_per_trade_pct=(
                Decimal(body.risk_per_trade_pct)
                if body.risk_per_trade_pct is not None
                else None
            ),
            max_daily_loss_pct=(
                Decimal(body.max_daily_loss_pct)
                if body.max_daily_loss_pct is not None
                else None
            ),
            allowed_sessions=(
                tuple(body.allowed_sessions)
                if body.allowed_sessions is not None
                else None
            ),
            allowed_symbols=(
                tuple(body.allowed_symbols)
                if body.allowed_symbols is not None
                else None
            ),
            max_spread=(
                Decimal(body.max_spread) if body.max_spread is not None else None
            ),
            news_filter_enabled=body.news_filter_enabled,
            reason=body.reason,
        )
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"policy": policy.to_dict()}


@router.post("/auto-trading/evaluate")
def evaluate_auto_trading(
    body: AutoTradeEvaluateBody,
    _user: OperatorUser,
) -> dict[str, Any]:
    """Evaluate live safety conditions and return exact failure reasons."""
    plane = get_control_plane()
    settings = get_settings()
    safety = plane.evaluate_auto_trading(
        AutoTradeLiveFacts(
            gateway_connected=body.gateway_connected,
            broker_connected=body.broker_connected,
            market_data_live=body.market_data_live,
            risk_engine_pass=body.risk_engine_pass,
            risk_engine_reasons=tuple(body.risk_engine_reasons),
            account_trading_enabled=body.account_trading_enabled,
            mt5_autotrading_enabled=body.mt5_autotrading_enabled,
            symbol=body.symbol,
            symbol_tradable=body.symbol_tradable,
            margin_available=body.margin_available,
            no_broker_restrictions=body.no_broker_restrictions,
            open_positions=body.open_positions,
            session=body.session,
            spread=Decimal(body.spread) if body.spread is not None else None,
            news_blocked=body.news_blocked,
            news_reason=body.news_reason,
            daily_loss_exceeded=body.daily_loss_exceeded,
            emergency_stop=plane.kill_switch_armed,
            ops_mode=plane.mode.value,
            execution_enabled=bool(getattr(settings, "execution_enabled", False)),
        )
    )
    return safety.to_dict()


@router.post("/auto-trading/emergency-stop")
def emergency_stop_auto_trading(
    body: ConfirmBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    try:
        plane.emergency_stop(op, reason=body.reason, confirmed=body.confirmed)
    except (PermissionDenied, ValueError) as exc:
        raise HTTPException(
            status_code=403 if isinstance(exc, PermissionDenied) else 400,
            detail=str(exc),
        ) from exc
    return {
        "emergency_stop": True,
        "auto_trading_enabled": False,
        "kill_switch": True,
    }


@router.get("/auto-trading/live-certification")
def live_certification_probe(_user: OperatorUser) -> dict[str, Any]:
    """Step 1 probe — STOP with exact reasons when live conditions fail.

    Never sends orders. Never fabricates broker fills.
    """
    from app.application.services.live_auto_trade_certification import (
        get_live_cert_service,
    )

    svc = get_live_cert_service()
    payload = svc.probe_local_environment()
    last = svc.last_report()
    payload["last_report"] = last.to_dict() if last is not None else None
    return payload


class LiveCertAttemptBody(BaseModel):
    reason: str = Field(min_length=1)
    confirmed: bool = False
    # Live facts — caller must supply measured values; defaults fail-closed
    gateway_connected: bool = False
    broker_connected: bool = False
    market_data_live: bool = False
    risk_engine_pass: bool = False
    risk_engine_reasons: list[str] = Field(default_factory=list)
    account_trading_enabled: bool = False
    mt5_autotrading_enabled: bool = False
    symbol: str = "XAUUSD"
    symbol_tradable: bool = False
    margin_available: bool = False
    no_broker_restrictions: bool = False
    open_positions: int = 0
    session: str = "off_hours"
    spread: str | None = None
    news_blocked: bool = False
    news_reason: str = ""
    daily_loss_exceeded: bool = False
    mt5_logged_in: bool = False
    exposure_pass: bool = False
    drawdown_pass: bool = False
    account_is_demo: bool = False
    # Optional real trade evidence (omit unless broker returned real tickets)
    trade: dict[str, Any] | None = None
    stages_completed: dict[str, bool] = Field(default_factory=dict)


@router.post("/auto-trading/live-certification/attempt")
def live_certification_attempt(
    body: LiveCertAttemptBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    """Attempt Demo certification. Refuses without real trade evidence.

    Never auto-switches SHADOW→LIVE. On failure disables Auto Trading.
    """
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmation required")

    from app.application.services.live_auto_trade_certification import (
        get_live_cert_service,
    )
    from app.domain.institutional_trading.live_certification import LiveTradeEvidence

    plane = get_control_plane()
    op = _operator(user, request, x_forwarded_for)
    settings = get_settings()
    facts = AutoTradeLiveFacts(
        gateway_connected=body.gateway_connected,
        broker_connected=body.broker_connected,
        market_data_live=body.market_data_live,
        risk_engine_pass=body.risk_engine_pass,
        risk_engine_reasons=tuple(body.risk_engine_reasons),
        account_trading_enabled=body.account_trading_enabled,
        mt5_autotrading_enabled=body.mt5_autotrading_enabled,
        symbol=body.symbol,
        symbol_tradable=body.symbol_tradable,
        margin_available=body.margin_available,
        no_broker_restrictions=body.no_broker_restrictions,
        open_positions=body.open_positions,
        session=body.session,
        spread=Decimal(body.spread) if body.spread is not None else None,
        news_blocked=body.news_blocked,
        news_reason=body.news_reason,
        daily_loss_exceeded=body.daily_loss_exceeded,
        emergency_stop=plane.kill_switch_armed,
        ops_mode=plane.mode.value,
        execution_enabled=bool(getattr(settings, "execution_enabled", False)),
    )

    trade: LiveTradeEvidence | None = None
    if body.trade is not None:
        t = body.trade
        try:
            trade = LiveTradeEvidence(
                broker=str(t.get("broker") or ""),
                account_type=str(t.get("account_type") or ""),
                symbol=str(t.get("symbol") or "XAUUSD"),
                volume=Decimal(str(t.get("volume") or "0")),
                ticket=int(t.get("ticket") or 0),
                deal=int(t.get("deal") or 0),
                entry=Decimal(str(t.get("entry") or "0")),
                exit=(
                    Decimal(str(t["exit"]))
                    if t.get("exit") is not None
                    else None
                ),
                profit_loss=(
                    Decimal(str(t["profit_loss"]))
                    if t.get("profit_loss") is not None
                    else None
                ),
                execution_latency_ms=float(t.get("execution_latency_ms") or 0),
                margin_used=(
                    Decimal(str(t["margin_used"]))
                    if t.get("margin_used") is not None
                    else None
                ),
                risk_pct=Decimal(str(t.get("risk_pct") or "0")),
                audit_id=str(t.get("audit_id") or ""),
                position_closed=bool(t.get("position_closed")),
                history_recorded=bool(t.get("history_recorded")),
                analytics_recorded=bool(t.get("analytics_recorded")),
                signal_time_ms=(
                    float(t["signal_time_ms"])
                    if t.get("signal_time_ms") is not None
                    else None
                ),
                risk_time_ms=(
                    float(t["risk_time_ms"])
                    if t.get("risk_time_ms") is not None
                    else None
                ),
                order_check_time_ms=(
                    float(t["order_check_time_ms"])
                    if t.get("order_check_time_ms") is not None
                    else None
                ),
                broker_fill_time_ms=(
                    float(t["broker_fill_time_ms"])
                    if t.get("broker_fill_time_ms") is not None
                    else None
                ),
                total_execution_time_ms=(
                    float(t["total_execution_time_ms"])
                    if t.get("total_execution_time_ms") is not None
                    else None
                ),
                slippage=(
                    str(t["slippage"]) if t.get("slippage") is not None else None
                ),
                spread=str(t["spread"]) if t.get("spread") is not None else None,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail=f"invalid trade evidence: {exc}"
            ) from exc

    report = get_live_cert_service().run_certification_attempt(
        op,
        facts=facts,
        mt5_logged_in=body.mt5_logged_in,
        exposure_pass=body.exposure_pass,
        drawdown_pass=body.drawdown_pass,
        account_is_demo=body.account_is_demo,
        trade=trade,
        stage_completed=body.stages_completed,
        reason=body.reason,
    )
    return report.to_dict()


@router.get("/auto-trading/live-certification/report")
def live_certification_report(_user: OperatorUser) -> dict[str, Any]:
    from app.application.services.live_auto_trade_certification import (
        get_live_cert_service,
    )

    last = get_live_cert_service().last_report()
    if last is None:
        raise HTTPException(status_code=404, detail="no live certification report yet")
    return last.to_dict()
