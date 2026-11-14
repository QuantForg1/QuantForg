"""Phase 5 — Institutional Ops Control Center API (read-mostly facade).

Prefix: /institutional-ops
Never order_send. Never auto LIVE deploy. Mutations stay on existing routers.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.application.services import institutional_ops_control as ioc
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/institutional-ops", tags=["institutional-ops-control"])


async def _load_attempts(user_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
    try:
        from app.presentation.dependencies.execution import get_execution_uow_factory

        factory = get_execution_uow_factory()
    except Exception:
        return []
    try:
        async with factory() as uow:
            rows = await uow.attempts.list_for_user(user_id, limit=limit)
            return [a.to_dict() for a in rows]
    except Exception:
        return []


async def _load_decisions(user_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
    try:
        from app.presentation.dependencies.execution import get_execution_uow_factory

        factory = get_execution_uow_factory()
    except Exception:
        return []
    try:
        async with factory() as uow:
            rows = await uow.decisions.list_recent_for_user(user_id, limit=limit)
            return [d.to_dict() for d in rows]
    except Exception:
        return []


def _prp_incidents() -> list[dict[str, Any]]:
    try:
        from app.domain.production_reliability.incidents import list_incidents

        rows = list_incidents()
        if isinstance(rows, list):
            out: list[dict[str, Any]] = []
            for r in rows:
                if isinstance(r, dict):
                    out.append(r)
                elif hasattr(r, "__dict__"):
                    out.append(
                        {
                            "incident_id": getattr(r, "id", None)
                            or getattr(r, "incident_id", None),
                            "severity": getattr(r, "severity", None),
                            "status": getattr(r, "status", None),
                            "created_at": str(getattr(r, "created_at", "") or ""),
                            "updated_at": str(getattr(r, "updated_at", "") or ""),
                            "detail": getattr(r, "summary", None)
                            or getattr(r, "detail", None),
                        }
                    )
            return out
    except Exception:
        return []
    return []


def _audit_events() -> list[dict[str, Any]]:
    try:
        from app.application.services import audit_governance as ag

        pack = ag.run_audit_governance(limit=100)
        if isinstance(pack, dict):
            rows = pack.get("events") or pack.get("audit_events") or []
            return [r for r in rows if isinstance(r, dict)]
    except Exception:
        return []
    return []


def _approval_list(fn_name: str, module_path: str) -> list[dict[str, Any]]:
    try:
        import importlib

        mod = importlib.import_module(module_path)
        fn = getattr(mod, fn_name, None)
        if not callable(fn):
            # try dashboard scrape
            dash = getattr(mod, "build_islm_dashboard", None) or getattr(
                mod, "build_irdp_dashboard", None
            )
            if callable(dash):
                pack = dash()
                if isinstance(pack, dict):
                    for key in ("approvals", "pending_approvals", "approval_queue"):
                        val = pack.get(key)
                        if isinstance(val, list):
                            return [x for x in val if isinstance(x, dict)]
            return []
        pack = fn()
        if isinstance(pack, dict):
            rows = (
                pack.get("approvals")
                or pack.get("pending_approvals")
                or pack.get("items")
                or []
            )
            return [r for r in rows if isinstance(r, dict)]
        if isinstance(pack, list):
            return [r for r in pack if isinstance(r, dict)]
    except Exception:
        return []
    return []


@router.get("/health")
async def ops_health(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return ioc.health()


@router.get("/summary")
async def ops_summary(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return ioc.summary()


@router.get("/operations/overview")
async def operations_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return ioc.operations_overview()


@router.get("/strategy-lifecycle/overview")
async def strategy_lifecycle_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return ioc.strategy_lifecycle_overview()


@router.get("/execution/overview")
async def execution_overview(user: CurrentUser) -> dict[str, Any]:
    attempts = await _load_attempts(user.id)
    decisions = await _load_decisions(user.id)
    return ioc.execution_overview(attempts=attempts, decisions=decisions)


@router.get("/accounts/overview")
async def accounts_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    ops_summary: dict[str, Any] = {}
    dispatch_status: dict[str, Any] = {}
    try:
        import importlib

        ma = importlib.import_module("app.application.services.multi_account_ops")
        if hasattr(ma, "ops_summary"):
            raw = ma.ops_summary()
            if isinstance(raw, dict):
                ops_summary = raw
        if hasattr(ma, "dispatch_status"):
            raw = ma.dispatch_status()
            if isinstance(raw, dict):
                dispatch_status = raw
    except Exception:
        # Multi-account services may be unavailable in local/CI — honest empty.
        ops_summary = {}
        dispatch_status = {}
    return ioc.accounts_overview(
        ops_summary=ops_summary,
        dispatch_status=dispatch_status,
    )


@router.get("/risk/overview")
async def risk_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    ati_alerts: list[dict[str, Any]] = []
    try:
        from app.domain.ai_trading_intelligence.risk_alerts import build_ai_risk_alerts

        alerts = build_ai_risk_alerts(
            portfolio={},
            strategy_health={},
            signal_quality_drift={},
            execution={},
        )
        for a in alerts:
            ati_alerts.append(
                {
                    "code": a.code,
                    "severity": a.severity,
                    "title": a.title,
                    "explanation": a.explanation,
                    "recommended_action": a.recommended_action,
                    "advisory_only": True,
                }
            )
    except Exception:
        ati_alerts = []
    return ioc.risk_overview(ati_alerts=ati_alerts)


@router.get("/incidents/overview")
async def incidents_overview(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return ioc.incidents_overview(prp_incidents=_prp_incidents())


@router.get("/governance/summary")
async def governance_summary(user: CurrentUser) -> dict[str, Any]:
    _ = user
    islm = _approval_list(
        "islm_approvals",
        "app.application.services.institutional_strategy_lifecycle",
    )
    irdp = _approval_list(
        "irdp_approvals",
        "app.application.services.institutional_release_deployment",
    )
    qsf = _approval_list(
        "qsf_approvals",
        "app.application.services.quantforg_strategy_factory",
    )
    return ioc.governance_summary(
        audit_events=_audit_events(),
        islm_approvals=islm,
        irdp_approvals=irdp,
        qsf_approvals=qsf,
    )
