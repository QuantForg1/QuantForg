"""Continuous Shadow orchestrator + ITE runtime wiring.

Does not modify OMS. Shadow path never order_send.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from threading import Event, Lock
from typing import Any
from uuid import UUID, uuid4

from app.application.services.institutional_decision_pipeline import (
    InstitutionalDecisionPipeline,
)
from app.application.services.institutional_execution_integration import (
    InstitutionalExecutionIntegration,
)
from app.application.services.institutional_live_probes import LiveProbeCollector
from app.application.services.institutional_oms_adapter import InstitutionalOmsAdapter
from app.application.services.institutional_oms_manage_adapter import (
    InstitutionalOmsManageAdapter,
)
from app.application.services.institutional_ops_guards import (
    GuardedOmsManagePort,
    GuardedOmsSubmitPort,
)
from app.application.services.institutional_position_management import (
    InstitutionalPositionManagement,
)
from app.domain.institutional_trading.auto_trading import AutoTradeLiveFacts
from app.domain.institutional_trading.decision_models import AccountRiskState
from app.domain.institutional_trading.execution.models import (
    ExecutionBridgeContext,
    ExecutionMode,
)
from app.domain.institutional_trading.management.models import PositionManageContext
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
    get_control_plane,
)
from app.domain.institutional_trading.operations.models import OpsExecutionMode
from app.domain.institutional_trading.reliability.models import (
    ComponentName,
    TimelineEvent,
    TraceStage,
)
from app.domain.institutional_trading.reliability.platform import (
    ReliabilityPlatform,
    get_reliability_platform,
)
from app.domain.institutional_trading.reliability.tracing import new_trace_id
from core.config.settings import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ShadowCycleResult:
    ok: bool
    trace_id: str | None
    mode: str
    decision_action: str | None = None
    forwarded_to_oms: bool = False
    detail: str = ""
    health: dict[str, Any] | None = None
    cycle_outcome: str = "unknown"
    abort_reason: str | None = None
    decision_reasons: tuple[str, ...] = ()
    safety_failed_reasons: tuple[str, ...] = ()
    snapshot_present: bool = False
    market_context_reason: str | None = None
    market_context_diagnostics: dict[str, Any] | None = None
    signal_id: str | None = None
    oms_message: str | None = None
    broker_retcode: int | None = None
    mt5_ticket: int | None = None
    latency_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "trace_id": self.trace_id,
            "mode": self.mode,
            "decision_action": self.decision_action,
            "forwarded_to_oms": self.forwarded_to_oms,
            "detail": self.detail,
            "health": self.health,
            "cycle_outcome": self.cycle_outcome,
            "abort_reason": self.abort_reason,
            "decision_reasons": list(self.decision_reasons),
            "safety_failed_reasons": list(self.safety_failed_reasons),
            "snapshot_present": self.snapshot_present,
            "market_context_reason": self.market_context_reason,
            "market_context_diagnostics": self.market_context_diagnostics,
            "signal_id": self.signal_id,
            "oms_message": self.oms_message,
            "broker_retcode": self.broker_retcode,
            "mt5_ticket": self.mt5_ticket,
            "latency_ms": self.latency_ms,
        }


@dataclass
class InstitutionalIteRuntime:
    """Production ITE wiring: Guarded OMS + shared kill + shadow loop."""

    plane: OperationsControlPlane
    reliability: ReliabilityPlatform
    probes: LiveProbeCollector
    guarded_submit: GuardedOmsSubmitPort
    guarded_manage: GuardedOmsManagePort
    execution: InstitutionalExecutionIntegration
    position_management: InstitutionalPositionManagement
    decision_pipeline: InstitutionalDecisionPipeline = field(
        default_factory=InstitutionalDecisionPipeline
    )
    interval_seconds: float = 60.0
    mt5_adapter: Any | None = None
    _stop: Event = field(default_factory=Event, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)
    _last_cycle: ShadowCycleResult | None = field(default=None, repr=False)
    _cycles: int = 0
    user_id: UUID = field(default_factory=uuid4)

    def tick_health(self) -> dict[str, Any]:
        """Live probes → ReliabilityPlatform.tick (no POST body flags)."""
        probes = self.probes.collect()
        # Heartbeats for core components each tick
        now = datetime.now(UTC)
        for comp in (
            ComponentName.GATEWAY,
            ComponentName.MT5,
            ComponentName.DECISION,
            ComponentName.OMS,
            ComponentName.RAILWAY_API,
            ComponentName.SUPABASE,
            ComponentName.CLOUDFLARE_TUNNEL,
        ):
            self.reliability.heartbeats.publish(comp, now=now)
        result = self.reliability.tick(
            probes,
            now=now,
            required_heartbeats=(
                ComponentName.GATEWAY,
                ComponentName.DECISION,
                ComponentName.OMS,
            ),
        )
        # Expose the exact ProbeInputs used for this tick (avoid a second collect).
        result["live_probes"] = {
            "gateway": probes.gateway_available,
            "mt5": probes.mt5_connected,
            "railway": probes.railway_api_up,
            "supabase": probes.supabase_up,
            "cloudflare": probes.cloudflare_tunnel_up,
        }
        return result

    def run_shadow_cycle(
        self,
        *,
        snapshot: Any | None = None,
        account: AccountRiskState | None = None,
        market_context_diagnostics: dict[str, Any] | None = None,
    ) -> ShadowCycleResult:
        """One automatic Decision→…→Reliability shadow cycle. Never order_send."""
        health = self.tick_health()
        if self.plane.mode is not OpsExecutionMode.SHADOW:
            result = ShadowCycleResult(
                ok=False,
                trace_id=None,
                mode=self.plane.mode.value,
                detail="orchestrator idle — ops mode is not SHADOW",
                health=health.get("health") if isinstance(health, dict) else None,
            )
            with self._lock:
                self._last_cycle = result
            return result

        return self._run_cycle(
            snapshot=snapshot,
            account=account,
            health=health,
            execution_enabled=False,
            force_shadow=True,
            market_context_diagnostics=market_context_diagnostics,
        )

    def run_auto_cycle(
        self,
        *,
        snapshot: Any | None = None,
        account: AccountRiskState | None = None,
        gateway_connected: bool = False,
        broker_connected: bool = False,
        market_data_live: bool = False,
        account_trading_enabled: bool = False,
        mt5_autotrading_enabled: bool = False,
        symbol_tradable: bool = False,
        no_broker_restrictions: bool = False,
        risk_allowed: bool = False,
        risk_reasons: tuple[str, ...] = (),
        market_context_diagnostics: dict[str, Any] | None = None,
    ) -> ShadowCycleResult:
        """CANARY/LIVE auto-trade cycle — submits only when safety gate passes."""
        health = self.tick_health()
        if self.plane.mode is OpsExecutionMode.SHADOW:
            return self.run_shadow_cycle(snapshot=snapshot, account=account)

        live_probes: dict[str, Any] = {}
        if isinstance(health, dict):
            raw_probes = health.get("live_probes") or {}
            if isinstance(raw_probes, dict):
                live_probes = raw_probes
        gw = bool(live_probes.get("gateway", gateway_connected))
        mt5 = bool(live_probes.get("mt5", broker_connected))

        settings = get_settings()
        execution_on = bool(getattr(settings, "execution_enabled", False))

        if snapshot is None or account is None:
            safety = self.plane.evaluate_auto_trading(
                AutoTradeLiveFacts(
                    gateway_connected=gw,
                    broker_connected=mt5,
                    market_data_live=market_data_live,
                    risk_engine_pass=risk_allowed,
                    risk_engine_reasons=risk_reasons,
                    account_trading_enabled=account_trading_enabled,
                    mt5_autotrading_enabled=mt5_autotrading_enabled,
                    symbol_tradable=symbol_tradable,
                    margin_available=False,
                    no_broker_restrictions=no_broker_restrictions,
                    ops_mode=self.plane.mode.value,
                    execution_enabled=execution_on,
                )
            )
            result = ShadowCycleResult(
                ok=True,
                trace_id=None,
                mode=self.plane.mode.value,
                detail=(
                    "no snapshot/account — "
                    + (
                        "Auto Trading Enabled"
                        if safety.allowed
                        else "; ".join(safety.failed_reasons) or "Disabled"
                    )
                ),
                health=health.get("health") if isinstance(health, dict) else None,
                cycle_outcome="no_snapshot",
                abort_reason="NO_SNAPSHOT",
                safety_failed_reasons=tuple(safety.failed_reasons),
                snapshot_present=False,
                market_context_reason="snapshot/account not supplied",
            )
            with self._lock:
                self._last_cycle = result
                self._cycles += 1
            logger.info(
                "ite_cycle_outcome",
                outcome=result.cycle_outcome,
                detail=result.detail,
                mode=result.mode,
            )
            return result

        free = account.free_margin
        margin_ok = free is not None and free > 0
        session = getattr(snapshot.session, "session", None)
        session_val = str(getattr(session, "value", None) or session or "off_hours")
        news = snapshot.news
        safety = self.plane.evaluate_auto_trading(
            AutoTradeLiveFacts(
                gateway_connected=gw,
                broker_connected=mt5,
                market_data_live=bool(market_data_live),
                risk_engine_pass=risk_allowed,
                risk_engine_reasons=risk_reasons,
                account_trading_enabled=account_trading_enabled,
                mt5_autotrading_enabled=mt5_autotrading_enabled,
                symbol=getattr(snapshot, "symbol", "XAUUSD"),
                symbol_tradable=symbol_tradable,
                margin_available=margin_ok,
                no_broker_restrictions=no_broker_restrictions,
                open_positions=account.open_positions,
                session=session_val,
                spread=getattr(snapshot, "spread", None),
                news_blocked=bool(news.blocked),
                news_reason=str(news.reason or ""),
                daily_loss_exceeded=self.plane.daily_loss_exceeded,
                emergency_stop=self.plane.kill_switch_armed,
                ops_mode=self.plane.mode.value,
                execution_enabled=execution_on,
            )
        )
        if not safety.allowed:
            result = ShadowCycleResult(
                ok=True,
                trace_id=None,
                mode=self.plane.mode.value,
                detail="; ".join(safety.failed_reasons) or "Auto Trading Disabled",
                health=health.get("health") if isinstance(health, dict) else None,
                cycle_outcome="safety_blocked",
                abort_reason="SAFETY_BLOCKED",
                safety_failed_reasons=tuple(safety.failed_reasons),
                snapshot_present=True,
            )
            with self._lock:
                self._last_cycle = result
                self._cycles += 1
            logger.info(
                "ite_cycle_outcome",
                outcome=result.cycle_outcome,
                reasons=list(result.safety_failed_reasons),
                mode=result.mode,
            )
            return result

        return self._run_cycle(
            snapshot=snapshot,
            account=account,
            health=health,
            execution_enabled=execution_on,
            force_shadow=False,
            gateway_connected=gw,
            broker_connected=mt5,
            market_data_live=market_data_live or bool(account.market_open),
            account_trading_enabled=account_trading_enabled,
            mt5_autotrading_enabled=mt5_autotrading_enabled,
            symbol_tradable=symbol_tradable,
            no_broker_restrictions=no_broker_restrictions,
            risk_allowed=risk_allowed,
            risk_reasons=risk_reasons,
            market_context_diagnostics=market_context_diagnostics,
        )

    def _run_cycle(
        self,
        *,
        snapshot: Any | None,
        account: AccountRiskState | None,
        health: dict[str, Any],
        execution_enabled: bool,
        force_shadow: bool,
        gateway_connected: bool = False,
        broker_connected: bool = False,
        market_data_live: bool = False,
        account_trading_enabled: bool = False,
        mt5_autotrading_enabled: bool = False,
        symbol_tradable: bool = False,
        no_broker_restrictions: bool = False,
        risk_allowed: bool = True,
        risk_reasons: tuple[str, ...] = (),
        market_context_diagnostics: dict[str, Any] | None = None,
    ) -> ShadowCycleResult:
        if snapshot is None or account is None:
            result = ShadowCycleResult(
                ok=True,
                trace_id=None,
                mode=self.plane.mode.value,
                detail="no snapshot/account — health tick only",
                health=health.get("health") if isinstance(health, dict) else None,
                cycle_outcome="no_snapshot",
                abort_reason="NO_SNAPSHOT",
                snapshot_present=False,
            )
            with self._lock:
                self._last_cycle = result
                self._cycles += 1
            try:
                from app.application.services.strategy_diagnostics import (
                    get_strategy_diagnostics_store,
                )

                get_strategy_diagnostics_store().record_from_artefacts(
                    snapshot=None,
                    decision=None,
                    cycle_outcome="no_snapshot",
                    decision_action=None,
                    abort_reason="NO_SNAPSHOT",
                    decision_reasons=(),
                    market_context_diagnostics=market_context_diagnostics,
                    signal_id=None,
                    forwarded_to_oms=False,
                    trace_id=None,
                )
            except Exception:
                logger.exception("strategy_diagnostics_record_failed")
            return result

        tid = new_trace_id()
        t0 = time.perf_counter()
        self.reliability.traces.start(
            trace_id=tid, decision_id=None, symbol=getattr(snapshot, "symbol", "XAUUSD")
        )

        decision = self.decision_pipeline.run(snapshot, account)
        decision_reasons = tuple(getattr(decision, "reasons", ()) or ())
        self.reliability.traces.span(
            tid,
            TraceStage.DECISION,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            ok=True,
            detail=decision.action.value,
        )
        self.reliability.traces.span(
            tid,
            TraceStage.ELIGIBILITY,
            latency_ms=1.0,
            ok=decision.eligibility.eligible,
            detail=";".join(decision.eligibility.rejection_reasons) or "ok",
        )

        ctx = ExecutionBridgeContext(
            snapshot=snapshot,
            account=account,
            expected_input_hash=decision.input_hash,
            now=decision.as_of,
            user_id=self.user_id,
            execution_enabled=False if force_shadow else execution_enabled,
            risk_allowed=risk_allowed,
            risk_reasons=risk_reasons,
            connected=broker_connected or force_shadow,
            login=None,
            request_id=f"{'shadow' if force_shadow else 'auto'}_{tid[:12]}",
            gateway_connected=True if force_shadow else gateway_connected,
            broker_connected=True if force_shadow else broker_connected,
            market_data_live=True if force_shadow else market_data_live,
            account_trading_enabled=(
                True if force_shadow else account_trading_enabled
            ),
            mt5_autotrading_enabled=(
                True if force_shadow else mt5_autotrading_enabled
            ),
            symbol_tradable=True if force_shadow else symbol_tradable,
            no_broker_restrictions=True if force_shadow else no_broker_restrictions,
        )
        bridge_result = self.execution.bridge.handle(decision, ctx, trace_id=tid)

        for ticket in list(self.position_management.engine._positions.keys()):
            pos = self.position_management.engine.get(ticket)
            if pos is None:
                continue
            pctx = PositionManageContext(
                now=datetime.now(UTC),
                current_price=account.mid_price or Decimal("2300"),
                atr=account.atr or Decimal("1"),
                spread=snapshot.spread,
                market_open=True,
                position_still_open=True,
                kill_switch_armed=self.plane.kill_switch_armed,
                daily_loss_exceeded=self.plane.daily_loss_exceeded,
                user_id=self.user_id,
            )
            self.position_management.evaluate(ticket, pctx)

        reason_detail = (
            f"action={decision.action.value} "
            f"forwarded={bridge_result.forwarded_to_oms} "
            f"abort={bridge_result.abort_reason.value}"
        )
        if decision_reasons:
            reason_detail += f" reasons={';'.join(decision_reasons)}"
        self.reliability.timeline.append(
            TimelineEvent(
                timestamp=datetime.now(UTC),
                category="shadow" if force_shadow else "auto",
                action="cycle",
                detail=reason_detail,
                severity="INFO",
                trace_id=tid,
            )
        )

        oms_message = None
        broker_retcode = None
        mt5_ticket = None
        entry = getattr(bridge_result, "journal_entry", None)
        if entry is not None:
            oms_message = getattr(entry, "comment", None)
            broker_retcode = getattr(entry, "retcode", None)
            mt5_ticket = getattr(entry, "ticket", None) or getattr(
                entry, "order_ticket", None
            )

        if bridge_result.forwarded_to_oms:
            cycle_outcome = "forwarded"
        elif str(decision.action.value) in {"NO_TRADE", "WATCH"}:
            cycle_outcome = "no_trade"
        else:
            cycle_outcome = "aborted"

        latency_ms = (time.perf_counter() - t0) * 1000.0
        detail = (
            "shadow cycle complete"
            if force_shadow
            else (
                "auto cycle forwarded"
                if bridge_result.forwarded_to_oms
                else (
                    (entry.comment if entry is not None else None)
                    or bridge_result.abort_reason.value
                )
            )
        )
        if not bridge_result.forwarded_to_oms and decision_reasons:
            detail = f"{detail} | {'; '.join(decision_reasons)}"

        result = ShadowCycleResult(
            ok=(not bridge_result.forwarded_to_oms) if force_shadow else True,
            trace_id=tid,
            mode=(
                OpsExecutionMode.SHADOW.value
                if force_shadow
                else self.plane.mode.value
            ),
            decision_action=decision.action.value,
            forwarded_to_oms=bridge_result.forwarded_to_oms,
            detail=detail,
            health=health.get("health") if isinstance(health, dict) else None,
            cycle_outcome="shadow" if force_shadow else cycle_outcome,
            abort_reason=bridge_result.abort_reason.value,
            decision_reasons=decision_reasons,
            snapshot_present=True,
            market_context_diagnostics=(
                dict(market_context_diagnostics)
                if market_context_diagnostics
                else None
            ),
            signal_id=str(getattr(decision, "id", "") or "") or None,
            oms_message=str(oms_message) if oms_message else None,
            broker_retcode=int(broker_retcode) if broker_retcode is not None else None,
            mt5_ticket=int(mt5_ticket) if mt5_ticket is not None else None,
            latency_ms=round(latency_ms, 3),
        )
        with self._lock:
            self._last_cycle = result
            self._cycles += 1
        # Observation only — never mutates decision / risk / safety / OMS.
        try:
            from app.application.services.strategy_diagnostics import (
                get_strategy_diagnostics_store,
            )

            get_strategy_diagnostics_store().record_from_artefacts(
                snapshot=snapshot,
                decision=decision,
                cycle_outcome=result.cycle_outcome,
                decision_action=result.decision_action,
                abort_reason=result.abort_reason,
                decision_reasons=decision_reasons,
                market_context_diagnostics=result.market_context_diagnostics,
                signal_id=result.signal_id,
                forwarded_to_oms=result.forwarded_to_oms,
                trace_id=result.trace_id,
            )
        except Exception:
            logger.exception("strategy_diagnostics_record_failed")
        if force_shadow and bridge_result.forwarded_to_oms:
            logger.error(
                "shadow_cycle_forwarded_to_oms",
                trace_id=tid,
                detail="BUG — shadow must never call OMS",
            )
        logger.info(
            "ite_cycle_outcome",
            outcome=result.cycle_outcome,
            decision_action=result.decision_action,
            abort_reason=result.abort_reason,
            reasons=list(result.decision_reasons),
            forwarded_to_oms=result.forwarded_to_oms,
            signal_id=result.signal_id,
            latency_ms=result.latency_ms,
            mode=result.mode,
        )
        return result

    def status(self) -> dict[str, Any]:
        with self._lock:
            last = self._last_cycle
            cycles = self._cycles
        settings = get_settings()
        return {
            "mode": self.plane.mode.value,
            "kill_switch": self.plane.kill_switch_armed,
            "auto_trading_enabled": self.plane.auto_trading_enabled,
            "execution_enabled_setting": bool(
                getattr(settings, "execution_enabled", False)
            ),
            "bridge_mode": self.execution.bridge.effective_mode().value,
            "oms_orders_allowed": self.plane.oms_orders_allowed(),
            "cycles": cycles,
            "last_cycle": last.to_dict() if last else None,
            "interval_seconds": self.interval_seconds,
            "running": not self._stop.is_set(),
        }

    def strategy_diagnostics(self, *, limit: int = 100) -> dict[str, Any]:
        """Read-only NO_TRADE diagnostics for Operations desk."""
        from app.application.services.strategy_diagnostics import (
            get_strategy_diagnostics_store,
        )

        return get_strategy_diagnostics_store().snapshot(limit=limit)

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        """Background loop — live market context → Decision→Risk→Safety→OMS."""
        logger.info(
            "ite_orchestrator_started",
            interval_seconds=self.interval_seconds,
            mode=self.plane.mode.value,
        )
        while not self._stop.is_set():
            try:
                from app.application.services.auto_trading_status import (
                    _enrich_from_adapter,
                )
                from app.application.services.ite_cycle_market_context import (
                    build_ite_cycle_market_context,
                )

                enrich = _enrich_from_adapter(self.probes)
                ctx = await build_ite_cycle_market_context(self.mt5_adapter)
                if not ctx.ok or ctx.snapshot is None or ctx.account is None:
                    health = self.tick_health()
                    result = ShadowCycleResult(
                        ok=True,
                        trace_id=None,
                        mode=self.plane.mode.value,
                        detail=ctx.reason or "market context unavailable",
                        health=(
                            health.get("health") if isinstance(health, dict) else None
                        ),
                        cycle_outcome="no_snapshot",
                        abort_reason="NO_MARKET_CONTEXT",
                        snapshot_present=False,
                        market_context_reason=ctx.reason,
                        market_context_diagnostics=dict(ctx.diagnostics),
                        latency_ms=ctx.latency_ms,
                    )
                    with self._lock:
                        self._last_cycle = result
                        self._cycles += 1
                    try:
                        from app.application.services.strategy_diagnostics import (
                            get_strategy_diagnostics_store,
                        )

                        get_strategy_diagnostics_store().record_from_artefacts(
                            snapshot=None,
                            decision=None,
                            cycle_outcome="no_snapshot",
                            decision_action=None,
                            abort_reason="NO_MARKET_CONTEXT",
                            decision_reasons=(),
                            market_context_diagnostics=dict(ctx.diagnostics),
                            signal_id=None,
                            forwarded_to_oms=False,
                            trace_id=None,
                        )
                    except Exception:
                        logger.exception("strategy_diagnostics_record_failed")
                    logger.info(
                        "ite_cycle_outcome",
                        outcome="no_snapshot",
                        reason=ctx.reason,
                        bars=ctx.bars_loaded,
                        diagnostics=ctx.diagnostics,
                        mode=self.plane.mode.value,
                    )
                else:
                    mt5_at = (
                        bool(enrich["mt5_autotrading_enabled"])
                        if enrich.get("mt5_autotrading_enabled") is not None
                        else True
                    )
                    acct_ok = (
                        bool(enrich["account_trading_enabled"])
                        if enrich.get("account_trading_enabled") is not None
                        else ctx.account_trading_enabled
                    )
                    sym_ok = (
                        bool(enrich["symbol_tradable"])
                        if enrich.get("symbol_tradable") is not None
                        else ctx.symbol_tradable
                    )
                    mkt_ok = (
                        bool(enrich["market_data_live"])
                        if enrich.get("market_data_live") is not None
                        else ctx.market_data_live
                    )
                    no_restr = (
                        bool(enrich["no_broker_restrictions"])
                        if enrich.get("no_broker_restrictions") is not None
                        else True
                    )
                    if self.plane.mode is OpsExecutionMode.SHADOW:
                        self.run_shadow_cycle(
                            snapshot=ctx.snapshot,
                            account=ctx.account,
                            market_context_diagnostics=dict(ctx.diagnostics),
                        )
                    else:
                        self.run_auto_cycle(
                            snapshot=ctx.snapshot,
                            account=ctx.account,
                            gateway_connected=True,
                            broker_connected=True,
                            market_data_live=mkt_ok,
                            account_trading_enabled=acct_ok,
                            mt5_autotrading_enabled=mt5_at,
                            symbol_tradable=sym_ok,
                            no_broker_restrictions=no_restr,
                            risk_allowed=True,
                            market_context_diagnostics=dict(ctx.diagnostics),
                        )
                    with self._lock:
                        if self._last_cycle is not None:
                            self._last_cycle.market_context_diagnostics = dict(
                                ctx.diagnostics
                            )
                            self._last_cycle.market_context_reason = ctx.reason
                            self._last_cycle.snapshot_present = True
            except Exception as exc:
                logger.exception("ite_orchestrator_cycle_failed", error=str(exc))
                with self._lock:
                    self._last_cycle = ShadowCycleResult(
                        ok=False,
                        trace_id=None,
                        mode=self.plane.mode.value,
                        detail=f"cycle exception: {exc}",
                        cycle_outcome="error",
                        abort_reason="CYCLE_EXCEPTION",
                    )
                    self._cycles += 1
            for _ in range(int(max(1, self.interval_seconds))):
                if self._stop.is_set():
                    break
                await asyncio.sleep(1)
        logger.info("ite_orchestrator_stopped")


def build_ite_runtime(
    *,
    settings: Any,
    mt5_adapter: Any,
    execution_gateway: Any,
    execution_safety: Any,
    mt5_order_validation: Any,
    supabase: Any | None,
    interval_seconds: float = 60.0,
) -> InstitutionalIteRuntime:
    """Wire Guarded OMS ports + shared kill + reliability into one runtime."""
    from app.application.services.execution_intelligence import (
        ExecutionIntelligenceService,
    )
    from app.application.services.institutional_execution_engine import (
        InstitutionalExecutionEngine,
    )
    from app.domain.execution_engine.journal import ExecutionJournalStore
    from app.domain.institutional_trading.execution.config import (
        ExecutionBridgeConfig,
    )

    plane = get_control_plane()
    reliability = get_reliability_platform()
    # Force shadow defaults for production shadow readiness
    if plane.mode is not OpsExecutionMode.SHADOW:
        # do not auto-transition; operator must set — but log
        logger.warning(
            "ite_runtime_mode_not_shadow",
            mode=plane.mode.value,
        )

    engine = InstitutionalExecutionEngine(
        gateway=execution_gateway,
        safety=execution_safety,
        order_validation=mt5_order_validation,
        intelligence=ExecutionIntelligenceService(),
        journal=ExecutionJournalStore(),
    )
    raw_submit = InstitutionalOmsAdapter(engine=engine)
    raw_manage = InstitutionalOmsManageAdapter(engine=engine)
    guarded_submit = GuardedOmsSubmitPort(inner=raw_submit, plane=plane)
    guarded_manage = GuardedOmsManagePort(inner=raw_manage, plane=plane)

    config = ExecutionBridgeConfig(mode=ExecutionMode.SHADOW)
    execution = InstitutionalExecutionIntegration.create(guarded_submit, config=config)
    execution.bridge.bind_ops(plane, reliability=reliability)

    pme = InstitutionalPositionManagement.create(guarded_manage, ops_plane=plane)

    probes = LiveProbeCollector(
        settings=settings, mt5_adapter=mt5_adapter, supabase=supabase
    )
    return InstitutionalIteRuntime(
        plane=plane,
        reliability=reliability,
        probes=probes,
        guarded_submit=guarded_submit,
        guarded_manage=guarded_manage,
        execution=execution,
        position_management=pme,
        interval_seconds=interval_seconds,
        mt5_adapter=mt5_adapter,
    )


_RUNTIME: InstitutionalIteRuntime | None = None
_RUNTIME_LOCK = Lock()


def get_ite_runtime() -> InstitutionalIteRuntime | None:
    with _RUNTIME_LOCK:
        return _RUNTIME


def set_ite_runtime(runtime: InstitutionalIteRuntime | None) -> None:
    global _RUNTIME
    with _RUNTIME_LOCK:
        _RUNTIME = runtime
