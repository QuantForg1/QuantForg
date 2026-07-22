"""Scalping AI V2 orchestrator — continuous advisory loop, never order_send."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.domain.scalping_ai_v2.analytics import (
    build_observability_dashboard,
    build_performance_analytics,
    build_post_trade_intelligence,
)
from app.domain.scalping_ai_v2.audit import ProductionAuditLog
from app.domain.scalping_ai_v2.config import (
    DEFAULT_SCALPING_CONFIG,
    ScalpingAiV2Config,
)
from app.domain.scalping_ai_v2.diagnostics import (
    build_diagnostics_center,
    build_operator_dashboard,
)
from app.domain.scalping_ai_v2.engines import (
    evaluate_liquidity,
    evaluate_market_quality,
    evaluate_market_structure,
    evaluate_multi_timeframe,
    rank_opportunities,
)
from app.domain.scalping_ai_v2.events import EVENT_TYPES, ScalpEventBus
from app.domain.scalping_ai_v2.hardening import (
    EmergencyStop,
    LatencyMonitor,
    SafeModeController,
    StabilityMonitor,
    classify_retry,
    next_backoff_with_jitter_ms,
    plan_restart_recovery,
    reconcile_mt5_state,
    validate_market_data,
)
from app.domain.scalping_ai_v2.reliability import (
    DuplicateProtection,
    RecoveryLog,
    next_backoff_ms,
    plan_incident_recovery,
    run_auto_controller,
    run_watchdog,
    supervise_active_trade,
)
from app.domain.scalping_ai_v2.risk_execution import (
    integrate_dynamic_risk,
    monitor_execution_quality,
)
from app.domain.scalping_ai_v2.state_store import OperationalStateStore
from app.domain.scalping_ai_v2.types import ScalpCycleInput
from app.domain.trading.gold_only import GOLD_SYMBOL

FORBIDDEN = frozenset(
    {
        "martingale",
        "grid",
        "average_down",
        "average_losing",
        "pyramid_into_loss",
    }
)


@dataclass
class ScalpingAiV2:
    config: ScalpingAiV2Config = field(
        default_factory=lambda: DEFAULT_SCALPING_CONFIG
    )
    bus: ScalpEventBus = field(default_factory=ScalpEventBus)
    duplicates: DuplicateProtection = field(default_factory=DuplicateProtection)
    recovery_log: RecoveryLog = field(default_factory=RecoveryLog)
    history: list[dict[str, Any]] = field(default_factory=list)
    # V2.1 hardening (additive — does not replace V2 modules)
    state_store: OperationalStateStore = field(
        default_factory=OperationalStateStore
    )
    stability: StabilityMonitor = field(default_factory=StabilityMonitor)
    latency_monitor: LatencyMonitor = field(default_factory=LatencyMonitor)
    emergency: EmergencyStop = field(default_factory=EmergencyStop)
    safe_mode: SafeModeController = field(default_factory=SafeModeController)
    audit: ProductionAuditLog = field(default_factory=ProductionAuditLog)
    _restored: bool = False
    _last_modules: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.bus.max_events = self.config.max_events
        if self.config.state_persist_enabled:
            self._bootstrap_state()

    def _bootstrap_state(self) -> None:
        snap = self.state_store.load()
        ids = snap.get("execution_identities")
        if isinstance(ids, list):
            self.duplicates.import_identities([str(x) for x in ids])
        if snap.get("emergency_stop") is True:
            self.emergency.arm(str(snap.get("emergency_reason") or "restored"))
        if snap.get("safe_mode") is True:
            self.safe_mode.force(True, ["restored_from_state_store"])
        if snap:
            self._restored = True
            self.bus.publish(
                event_type="StateRestored",
                payload={"keys": list(snap.keys())},
                cycle_id="bootstrap",
            )

    def status(self) -> dict[str, object]:
        return {
            **self.config.to_dict(),
            "modules": [
                "market_quality_engine",
                "multi_timeframe_trend_engine",
                "liquidity_intelligence",
                "market_structure_engine",
                "opportunity_ranking_engine",
                "dynamic_risk_engine_integration",
                "execution_quality_monitor",
                "active_trade_supervisor",
                "continuous_auto_trading_controller",
                "production_watchdog",
                "incident_recovery",
                "duplicate_protection",
                "event_driven_architecture",
                "performance_analytics",
                "post_trade_intelligence",
                "configuration_center",
                "logging",
                "observability",
                "reliability_controls",
                "production_requirements",
                "long_running_stability",
                "state_persistence",
                "restart_recovery",
                "mt5_synchronization",
                "data_integrity",
                "safe_mode",
                "emergency_stop",
                "latency_monitor",
                "intelligent_retry",
                "production_diagnostics",
                "soak_testing",
                "production_audit",
                "operator_dashboard",
            ],
            "capabilities": {
                "xauusd_only": True,
                "continuous_auto_trading": True,
                "never_bypass_risk": True,
                "never_bypass_safety": True,
                "never_bypass_decision_center": True,
                "never_alternate_execution_path": True,
                "execution_pipeline_single_source": True,
                "prefer_no_trade": True,
                "explainable": True,
                "auditable": True,
                "recoverable_failures": True,
                "never_order_send": True,
                "never_fabricate_market_data": True,
                "never_guarantee_profits": True,
                "production_hardening_v21": True,
                "state_persistence": True,
                "safe_mode": True,
                "emergency_stop": True,
                "never_second_auto_trading_loop": True,
                "never_second_execution_engine": True,
                "symbol": GOLD_SYMBOL,
            },
            "event_types": list(EVENT_TYPES),
            "recent": self.history[:10],
            "recovery_log": self.recovery_log.entries[:10],
            "emergency_stop": self.emergency.status(),
            "safe_mode": {"active": self.safe_mode.active},
            "state_store": self.state_store.export_for_restart(),
            "stability": self.stability.summary(),
            "latency_distributions": self.latency_monitor.distributions(),
            "audit_recent": self.audit.list(limit=10),
            "state_restored": self._restored,
        }

    def arm_emergency_stop(self, reason: str = "operator") -> dict[str, Any]:
        row = self.emergency.arm(reason)
        self.state_store.update(
            {"emergency_stop": True, "emergency_reason": reason}
        )
        self.bus.publish(
            event_type="EmergencyStopArmed",
            payload=row,
            cycle_id="ops",
        )
        self.audit.record(
            module="emergency_stop",
            severity="critical",
            decision="No new trades",
            reason=reason,
            correlation_id="ops",
            recovery_status="armed",
        )
        return row

    def clear_emergency_stop(
        self, reason: str = "operator_clear"
    ) -> dict[str, Any]:
        row = self.emergency.disarm(reason)
        self.state_store.update(
            {"emergency_stop": False, "emergency_reason": reason}
        )
        self.bus.publish(
            event_type="EmergencyStopCleared",
            payload=row,
            cycle_id="ops",
        )
        self.audit.record(
            module="emergency_stop",
            severity="info",
            decision="Cleared",
            reason=reason,
            correlation_id="ops",
            recovery_status="cleared",
        )
        return row

    def diagnostics(self) -> dict[str, Any]:
        modules = self._last_modules
        diag = build_diagnostics_center(
            modules=modules,
            stability=self.stability.summary(),
            latency={"distributions": self.latency_monitor.distributions()},
            emergency=self.emergency.status(),
            safe_mode={"safe_mode": self.safe_mode.active},
            state_store=self.state_store.snapshot(),
            audit_count=len(self.audit.list(limit=2000)),
            event_bus_count=len(self.bus.list(limit=10_000)),
        )
        return diag.to_dict()

    def operator_dashboard(self) -> dict[str, Any]:
        modules = self._last_modules
        last = self.history[0] if self.history else {}
        rec = str(last.get("recommendation") or "—") if last else "—"
        return build_operator_dashboard(
            recommendation=rec,
            modules=modules,
            emergency=self.emergency.status(),
            safe_mode={"safe_mode": self.safe_mode.active},
            state=self.state_store.snapshot(),
            stability=self.stability.summary(),
            diagnostics=self.diagnostics(),
        )

    def run_soak(self, profile: str = "24h") -> dict[str, Any]:
        from app.domain.scalping_ai_v2.soak import run_soak

        return run_soak(self, profile=profile, config=self.config)

    def list_audit(self, *, limit: int = 100) -> dict[str, Any]:
        rows = self.audit.list(limit=limit)
        return {"status": "available" if rows else "empty", "items": rows}

    def update_policies(self, updates: dict[str, object]) -> dict[str, object]:
        self.config = self.config.update(updates)
        self.bus.max_events = self.config.max_events
        return self.config.to_dict()

    def list_events(
        self, *, limit: int = 100, cycle_id: str | None = None
    ) -> dict[str, Any]:
        rows = [
            e.to_dict() for e in self.bus.list(limit=limit, cycle_id=cycle_id)
        ]
        return {"status": "available" if rows else "empty", "events": rows}

    def list_history(self, *, limit: int = 50) -> dict[str, Any]:
        rows = self.history[: max(1, min(limit, self.config.max_history))]
        return {"status": "available" if rows else "empty", "items": rows}

    def run_cycle(self, inp: ScalpCycleInput) -> dict[str, Any]:
        started = perf_counter()
        cycle_id = f"sc_{uuid4().hex[:12]}"
        correlation_id = inp.correlation_id or cycle_id
        self.bus.publish(
            event_type="MarketUpdated",
            payload={"side": inp.side, "symbol": GOLD_SYMBOL},
            cycle_id=cycle_id,
        )

        # Resources for stability sample (recorded once at cycle end)
        resources = inp.resources
        if resources is None and isinstance(inp.health, dict):
            raw_res = inp.health.get("resources")
            resources = raw_res if isinstance(raw_res, dict) else None

        # Emergency stop (global) — no new trades
        if self.emergency.armed or inp.emergency_stop is True:
            if inp.emergency_stop is True and not self.emergency.armed:
                self.arm_emergency_stop("cycle_payload")
            self.audit.record(
                module="emergency_stop",
                severity="critical",
                decision="No Trade",
                reason="Emergency stop armed",
                correlation_id=correlation_id,
                execution_identity=inp.execution_identity,
            )
            return self._finalize(
                cycle_id,
                inp,
                recommendation="No Trade",
                modules={},
                extra_reasons=(
                    "Emergency stop — no new trades",
                    "Open positions remain supervised",
                ),
                correlation_id=correlation_id,
            )

        # Forbidden techniques
        tech = (inp.technique or "").lower().replace("-", "_").replace(" ", "_")
        if any(f in tech for f in FORBIDDEN):
            self.bus.publish(
                event_type="NoTrade",
                payload={"reason": "forbidden_technique", "technique": tech},
                cycle_id=cycle_id,
            )
            self.audit.record(
                module="technique_guard",
                severity="warning",
                decision="No Trade",
                reason=f"Forbidden technique {tech}",
                correlation_id=correlation_id,
            )
            return self._finalize(
                cycle_id,
                inp,
                recommendation="No Trade",
                modules={},
                extra_reasons=(
                    f"Forbidden technique blocked: {tech}",
                    "Never martingale/grid/average-down",
                ),
                correlation_id=correlation_id,
            )

        # Duplicate protection
        dup = self.duplicates.claim(inp.execution_identity)
        if dup["duplicate"]:
            self.bus.publish(
                event_type="DuplicateBlocked",
                payload=dup,
                cycle_id=cycle_id,
            )
            self.audit.record(
                module="duplicate_protection",
                severity="warning",
                decision="No Trade",
                reason=str(dup["reason"]),
                correlation_id=correlation_id,
                execution_identity=dup["execution_identity"],
            )
            return self._finalize(
                cycle_id,
                inp,
                recommendation="No Trade",
                modules={},
                extra_reasons=(dup["reason"],),
                execution_identity=dup["execution_identity"],
                correlation_id=correlation_id,
            )

        # V2.1: data integrity, MT5 sync, restart recovery
        integrity = validate_market_data(inp, self.config)
        if integrity.passed is False:
            self.bus.publish(
                event_type="DataIntegrityRejected",
                payload=integrity.details,
                cycle_id=cycle_id,
            )
        mt5 = reconcile_mt5_state(inp, self.config)
        if mt5.details.get("mismatches"):
            self.bus.publish(
                event_type="Mt5DriftDetected",
                payload=mt5.details,
                cycle_id=cycle_id,
            )
        restart = plan_restart_recovery(inp, self.config)
        if restart.recommendation == "Recover":
            self.bus.publish(
                event_type="RestartRecoveryStarted",
                payload=restart.details,
                cycle_id=cycle_id,
            )

        # Latency samples
        lat_src = inp.latencies
        if lat_src is None and isinstance(inp.health, dict):
            raw_lat = inp.health.get("latencies")
            lat_src = raw_lat if isinstance(raw_lat, dict) else None
        latency = self.latency_monitor.record(lat_src)
        if latency.get("recorded"):
            self.bus.publish(
                event_type="LatencySampled",
                payload=latency.get("recorded") or {},
                cycle_id=cycle_id,
            )

        # Intelligent retry classification (advisory)
        retry_info = classify_retry(inp.failure_code)
        retry_backoff = [
            next_backoff_with_jitter_ms(
                i, self.config, jitter_ratio=self.config.retry_jitter_ratio
            )
            for i in range(min(4, self.config.max_retries + 1))
        ]

        mq = evaluate_market_quality(inp, self.config)
        mtf = evaluate_multi_timeframe(inp, self.config)
        liq = evaluate_liquidity(inp, self.config)
        struct = evaluate_market_structure(inp, self.config)
        ranking = rank_opportunities(inp, self.config)
        risk = integrate_dynamic_risk(inp, self.config)
        exec_mon = monitor_execution_quality(inp, self.config)
        supervisor = supervise_active_trade(inp, self.config)
        controller = run_auto_controller(inp, self.config)
        watchdog = run_watchdog(inp, self.config)
        recovery = plan_incident_recovery(inp, self.config)
        analytics = build_performance_analytics(inp, self.config)
        post = build_post_trade_intelligence(inp, self.config)

        # Safe mode from health probes
        health = inp.health if isinstance(inp.health, dict) else {}
        safe = self.safe_mode.evaluate(health)
        if safe.get("safe_mode") and not self.safe_mode.active:
            # evaluate already set state; publish transition from prior
            pass
        if safe.get("safe_mode"):
            self.bus.publish(
                event_type="SafeModeEntered",
                payload=safe,
                cycle_id=cycle_id,
            )
        elif health and all(
            health.get(k) is True
            for k in (
                "broker_connection",
                "gateway",
                "risk_engine",
                "safety_engine",
                "decision_engine",
                "database",
            )
            if k in health
        ):
            self.bus.publish(
                event_type="SafeModeExited",
                payload=safe,
                cycle_id=cycle_id,
            )

        if ranking.passed and ranking.details.get("selected"):
            self.bus.publish(
                event_type="SignalGenerated",
                payload={"selected": ranking.details.get("selected")},
                cycle_id=cycle_id,
            )

        if inp.risk_engine_passed is True:
            self.bus.publish(
                event_type="RiskApproved",
                payload={"risk_engine_passed": True},
                cycle_id=cycle_id,
            )
        if inp.safety_engine_passed is True:
            self.bus.publish(
                event_type="SafetyApproved",
                payload={"safety_engine_passed": True},
                cycle_id=cycle_id,
            )
        decision_ok = (
            inp.decision_approved is True
            or str((inp.decision_center or {}).get("decision") or "").upper()
            == "APPROVE"
        )
        if decision_ok:
            self.bus.publish(
                event_type="DecisionApproved",
                payload={"decision_center": inp.decision_center or {}},
                cycle_id=cycle_id,
            )

        if watchdog.details.get("safe_mode"):
            self.bus.publish(
                event_type="WatchdogAlert",
                payload=watchdog.details,
                cycle_id=cycle_id,
            )
        if recovery.recommendation == "Recover":
            self.bus.publish(
                event_type="RecoveryStarted",
                payload=recovery.details,
                cycle_id=cycle_id,
            )
            self.recovery_log.record(
                incident=str(
                    (inp.health or {}).get("incident")
                    if isinstance(inp.health, dict)
                    else "health"
                ),
                attempt=1,
                duration_ms=0,
                outcome="planned",
                detail="Recovery plan issued (advisory)",
            )
            self.bus.publish(
                event_type="RecoveryCompleted",
                payload={"planned": True},
                cycle_id=cycle_id,
            )

        gates = [
            mq,
            mtf,
            liq,
            struct,
            ranking,
            risk,
            exec_mon,
            controller,
            integrity,
        ]
        no_trade = False
        gate_reasons: list[str] = []
        for g in gates:
            if g.passed is False or g.recommendation == "No Trade":
                no_trade = True
                gate_reasons.extend(list(g.reasons)[:1])

        # Authority hard locks — never bypass
        if inp.risk_engine_passed is not True:
            no_trade = True
            gate_reasons.append("Risk Engine not passed — never bypass")
        if inp.safety_engine_passed is not True:
            no_trade = True
            gate_reasons.append("Safety Engine not passed — never bypass")
        if not decision_ok:
            no_trade = True
            gate_reasons.append(
                "Decision Center not approved — never bypass"
            )
        if inp.kill_switch is True or inp.news_blackout is True:
            no_trade = True
            gate_reasons.append("Kill switch / news blackout — No Trade")
        if watchdog.details.get("safe_mode") or safe.get("safe_mode"):
            no_trade = True
            gate_reasons.append("Safe mode — pause new trades")
        if self.emergency.armed:
            no_trade = True
            gate_reasons.append("Emergency stop — no new trades")

        recommendation = "No Trade" if no_trade else "Proceed"
        duration_ms = (perf_counter() - started) * 1000.0
        stability = self.stability.record(resources, loop_latency_ms=duration_ms)

        if recommendation == "No Trade":
            self.bus.publish(
                event_type="NoTrade",
                payload={"reasons": gate_reasons[:8]},
                cycle_id=cycle_id,
            )
        else:
            # Advisory only — never starts real execution
            self.bus.publish(
                event_type="ExecutionStarted",
                payload={
                    "advisory_only": True,
                    "never_order_send": True,
                    "uses_existing_pipeline": True,
                },
                cycle_id=cycle_id,
            )

        modules = {
            "market_quality_engine": mq.to_dict(),
            "multi_timeframe_trend_engine": mtf.to_dict(),
            "liquidity_intelligence": liq.to_dict(),
            "market_structure_engine": struct.to_dict(),
            "opportunity_ranking_engine": ranking.to_dict(),
            "dynamic_risk_engine_integration": risk.to_dict(),
            "execution_quality_monitor": exec_mon.to_dict(),
            "active_trade_supervisor": supervisor.to_dict(),
            "continuous_auto_trading_controller": controller.to_dict(),
            "production_watchdog": watchdog.to_dict(),
            "incident_recovery": recovery.to_dict(),
            "performance_analytics": analytics.to_dict(),
            "post_trade_intelligence": post.to_dict(),
            "data_integrity": integrity.to_dict(),
            "mt5_synchronization": mt5.to_dict(),
            "restart_recovery": restart.to_dict(),
            "long_running_stability": {
                "module": "long_running_stability",
                "status": stability.get("status"),
                "score": None,
                "passed": not bool(stability.get("alerts")),
                "recommendation": (
                    "Alert" if stability.get("alerts") else "Stable"
                ),
                "reasons": stability.get("alerts") or ["Stability sample ok"],
                "details": stability,
                "explainable": True,
                "invented": False,
                "never_order_send": True,
            },
            "latency_monitor": {
                "module": "latency_monitor",
                "status": latency.get("status"),
                "score": None,
                "passed": True,
                "recommendation": "Recorded",
                "reasons": ["Latency distributions updated"],
                "details": latency,
                "explainable": True,
                "invented": False,
                "never_order_send": True,
            },
            "intelligent_retry": {
                "module": "intelligent_retry",
                "status": "available",
                "score": None,
                "passed": True,
                "recommendation": (
                    "Retry" if retry_info.get("retry") else "No retry"
                ),
                "reasons": [str(retry_info.get("reason"))],
                "details": {
                    **retry_info,
                    "backoff_example_ms": retry_backoff,
                },
                "explainable": True,
                "invented": False,
                "never_order_send": True,
            },
            "safe_mode": {
                "module": "safe_mode",
                "status": "available",
                "score": None,
                "passed": not bool(safe.get("safe_mode")),
                "recommendation": (
                    "Safe mode" if safe.get("safe_mode") else "Normal"
                ),
                "reasons": list(safe.get("reasons") or []),
                "details": safe,
                "explainable": True,
                "invented": False,
                "never_order_send": True,
            },
            "emergency_stop": {
                "module": "emergency_stop",
                "status": "available",
                "score": None,
                "passed": not self.emergency.armed,
                "recommendation": (
                    "Armed" if self.emergency.armed else "Clear"
                ),
                "reasons": [str(self.emergency.status().get("reason") or "ok")],
                "details": self.emergency.status(),
                "explainable": True,
                "invented": False,
                "never_order_send": True,
            },
        }

        diag = build_diagnostics_center(
            modules=modules,
            stability=stability,
            latency=latency,
            emergency=self.emergency.status(),
            safe_mode=safe,
            state_store=self.state_store.snapshot(),
            audit_count=len(self.audit.list(limit=2000)),
            event_bus_count=len(self.bus.list(limit=10_000)),
        )
        modules["production_diagnostics"] = diag.to_dict()
        operator = build_operator_dashboard(
            recommendation=recommendation,
            modules=modules,
            emergency=self.emergency.status(),
            safe_mode=safe,
            state=self.state_store.snapshot(),
            stability=stability,
            diagnostics=diag.to_dict(),
        )
        modules["operator_dashboard"] = {
            "module": "operator_dashboard",
            "status": "available",
            "score": None,
            "passed": True,
            "recommendation": "Display",
            "reasons": ["Operator dashboard assembled"],
            "details": operator,
            "explainable": True,
            "invented": False,
            "never_order_send": True,
        }

        if analytics.status == "available":
            self.bus.publish(
                event_type="AnalyticsUpdated",
                payload=analytics.details,
                cycle_id=cycle_id,
            )

        self.audit.record(
            module="scalping_cycle",
            severity="info" if recommendation == "Proceed" else "warning",
            decision=recommendation,
            reason="; ".join(gate_reasons[:3]) or "gates_passed",
            correlation_id=correlation_id,
            execution_identity=dup["execution_identity"],
            duration_ms=duration_ms,
            recovery_status=(
                "planned" if recovery.recommendation == "Recover" else "none"
            ),
        )

        # Persist operational state (never loses identities / safe mode)
        pending = []
        if isinstance(inp.active_trade, dict):
            pending = [inp.active_trade]
        open_pos = self.state_store.get("open_positions") or []
        if isinstance(inp.mt5_sync, dict) and "local_open_positions" in inp.mt5_sync:
            # store count/list if provided as list
            lop = inp.mt5_sync.get("local_open_positions")
            if isinstance(lop, list):
                open_pos = lop
        incidents = list(self.state_store.get("active_incidents") or [])
        if isinstance(inp.health, dict) and inp.health.get("incident"):
            incidents = [
                {"incident": inp.health.get("incident"), "cycle_id": cycle_id},
                *incidents,
            ][:50]
        self.state_store.restore_bundle(
            auto_trading_state=str(
                (controller.details or {}).get("run_state") or inp.run_state
            ),
            pending_supervision=pending,
            open_positions=open_pos if isinstance(open_pos, list) else [],
            execution_identities=self.duplicates.export_identities(),
            active_incidents=incidents,
            recovery_state=recovery.details,
            safe_mode=bool(safe.get("safe_mode")),
            emergency_stop=self.emergency.armed,
        )
        self.bus.publish(
            event_type="StatePersisted",
            payload={"keys": list(self.state_store.snapshot().keys())},
            cycle_id=cycle_id,
        )

        return self._finalize(
            cycle_id,
            inp,
            recommendation=recommendation,
            modules=modules,
            extra_reasons=tuple(gate_reasons[:12]),
            execution_identity=dup["execution_identity"],
            controller=controller.to_dict(),
            watchdog=watchdog.to_dict(),
            correlation_id=correlation_id,
            duration_ms=duration_ms,
            operator=operator,
            retry_backoff=retry_backoff,
        )

    def _finalize(
        self,
        cycle_id: str,
        inp: ScalpCycleInput,
        *,
        recommendation: str,
        modules: dict[str, Any],
        extra_reasons: tuple[str, ...] = (),
        execution_identity: str | None = None,
        controller: dict[str, Any] | None = None,
        watchdog: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        duration_ms: float | None = None,
        operator: dict[str, Any] | None = None,
        retry_backoff: list[int] | None = None,
    ) -> dict[str, Any]:
        events = [e.to_dict() for e in self.bus.list(cycle_id=cycle_id)]
        obs = build_observability_dashboard(
            modules=modules,
            controller=controller or {},
            watchdog=watchdog or {},
            events_count=len(events),
        )
        self.bus.publish(
            event_type="CycleCompleted",
            payload={"recommendation": recommendation},
            cycle_id=cycle_id,
        )
        events = [e.to_dict() for e in self.bus.list(cycle_id=cycle_id)]
        result = {
            "version": self.config.version,
            "symbol": GOLD_SYMBOL,
            "cycle_id": cycle_id,
            "correlation_id": correlation_id or cycle_id,
            "recommendation": recommendation,
            "side": inp.side,
            "execution_identity": execution_identity,
            "modules": modules,
            "reasons": list(extra_reasons),
            "events": events,
            "observability": obs,
            "operator_dashboard": operator,
            "duration_ms": duration_ms,
            "advisory_only": True,
            "never_order_send": True,
            "bypasses_risk": False,
            "bypasses_safety": False,
            "bypasses_decision_center": False,
            "alternate_execution_path": False,
            "execution_pipeline_unchanged": True,
            "never_second_auto_trading_loop": True,
            "never_second_execution_engine": True,
            "invented_market_data": False,
            "promise_profitability": False,
            "explainable": True,
            "auditable": True,
            "retry_backoff_example_ms": retry_backoff
            or [
                next_backoff_ms(i, self.config)
                for i in range(min(4, self.config.max_retries + 1))
            ],
            "config_snapshot": {
                "min_market_quality": str(self.config.min_market_quality),
                "min_confidence": str(self.config.min_confidence),
                "max_spread": str(self.config.max_spread),
                "max_retries": self.config.max_retries,
            },
        }
        self._last_modules = modules
        self.history.insert(
            0,
            {
                "cycle_id": cycle_id,
                "recommendation": recommendation,
                "execution_identity": execution_identity,
                "correlation_id": correlation_id or cycle_id,
                "module_keys": list(modules.keys()),
            },
        )
        if len(self.history) > self.config.max_history:
            self.history = self.history[: self.config.max_history]
        return result


def input_from_dict(data: dict[str, Any]) -> ScalpCycleInput:
    def d(v: Any) -> Decimal | None:
        if v is None:
            return None
        try:
            return Decimal(str(v))
        except (InvalidOperation, ValueError, TypeError):
            return None

    def b(v: Any) -> bool | None:
        return v if isinstance(v, bool) else None

    def i(v: Any) -> int | None:
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    return ScalpCycleInput(
        side=str(data.get("side") or "buy"),
        bid=d(data.get("bid")),
        ask=d(data.get("ask")),
        spread=d(data.get("spread")),
        atr=d(data.get("atr")),
        price=d(data.get("price")),
        regime=str(data["regime"]) if data.get("regime") else None,
        session=str(data["session"]) if data.get("session") else None,
        trend=str(data["trend"]) if data.get("trend") else None,
        volatility=str(data["volatility"]) if data.get("volatility") else None,
        liquidity_state=(
            str(data["liquidity_state"]) if data.get("liquidity_state") else None
        ),
        market_health=(
            str(data["market_health"]) if data.get("market_health") else None
        ),
        confidence=d(data.get("confidence")),
        htf_bias=str(data["htf_bias"]) if data.get("htf_bias") else None,
        ltf_confirmation=(
            str(data["ltf_confirmation"])
            if data.get("ltf_confirmation")
            else None
        ),
        trend_strength=d(data.get("trend_strength")),
        trend_consistency=d(data.get("trend_consistency")),
        sweep_detected=b(data.get("sweep_detected")),
        equal_highs_lows=b(data.get("equal_highs_lows")),
        session_liquidity=(
            str(data["session_liquidity"])
            if data.get("session_liquidity")
            else None
        ),
        liquidity_side=(
            str(data["liquidity_side"]) if data.get("liquidity_side") else None
        ),
        stop_hunt=b(data.get("stop_hunt")),
        bos=b(data.get("bos")),
        choch=b(data.get("choch")),
        mss=b(data.get("mss")),
        swing_bias=str(data["swing_bias"]) if data.get("swing_bias") else None,
        structure_phase=(
            str(data["structure_phase"]) if data.get("structure_phase") else None
        ),
        opportunities=(
            data.get("opportunities")
            if isinstance(data.get("opportunities"), list)
            else None
        ),
        risk_engine_passed=b(data.get("risk_engine_passed")),
        safety_engine_passed=b(data.get("safety_engine_passed")),
        decision_center=(
            data.get("decision_center")
            if isinstance(data.get("decision_center"), dict)
            else None
        ),
        decision_approved=b(data.get("decision_approved")),
        broker_connected=b(data.get("broker_connected")),
        gateway_healthy=b(data.get("gateway_healthy")),
        latency_ms=d(data.get("latency_ms")),
        market_open=b(data.get("market_open")),
        margin_available=b(data.get("margin_available")),
        max_latency_ms=d(data.get("max_latency_ms")),
        equity=d(data.get("equity")),
        daily_loss_pct=d(data.get("daily_loss_pct")),
        open_exposure_pct=d(data.get("open_exposure_pct")),
        trades_today=i(data.get("trades_today")),
        consecutive_losses=i(data.get("consecutive_losses")),
        active_trade=(
            data.get("active_trade")
            if isinstance(data.get("active_trade"), dict)
            else None
        ),
        closed_trade=(
            data.get("closed_trade")
            if isinstance(data.get("closed_trade"), dict)
            else None
        ),
        health=(
            data.get("health") if isinstance(data.get("health"), dict) else None
        ),
        run_state=str(data["run_state"]) if data.get("run_state") else None,
        kill_switch=b(data.get("kill_switch")),
        news_blackout=b(data.get("news_blackout")),
        technique=str(data["technique"]) if data.get("technique") else None,
        execution_identity=(
            str(data["execution_identity"])
            if data.get("execution_identity")
            else None
        ),
        market_data=(
            data.get("market_data")
            if isinstance(data.get("market_data"), dict)
            else None
        ),
        mt5_sync=(
            data.get("mt5_sync")
            if isinstance(data.get("mt5_sync"), dict)
            else None
        ),
        restart=b(data.get("restart")),
        resources=(
            data.get("resources")
            if isinstance(data.get("resources"), dict)
            else None
        ),
        latencies=(
            data.get("latencies")
            if isinstance(data.get("latencies"), dict)
            else None
        ),
        failure_code=(
            str(data["failure_code"]) if data.get("failure_code") else None
        ),
        emergency_stop=b(data.get("emergency_stop")),
        correlation_id=(
            str(data["correlation_id"]) if data.get("correlation_id") else None
        ),
    )
