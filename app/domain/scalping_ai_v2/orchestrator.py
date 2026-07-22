"""Scalping AI V2 orchestrator — continuous advisory loop, never order_send."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from app.domain.scalping_ai_v2.analytics import (
    build_observability_dashboard,
    build_performance_analytics,
    build_post_trade_intelligence,
)
from app.domain.scalping_ai_v2.config import (
    DEFAULT_SCALPING_CONFIG,
    ScalpingAiV2Config,
)
from app.domain.scalping_ai_v2.engines import (
    evaluate_liquidity,
    evaluate_market_quality,
    evaluate_market_structure,
    evaluate_multi_timeframe,
    rank_opportunities,
)
from app.domain.scalping_ai_v2.events import EVENT_TYPES, ScalpEventBus
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

    def __post_init__(self) -> None:
        self.bus.max_events = self.config.max_events

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
                "symbol": GOLD_SYMBOL,
            },
            "event_types": list(EVENT_TYPES),
            "recent": self.history[:10],
            "recovery_log": self.recovery_log.entries[:10],
        }

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
        cycle_id = f"sc_{uuid4().hex[:12]}"
        self.bus.publish(
            event_type="MarketUpdated",
            payload={"side": inp.side, "symbol": GOLD_SYMBOL},
            cycle_id=cycle_id,
        )

        # Forbidden techniques
        tech = (inp.technique or "").lower().replace("-", "_").replace(" ", "_")
        if any(f in tech for f in FORBIDDEN):
            self.bus.publish(
                event_type="NoTrade",
                payload={"reason": "forbidden_technique", "technique": tech},
                cycle_id=cycle_id,
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
            )

        # Duplicate protection
        dup = self.duplicates.claim(inp.execution_identity)
        if dup["duplicate"]:
            self.bus.publish(
                event_type="DuplicateBlocked",
                payload=dup,
                cycle_id=cycle_id,
            )
            return self._finalize(
                cycle_id,
                inp,
                recommendation="No Trade",
                modules={},
                extra_reasons=(dup["reason"],),
                execution_identity=dup["execution_identity"],
            )

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

        gates = [mq, mtf, liq, struct, ranking, risk, exec_mon, controller]
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
        if watchdog.details.get("safe_mode"):
            no_trade = True
            gate_reasons.append("Watchdog safe mode — pause trading")

        recommendation = "No Trade" if no_trade else "Proceed"
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
        }
        if analytics.status == "available":
            self.bus.publish(
                event_type="AnalyticsUpdated",
                payload=analytics.details,
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
            "recommendation": recommendation,
            "side": inp.side,
            "execution_identity": execution_identity,
            "modules": modules,
            "reasons": list(extra_reasons),
            "events": events,
            "observability": obs,
            "advisory_only": True,
            "never_order_send": True,
            "bypasses_risk": False,
            "bypasses_safety": False,
            "bypasses_decision_center": False,
            "alternate_execution_path": False,
            "execution_pipeline_unchanged": True,
            "invented_market_data": False,
            "promise_profitability": False,
            "explainable": True,
            "auditable": True,
            "retry_backoff_example_ms": [
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
        self.history.insert(
            0,
            {
                "cycle_id": cycle_id,
                "recommendation": recommendation,
                "execution_identity": execution_identity,
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
    )
