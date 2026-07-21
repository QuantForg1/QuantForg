"""Production Readiness Program orchestrator — compose, never mutate execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.production_readiness.audit import ReadinessAuditLog
from app.domain.production_readiness.checklists import (
    build_post_trade_checklist,
    build_pre_trade_checklist,
)
from app.domain.production_readiness.config import (
    DEFAULT_PR_CONFIG,
    HealthPolicies,
    ProductionReadinessConfig,
)
from app.domain.production_readiness.panel import PanelSnapshot, panel


def _panel_status(raw: object) -> str:
    value = str(raw or "unavailable")
    if value in ("available", "empty", "unavailable"):
        return value
    return "available"


@dataclass
class ReadinessFeeds:
    control_center: dict[str, Any] | None = None
    readiness: dict[str, Any] | None = None
    reliability: dict[str, Any] | None = None
    incidents: list[dict[str, Any]] | None = None
    recovery_events: list[dict[str, Any]] | None = None
    runbooks: list[dict[str, Any]] | None = None
    ops_audit: list[dict[str, Any]] | None = None
    certification: dict[str, Any] | None = None
    go_nogo: dict[str, Any] | None = None
    shadow_readiness: dict[str, Any] | None = None
    pre_trade_facts: dict[str, Any] | None = None
    post_trade_rows: list[dict[str, Any]] | None = None
    security: dict[str, Any] | None = None
    timeline: list[dict[str, Any]] | None = None


@dataclass
class ProductionReadinessCenter:
    config: ProductionReadinessConfig = field(
        default_factory=lambda: DEFAULT_PR_CONFIG
    )
    audit: ReadinessAuditLog = field(default_factory=ReadinessAuditLog)

    def __post_init__(self) -> None:
        self.audit.max_events = self.config.max_audit

    @property
    def policies(self) -> HealthPolicies:
        return self.config.health_policies

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "capabilities": {
                "changes_execution_architecture": False,
                "bypass_risk": False,
                "bypass_safety": False,
                "order_send": False,
                "fabricate_metrics": False,
                "mutations_via_ops_only": True,
                "recovery_never_retries_orders": True,
                "health_policies_configurable": True,
                "auditable_failures": True,
                "logged_recoveries": True,
            },
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def update_policies(self, updates: dict[str, Any]) -> dict[str, Any]:
        self.config.health_policies = self.config.health_policies.update(updates)
        self.audit.record(
            action="policies.update",
            ok=True,
            detail="Health policies updated (hard locks unchanged)",
            operator=str(updates.get("operator") or "operator"),
            meta={"keys": sorted(k for k in updates if k != "operator")},
        )
        return self.config.health_policies.to_dict()

    def log_recovery(
        self,
        *,
        action: str,
        ok: bool,
        detail: str,
        operator: str = "system",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.audit.record(
            action=f"recovery.{action}",
            ok=ok,
            detail=detail,
            operator=operator,
            meta=meta,
        ).to_dict()

    def log_failure(
        self,
        *,
        action: str,
        detail: str,
        operator: str = "system",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.audit.record(
            action=f"failure.{action}",
            ok=False,
            detail=detail,
            operator=operator,
            meta=meta,
        ).to_dict()

    def list_audit(self, *, limit: int = 50) -> dict[str, Any]:
        rows = self.audit.list(limit=limit)
        return {
            "status": "available" if rows else "empty",
            "events": [e.to_dict() for e in rows],
        }

    def build_dashboard(self, feeds: ReadinessFeeds) -> dict[str, Any]:
        panels = [
            self._pre_trade(feeds),
            self._post_trade(feeds),
            self._circuit_breakers(feeds),
            self._health_policies(feeds),
            self._recovery(feeds),
            self._incidents(feeds),
            self._playbooks(feeds),
            self._deployment(feeds),
            self._security(feeds),
            self._disaster(feeds),
        ]
        return {
            "product": self.config.product,
            "version": self.config.version,
            "never_changes_execution_architecture": True,
            "never_bypasses_risk": True,
            "never_bypasses_safety": True,
            "fabricates_metrics": False,
            "generated_at": datetime.now(UTC).isoformat(),
            "panels": {p.panel_id: p.to_dict() for p in panels},
            "panel_order": [p.panel_id for p in panels],
            "deep_links": {
                "ops": "/ops",
                "monitoring": "/monitoring",
                "mission_control": "/mission-control",
                "risk": "/risk",
                "terminal": "/terminal",
                "execution_intel": "/execution-intel",
            },
            "audit_tail": [e.to_dict() for e in self.audit.list(limit=10)],
        }

    def _pre_trade(self, feeds: ReadinessFeeds) -> PanelSnapshot:
        checklist = build_pre_trade_checklist(feeds.pre_trade_facts)
        status = _panel_status(checklist.get("status"))
        return panel(
            "pre_trade_validation",
            "Pre-Trade Validation Checklist",
            source="execution_intelligence.checklist|risk|safety",
            data=checklist if status != "unavailable" else {},
            status=status,
            message=str(
                checklist.get("message")
                or checklist.get("note")
                or "Diagnostic only — does not place orders"
            ),
        )

    def _post_trade(self, feeds: ReadinessFeeds) -> PanelSnapshot:
        checklist = build_post_trade_checklist(feeds.post_trade_rows)
        status = _panel_status(checklist.get("status"))
        return panel(
            "post_trade_validation",
            "Post-Trade Validation Checklist",
            source="execution_intelligence.post_trade",
            data=checklist if status != "unavailable" else {},
            status=status,
            message=str(checklist.get("message") or ""),
        )

    def _circuit_breakers(self, feeds: ReadinessFeeds) -> PanelSnapshot:
        cc = feeds.control_center
        if not cc:
            return panel(
                "circuit_breakers",
                "Circuit Breakers",
                source="ite.ops.control_center",
                status="unavailable",
                message="Control center feed unavailable",
            )
        risk = cc.get("risk") if isinstance(cc.get("risk"), dict) else {}
        auto = (
            cc.get("auto_trading")
            if isinstance(cc.get("auto_trading"), dict)
            else {}
        )
        data = {
            "kill_switch": cc.get("kill_switch"),
            "oms_orders_allowed": cc.get("oms_orders_allowed"),
            "execution_mode": cc.get("execution_mode"),
            "system_status": cc.get("system_status"),
            "daily_loss_exceeded": risk.get("daily_loss_exceeded"),
            "auto_trading_status": auto.get("status"),
            "mutations_href": "/ops",
            "never_bypasses_risk": True,
            "never_bypasses_safety": True,
        }
        return panel(
            "circuit_breakers",
            "Circuit Breakers",
            source="ite.ops.control_center",
            data=data,
            message="Breaker mutations only via Ops control plane",
        )

    def _health_policies(self, feeds: ReadinessFeeds) -> PanelSnapshot:
        health = None
        if feeds.control_center and isinstance(
            feeds.control_center.get("health"), dict
        ):
            health = feeds.control_center.get("health")
        elif feeds.reliability and isinstance(feeds.reliability.get("health"), dict):
            health = feeds.reliability.get("health")
        elif feeds.readiness:
            health = {
                "health_score": feeds.readiness.get("health_score"),
                "gateway_available": feeds.readiness.get("gateway") == "up",
                "mt5_connected": feeds.readiness.get("mt5") == "connected",
            }
        evaluation = self.policies.evaluate(
            health if isinstance(health, dict) else None
        )
        if evaluation.get("status") == "unavailable":
            return panel(
                "platform_health_policies",
                "Platform Health Policies",
                source="production_readiness.health_policies",
                status="unavailable",
                message=str(evaluation.get("message") or ""),
                data={"policies": self.policies.to_dict()},
            )
        return panel(
            "platform_health_policies",
            "Platform Health Policies",
            source="production_readiness.health_policies",
            data={
                "policies": self.policies.to_dict(),
                "evaluation": evaluation,
            },
            message="Thresholds configurable — Risk/Safety bypass locked off",
        )

    def _recovery(self, feeds: ReadinessFeeds) -> PanelSnapshot:
        events = feeds.recovery_events
        if events is None and feeds.reliability is None:
            return panel(
                "automatic_recovery",
                "Automatic Recovery Workflows",
                source="ite.reliability.recovery",
                status="unavailable",
                message="Recovery feed unavailable",
            )
        rows = list(events or [])
        if not rows and isinstance(feeds.reliability, dict):
            raw = feeds.reliability.get("recovery_events")
            if isinstance(raw, list):
                rows = [r for r in raw if isinstance(r, dict)]
        data = {
            "events": rows[:30],
            "event_count": len(rows),
            "actions": ["gateway", "mt5", "safe-read"],
            "never_retries_order_send": True,
            "mutations_href": "/ops",
            "api_prefix": "/ite/reliability/recovery",
        }
        if not rows:
            return panel(
                "automatic_recovery",
                "Automatic Recovery Workflows",
                source="ite.reliability.recovery",
                status="empty",
                message="No recovery events logged yet",
                data=data,
            )
        return panel(
            "automatic_recovery",
            "Automatic Recovery Workflows",
            source="ite.reliability.recovery",
            data=data,
            message="Safe reconnect/reads only — every recovery must be logged",
        )

    def _incidents(self, feeds: ReadinessFeeds) -> PanelSnapshot:
        if feeds.incidents is None and feeds.reliability is None:
            return panel(
                "incident_manager",
                "Incident Manager",
                source="ite.reliability.incidents",
                status="unavailable",
                message="Incident feed unavailable",
            )
        rows = list(feeds.incidents or [])
        if not rows and isinstance(feeds.reliability, dict):
            active = feeds.reliability.get("active_incidents")
            if isinstance(active, list):
                rows = [r for r in active if isinstance(r, dict)]
        data = {
            "incidents": rows[:30],
            "open_count": len(rows),
            "mutations_href": "/ops",
        }
        if not rows:
            return panel(
                "incident_manager",
                "Incident Manager",
                source="ite.reliability.incidents",
                status="empty",
                message="No open incidents",
                data=data,
            )
        return panel(
            "incident_manager",
            "Incident Manager",
            source="ite.reliability.incidents",
            data=data,
        )

    def _playbooks(self, feeds: ReadinessFeeds) -> PanelSnapshot:
        if feeds.runbooks is None:
            return panel(
                "operator_playbooks",
                "Operator Playbooks",
                source="ite.ops.runbooks",
                status="unavailable",
                message="Runbook catalog unavailable",
            )
        rows = [r for r in feeds.runbooks if isinstance(r, dict)]
        data = {
            "runbooks": rows,
            "count": len(rows),
            "mutations_href": "/ops",
            "execute_api": "/ite/ops/runbooks/{id}/execute",
        }
        if not rows:
            return panel(
                "operator_playbooks",
                "Operator Playbooks",
                source="ite.ops.runbooks",
                status="empty",
                message="No runbooks registered",
                data=data,
            )
        return panel(
            "operator_playbooks",
            "Operator Playbooks",
            source="ite.ops.runbooks",
            data=data,
            message="Execute via Ops — actions are audited",
        )

    def _deployment(self, feeds: ReadinessFeeds) -> PanelSnapshot:
        cert = feeds.certification
        go = feeds.go_nogo
        shadow = feeds.shadow_readiness
        cc = feeds.control_center or {}
        if cert is None and go is None and shadow is None and not cc:
            return panel(
                "deployment_verification",
                "Deployment Verification Dashboard",
                source="ite.certification|shadow.readiness",
                status="unavailable",
                message="Deployment verification feeds unavailable",
            )
        data: dict[str, Any] = {
            "config_version": cc.get("config_version"),
            "strategy_version": cc.get("strategy_version"),
            "git_commit": cc.get("git_commit"),
            "execution_mode": cc.get("execution_mode"),
            "deep_link": "/ops",
            "auto_promote": False,
        }
        if cert is not None:
            data["certification"] = cert
        if go is not None:
            data["go_nogo"] = go
        if shadow is not None:
            data["shadow_readiness"] = shadow
        return panel(
            "deployment_verification",
            "Deployment Verification Dashboard",
            source="ite.certification|shadow.readiness",
            data=data,
            message="Verification only — never auto-promotes live execution",
        )

    def _security(self, feeds: ReadinessFeeds) -> PanelSnapshot:
        cc = feeds.control_center or {}
        sec = feeds.security
        if not cc and sec is None:
            return panel(
                "security_hardening",
                "Security Hardening",
                source="ops.security|control_center",
                status="unavailable",
                message="Security posture feed unavailable",
            )
        data: dict[str, Any] = {
            "kill_switch": cc.get("kill_switch"),
            "oms_orders_allowed": cc.get("oms_orders_allowed"),
            "execution_mode": cc.get("execution_mode"),
            "hard_locks": {
                "bypass_risk": False,
                "bypass_safety": False,
                "order_send_from_readiness": False,
            },
            "deep_links": {
                "settings": "/settings",
                "gateway": "/gateway",
                "ops": "/ops",
            },
        }
        if sec is not None:
            data["security"] = sec
        return panel(
            "security_hardening",
            "Security Hardening",
            source="ops.security|control_center",
            data=data,
            message="Read-only posture — hardening mutations stay on Ops/Settings",
        )

    def _disaster(self, feeds: ReadinessFeeds) -> PanelSnapshot:
        runbooks = feeds.runbooks
        recovery = feeds.recovery_events
        audit = feeds.ops_audit
        if runbooks is None and recovery is None and audit is None:
            return panel(
                "disaster_recovery",
                "Disaster Recovery Center",
                source="ite.ops.runbooks|reliability.recovery",
                status="unavailable",
                message="DR feeds unavailable",
            )
        dr_ids = {
            "emergency_shutdown",
            "rollback",
            "gateway_restart",
            "mt5_reconnect",
        }
        dr_books = [
            r
            for r in (runbooks or [])
            if isinstance(r, dict)
            and str(r.get("id") or r.get("runbook_id") or "") in dr_ids
        ]
        # Include any runbook with emergency/rollback in title if ids differ
        if not dr_books and runbooks:
            for r in runbooks:
                if not isinstance(r, dict):
                    continue
                title = str(r.get("title") or "").lower()
                rid = str(r.get("id") or r.get("runbook_id") or "").lower()
                if any(
                    k in title or k in rid
                    for k in ("emergency", "rollback", "gateway", "mt5", "reconnect")
                ):
                    dr_books.append(r)
        data = {
            "runbooks": dr_books,
            "recovery_events": (recovery or [])[:20],
            "ops_audit_tail": (audit or [])[:15],
            "mutations_href": "/ops",
            "never_retries_order_send": True,
        }
        if not dr_books and not recovery and not audit:
            return panel(
                "disaster_recovery",
                "Disaster Recovery Center",
                source="ite.ops.runbooks|reliability.recovery",
                status="empty",
                message="No DR runbooks or recovery events",
                data=data,
            )
        return panel(
            "disaster_recovery",
            "Disaster Recovery Center",
            source="ite.ops.runbooks|reliability.recovery",
            data=data,
            message="All DR actions execute via Ops and are audited",
        )
