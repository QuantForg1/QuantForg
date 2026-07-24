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
    guarded_submit: Any  # GuardedOmsSubmitPort or RetryingOmsSubmitPort wrapper
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
    _last_decision: Any | None = field(default=None, repr=False)
    _last_bridge_result: Any | None = field(default=None, repr=False)
    _manual_execution: bool = field(default=False, repr=False)
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

        # Force Sync Positions before max-open / safety evaluation.
        # MT5 is source of truth — never block solely on stale internal counts.
        try:
            from app.application.services.mt5_position_truth import (
                apply_mt5_position_truth,
                force_sync_positions,
            )

            prior_internal = int(account.open_positions)
            sync = force_sync_positions(
                self.mt5_adapter,
                symbol=str(getattr(snapshot, "symbol", "XAUUSD") or "XAUUSD"),
                internal_positions=prior_internal,
                position_engine=self.position_management.engine,
            )
            account = apply_mt5_position_truth(account, sync)
            if sync.repaired or sync.mt5_positions != prior_internal:
                logger.warning(
                    "force_sync_before_safety",
                    mt5_positions=sync.mt5_positions,
                    internal_positions=prior_internal,
                    repaired=sync.repaired,
                )
        except Exception:
            logger.exception("force_sync_positions_before_safety_failed")

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
            # Last-chance Force Sync if the only blocker is max open positions.
            max_open_block = any(
                "Open positions" in r and "at max" in r
                for r in (safety.failed_reasons or ())
            )
            if max_open_block:
                try:
                    from app.application.services.mt5_position_truth import (
                        apply_mt5_position_truth,
                        force_sync_positions,
                    )

                    prior_internal = int(account.open_positions)
                    sync = force_sync_positions(
                        self.mt5_adapter,
                        symbol=str(
                            getattr(snapshot, "symbol", "XAUUSD") or "XAUUSD"
                        ),
                        internal_positions=prior_internal,
                        position_engine=self.position_management.engine,
                    )
                    account = apply_mt5_position_truth(account, sync)
                    logger.warning(
                        "force_sync_before_max_open_reject",
                        mt5_positions=sync.mt5_positions,
                        internal_positions=prior_internal,
                        repaired=sync.repaired,
                    )
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
                except Exception:
                    logger.exception("force_sync_before_max_open_reject_failed")

        if not safety.allowed:
            from app.domain.institutional_trading.force_first_trade import (
                is_force_first_trade_armed,
            )

            force_armed = is_force_first_trade_armed(settings)
            can_force = (
                force_armed
                and execution_on
                and gw
                and mt5
                and account.open_positions <= 0
                and not account.already_in_trade
            )
            if not can_force:
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
            logger.warning(
                "FORCE_FIRST_TRADE proceeding despite safety blockers: %s",
                "; ".join(safety.failed_reasons) or "unknown",
            )

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
        try:
            from app.domain.institutional_trading.production_hardening.observe import (
                record_lifecycle,
            )

            record_lifecycle(
                stage="SIGNAL",
                status="ok",
                detail=f"symbol={getattr(snapshot, 'symbol', '')}",
                trace_id=tid,
                symbol=str(getattr(snapshot, "symbol", "") or ""),
            )
        except Exception:
            logger.exception("hardening_signal_lifecycle_failed")

        decision = self.decision_pipeline.run(snapshot, account)
        # Temporary Force First Trade override — before signal rejection only.
        forced_override = False
        try:
            from app.domain.institutional_trading.force_first_trade import (
                maybe_override_decision,
            )
            from core.config.settings import get_settings as _get_settings

            decision, forced_override = maybe_override_decision(
                decision,
                snapshot=snapshot,
                account=account,
                ite_config=self.decision_pipeline.config,
                settings=_get_settings(),
                execution_enabled=False if force_shadow else execution_enabled,
                gateway_connected=gateway_connected,
                broker_connected=broker_connected,
                force_shadow=force_shadow,
            )
        except Exception:
            logger.exception("force_first_trade_override_failed")
            forced_override = False

        with self._lock:
            self._last_decision = decision

        decision_reasons = tuple(getattr(decision, "reasons", ()) or ())
        if self._manual_execution or forced_override:
            logger.warning(
                "AI Decision Complete",
                action=str(getattr(decision.action, "value", decision.action)),
                forced=forced_override,
            )
        else:
            logger.info(
                "AI Decision Complete",
                action=str(getattr(decision.action, "value", decision.action)),
            )

        try:
            from app.domain.institutional_trading.production_hardening.observe import (
                record_lifecycle,
            )

            record_lifecycle(
                stage="AI_DECISION",
                status="ok",
                detail=f"action={decision.action.value} conf={getattr(decision, 'confidence', '')}",
                trace_id=tid,
                symbol=str(getattr(decision, "symbol", "") or getattr(snapshot, "symbol", "")),
            )
            record_lifecycle(
                stage="RISK_VALIDATION",
                status="ok" if decision.eligibility.eligible else "failed",
                detail=";".join(decision.eligibility.rejection_reasons) or "eligible",
                trace_id=tid,
                symbol=str(getattr(decision, "symbol", "") or ""),
            )
        except Exception:
            logger.exception("hardening_decision_lifecycle_failed")

        # Enrich diagnostics with live ATR sizing facts (observational only).
        sizing_diag: dict[str, Any] = dict(market_context_diagnostics or {})
        atr_val = getattr(account, "atr", None)
        stop_dist = (
            (atr_val * Decimal("1.5")).quantize(Decimal("0.0001"))
            if atr_val is not None and atr_val > 0
            else None
        )
        risk_pct = getattr(self.decision_pipeline.config, "risk_per_trade_pct", None)
        if risk_pct is None:
            risk_pct = Decimal("1.0")
        risk_budget = (
            (account.equity * (Decimal(str(risk_pct)) / Decimal("100"))).quantize(
                Decimal("0.01")
            )
            if account.equity is not None
            else None
        )
        sizing_diag.update(
            {
                "atr": str(atr_val) if atr_val is not None else sizing_diag.get("atr"),
                "stop_distance": (
                    str(stop_dist)
                    if stop_dist is not None
                    else sizing_diag.get("stop_distance")
                ),
                "risk_budget": (
                    str(risk_budget)
                    if risk_budget is not None
                    else sizing_diag.get("risk_budget")
                ),
                "risk_pct": str(risk_pct),
                "calculated_lots": (
                    str(decision.approved_lots)
                    if decision.approved_lots is not None
                    else sizing_diag.get("calculated_lots")
                ),
                "approved_lots": (
                    str(decision.approved_lots)
                    if decision.approved_lots is not None
                    else None
                ),
                "force_first_trade": forced_override,
            }
        )
        market_context_diagnostics = sizing_diag

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
            risk_allowed=(
                True
                if forced_override
                else risk_allowed
            ),
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
        if self._manual_execution:
            logger.warning(
                "Submitting Order",
                action=str(getattr(decision.action, "value", decision.action)),
                direction=str(getattr(decision.direction, "value", decision.direction)),
                lots=str(getattr(decision, "approved_lots", None) or ""),
            )
        bridge_result = self.execution.bridge.handle(decision, ctx, trace_id=tid)
        with self._lock:
            self._last_bridge_result = bridge_result

        try:
            from app.domain.institutional_trading.production_hardening.observe import (
                observe_oms_outcome,
                store_trade_explanation,
            )

            oms = getattr(bridge_result, "oms_result", None)
            success = (
                not getattr(bridge_result, "aborted", True)
                and getattr(bridge_result, "forwarded_to_oms", False)
            )
            if oms is not None:
                outcome = str(getattr(oms, "outcome", "") or "").lower()
                success = outcome in {"success", "filled", "done"}
            ticket = None
            if oms is not None:
                ticket = getattr(oms, "order_ticket", None) or getattr(
                    oms, "deal_ticket", None
                )
            lat = (time.perf_counter() - t0) * 1000.0
            retries = 0
            inner = getattr(self.guarded_submit, "retry_count", None)
            if isinstance(inner, int):
                retries = inner
            observe_oms_outcome(
                trace_id=tid,
                symbol=str(getattr(decision, "symbol", "") or getattr(snapshot, "symbol", "")),
                forwarded=bool(getattr(bridge_result, "forwarded_to_oms", False)),
                success=bool(success),
                latency_ms=lat,
                retcode=getattr(oms, "retcode", None) if oms is not None else None,
                message=str(getattr(oms, "message", "") or "") if oms is not None else None,
                ticket=ticket,
                spread=float(snapshot.spread) if getattr(snapshot, "spread", None) is not None else None,
                retries=retries,
            )
            if success and getattr(bridge_result, "forwarded_to_oms", False):
                store_trade_explanation(
                    decision=decision,
                    ticket=str(ticket) if ticket is not None else None,
                    risk_pct=str(risk_pct),
                    extras={"trace_id": tid, "forced": forced_override},
                )
        except Exception:
            logger.exception("hardening_post_bridge_observe_failed")
        if self._manual_execution:
            oms = getattr(bridge_result, "oms_result", None)
            logger.warning(
                "Broker Response",
                forwarded=bool(getattr(bridge_result, "forwarded_to_oms", False)),
                abort=str(
                    getattr(
                        getattr(bridge_result, "abort_reason", None),
                        "value",
                        getattr(bridge_result, "abort_reason", ""),
                    )
                ),
                message=str(
                    getattr(oms, "message", None)
                    or getattr(getattr(bridge_result, "journal_entry", None), "comment", None)
                    or ""
                ),
                retcode=getattr(oms, "retcode", None),
                ticket=getattr(oms, "order_ticket", None)
                or getattr(oms, "deal_ticket", None),
            )

        if forced_override:
            oms = getattr(bridge_result, "oms_result", None)
            if oms is not None:
                outcome = str(getattr(oms, "outcome", "") or "").lower()
            else:
                outcome = ""
            oms_success = bridge_result.forwarded_to_oms and outcome in {
                "success",
                "filled",
                "done",
            }
            if oms_success:
                try:
                    from app.domain.institutional_trading.force_first_trade import (
                        record_forced_trade_success,
                    )

                    entry = getattr(bridge_result, "journal_entry", None)
                    ticket = None
                    price = None
                    if entry is not None:
                        ticket = getattr(entry, "ticket", None) or getattr(
                            entry, "order_ticket", None
                        )
                        price = getattr(entry, "price", None) or getattr(
                            entry, "fill_price", None
                        )
                    if price is None and account.mid_price is not None:
                        price = account.mid_price
                    if oms is not None and ticket is None:
                        ticket = getattr(oms, "order_ticket", None) or getattr(
                            oms, "deal_ticket", None
                        )
                    record_forced_trade_success(
                        direction=str(decision.direction.value),
                        lot=decision.approved_lots or Decimal("0.01"),
                        ticket=int(ticket) if ticket is not None else None,
                        price=price,
                    )
                except Exception:
                    logger.exception("force_first_trade_record_failed")
            else:
                try:
                    from app.domain.institutional_trading.force_first_trade import (
                        log_force_first_trade_rejection,
                    )

                    entry = getattr(bridge_result, "journal_entry", None)
                    comment = None
                    if entry is not None:
                        comment = getattr(entry, "comment", None)
                    oms_msg = None
                    retcode = None
                    if oms is not None:
                        oms_msg = getattr(oms, "message", None)
                        retcode = getattr(oms, "retcode", None)
                    log_force_first_trade_rejection(
                        stage=(
                            "OMS/MT5"
                            if bridge_result.forwarded_to_oms
                            else "pre-OMS bridge"
                        ),
                        reason=str(bridge_result.abort_reason.value),
                        retcode=int(retcode) if retcode is not None else None,
                        oms_message=str(oms_msg or comment or "") or None,
                        detail="; ".join(decision_reasons) or None,
                    )
                except Exception:
                    logger.exception("force_first_trade_reject_log_failed")

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

        try:
            from app.domain.institutional_trading.production_hardening.position_recovery import (
                persist_pme_state,
            )

            persist_pme_state(self.position_management.engine)
            from app.domain.institutional_trading.production_hardening.observe import (
                record_lifecycle,
            )

            if self.position_management.engine._positions:
                record_lifecycle(
                    stage="POSITION_MONITOR",
                    status="ok",
                    detail=f"managed={len(self.position_management.engine._positions)}",
                    trace_id=tid,
                )
        except Exception:
            logger.exception("hardening_pme_persist_failed")

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
            "trading_mode": getattr(self.decision_pipeline.config, "trading_mode", "swing"),
            "ai_score": (
                self.decision_pipeline.last_ai_score()
                if hasattr(self.decision_pipeline, "last_ai_score")
                else None
            ),
        }

    def strategy_diagnostics(self, *, limit: int = 100) -> dict[str, Any]:
        """Read-only NO_TRADE diagnostics for Operations desk."""
        from app.application.services.strategy_diagnostics import (
            get_strategy_diagnostics_store,
        )

        return get_strategy_diagnostics_store().snapshot(limit=limit)

    @staticmethod
    def _zone_price(zone: Any, *, prefer: str = "mid") -> float | None:
        if zone is None:
            return None
        mid = getattr(zone, "mid", None)
        low = getattr(zone, "low", None)
        high = getattr(zone, "high", None)
        if prefer == "mid" and mid is not None:
            return float(mid)
        if prefer == "low" and low is not None:
            return float(low)
        if prefer == "high" and high is not None:
            return float(high)
        for candidate in (mid, low, high):
            if candidate is not None:
                return float(candidate)
        return None

    def build_execute_now_payload(
        self,
        cycle: ShadowCycleResult,
        *,
        execution_ms: float,
    ) -> dict[str, Any]:
        """Map one Auto Trading cycle into the Execute Now API response."""
        with self._lock:
            decision = self._last_decision
            bridge = self._last_bridge_result

        market = None
        direction = None
        lot: float | None = None
        entry: float | None = None
        sl: float | None = None
        tp: float | None = None
        if decision is not None:
            market = str(getattr(decision, "symbol", "") or "") or None
            direction = str(
                getattr(getattr(decision, "direction", None), "value", None)
                or getattr(decision, "direction", None)
                or ""
            ) or None
            lots = getattr(decision, "approved_lots", None)
            if lots is not None:
                lot = float(lots)
            entry = self._zone_price(getattr(decision, "entry_zone", None), prefer="mid")
            stop = getattr(decision, "stop_zone", None)
            target = getattr(decision, "target_zone", None)
            dir_u = (direction or "").upper()
            if dir_u == "BUY":
                sl = self._zone_price(stop, prefer="low")
                tp = self._zone_price(target, prefer="high")
            elif dir_u == "SELL":
                sl = self._zone_price(stop, prefer="high")
                tp = self._zone_price(target, prefer="low")
            else:
                sl = self._zone_price(stop, prefer="mid")
                tp = self._zone_price(target, prefer="mid")

        ticket: str | None = None
        if cycle.mt5_ticket is not None:
            ticket = str(cycle.mt5_ticket)
        oms = getattr(bridge, "oms_result", None) if bridge is not None else None
        if ticket is None and oms is not None:
            raw_ticket = getattr(oms, "order_ticket", None) or getattr(
                oms, "deal_ticket", None
            )
            if raw_ticket is not None:
                ticket = str(raw_ticket)
        if entry is None and oms is not None:
            fill = getattr(oms, "fill_price", None) or getattr(oms, "price", None)
            if fill is not None:
                entry = float(fill)

        outcome = str(getattr(oms, "outcome", "") or "").lower() if oms else ""
        oms_success = bool(cycle.forwarded_to_oms) and outcome in {
            "success",
            "filled",
            "done",
        }
        # Some adapters mark success via journal status without outcome string.
        if not oms_success and cycle.forwarded_to_oms and ticket and not cycle.oms_message:
            if (cycle.abort_reason or "").upper() in {"NONE", "", "OK", "SUCCESS"}:
                oms_success = True

        exact_reason_parts: list[str] = []
        if cycle.oms_message:
            exact_reason_parts.append(str(cycle.oms_message))
        if oms is not None:
            msg = getattr(oms, "message", None)
            if msg and str(msg) not in exact_reason_parts:
                exact_reason_parts.append(str(msg))
        if cycle.safety_failed_reasons:
            for reason in cycle.safety_failed_reasons:
                if reason and reason not in exact_reason_parts:
                    exact_reason_parts.append(str(reason))
        if cycle.decision_reasons:
            for reason in cycle.decision_reasons:
                if reason and reason not in exact_reason_parts:
                    exact_reason_parts.append(str(reason))
        if cycle.detail and cycle.detail not in exact_reason_parts:
            # Prefer broker/OMS text; keep detail when nothing else exists.
            if not exact_reason_parts:
                exact_reason_parts.append(str(cycle.detail))
        if cycle.abort_reason and cycle.abort_reason.upper() not in {
            "NONE",
            "OK",
            "SUCCESS",
        }:
            abort = str(cycle.abort_reason)
            if abort not in exact_reason_parts:
                exact_reason_parts.append(abort)
        if cycle.broker_retcode is not None:
            ret = f"retcode={cycle.broker_retcode}"
            if ret not in exact_reason_parts:
                exact_reason_parts.append(ret)

        reason = "; ".join(exact_reason_parts) if exact_reason_parts else (
            cycle.detail or cycle.abort_reason or "Execution rejected"
        )

        base = {
            "market": market,
            "direction": direction,
            "lot": lot,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "ticket": ticket,
            "execution_ms": int(round(execution_ms)),
            "cycle_outcome": cycle.cycle_outcome,
            "abort_reason": cycle.abort_reason,
            "trace_id": cycle.trace_id,
        }
        if oms_success:
            return {
                **base,
                "success": True,
                "status": "SUCCESS",
                "message": "Order executed successfully.",
            }
        return {
            **base,
            "success": False,
            "status": "REJECTED",
            "reason": reason,
            "message": reason,
        }

    def _alpha_preferred_symbol(self) -> str | None:
        """When Institutional Alpha is on, return highest-ranked executable symbol."""
        try:
            from app.application.services.institutional_alpha_engine import (
                get_alpha_config,
                run_alpha_scan,
            )
            from app.domain.trading.gold_only import GOLD_SYMBOL

            cfg = get_alpha_config()
            if not cfg.enabled and not getattr(self.plane, "alpha_engine_enabled", False):
                mode = str(getattr(self.plane, "trading_mode", "") or "")
                if mode != "alpha":
                    return None
            open_symbols: list[str] = []
            try:
                open_symbols = [
                    str(getattr(p, "symbol", "") or "")
                    for p in self.position_management.engine._positions.values()
                ]
            except Exception:
                open_symbols = []
            scan = run_alpha_scan(
                mt5_adapter=self.mt5_adapter,
                open_symbols=open_symbols,
            )
            selected = scan.get("selected") or []
            if selected:
                sym = str(selected[0].get("symbol") or "").upper()
                logger.warning(
                    "alpha_opportunity_selected",
                    symbol=sym,
                    score=selected[0].get("opportunity_score"),
                    rank=selected[0].get("rank"),
                )
                return sym or GOLD_SYMBOL
            logger.warning("alpha_scan_no_executable_opportunity")
            return None
        except Exception:
            logger.exception("alpha_preferred_symbol_failed")
            return None

    async def execute_now(self) -> dict[str, Any]:
        """Run one complete Auto Trading cycle immediately (manual trigger).

        Reuses the same market-context + run_auto_cycle / run_shadow_cycle path
        as the background scheduler — does not duplicate trading logic.
        """
        t0 = time.perf_counter()
        self._manual_execution = True
        logger.warning("MANUAL EXECUTION STARTED")
        try:
            from app.application.services.auto_trading_status import (
                _enrich_from_adapter,
            )
            from app.application.services.ite_cycle_market_context import (
                build_ite_cycle_market_context,
            )
            from app.domain.trading.gold_only import GOLD_SYMBOL

            logger.warning("Force Sync Positions")
            enrich = _enrich_from_adapter(self.probes)
            symbol = self._alpha_preferred_symbol() or GOLD_SYMBOL
            ctx = await build_ite_cycle_market_context(
                self.mt5_adapter,
                symbol=symbol,
                position_engine=self.position_management.engine,
            )
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
                payload = self.build_execute_now_payload(
                    result,
                    execution_ms=(time.perf_counter() - t0) * 1000.0,
                )
                logger.warning(
                    "Execution Finished",
                    success=payload.get("success"),
                    status=payload.get("status"),
                )
                return payload

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
                cycle = self.run_shadow_cycle(
                    snapshot=ctx.snapshot,
                    account=ctx.account,
                    market_context_diagnostics=dict(ctx.diagnostics),
                )
            else:
                cycle = self.run_auto_cycle(
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
                    self._last_cycle.market_context_diagnostics = dict(ctx.diagnostics)
                    self._last_cycle.market_context_reason = ctx.reason
                    self._last_cycle.snapshot_present = True
                    cycle = self._last_cycle
            payload = self.build_execute_now_payload(
                cycle,
                execution_ms=(time.perf_counter() - t0) * 1000.0,
            )
            logger.warning(
                "Execution Finished",
                success=payload.get("success"),
                status=payload.get("status"),
                ticket=payload.get("ticket"),
            )
            return payload
        except Exception as exc:
            logger.exception("manual_execute_now_failed", error=str(exc))
            ms = (time.perf_counter() - t0) * 1000.0
            reason = f"cycle exception: {exc}"
            logger.warning("Execution Finished", success=False, status="REJECTED")
            return {
                "success": False,
                "status": "REJECTED",
                "reason": reason,
                "message": reason,
                "execution_ms": int(round(ms)),
                "market": None,
                "direction": None,
                "lot": None,
                "entry": None,
                "sl": None,
                "tp": None,
                "ticket": None,
            }
        finally:
            self._manual_execution = False

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
                from app.domain.trading.gold_only import GOLD_SYMBOL

                symbol = self._alpha_preferred_symbol() or GOLD_SYMBOL
                ctx = await build_ite_cycle_market_context(
                    self.mt5_adapter,
                    symbol=symbol,
                    position_engine=self.position_management.engine,
                )
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

    # Production hardening v6 — retry only transient MT5 rejects (never permanent).
    from app.domain.institutional_trading.production_hardening import (
        RetryingOmsSubmitPort,
    )

    def _on_oms_retry(attempt: int, decision: Any, _last: Any) -> None:
        logger.warning(
            "oms_transient_retry",
            attempt=attempt,
            reason=getattr(decision, "reason", ""),
            backoff_ms=getattr(decision, "backoff_ms", 0),
        )

    submit_port: Any = RetryingOmsSubmitPort(
        guarded_submit, on_retry=_on_oms_retry
    )

    config = ExecutionBridgeConfig(mode=ExecutionMode.SHADOW)
    execution = InstitutionalExecutionIntegration.create(submit_port, config=config)
    execution.bridge.bind_ops(plane, reliability=reliability)

    pme = InstitutionalPositionManagement.create(guarded_manage, ops_plane=plane)

    probes = LiveProbeCollector(
        settings=settings, mt5_adapter=mt5_adapter, supabase=supabase
    )
    return InstitutionalIteRuntime(
        plane=plane,
        reliability=reliability,
        probes=probes,
        guarded_submit=submit_port,
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
