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


def _cycle_flag_prefer_context(
    *,
    ctx_value: bool,
    enrich: dict[str, Any],
    key: str,
) -> bool:
    """Prefer fresher market-context flags over earlier enrich probes.

    Enrich runs before ``build_ite_cycle_market_context``. An explicit stale
    ``False`` in enrich must not override a live ``True`` from context.
    """
    ctx_bool = bool(ctx_value)
    if key not in enrich or enrich.get(key) is None:
        return ctx_bool
    enrich_bool = bool(enrich.get(key))
    if enrich_bool != ctx_bool:
        logger.warning(
            "cycle_flag_enrich_ctx_mismatch",
            key=key,
            enrich=enrich_bool,
            context=ctx_bool,
            using="context",
        )
    return ctx_bool


def _oms_submit_path_healthy(probes: Any) -> bool:
    """OMS heartbeat reflects the submit path (gateway), not Railway self-probe.

    Historically OMS was gated on ``railway_api_up AND gateway_available``.
    When ``RAILWAY_PUBLIC_DOMAIN`` is unset or the in-process self-GET to
    ``/health`` fails (common inside the same container), that falsely marks
    OMS stale → ``continuous_ops_pause_new_entries`` / ``stale heartbeat:oms``
    while Gateway Connectivity already PASSes and OMS is never called.

    OMS posts to the Windows gateway — so gateway reachability is the correct
    liveness signal. Railway API health remains its own component heartbeat.
    """
    return bool(getattr(probes, "gateway_available", False))


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
    _last_multi_asset_scan: dict[str, Any] | None = field(default=None, repr=False)
    _manual_execution: bool = field(default=False, repr=False)
    _cycles: int = 0
    user_id: UUID = field(default_factory=uuid4)

    def tick_health(self) -> dict[str, Any]:
        """Live probes → ReliabilityPlatform.tick (no POST body flags)."""
        probes = self.probes.collect()
        # Heartbeats only for components that are currently healthy — never
        # refresh a failed dependency as alive (stale-heartbeat pause must work).
        now = datetime.now(UTC)
        oms_ok_probe = _oms_submit_path_healthy(probes)
        healthy_map = {
            ComponentName.GATEWAY: bool(probes.gateway_available),
            ComponentName.MT5: bool(probes.mt5_connected),
            ComponentName.DECISION: True,  # this process is deciding
            ComponentName.OMS: oms_ok_probe,
            ComponentName.RAILWAY_API: bool(getattr(probes, "railway_api_up", False)),
            ComponentName.SUPABASE: bool(getattr(probes, "supabase_up", False)),
            ComponentName.CLOUDFLARE_TUNNEL: bool(
                getattr(probes, "cloudflare_tunnel_up", False)
            ),
        }
        for comp, ok in healthy_map.items():
            if ok:
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
        # v7.1 continuous ops — heal deps, pause new entries only, never abandon book
        try:
            from app.domain.institutional_trading.ai_scalping.config import (
                DEFAULT_AI_SCALPING_CONFIG,
            )
            from app.domain.institutional_trading.ai_scalping.continuous_operation import (  # noqa: E501
                get_continuous_operation_controller,
            )

            if DEFAULT_AI_SCALPING_CONFIG.continuous_operation_enabled:
                ctrl = get_continuous_operation_controller(DEFAULT_AI_SCALPING_CONFIG)
                if not getattr(self, "_continuous_ops_bound", False):
                    ctrl.mark_startup_resume()
                    adapter = self.mt5_adapter

                    def _gw() -> bool:
                        try:
                            client = getattr(adapter, "client", None)
                            if client is not None and hasattr(client, "gateway_health"):
                                h = client.gateway_health()
                                return bool(
                                    isinstance(h, dict)
                                    and (
                                        h.get("status") == "ok"
                                        or h.get("connected")
                                        or (h.get("mt5") or {}).get("connected")
                                    )
                                )
                        except Exception:
                            return False
                        return False

                    def _mt5() -> bool:
                        try:
                            if adapter is not None and hasattr(adapter, "attach"):
                                adapter.attach(path="")
                            client = getattr(adapter, "client", None) or getattr(
                                adapter, "_client", None
                            )
                            return bool(
                                client is not None
                                and getattr(client, "is_connected", False)
                            )
                        except Exception:
                            return False

                    ctrl.bind_reconnects(gateway=_gw, mt5=_mt5, oms=_gw, feed=_gw)
                    # Heartbeat timeout must outlive the scheduler interval or
                    # age-based missing() falsely reports OMS/gateway stale
                    # between ticks (default interval 60s vs registry 30s).
                    ctrl.heartbeats.timeout_seconds = max(
                        float(ctrl.heartbeats.timeout_seconds),
                        float(self.interval_seconds) * 2.0 + 5.0,
                    )
                    self.reliability.heartbeats.timeout_seconds = max(
                        float(self.reliability.heartbeats.timeout_seconds),
                        float(self.interval_seconds) * 2.0 + 5.0,
                    )
                    self._continuous_ops_bound = True
                # Live pause inputs; never hardcode market/portfolio as always-ok
                oms_ok = _oms_submit_path_healthy(probes)
                if not oms_ok:
                    logger.warning(
                        "oms_heartbeat_unhealthy",
                        gateway_available=bool(probes.gateway_available),
                        mt5_connected=bool(probes.mt5_connected),
                        railway_api_up=bool(getattr(probes, "railway_api_up", False)),
                        note=(
                            "OMS heartbeat follows gateway submit path; "
                            "railway_api_up is reported separately"
                        ),
                    )
                market_open = True
                try:
                    from app.application.services.market_closed_cooldown import (
                        is_market_closed_cooled,
                    )
                    from app.domain.institutional_trading.ai_scalping.config import (
                        DEFAULT_SCALPING_UNIVERSE,
                    )

                    # If any universe symbol is in market-closed cooldown, pause entries
                    for sym in DEFAULT_SCALPING_UNIVERSE:
                        if is_market_closed_cooled(str(sym)):
                            market_open = False
                            break
                except Exception:
                    logger.exception("continuous_ops_market_open_probe_failed")
                    market_open = False  # fail closed

                portfolio_risk_exceeded = False
                try:
                    last_acct = getattr(self, "_last_account_risk", None)
                    if last_acct is not None:
                        from app.domain.institutional_trading.ai_scalping import (
                            aggregate_portfolio_risk,
                            check_portfolio_limits,
                        )

                        risk_snap = aggregate_portfolio_risk(
                            last_acct,
                            config=DEFAULT_AI_SCALPING_CONFIG,
                            ite_config=self.decision_pipeline.config,
                        )
                        blocked, _why = check_portfolio_limits(
                            open_positions=risk_snap.open_positions,
                            max_open_positions=risk_snap.max_open_positions,
                            daily_loss_pct=risk_snap.daily_loss_pct,
                            max_daily_loss_pct=risk_snap.max_daily_loss_pct,
                            exposure_pct=risk_snap.exposure_pct,
                            max_exposure_pct=risk_snap.max_exposure_pct,
                        )
                        portfolio_risk_exceeded = bool(blocked)
                except Exception:
                    logger.exception("continuous_ops_portfolio_risk_probe_failed")
                    portfolio_risk_exceeded = True  # fail closed

                snap = ctrl.tick(
                    gateway_ok=bool(probes.gateway_available),
                    mt5_ok=bool(probes.mt5_connected),
                    oms_ok=oms_ok,
                    feed_ok=bool(probes.gateway_available),
                    daily_loss_exceeded=bool(self.plane.daily_loss_exceeded),
                    broker_available=bool(probes.mt5_connected),
                    market_open=market_open,
                    portfolio_risk_exceeded=portfolio_risk_exceeded,
                )
                result["continuous_operation"] = snap.to_dict()
                self._last_continuous_op = snap.to_dict()
        except Exception:
            logger.exception("continuous_operation_tick_failed")
            # Fail closed: pause new entries until the next healthy tick.
            fail_closed = {
                "pause": {
                    "pause_new_entries": True,
                    "manage_open_positions": True,
                    "reasons": ["continuous_operation_tick_failed"],
                },
                "error": True,
            }
            self._last_continuous_op = fail_closed
            result["continuous_operation"] = fail_closed
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
        # Production Validation Mode — observe only (never changes decisions).
        _pvm_vid: str | None = None
        _pvm_token = None
        try:
            from app.domain.institutional_trading.production_validation_mode import (
                ensure_validation,
                get_production_validation_recorder,
            )

            session_hint = ""
            if snapshot is not None:
                sess = getattr(snapshot, "session", None)
                sess_v = getattr(sess, "session", None) if sess else None
                session_hint = str(getattr(sess_v, "value", None) or sess_v or "")
            _pvm_vid = ensure_validation(
                symbol=str(getattr(snapshot, "symbol", "") or "") if snapshot else "",
                market_session=session_hint,
                execution_mode=self.plane.mode.value,
            )
            if _pvm_vid:
                _pvm_token = get_production_validation_recorder().bind_context(_pvm_vid)
        except Exception:
            logger.exception("pvm_run_auto_cycle_begin_failed")

        health = self.tick_health()
        if self.plane.mode is OpsExecutionMode.SHADOW:
            try:
                if _pvm_token is not None:
                    from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                        get_production_validation_recorder as _pvm_rec,
                    )

                    _pvm_rec().unbind_context(_pvm_token)
            except Exception:
                logger.exception("pvm_unbind_shadow_handoff_failed")
            return self.run_shadow_cycle(snapshot=snapshot, account=account)

        live_probes: dict[str, Any] = {}
        if isinstance(health, dict):
            raw_probes = health.get("live_probes") or {}
            if isinstance(raw_probes, dict):
                live_probes = raw_probes
        # After a successful market-context build, callers pass gateway/broker=True.
        # Do not let a flaky live_probes False wipe that proven connectivity
        # (would SAFETY_BLOCK while bars/account already loaded).
        probe_gw = live_probes.get("gateway")
        probe_mt5 = live_probes.get("mt5")
        gw = bool(gateway_connected) or (
            bool(probe_gw) if probe_gw is not None else False
        )
        mt5 = bool(broker_connected) or (
            bool(probe_mt5) if probe_mt5 is not None else False
        )
        if gateway_connected and probe_gw is False:
            logger.warning(
                "live_probe_gateway_false_ignored",
                kwargs_gateway=gateway_connected,
                probe_gateway=probe_gw,
            )
        if broker_connected and probe_mt5 is False:
            logger.warning(
                "live_probe_mt5_false_ignored",
                kwargs_broker=broker_connected,
                probe_mt5=probe_mt5,
            )

        settings = get_settings()
        execution_on = bool(getattr(settings, "execution_enabled", False))
        adapter_exec = bool(getattr(self.mt5_adapter, "execution_enabled", False))
        if execution_on and not adapter_exec:
            logger.warning(
                "execution_enabled_settings_adapter_mismatch",
                settings_execution_enabled=execution_on,
                adapter_execution_enabled=adapter_exec,
                hint=(
                    "settings True but MT5Adapter live-send False — usually "
                    "missing MT5_GATEWAY_CALLER_TOKEN (MockMT5Client path)"
                ),
            )

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
            try:
                from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                    ValidationStage,
                    finalize as pvm_finalize,
                    stage as pvm_stage,
                )

                pvm_stage(
                    ValidationStage.CONTEXT,
                    ok=False,
                    reason=result.market_context_reason or "NO_SNAPSHOT",
                    validation_id=_pvm_vid,
                )
                pvm_finalize(validation_id=_pvm_vid)
            except Exception:
                logger.exception("pvm_no_snapshot_finalize_failed")
            finally:
                try:
                    if _pvm_token is not None:
                        from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                            get_production_validation_recorder as _pvm_rec2,
                        )

                        _pvm_rec2().unbind_context(_pvm_token)
                except Exception:
                    logger.exception("pvm_unbind_no_snapshot_failed")
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
                        symbol=str(getattr(snapshot, "symbol", "XAUUSD") or "XAUUSD"),
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
                # Entry blocked (max-open / paused / session / etc.) — still manage
                # open MT5 positions so exits free the slot for continuous scalping.
                try:
                    self._sync_and_manage_open_positions(
                        snapshot=snapshot,
                        account=account,
                        reason="safety_blocked_manage",
                    )
                except Exception:
                    logger.exception("safety_blocked_manage_failed")
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
                logger.warning(
                    "execution_path_step",
                    step="Safety",
                    result="FAIL",
                    abort_reason="SAFETY_BLOCKED",
                    primary_blocker=(
                        safety.failed_reasons[0] if safety.failed_reasons else None
                    ),
                    reasons=list(result.safety_failed_reasons),
                    gateway=gw,
                    broker=mt5,
                    execution_enabled=execution_on,
                    mt5_autotrading_enabled=mt5_autotrading_enabled,
                    forwarded_to_oms=False,
                )
                logger.info(
                    "ite_cycle_outcome",
                    outcome=result.cycle_outcome,
                    reasons=list(result.safety_failed_reasons),
                    mode=result.mode,
                    pme_positions=len(
                        getattr(self.position_management.engine, "_positions", {}) or {}
                    ),
                )
                try:
                    from app.application.services.strategy_diagnostics import (
                        get_strategy_diagnostics_store,
                    )

                    get_strategy_diagnostics_store().record_from_artefacts(
                        snapshot=snapshot,
                        decision=None,
                        cycle_outcome="safety_blocked",
                        decision_action="NO_TRADE",
                        abort_reason="SAFETY_BLOCKED",
                        decision_reasons=tuple(safety.failed_reasons),
                        market_context_diagnostics=None,
                        signal_id=None,
                        forwarded_to_oms=False,
                        trace_id=None,
                    )
                except Exception:
                    logger.exception("strategy_diagnostics_safety_blocked_failed")
                try:
                    from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                        ValidationStage,
                        capture_signal as pvm_capture,
                        finalize as pvm_finalize,
                        stage as pvm_stage,
                    )
                    from app.domain.institutional_trading.production_validation_mode.recorder import (  # noqa: E501
                        get_production_validation_recorder as _pvm_get,
                    )

                    pvm_capture(
                        snapshot=snapshot,
                        execution_mode=self.plane.mode.value,
                        validation_id=_pvm_vid,
                    )
                    blocker = (
                        safety.failed_reasons[0]
                        if safety.failed_reasons
                        else "SAFETY_BLOCKED"
                    )
                    pvm_stage(
                        ValidationStage.ELIGIBILITY,
                        ok=False,
                        reason=str(blocker),
                        validation_id=_pvm_vid,
                    )
                    _pvm_get().record_no_trade_reasons(
                        list(safety.failed_reasons),
                        validation_id=_pvm_vid,
                    )
                    pvm_finalize(validation_id=_pvm_vid)
                except Exception:
                    logger.exception("pvm_safety_blocked_finalize_failed")
                finally:
                    try:
                        if _pvm_token is not None:
                            from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                                get_production_validation_recorder as _pvm_rec3,
                            )

                            _pvm_rec3().unbind_context(_pvm_token)
                    except Exception:
                        logger.exception("pvm_unbind_safety_blocked_failed")
                return result
            logger.warning(
                "FORCE_FIRST_TRADE proceeding despite safety blockers: %s",
                "; ".join(safety.failed_reasons) or "unknown",
            )

        try:
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
        finally:
            try:
                if _pvm_token is not None:
                    from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                        get_production_validation_recorder as _pvm_rec4,
                    )

                    _pvm_rec4().unbind_context(_pvm_token)
            except Exception:
                logger.exception("pvm_unbind_run_auto_cycle_failed")

    def _sync_and_manage_open_positions(
        self,
        *,
        snapshot: Any,
        account: AccountRiskState,
        reason: str = "cycle",
    ) -> int:
        """Upsert live MT5 fills into PME, then evaluate each managed ticket.

        Never opens trades. Required for continuous scalping: without this,
        fills sit unmanaged, max-open never clears, and the loop stalls.
        """
        symbol = str(getattr(snapshot, "symbol", "XAUUSD") or "XAUUSD")
        engine = self.position_management.engine
        try:
            from app.domain.institutional_trading.production_hardening.position_recovery import (  # noqa: E501
                recover_positions_from_mt5,
            )

            if self.mt5_adapter is not None:
                recovery = recover_positions_from_mt5(
                    mt5_adapter=self.mt5_adapter,
                    engine=engine,
                    symbol=symbol,
                )
                if int(recovery.get("registered") or 0) > 0:
                    logger.warning(
                        "Position Opened — PME registered from MT5",
                        registered=recovery.get("registered"),
                        mt5_positions=recovery.get("mt5_positions"),
                        tickets=recovery.get("tickets"),
                        reason=reason,
                    )
                    try:
                        from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                            ValidationStage,
                            stage as pvm_stage,
                        )

                        pvm_stage(
                            ValidationStage.POSITION_OPEN,
                            ok=True,
                            reason=(
                                f"registered={recovery.get('registered')} "
                                f"tickets={recovery.get('tickets')}"
                            ),
                        )
                    except Exception:
                        logger.exception("pvm_position_open_stage_failed")
        except Exception:
            logger.exception("pme_recover_before_manage_failed", reason=reason)

        # Per-ticket live mid from MT5 — never manage gold with EURUSD mid.
        live_by_ticket: dict[int, Any] = {}
        try:
            if self.mt5_adapter is not None and hasattr(
                self.mt5_adapter, "list_positions"
            ):
                for row in list(self.mt5_adapter.list_positions() or []):
                    try:
                        t = int(getattr(row, "ticket", 0) or 0)
                    except (TypeError, ValueError):
                        t = 0
                    if t > 0:
                        live_by_ticket[t] = row
        except Exception:
            logger.exception("pme_live_positions_for_manage_failed")

        managed = 0
        for ticket in list(getattr(engine, "_positions", {}).keys()):
            pos = engine.get(ticket)
            if pos is None:
                continue
            live = live_by_ticket.get(int(ticket))
            live_px = None
            if live is not None:
                try:
                    live_px = Decimal(str(getattr(live, "current_price", 0) or 0))
                except Exception:
                    live_px = None
            fallback_mid = account.mid_price or Decimal("0")
            # Prefer broker mark for THIS ticket; only fall back to account mid
            # when it is same-symbol scale (avoid 1.15 mid on a 4060 gold book).
            current_px = live_px if live_px and live_px > 0 else fallback_mid
            if current_px <= 0:
                current_px = Decimal(str(getattr(pos, "entry_price", 0) or 0)) or Decimal(
                    "1"
                )
            # Empty book ⇒ ambiguous (gateway blip); never force local EXIT.
            # Non-empty book without this ticket ⇒ truly closed on MT5.
            pos_still_open = True if not live_by_ticket else (live is not None)
            book_vol = None
            book_sl = None
            if live is not None:
                try:
                    book_vol = Decimal(str(getattr(live, "volume", 0) or 0))
                except Exception:
                    book_vol = None
                try:
                    book_sl = Decimal(
                        str(
                            getattr(live, "stop_loss", 0)
                            or getattr(live, "sl", 0)
                            or 0
                        )
                    )
                    if book_sl <= 0:
                        book_sl = None
                except Exception:
                    book_sl = None
            pctx = PositionManageContext(
                now=datetime.now(UTC),
                current_price=current_px,
                atr=account.atr or Decimal("1"),
                mid_price=current_px,
                spread=getattr(snapshot, "spread", None),
                market_open=True,
                position_still_open=pos_still_open,
                book_volume=book_vol,
                book_stop=book_sl,
                kill_switch_armed=self.plane.kill_switch_armed,
                daily_loss_exceeded=self.plane.daily_loss_exceeded,
                user_id=self.user_id,
                market_session=str(
                    getattr(
                        getattr(getattr(snapshot, "session", None), "session", None),
                        "value",
                        None,
                    )
                    or getattr(getattr(snapshot, "session", None), "session", None)
                    or ""
                )
                or None,
            )
            result = self.position_management.evaluate(ticket, pctx)
            managed += 1
            try:
                from app.domain.institutional_trading.ai_scalping.institutional_position_monitor import (  # noqa: E501
                    build_position_monitor,
                )
                from app.domain.institutional_trading.ai_scalping.trade_lifecycle_timeline import (  # noqa: E501
                    get_trade_lifecycle_store,
                )
                from app.domain.institutional_trading.management.r_math import signed_r

                build_position_monitor(
                    getattr(engine, "_positions", {}),
                    mid_price=float(current_px),
                    atr=float(account.atr)
                    if getattr(account, "atr", None) is not None
                    else None,
                    market_session=str(getattr(pctx, "market_session", "") or "")
                    or None,
                )
                get_trade_lifecycle_store().mark(
                    f"pos_{ticket}",
                    "MANAGED",
                    ok=True,
                    reason=str(
                        getattr(
                            getattr(result, "action", None),
                            "value",
                            getattr(result, "action", ""),
                        )
                        or "manage"
                    ),
                )
                r_now = signed_r(pos, current_px)
                be_at = getattr(
                    getattr(self.position_management.engine, "config", None),
                    "break_even_at_r",
                    None,
                )
                logger.warning(
                    "PME Active",
                    ticket=ticket,
                    symbol=getattr(pos, "symbol", ""),
                    side=getattr(pos, "side", ""),
                    mid=str(current_px),
                    entry=str(getattr(pos, "entry_price", "")),
                    risk_distance=str(getattr(pos, "risk_distance", "")),
                    r=str(r_now),
                    break_even_at_r=str(be_at),
                    be_moved=bool(getattr(pos, "be_moved", False)),
                    state=str(
                        getattr(getattr(pos, "state", None), "value", getattr(pos, "state", ""))
                    ),
                    still_open=pos_still_open,
                )
            except Exception:
                logger.exception("position_monitor_update_failed")
            try:
                action_v = getattr(
                    getattr(result, "action", None),
                    "value",
                    getattr(result, "action", None),
                )
                if action_v and str(action_v).lower() not in {"skip", "none", ""}:
                    logger.warning(
                        "Position Managed",
                        ticket=ticket,
                        action=str(action_v),
                        reason=reason,
                        mid=str(current_px),
                    )
                to_state = getattr(getattr(result, "record", None), "to_state", None)
                to_v = getattr(to_state, "value", to_state)
                pos_state = getattr(getattr(result, "position", None), "state", None)
                pos_v = getattr(pos_state, "value", pos_state)
                if str(to_v or pos_v or "").lower() in {"exited", "closed"}:
                    logger.warning(
                        "Position Closed",
                        ticket=ticket,
                        reason=reason,
                        exit_reason=getattr(
                            getattr(result, "record", None), "reason", ""
                        ),
                    )
                    try:
                        from app.domain.institutional_trading.ai_scalping.trade_lifecycle_timeline import (  # noqa: E501
                            get_trade_lifecycle_store,
                        )

                        _cr = str(
                            getattr(getattr(result, "record", None), "reason", "")
                            or reason
                            or "closed"
                        )
                        get_trade_lifecycle_store().mark(
                            f"pos_{ticket}",
                            "CLOSED",
                            ok=True,
                            reason=_cr,
                        )
                        get_trade_lifecycle_store().mark(
                            f"pos_{ticket}",
                            "ARCHIVED",
                            ok=True,
                            reason=_cr,
                        )
                    except Exception:
                        logger.exception("lifecycle_close_mark_failed")
                    try:
                        from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                            ValidationStage,
                            stage as pvm_stage,
                        )

                        _close_record = getattr(result, "record", None)
                        _close_reason = getattr(_close_record, "reason", "")
                        pvm_stage(
                            ValidationStage.POSITION_CLOSE,
                            ok=True,
                            reason=f"ticket={ticket} exit={_close_reason}",
                        )
                    except Exception:
                        logger.exception("pvm_position_close_stage_failed")
                    try:
                        from app.domain.institutional_trading.ai_scalping.decision_explain import (  # noqa: E501
                            explain_decision,
                        )
                        from app.domain.institutional_trading.ai_scalping.learning import (  # noqa: E501
                            LearningTradeRecord,
                            get_scalping_learning_store,
                        )

                        ai = getattr(self.decision_pipeline, "_last_ai_score", None)
                        ai_d = ai if isinstance(ai, dict) else {}
                        pnl_raw = getattr(pos, "profit", None)
                        try:
                            pnl_f = float(pnl_raw) if pnl_raw is not None else 0.0
                        except Exception:
                            pnl_f = 0.0
                        direction = str(
                            getattr(getattr(pos, "direction", None), "value", None)
                            or getattr(pos, "side", None)
                            or ai_d.get("direction")
                            or ""
                        )
                        explain = explain_decision(
                            direction=direction,
                            manage_action="close",
                            manage_reason=str(_close_reason or reason or "closed"),
                        )
                        logger.warning(
                            "AI Decision Explained",
                            action=explain.get("action"),
                            why=explain.get("why"),
                            ticket=ticket,
                        )
                        trade_rec = LearningTradeRecord(
                                closed_at=datetime.now(UTC).isoformat(),
                                symbol=str(
                                    getattr(pos, "symbol", None)
                                    or getattr(snapshot, "symbol", "")
                                    or "XAUUSD"
                                ),
                                direction=direction,
                                session=str(
                                    getattr(
                                        getattr(
                                            getattr(snapshot, "session", None),
                                            "session",
                                            None,
                                        ),
                                        "value",
                                        None,
                                    )
                                    or getattr(
                                        getattr(snapshot, "session", None),
                                        "session",
                                        "",
                                    )
                                    or ""
                                ),
                                win=pnl_f > 0,
                                pnl=str(pnl_raw if pnl_raw is not None else "0"),
                                confidence=int(
                                    ai_d.get("ai_confidence")
                                    or ai_d.get("confidence")
                                    or 0
                                ),
                                quality=int(
                                    ai_d.get("trade_quality")
                                    or ai_d.get("quality")
                                    or 0
                                ),
                                confluence=int(ai_d.get("confluence") or 0),
                                spread=(
                                    str(getattr(snapshot, "spread", None))
                                    if getattr(snapshot, "spread", None) is not None
                                    else None
                                ),
                                atr_pct=(
                                    str(ai_d.get("atr_pct"))
                                    if ai_d.get("atr_pct") is not None
                                    else None
                                ),
                                regime=ai_d.get("market_regime") or ai_d.get("regime"),
                                execution_ms=None,
                                ticket=str(ticket),
                                entry_reason=ai_d.get("entry_reason")
                                or (
                                    "; ".join(ai_d.get("reasons") or [])
                                    if isinstance(ai_d.get("reasons"), list)
                                    else None
                                ),
                                exit_reason=str(_close_reason or reason or "closed"),
                                rejection_reason=ai_d.get("reject_reason"),
                                setup_family=ai_d.get("setup_family"),
                                holding_time_minutes=(
                                    float(getattr(pos, "holding_time_minutes", None))
                                    if getattr(pos, "holding_time_minutes", None)
                                    is not None
                                    else None
                                ),
                                r_multiple=(
                                    str(getattr(pos, "r_multiple", None))
                                    if getattr(pos, "r_multiple", None) is not None
                                    else None
                                ),
                                indicators={
                                    "explain": explain,
                                    "management_reason": reason,
                                    "mtf": ai_d.get("mtf_alignment")
                                    or ai_d.get("mtf"),
                                    "liquidity": ai_d.get("liquidity"),
                                },
                            )
                        get_scalping_learning_store().record(trade_rec)
                        # AI v8 — append-only observation (never auto-applies)
                        try:
                            from app.domain.institutional_trading.ai_scalping.institutional_learning_engine import (  # noqa: E501
                                observe_from_learning_trade,
                            )

                            observe_from_learning_trade(
                                trade_rec,
                                management_phase=str(reason or "closed"),
                                liquidity=(
                                    float(ai_d["liquidity"])
                                    if ai_d.get("liquidity") is not None
                                    else None
                                ),
                                mtf=(
                                    int(
                                        ai_d.get("mtf_alignment")
                                        or ai_d.get("mtf")
                                        or 0
                                    )
                                    or None
                                ),
                                extras={"auto_applies": False, "ai_version": "v8"},
                            )
                        except Exception:
                            logger.exception("institutional_learning_observe_failed")
                    except Exception:
                        logger.exception("ai_scalping_learning_record_failed")
                    try:
                        from app.domain.institutional_trading.ai_scalping.config import (  # noqa: E501
                            DEFAULT_AI_SCALPING_CONFIG,
                        )
                        from app.domain.institutional_trading.ai_scalping.continuous_operation import (  # noqa: E501
                            get_continuous_operation_controller,
                        )

                        if DEFAULT_AI_SCALPING_CONFIG.post_close_rescan_enabled:
                            get_continuous_operation_controller(
                                DEFAULT_AI_SCALPING_CONFIG
                            ).request_rescan_after_close()
                    except Exception:
                        logger.exception("post_close_rescan_flag_failed")
            except Exception:
                logger.exception("pme_manage_log_failed", ticket=ticket)

        try:
            from app.domain.institutional_trading.production_hardening.position_recovery import (  # noqa: E501
                persist_pme_state,
            )

            persist_pme_state(engine)
            from app.domain.institutional_trading.production_hardening.observe import (
                record_lifecycle,
            )

            if getattr(engine, "_positions", None):
                record_lifecycle(
                    stage="POSITION_MONITOR",
                    status="ok",
                    detail=f"managed={len(engine._positions)} reason={reason}",
                )
        except Exception:
            logger.exception("hardening_pme_persist_failed", reason=reason)
        return managed

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
        risk_allowed: bool = True,  # noqa: ARG002
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
        try:  # noqa: SIM105
            # Cache for continuous-ops portfolio pause probes on health ticks
            self._last_account_risk = account
        except Exception:  # noqa: S110
            pass
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

        live_positions: list[Any] = []
        try:
            if self.mt5_adapter is not None and hasattr(
                self.mt5_adapter, "list_positions"
            ):
                live_positions = list(self.mt5_adapter.list_positions() or [])
        except Exception:
            logger.exception("ite_runtime_list_positions_for_pre_failed")
            live_positions = []

        decision = self.decision_pipeline.run(
            snapshot, account, positions=live_positions or None
        )
        try:
            from app.domain.institutional_trading.production_validation_mode import (
                ValidationStage,
                capture_signal as pvm_capture,
                ensure_validation,
                stage as pvm_stage,
            )

            ensure_validation(
                symbol=str(getattr(snapshot, "symbol", "") or ""),
                execution_mode=(
                    OpsExecutionMode.SHADOW.value
                    if force_shadow
                    else self.plane.mode.value
                ),
            )
            pvm_capture(
                snapshot=snapshot,
                decision=decision,
                execution_mode=(
                    OpsExecutionMode.SHADOW.value
                    if force_shadow
                    else self.plane.mode.value
                ),
            )
            pvm_stage(
                ValidationStage.CONTEXT,
                ok=True,
                reason="snapshot+account present",
            )
        except Exception:
            logger.exception("pvm_pre_decision_capture_failed")
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

        # v7.1 continuous ops — pause NEW entries only; keep managing open book
        try:
            from dataclasses import replace as _dc_replace
            from decimal import Decimal as _Dec

            from app.domain.institutional_trading.ai_scalping.config import (
                DEFAULT_AI_SCALPING_CONFIG as _scalp_cfg,
            )
            from app.domain.institutional_trading.ai_scalping.continuous_operation import (  # noqa: E501
                get_continuous_operation_controller as _get_co,
            )
            from app.domain.institutional_trading.decision_models import (
                DecisionAction as _DA,
                EligibilityResult as _Elig,
                TradeDirection as _TD,
            )

            if _scalp_cfg.continuous_operation_enabled:
                ctrl = _get_co(_scalp_cfg)
                # After close: clear entry spacing so a NEW valid setup can scan
                if _scalp_cfg.post_close_rescan_enabled and ctrl.consume_rescan():
                    try:
                        from app.domain.institutional_trading.ai_scalping.adaptive_cooldown import (  # noqa: E501
                            get_adaptive_cooldown_gate,
                        )

                        get_adaptive_cooldown_gate().clear_for_post_close_rescan()
                    except Exception:
                        logger.exception("post_close_cooldown_clear_failed")
                co = getattr(self, "_last_continuous_op", None)
                pause = (co or {}).get("pause") if isinstance(co, dict) else None
                if not isinstance(pause, dict):
                    market_open = True
                    try:
                        from app.application.services.market_closed_cooldown import (
                            is_market_closed_cooled,
                        )

                        sym = str(
                            getattr(snapshot, "symbol", "")
                            or getattr(decision, "symbol", "")
                            or ""
                        )
                        if sym and is_market_closed_cooled(sym):
                            market_open = False
                    except Exception:
                        logger.exception("entry_pause_market_open_probe_failed")
                        market_open = False  # fail closed

                    portfolio_risk_exceeded = False
                    try:
                        from app.domain.institutional_trading.ai_scalping import (
                            aggregate_portfolio_risk,
                            check_portfolio_limits,
                        )

                        risk_snap = aggregate_portfolio_risk(
                            account,
                            config=_scalp_cfg,
                            ite_config=self.decision_pipeline.config,
                        )
                        blocked, _why = check_portfolio_limits(
                            open_positions=risk_snap.open_positions,
                            max_open_positions=risk_snap.max_open_positions,
                            daily_loss_pct=risk_snap.daily_loss_pct,
                            max_daily_loss_pct=risk_snap.max_daily_loss_pct,
                            exposure_pct=risk_snap.exposure_pct,
                            max_exposure_pct=risk_snap.max_exposure_pct,
                        )
                        portfolio_risk_exceeded = bool(blocked)
                    except Exception:
                        logger.exception("entry_pause_portfolio_risk_probe_failed")
                        portfolio_risk_exceeded = True  # fail closed

                    pause = ctrl.evaluate_new_entry_pause(
                        daily_loss_exceeded=bool(self.plane.daily_loss_exceeded),
                        broker_available=bool(broker_connected),
                        gateway_available=bool(gateway_connected),
                        market_open=market_open,
                        portfolio_risk_exceeded=portfolio_risk_exceeded,
                    ).to_dict()
                if pause.get("pause_new_entries") and decision.action in {
                    _DA.BUY,
                    _DA.SELL,
                }:
                    why = tuple(str(r) for r in (pause.get("reasons") or ()))
                    decision = _dc_replace(
                        decision,
                        action=_DA.NO_TRADE,
                        direction=_TD.NONE,
                        reasons=(
                            *decision.reasons,
                            "continuous_ops_pause_new_entries",
                            *why,
                        ),
                        eligibility=_Elig(
                            eligible=False,
                            checks={
                                **dict(decision.eligibility.checks),
                                "continuous_ops_new_entries": False,
                            },
                            rejection_reasons=(
                                *decision.eligibility.rejection_reasons,
                                "continuous_ops_pause_new_entries",
                                *why,
                            ),
                        ),
                        approved_lots=_Dec("0"),
                    )
                    logger.warning(
                        "continuous_ops_pause_new_entries",
                        reasons=list(why),
                        manage_open=True,
                    )
        except Exception:
            logger.exception("continuous_ops_entry_pause_failed")
            # Fail closed: never allow new entries when pause evaluation breaks
            try:
                from dataclasses import replace as _dc_replace_fc
                from decimal import Decimal as _Dec_fc

                from app.domain.institutional_trading.decision_models import (
                    DecisionAction as _DA_fc,
                    EligibilityResult as _Elig_fc,
                    TradeDirection as _TD_fc,
                )

                if decision.action in {_DA_fc.BUY, _DA_fc.SELL}:
                    decision = _dc_replace_fc(
                        decision,
                        action=_DA_fc.NO_TRADE,
                        direction=_TD_fc.NONE,
                        reasons=(*decision.reasons, "continuous_ops_pause_eval_failed"),
                        eligibility=_Elig_fc(
                            eligible=False,
                            checks={
                                **dict(decision.eligibility.checks),
                                "continuous_ops_new_entries": False,
                            },
                            rejection_reasons=(
                                *decision.eligibility.rejection_reasons,
                                "continuous_ops_pause_eval_failed",
                            ),
                        ),
                        approved_lots=_Dec_fc("0"),
                    )
            except Exception:
                logger.exception("continuous_ops_fail_closed_demote_failed")

        with self._lock:
            self._last_decision = decision

        # v7 Shadow AI — independent evaluation; primary engine remains default
        try:
            from app.domain.institutional_trading.ai_validation import (
                run_shadow_validation,
            )

            run_shadow_validation(decision=decision, snapshot=snapshot, trace_id=tid)
        except Exception:
            logger.exception("shadow_ai_validation_failed")

        # v8 Champion vs Challenger — challenger never executes
        try:
            from app.domain.institutional_trading.performance_lab import (
                get_opportunity_outcome_store,
                run_champion_challenger,
            )

            duel = run_champion_challenger(
                decision=decision, snapshot=snapshot, trace_id=tid
            )
            action = str(getattr(decision.action, "value", decision.action))
            traded_intent = action in {"BUY", "SELL"}
            get_opportunity_outcome_store().record_evaluation(
                symbol=str(
                    getattr(decision, "symbol", "") or getattr(snapshot, "symbol", "")
                ),
                ai_confidence=int(getattr(decision, "confidence", 0) or 0),
                opportunity_score=int(
                    (duel.champion.get("opportunity_score") if duel else None)
                    or getattr(decision, "confidence", 0)
                    or 0
                ),
                traded=False,  # filled true after OMS success below
                skip_reason=None if traded_intent else f"action={action}",
                session=(duel.session if duel else None),
                regime=(duel.regime if duel else None),
                strategy=str(getattr(self.plane, "trading_mode", "swing") or "swing"),
                direction=str(
                    getattr(getattr(decision, "direction", None), "value", "") or ""
                ),
                expected_rr=(
                    float(getattr(decision, "estimated_rr", 0) or 0)
                    if getattr(decision, "estimated_rr", None) is not None
                    else None
                ),
                spread=(
                    float(snapshot.spread)
                    if getattr(snapshot, "spread", None) is not None
                    else None
                ),
            )
        except Exception:
            logger.exception("performance_lab_duel_failed")

        # v9 Portfolio Intelligence — portfolio-aware queue/protection (no auto-reallocate)  # noqa: E501
        try:
            from app.domain.institutional_trading.portfolio_intelligence import (
                build_portfolio_state,
                evaluate_capital_protection,
                get_dynamic_risk_budget,
                get_opportunity_queue,
            )

            open_syms = [
                str(getattr(p, "symbol", "") or "")
                for p in self.position_management.engine._positions.values()
            ]
            st = build_portfolio_state(
                equity=float(account.equity or 0),
                free_margin=(
                    float(account.free_margin or 0)
                    if getattr(account, "free_margin", None) is not None
                    else None
                ),
                open_symbols=open_syms,
                daily_pnl=float(account.daily_pnl or 0),
                weekly_pnl=float(account.weekly_pnl or 0),
                current_drawdown_pct=(
                    float(abs(account.daily_pnl) / account.equity * 100)
                    if account.equity and account.daily_pnl < 0
                    else 0.0
                ),
            )
            budget = get_dynamic_risk_budget().budget_for_state(st)
            prot = evaluate_capital_protection(
                st, candidate_symbol=str(getattr(decision, "symbol", "") or "")
            )
            get_opportunity_queue().rebuild(
                [
                    {
                        "symbol": getattr(decision, "symbol", ""),
                        "direction": str(
                            getattr(getattr(decision, "direction", None), "value", "")
                        ),
                        "opportunity_score": int(
                            getattr(decision, "confidence", 0) or 0
                        ),
                        "ai_confidence": int(getattr(decision, "confidence", 0) or 0),
                        "expected_rr": float(getattr(decision, "estimated_rr", 0) or 0),
                    }
                ],
                st,
                risk_budget_pct=float(budget["risk_budget_pct"]),
            )
            if not prot.allow_new_exposure:
                logger.warning(
                    "portfolio_capital_protection_block_new",
                    reasons=list(prot.reasons),
                    scale=prot.new_exposure_scale,
                )
            elif prot.new_exposure_scale < 1.0:
                logger.warning(
                    "portfolio_capital_protection_scale",
                    scale=prot.new_exposure_scale,
                    reasons=list(prot.reasons),
                )
        except Exception:
            logger.exception("portfolio_intelligence_cycle_failed")

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
                detail=f"action={decision.action.value} conf={getattr(decision, 'confidence', '')}",  # noqa: E501
                trace_id=tid,
                symbol=str(
                    getattr(decision, "symbol", "") or getattr(snapshot, "symbol", "")
                ),
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

        # Production Validation Mode — AI / Risk / Eligibility + every NO_TRADE reason.
        try:
            from app.domain.institutional_trading.production_validation_mode import (
                ValidationStage,
                capture_signal as pvm_capture,
                record_decision_reasons as pvm_reasons,
                stage as pvm_stage,
            )

            pvm_capture(snapshot=snapshot, decision=decision)
            action_s = str(getattr(decision.action, "value", decision.action) or "")
            ai_ok = action_s in {"BUY", "SELL"}
            pvm_stage(
                ValidationStage.AI,
                ok=ai_ok,
                reason=(
                    f"action={action_s} conf={getattr(decision, 'confidence', '')}"
                    if ai_ok
                    else (
                        "; ".join(decision_reasons)
                        or f"action={action_s} (not BUY/SELL)"
                    )
                ),
                latency_ms=(time.perf_counter() - t0) * 1000.0,
            )
            risk_ok = bool(decision.eligibility.checks.get("risk_available", True))
            risk_reason = "; ".join(decision.risk_reasons or risk_reasons or ())
            pvm_stage(
                ValidationStage.RISK,
                ok=risk_ok,
                reason=risk_reason or ("risk ok" if risk_ok else "risk rejected"),
            )
            pvm_stage(
                ValidationStage.ELIGIBILITY,
                ok=bool(decision.eligibility.eligible),
                reason=(
                    "; ".join(decision.eligibility.rejection_reasons)
                    or ("eligible" if decision.eligibility.eligible else "not eligible")
                ),
            )
            pvm_reasons(decision)
        except Exception:
            logger.exception("pvm_decision_stages_failed")

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
                else bool(decision.eligibility.checks.get("risk_available", False))
            ),
            risk_reasons=(
                ()
                if forced_override
                else tuple(decision.risk_reasons or risk_reasons or ())
            ),
            connected=broker_connected or force_shadow,
            login=None,
            request_id=f"{'shadow' if force_shadow else 'auto'}_{tid[:12]}",
            gateway_connected=True if force_shadow else gateway_connected,
            broker_connected=True if force_shadow else broker_connected,
            market_data_live=True if force_shadow else market_data_live,
            account_trading_enabled=(True if force_shadow else account_trading_enabled),
            mt5_autotrading_enabled=(True if force_shadow else mt5_autotrading_enabled),
            symbol_tradable=True if force_shadow else symbol_tradable,
            no_broker_restrictions=True if force_shadow else no_broker_restrictions,
        )
        if self._manual_execution:
            logger.warning(
                "Submitting Order...",
                action=str(getattr(decision.action, "value", decision.action)),
                direction=str(getattr(decision.direction, "value", decision.direction)),
                lots=str(getattr(decision, "approved_lots", None) or ""),
            )

        # --- Execution Intelligence: optimizer + SOR (pre-OMS, never changes AI) ---
        defer_submit = False
        optimizer_payload: dict[str, Any] | None = None
        sor_payload: dict[str, Any] | None = None
        action_for_exec = str(
            getattr(decision.action, "value", decision.action) or ""
        ).upper()
        try:
            from app.domain.institutional_trading.ai_scalping.execution_optimizer import (
                clear_optimizer_defers,
                evaluate_execution_moment,
            )
            from app.domain.institutional_trading.ai_scalping.smart_order_routing import (
                estimate_smart_routing,
            )
            from app.domain.institutional_trading.ai_scalping.trade_lifecycle_timeline import (  # noqa: E501
                get_trade_lifecycle_store,
            )

            lc = get_trade_lifecycle_store()
            lc.begin(
                lifecycle_id=tid,
                symbol=str(
                    getattr(decision, "symbol", "") or getattr(snapshot, "symbol", "")
                ),
                direction=str(
                    getattr(getattr(decision, "direction", None), "value", None)
                    or getattr(decision, "direction", None)
                    or ""
                ),
            )
            if action_for_exec in {"BUY", "SELL"}:
                lc.mark(tid, "AI_APPROVED", ok=True, reason=action_for_exec)
            if bool(decision.eligibility.eligible):
                lc.mark(tid, "RISK_APPROVED", ok=True)
                lc.mark(tid, "PRE_APPROVED", ok=True, reason="eligibility_passed")
            else:
                lc.mark(
                    tid,
                    "RISK_APPROVED",
                    ok=False,
                    reason=";".join(decision.eligibility.rejection_reasons) or "ineligible",
                )

            if (
                action_for_exec in {"BUY", "SELL"}
                and bool(decision.eligibility.eligible)
                and not forced_override
                and not force_shadow
            ):
                optimizer_payload = evaluate_execution_moment(
                    symbol=str(getattr(decision, "symbol", "") or ""),
                    decision=decision,
                    snapshot=snapshot,
                    account=account,
                    decision_key=(
                        f"{str(getattr(decision, 'symbol', '') or '').upper()}"
                        f":{action_for_exec}"
                    ),
                )
                sor_payload = estimate_smart_routing(
                    symbol=str(getattr(decision, "symbol", "") or ""),
                    side=action_for_exec,
                    spread=getattr(snapshot, "spread", None),
                    optimizer=optimizer_payload,
                )
                rec = str(optimizer_payload.get("recommendation") or "")
                if rec == "DEFER_TICK" or (
                    sor_payload.get("recommendation") == "WAIT_BETTER_TICK"
                    and rec != "PROCEED_DEGRADED"
                    and rec != "PROCEED"
                ):
                    # Soft defer only when optimizer agrees to wait within limits
                    if rec == "DEFER_TICK":
                        defer_submit = True
                        logger.warning(
                            "execution_optimizer_defer_tick",
                            symbol=optimizer_payload.get("symbol"),
                            score=optimizer_payload.get("execution_quality_score"),
                            reason=optimizer_payload.get("reason"),
                            defer_count=optimizer_payload.get("defer_count"),
                        )
                elif rec in {"PROCEED", "PROCEED_DEGRADED"}:
                    clear_optimizer_defers(
                        f"{str(getattr(decision, 'symbol', '') or '').upper()}"
                        f":{action_for_exec}"
                    )
            if isinstance(market_context_diagnostics, dict):
                if optimizer_payload:
                    market_context_diagnostics["execution_optimizer"] = (
                        optimizer_payload
                    )
                if sor_payload:
                    market_context_diagnostics["smart_order_routing"] = sor_payload
        except Exception:
            logger.exception("execution_intelligence_pre_oms_failed")

        if defer_submit:
            try:
                self._sync_and_manage_open_positions(
                    snapshot=snapshot,
                    account=account,
                    reason="execution_optimizer_defer_manage",
                )
            except Exception:
                logger.exception("execution_optimizer_defer_manage_failed")
            detail = (
                f"execution_optimizer_defer:"
                f"{(optimizer_payload or {}).get('reason') or 'await_better_tick'}"
            )
            result = ShadowCycleResult(
                ok=True,
                trace_id=tid,
                mode=self.plane.mode.value,
                decision_action=decision.action.value,
                forwarded_to_oms=False,
                detail=detail,
                health=health.get("health") if isinstance(health, dict) else None,
                cycle_outcome="execution_deferred",
                abort_reason="EXECUTION_OPTIMIZER_DEFER",
                decision_reasons=decision_reasons,
                snapshot_present=True,
                market_context_diagnostics=(
                    dict(market_context_diagnostics)
                    if market_context_diagnostics
                    else None
                ),
                signal_id=str(getattr(decision, "id", "") or "") or None,
            )
            with self._lock:
                self._last_cycle = result
                self._last_decision = decision
                self._cycles += 1
            return result

        bridge_result = self.execution.bridge.handle(decision, ctx, trace_id=tid)
        with self._lock:
            self._last_bridge_result = bridge_result
        try:
            from app.domain.institutional_trading.production_validation_mode import (
                ValidationStage,
                record_oms as pvm_oms,
                stage as pvm_stage,
            )

            forwarded = bool(getattr(bridge_result, "forwarded_to_oms", False))
            abort = getattr(bridge_result, "abort_reason", None)
            abort_val = str(getattr(abort, "value", abort) or "")
            oms = getattr(bridge_result, "oms_result", None)
            # Bridge PASS when BUY/SELL reached OMS, or intentional ignore of NO_TRADE.
            action_s = str(getattr(decision.action, "value", decision.action) or "")
            if action_s in {"BUY", "SELL"}:
                bridge_ok = forwarded and not bool(
                    getattr(bridge_result, "aborted", False)
                )
                pvm_stage(
                    ValidationStage.EXECUTION_BRIDGE,
                    ok=bridge_ok,
                    reason=(
                        "forwarded_to_oms"
                        if forwarded
                        else (abort_val or "bridge aborted")
                    ),
                    latency_ms=float(getattr(bridge_result, "latency_ms", 0) or 0)
                    or None,
                )
                if oms is not None:
                    outcome = str(getattr(oms, "outcome", "") or "").lower()
                    oms_ok = outcome in {"success", "filled", "done"}
                    pvm_stage(
                        ValidationStage.OMS,
                        ok=oms_ok,
                        reason=str(getattr(oms, "message", "") or outcome or "oms"),
                        latency_ms=float(getattr(oms, "latency_ms", 0) or 0) or None,
                    )
                    pvm_oms(
                        response={
                            "outcome": outcome,
                            "message": getattr(oms, "message", None),
                            "retcode": getattr(oms, "retcode", None),
                            "order_ticket": getattr(oms, "order_ticket", None),
                            "deal_ticket": getattr(oms, "deal_ticket", None),
                            "gateway_status": getattr(oms, "gateway_status", None),
                        },
                        latency_ms=float(getattr(oms, "latency_ms", 0) or 0) or None,
                        retry_count=int(
                            getattr(self.guarded_submit, "retry_count", 0) or 0
                        ),
                    )
                    ticket = getattr(oms, "order_ticket", None) or getattr(
                        oms, "deal_ticket", None
                    )
                    if oms_ok and ticket:
                        pvm_stage(
                            ValidationStage.BROKER,
                            ok=True,
                            reason=f"ticket={ticket}",
                        )
                        pvm_stage(
                            ValidationStage.POSITION_OPEN,
                            ok=True,
                            reason=f"ticket={ticket}",
                        )
                    elif forwarded:
                        pvm_stage(
                            ValidationStage.BROKER,
                            ok=False,
                            reason=str(getattr(oms, "message", "") or outcome),
                        )
                elif forwarded is False and action_s in {"BUY", "SELL"}:
                    pvm_stage(
                        ValidationStage.OMS,
                        ok=False,
                        reason=abort_val or "OMS not reached",
                        skip=False,
                    )
            else:
                pvm_stage(
                    ValidationStage.EXECUTION_BRIDGE,
                    ok=True,
                    reason=f"ignored_action {action_s}",
                    skip=False,
                )
        except Exception:
            logger.exception("pvm_bridge_stages_failed")
        try:
            from app.application.services.market_closed_cooldown import (
                note_oms_reject,
            )

            oms = getattr(bridge_result, "oms_result", None)
            if oms is not None:
                note_oms_reject(
                    symbol=str(getattr(decision, "symbol", "") or ""),
                    retcode=getattr(oms, "retcode", None),
                    message=str(getattr(oms, "message", "") or ""),
                )
        except Exception:
            logger.exception("market_closed_cooldown_note_failed")
        self._log_post_ai_execution_chain(
            decision=decision,
            bridge_result=bridge_result,
            execution_enabled=bool(ctx.execution_enabled),
            force_shadow=force_shadow,
        )

        try:
            from app.domain.institutional_trading.production_hardening.observe import (
                observe_oms_outcome,
                store_trade_explanation,
            )

            oms = getattr(bridge_result, "oms_result", None)
            success = not getattr(bridge_result, "aborted", True) and getattr(
                bridge_result, "forwarded_to_oms", False
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
                symbol=str(
                    getattr(decision, "symbol", "") or getattr(snapshot, "symbol", "")
                ),
                forwarded=bool(getattr(bridge_result, "forwarded_to_oms", False)),
                success=bool(success),
                latency_ms=lat,
                retcode=getattr(oms, "retcode", None) if oms is not None else None,
                message=(
                    str(getattr(oms, "message", "") or "") if oms is not None else None
                ),
                ticket=ticket,
                spread=(
                    float(snapshot.spread)
                    if getattr(snapshot, "spread", None) is not None
                    else None
                ),
                retries=retries,
            )
            # v7 execution quality + slippage (observational)
            try:
                from app.domain.institutional_trading.ai_validation import (
                    get_execution_quality_monitor,
                    get_slippage_store,
                    get_validation_alerter,
                )

                t_ai = (time.perf_counter() - t0) * 1000.0
                get_execution_quality_monitor().record(
                    {
                        "signal_generation": max(0.0, t_ai * 0.15),
                        "ai_decision": max(0.0, t_ai * 0.35),
                        "oms": (
                            max(0.0, t_ai * 0.20)
                            if getattr(bridge_result, "forwarded_to_oms", False)
                            else 0.0
                        ),
                        "gateway": (
                            max(0.0, t_ai * 0.10)
                            if getattr(bridge_result, "forwarded_to_oms", False)
                            else 0.0
                        ),
                        "mt5": (
                            max(0.0, t_ai * 0.10)
                            if getattr(bridge_result, "forwarded_to_oms", False)
                            else 0.0
                        ),
                        "broker": (
                            max(0.0, t_ai * 0.10)
                            if getattr(bridge_result, "forwarded_to_oms", False)
                            else 0.0
                        ),
                        "total": lat,
                    }
                )
                get_validation_alerter().on_latency_spike(latency_ms=lat)
                if success and getattr(bridge_result, "forwarded_to_oms", False):
                    entry_zone = getattr(decision, "entry_zone", None)
                    expected = None
                    if entry_zone is not None:
                        expected = float(
                            getattr(entry_zone, "mid", None)
                            or getattr(entry_zone, "low", 0)
                            or 0
                        )
                    actual = float(getattr(account, "mid_price", None) or expected or 0)
                    if expected and expected > 0 and actual > 0:
                        get_slippage_store().record_fill(
                            symbol=str(getattr(decision, "symbol", "") or ""),
                            side=str(
                                getattr(
                                    getattr(decision, "direction", None), "value", "buy"
                                )
                                or "buy"
                            ),
                            expected_entry=expected,
                            actual_entry=actual,
                        )
            except Exception:
                logger.exception("ai_validation_exec_metrics_failed")
            if success and getattr(bridge_result, "forwarded_to_oms", False):
                store_trade_explanation(
                    decision=decision,
                    ticket=str(ticket) if ticket is not None else None,
                    risk_pct=str(risk_pct),
                    extras={"trace_id": tid, "forced": forced_override},
                )
                try:
                    from app.domain.institutional_trading.performance_lab import (
                        build_replay_from_decision,
                        get_calibration_store,
                        get_opportunity_outcome_store,
                        get_trade_replay_store,
                        store_lab_explanation,
                    )

                    store_lab_explanation(
                        decision=decision,
                        ticket=str(ticket) if ticket is not None else None,
                        risk_pct=str(risk_pct),
                        extras={"trace_id": tid},
                    )
                    replay = build_replay_from_decision(
                        decision=decision,
                        snapshot=snapshot,
                        ticket=str(ticket) if ticket is not None else None,
                        entry=(
                            float(mid_price)
                            if (mid_price := getattr(account, "mid_price", None))
                            is not None
                            else None
                        ),
                    )
                    # Attach live institutional artefacts when present (never fabricate)
                    try:
                        inst: dict[str, Any] = {
                            "ai_decision": replay.ai_reasoning,
                            "risk_sizing": {"risk_pct": str(risk_pct)},
                            "oms": {
                                "forwarded": bool(
                                    getattr(bridge_result, "forwarded_to_oms", False)
                                ),
                                "ticket": str(ticket) if ticket is not None else None,
                            },
                            "mt5": {"trace_id": tid},
                        }
                        last_scan = getattr(self, "_last_multi_asset_scan", None)
                        if isinstance(last_scan, dict):
                            inst["scanner_ranking"] = {
                                "best_symbol": last_scan.get("best_symbol"),
                                "opportunity_ranked": (
                                    last_scan.get("opportunity_ranked") or []
                                )[:5],
                                "as_of": last_scan.get("as_of"),
                            }
                        # Execution intelligence artefacts
                        try:
                            from app.domain.institutional_trading.ai_scalping.execution_optimizer import (  # noqa: E501
                                get_last_execution_optimizer,
                            )
                            from app.domain.institutional_trading.ai_scalping.smart_order_routing import (  # noqa: E501
                                get_last_smart_routing,
                            )

                            opt = get_last_execution_optimizer()
                            sor = get_last_smart_routing()
                            if opt:
                                inst["execution_decision"] = opt
                            if sor:
                                inst["smart_order_routing"] = sor
                        except Exception:
                            logger.exception("replay_exec_intel_attach_failed")
                        oms_obj = getattr(bridge_result, "oms_result", None)
                        if oms_obj is not None:
                            inst["oms_payload"] = {
                                "outcome": str(getattr(oms_obj, "outcome", None)),
                                "message": str(getattr(oms_obj, "message", None) or "")[
                                    :200
                                ],
                                "retcode": getattr(oms_obj, "retcode", None),
                            }
                            inst["broker_response"] = dict(inst["oms_payload"])
                        replay.market_snapshot = {
                            **(replay.market_snapshot or {}),
                            "institutional": inst,
                        }
                    except Exception:
                        logger.exception("institutional_replay_enrich_failed")
                    get_trade_replay_store().record(replay)

                    # Rich execution quality + lifecycle FILLED
                    try:
                        from app.domain.institutional_trading.ai_scalping.execution_quality_analytics import (  # noqa: E501
                            classify_fill_quality,
                            get_execution_quality_analytics_store,
                        )
                        from app.domain.institutional_trading.ai_scalping.slippage_protection import (  # noqa: E501
                            extract_fill_price,
                        )
                        from app.domain.institutional_trading.ai_scalping.smart_order_routing import (  # noqa: E501
                            get_last_smart_routing,
                        )
                        from app.domain.institutional_trading.ai_scalping.trade_lifecycle_timeline import (  # noqa: E501
                            get_trade_lifecycle_store,
                        )

                        get_trade_lifecycle_store().mark(
                            tid, "OMS_SUBMITTED", ok=True
                        )
                        get_trade_lifecycle_store().mark(
                            tid, "BROKER_ACCEPTED", ok=True
                        )
                        filled_px = None
                        oms_obj = getattr(bridge_result, "oms_result", None)
                        if oms_obj is not None:
                            filled_px = extract_fill_price(
                                getattr(oms_obj, "raw", None)
                            )
                        req_px = getattr(account, "mid_price", None)
                        slip_v = None
                        try:
                            if filled_px is not None and req_px is not None:
                                side_l = str(
                                    getattr(
                                        getattr(decision, "direction", None),
                                        "value",
                                        "",
                                    )
                                    or ""
                                ).lower()
                                if side_l in {"buy", "long"}:
                                    slip_v = float(filled_px) - float(req_px)
                                else:
                                    slip_v = float(req_px) - float(filled_px)
                        except Exception:
                            slip_v = None
                        fq = classify_fill_quality(
                            slippage=slip_v, latency_ms=float(lat) if lat else None
                        )
                        get_execution_quality_analytics_store().record(
                            symbol=str(getattr(decision, "symbol", "") or ""),
                            side=str(
                                getattr(
                                    getattr(decision, "direction", None), "value", ""
                                )
                                or ""
                            ),
                            requested_price=float(req_px) if req_px is not None else None,
                            executed_price=(
                                float(filled_px) if filled_px is not None else None
                            ),
                            slippage=slip_v,
                            latency_ms=float(lat) if lat else None,
                            broker_execution_time_ms=float(lat) if lat else None,
                            fill_quality=fq,
                            execution_score=(
                                int(
                                    (
                                        get_last_smart_routing() or {}
                                    ).get("execution_quality_score")
                                    or 0
                                )
                                or None
                            ),
                            outcome="success",
                            ticket=str(ticket) if ticket is not None else None,
                        )
                        get_trade_lifecycle_store().mark(
                            tid,
                            "FILLED",
                            ok=True,
                            reason=fq,
                            metrics={"slippage": slip_v, "latency_ms": lat},
                        )
                    except Exception:
                        logger.exception("execution_quality_analytics_record_failed")
                    get_opportunity_outcome_store().record_evaluation(
                        symbol=str(getattr(decision, "symbol", "") or ""),
                        ai_confidence=int(getattr(decision, "confidence", 0) or 0),
                        opportunity_score=int(getattr(decision, "confidence", 0) or 0),
                        traded=True,
                        outcome=None,
                        session=None,
                        strategy=str(
                            getattr(self.plane, "trading_mode", "swing") or "swing"
                        ),
                        direction=str(
                            getattr(getattr(decision, "direction", None), "value", "")
                            or ""
                        ),
                        latency_ms=lat,
                    )
                    # Calibration updated when outcome known; seed sample as pending via confidence only later  # noqa: E501
                    _ = get_calibration_store
                except Exception:
                    logger.exception("performance_lab_post_fill_failed")
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
                    or getattr(
                        getattr(bridge_result, "journal_entry", None), "comment", None
                    )
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

        self._sync_and_manage_open_positions(
            snapshot=snapshot,
            account=account,
            reason=(
                "post_fill_manage"
                if bool(getattr(bridge_result, "forwarded_to_oms", False))
                else "cycle_manage"
            ),
        )

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
                OpsExecutionMode.SHADOW.value if force_shadow else self.plane.mode.value
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
                dict(market_context_diagnostics) if market_context_diagnostics else None
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
        # Explicit PASS/FAIL chain for live ops (current vs required, no generic labels).  # noqa: E501
        try:
            self._log_execution_path_pass_fail(
                decision=decision,
                bridge_result=bridge_result,
                result=result,
                execution_enabled=False if force_shadow else execution_enabled,
                gateway_connected=gateway_connected,
                broker_connected=broker_connected,
                force_shadow=force_shadow,
            )
        except Exception:
            logger.exception("execution_path_pass_fail_log_failed")
        try:
            from app.domain.institutional_trading.production_validation_mode import (
                finalize as pvm_finalize,
            )

            pvm_finalize()
        except Exception:
            logger.exception("pvm_cycle_finalize_failed")
        return result

    def _log_post_ai_execution_chain(
        self,
        *,
        decision: Any,
        bridge_result: Any,
        execution_enabled: bool,
        force_shadow: bool,
    ) -> None:
        """After AI Decision: Gate → Risk → OMS → MT5 → Broker. Always PASS/FAIL."""
        action = str(getattr(getattr(decision, "action", None), "value", "") or "")
        elig = getattr(decision, "eligibility", None)
        elig_ok = bool(getattr(elig, "eligible", False))
        elig_reasons = list(getattr(elig, "rejection_reasons", ()) or ())
        risk_reasons = list(getattr(decision, "risk_reasons", ()) or ())
        aborted = bool(getattr(bridge_result, "aborted", False))
        abort = getattr(bridge_result, "abort_reason", None)
        abort_val = str(getattr(abort, "value", abort) or "")
        forwarded = bool(getattr(bridge_result, "forwarded_to_oms", False))
        oms = getattr(bridge_result, "oms_result", None)
        oms_msg = str(getattr(oms, "message", "") or "") if oms is not None else ""
        oms_ret = getattr(oms, "retcode", None) if oms is not None else None
        ticket = None
        if oms is not None:
            ticket = getattr(oms, "order_ticket", None) or getattr(
                oms, "deal_ticket", None
            )
        journal = getattr(bridge_result, "journal_entry", None)
        journal_comment = str(getattr(journal, "comment", "") or "")

        logger.warning(
            "AI Decision",
            result="PASS" if action in {"BUY", "SELL"} else "FAIL",
            action=action or "NO_TRADE",
            required="BUY|SELL",
        )

        # Execution Gate = bridge reached live path (not shadow force, EXEC on)
        gate_ok = (
            (not force_shadow)
            and bool(execution_enabled)
            and action
            in {
                "BUY",
                "SELL",
            }
        )
        if abort_val in {
            "execution_disabled",
            "auto_trading_blocked",
            "kill_switch",
            "session_invalid",
            "market_closed",
            "spread_unacceptable",
        }:
            gate_ok = False
        logger.warning(
            "Execution Gate",
            result=(
                "PASS"
                if gate_ok
                and abort_val
                not in {
                    "execution_disabled",
                    "auto_trading_blocked",
                    "kill_switch",
                }
                else ("FAIL" if abort_val else ("PASS" if gate_ok else "FAIL"))
            ),
            execution_enabled=execution_enabled,
            force_shadow=force_shadow,
            abort=abort_val or "none",
        )

        # Prefer explicit eligibility for Risk Engine stage
        risk_pass = elig_ok if not forwarded else True
        if abort_val == "eligibility_failed":
            risk_pass = False
        risk_detail = (
            "; ".join(elig_reasons)
            or "; ".join(risk_reasons)
            or journal_comment
            or "eligible"
        )
        logger.warning(
            "Risk Engine",
            result="PASS" if risk_pass else "FAIL",
            eligible=elig_ok,
            detail=risk_detail[:500],
        )

        if aborted and not forwarded:
            logger.warning(
                "OMS Submit",
                result="FAIL",
                detail="OMS not called — bridge aborted before submit",
                abort=abort_val,
            )
            logger.warning(
                "MT5 Gateway",
                result="FAIL",
                detail="not reached",
            )
            logger.warning(
                "Broker",
                result="FAIL",
                detail="not reached",
            )
            logger.warning(
                "Rejected because: %s",
                journal_comment or abort_val or risk_detail or "unknown abort",
            )
            logger.warning(
                "execution_stop_detail",
                function="ExecutionBridge.handle",
                file="app/domain/institutional_trading/execution/bridge.py",
                condition=f"abort_reason == {abort_val or 'unknown'}",
                reason=journal_comment or abort_val or risk_detail,
            )
            return

        logger.warning(
            "OMS Submit",
            result="PASS" if forwarded else "FAIL",
            forwarded_to_oms=forwarded,
        )
        if forwarded:
            logger.warning("Submitting Order...")

        broker_ok = ticket is not None
        # Retcode 0 with rejection message is still a broker reply (FAIL accept)
        gateway_reached = forwarded and (oms is not None or bool(oms_msg) or abort_val)
        logger.warning(
            "MT5 Gateway",
            result="PASS" if gateway_reached else "FAIL",
            retcode=oms_ret,
            message=(oms_msg or abort_val or "none")[:400],
        )
        logger.warning(
            "Broker",
            result="PASS" if broker_ok else "FAIL",
            ticket=ticket,
            required="non-null ticket",
            message=(oms_msg or journal_comment or abort_val or "none")[:400],
        )
        if broker_ok:
            logger.warning(
                "MT5 Accepted",
                ticket=ticket,
            )
        else:
            reject = (
                oms_msg
                or journal_comment
                or abort_val
                or "OMS forwarded but broker did not accept"
            )
            logger.warning("Rejected because: %s", reject)
            # Exact stop for the known close-only path
            if "closeonly" in reject.lower() or "10044" in reject:
                logger.warning(
                    "execution_stop_detail",
                    function="InstitutionalExecutionEngine.run_submit",
                    file=(
                        "app/application/services/" "institutional_execution_engine.py"
                    ),
                    line=309,
                    condition=(
                        "trade_mode in {'closeonly','close_only'} and not is_manage"
                    ),
                    current="closeonly",
                    required="full",
                    reason=reject,
                )
            else:
                logger.warning(
                    "execution_stop_detail",
                    function="ExecutionBridge.handle / OMS submit_market",
                    file="app/domain/institutional_trading/execution/bridge.py",
                    condition=f"oms outcome abort={abort_val or 'oms_failure'}",
                    reason=reject,
                )

    def _log_execution_path_pass_fail(
        self,
        *,
        decision: Any,
        bridge_result: Any,
        result: ShadowCycleResult,
        execution_enabled: bool,
        gateway_connected: bool,
        broker_connected: bool,
        force_shadow: bool,
    ) -> None:
        """Print PASS/FAIL for Scheduler→…→Broker with exact condition values."""
        settings = get_settings()
        exec_setting = bool(getattr(settings, "execution_enabled", False))
        mode = self.plane.mode.value
        run_state = str(getattr(self.plane, "auto_trading_run_state", "off") or "off")
        action = str(getattr(getattr(decision, "action", None), "value", None) or "")
        oms = getattr(bridge_result, "oms_result", None)
        ticket = None
        oms_msg = ""
        oms_ret = None
        if oms is not None:
            ticket = getattr(oms, "order_ticket", None) or getattr(
                oms, "deal_ticket", None
            )
            oms_msg = str(getattr(oms, "message", "") or "")
            oms_ret = getattr(oms, "retcode", None)
        abort = str(result.abort_reason or "")
        forwarded = bool(result.forwarded_to_oms)
        forced = bool(
            getattr(decision, "reasons", None)
            and any("FORCED_TEST_TRADE" in str(r) for r in (decision.reasons or ()))
        )

        steps: list[tuple[str, bool, str]] = []
        steps.append(
            (
                "Scheduler Tick",
                True,
                f"interval_s={self.interval_seconds} force_shadow={force_shadow}",
            )
        )
        steps.append(
            (
                "Ops Mode",
                mode != "SHADOW",
                f"current={mode} required=CANARY|LIVE",
            )
        )
        steps.append(
            (
                "Auto Trading Run State",
                run_state == "running" or forced,
                f"current={run_state} required=running forced={forced}",
            )
        )
        steps.append(
            (
                "EXECUTION_ENABLED",
                exec_setting and execution_enabled,
                f"setting={exec_setting} context={execution_enabled} required=true",
            )
        )
        steps.append(
            (
                "AI Decision",
                action in {"BUY", "SELL"},
                f"current={action or 'NO_TRADE'} required=BUY|SELL",
            )
        )
        steps.append(
            (
                "Gate / Connectivity",
                bool(gateway_connected and broker_connected),
                f"gateway={gateway_connected} broker={broker_connected} required=both true",  # noqa: E501
            )
        )
        steps.append(
            (
                "OMS Received Request",
                forwarded,
                f"forwarded_to_oms={forwarded} abort={abort or 'none'}",
            )
        )
        # Broker reply (accept or reject) counts as MT5 round-trip completed.
        mt5_reached = bool(ticket is not None) or (
            forwarded and bool(oms_msg or oms_ret is not None or abort)
        )
        steps.append(
            (
                "MT5 Gateway / Broker Reply",
                mt5_reached,
                f"ticket={ticket} retcode={oms_ret} message={oms_msg or abort or 'none'}",  # noqa: E501
            )
        )
        steps.append(
            (
                "MT5 Accepted (ticket)",
                ticket is not None,
                f"ticket={ticket} required=non-null broker ticket",
            )
        )

        for name, ok, detail in steps:
            logger.warning(
                "execution_path_step",
                step=name,
                result="PASS" if ok else "FAIL",
                detail=detail,
            )
        if ticket is not None:
            logger.warning(
                "execution_path_complete",
                chain="Scheduler Tick → AI Decision → Submitting Order → MT5 Accepted → Ticket",  # noqa: E501
                ticket=ticket,
            )

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
            "trading_mode": getattr(
                self.decision_pipeline.config, "trading_mode", "swing"
            ),
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
            direction = (
                str(
                    getattr(getattr(decision, "direction", None), "value", None)
                    or getattr(decision, "direction", None)
                    or ""
                )
                or None
            )
            lots = getattr(decision, "approved_lots", None)
            if lots is not None:
                lot = float(lots)
            entry = self._zone_price(
                getattr(decision, "entry_zone", None), prefer="mid"
            )
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
        if (
            not oms_success
            and cycle.forwarded_to_oms
            and ticket
            and not cycle.oms_message
        ) and (cycle.abort_reason or "").upper() in {"NONE", "", "OK", "SUCCESS"}:
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
        if cycle.detail and cycle.detail not in exact_reason_parts:  # noqa: SIM102
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

        reason = (
            "; ".join(exact_reason_parts)
            if exact_reason_parts
            else (cycle.detail or cycle.abort_reason or "Execution rejected")
        )

        base = {
            "market": market,
            "direction": direction,
            "lot": lot,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "ticket": ticket,
            "execution_ms": round(execution_ms),
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
            if not cfg.enabled and not getattr(
                self.plane, "alpha_engine_enabled", False
            ):
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
            try:
                from app.domain.institutional_trading.ai_validation import (
                    get_opportunity_history_store,
                )

                ranking = list(
                    scan.get("opportunity_ranking") or scan.get("ranking") or []
                )
                top = []
                for row in ranking[:10]:
                    if not isinstance(row, dict):
                        continue
                    sym = str(row.get("symbol") or "")
                    traded = any(
                        s.upper() == sym.upper() for s in (open_symbols or [])
                    ) or (
                        bool(scan.get("selected"))
                        and str(
                            (scan.get("selected") or [{}])[0].get("symbol") or ""
                        ).upper()
                        == sym.upper()
                    )
                    top.append(
                        {
                            **row,
                            "traded": traded,
                            "skip_reason": (
                                None
                                if traded
                                else (
                                    "below_execute_threshold"
                                    if not (scan.get("selected"))
                                    else "not_selected"
                                )
                            ),
                        }
                    )
                if top:
                    get_opportunity_history_store().record_daily_top(top)
            except Exception:
                logger.exception("opportunity_history_record_failed")
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

    def _alpha_ranking_rows(self) -> list[dict[str, Any]]:
        try:
            from app.application.services.institutional_alpha_engine import (
                get_alpha_config,
                run_alpha_scan,
            )

            cfg = get_alpha_config()
            if not (
                cfg.enabled
                or getattr(self.plane, "alpha_engine_enabled", False)
                or str(getattr(self.plane, "trading_mode", "") or "") == "alpha"
            ):
                return []
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
            rows = list(scan.get("opportunity_ranking") or scan.get("ranking") or [])
            return [r for r in rows if isinstance(r, dict)]
        except Exception:
            logger.exception("alpha_ranking_rows_failed")
            return []

    async def _multi_asset_preferred_symbol(self) -> str | None:
        """Institutional Multi-Asset Scanner — full AI score per symbol, best only.

        Does not invoke Risk / PRE / OMS / MT5. Winner is handed to the existing
        single-symbol cycle which still runs the full institutional pipeline.
        """
        try:
            from app.application.services.institutional_multi_asset_scanner import (
                run_institutional_multi_asset_scan,
            )
            from app.domain.institutional_trading.ai_scalping.config import (
                DEFAULT_AI_SCALPING_CONFIG,
            )

            if not bool(
                getattr(DEFAULT_AI_SCALPING_CONFIG, "multi_asset_scan_enabled", True)
            ):
                return None
            open_n = 0
            try:
                open_n = len(
                    getattr(self.position_management.engine, "_positions", {}) or {}
                )
            except Exception:
                open_n = 0
            scan = await run_institutional_multi_asset_scan(
                self.mt5_adapter,
                position_engine=getattr(self.position_management, "engine", None),
                open_positions=open_n,
                plane=self.plane,
                config=DEFAULT_AI_SCALPING_CONFIG,
            )
            with self._lock:
                self._last_multi_asset_scan = dict(scan) if isinstance(scan, dict) else None
            best = str(scan.get("best_symbol") or "").upper() or None
            if best:
                logger.warning(
                    "multi_asset_opportunity_selected",
                    symbol=best,
                    eligible_count=scan.get("eligible_count"),
                    blocked_by_portfolio=scan.get("blocked_by_portfolio"),
                )
                return best
            logger.warning(
                "multi_asset_scan_no_executable_opportunity",
                eligible_count=scan.get("eligible_count"),
                blocked_by_portfolio=scan.get("blocked_by_portfolio"),
                reason=scan.get("portfolio_block_reason") or scan.get("note"),
            )
            return None
        except Exception:
            logger.exception("multi_asset_preferred_symbol_failed")
            return None

    def last_multi_asset_scan(self) -> dict[str, Any] | None:
        with self._lock:
            return (
                dict(self._last_multi_asset_scan)
                if isinstance(self._last_multi_asset_scan, dict)
                else None
            )

    async def _pick_executable_symbol_async(self) -> str | None:
        """Highest-ranked full-mode symbol after institutional multi-asset scan."""
        from app.application.services.closeonly_symbol_router import (
            resolve_executable_symbol,
        )
        from app.domain.trading.gold_only import GOLD_SYMBOL

        preferred = await self._multi_asset_preferred_symbol()
        with self._lock:
            last = (
                dict(self._last_multi_asset_scan)
                if isinstance(self._last_multi_asset_scan, dict)
                else None
            )
        scan_complete = bool(
            last
            and last.get("enabled")
            and last.get("as_of")
            and last.get("note") != "multi_asset_scan_disabled"
        )
        if not preferred:
            if scan_complete:
                # Full AI universe scanned — do not invent a single-market fallback.
                logger.warning(
                    "multi_asset_scan_exhausted_no_fallback",
                    eligible_count=last.get("eligible_count") if last else 0,
                    blocked_by_portfolio=(
                        last.get("blocked_by_portfolio") if last else None
                    ),
                )
                return None
            preferred = self._alpha_preferred_symbol() or GOLD_SYMBOL
        symbol, skipped = resolve_executable_symbol(
            self.mt5_adapter,
            preferred=preferred,
            plane=self.plane,
            alpha_ranking=self._alpha_ranking_rows(),
        )
        if skipped:
            logger.warning(
                "closeonly_symbols_removed_from_scanner",
                skipped=skipped,
                next_opportunity=symbol,
            )
        if symbol is None:
            logger.warning(
                "no_full_mode_symbol_available",
                preferred=preferred,
                skipped=skipped,
            )
        else:
            logger.warning("Submitting Order...", symbol=symbol)
        return symbol

    def _pick_executable_symbol(self) -> str | None:
        """Sync fallback — prefer Alpha / gold when async scan is not awaited."""
        from app.application.services.closeonly_symbol_router import (
            resolve_executable_symbol,
        )
        from app.domain.trading.gold_only import GOLD_SYMBOL

        preferred = self._alpha_preferred_symbol() or GOLD_SYMBOL
        # Prefer last multi-asset winner when a scan already completed this cycle.
        with self._lock:
            last = self._last_multi_asset_scan
        if isinstance(last, dict):
            best = str(last.get("best_symbol") or "").upper()
            if best:
                preferred = best
        symbol, skipped = resolve_executable_symbol(
            self.mt5_adapter,
            preferred=preferred,
            plane=self.plane,
            alpha_ranking=self._alpha_ranking_rows(),
        )
        if skipped:
            logger.warning(
                "closeonly_symbols_removed_from_scanner",
                skipped=skipped,
                next_opportunity=symbol,
            )
        if symbol is None:
            logger.warning(
                "no_full_mode_symbol_available",
                preferred=preferred,
                skipped=skipped,
            )
        else:
            logger.warning("Submitting Order...", symbol=symbol)
        return symbol

    async def execute_now(self) -> dict[str, Any]:
        """Run one complete Auto Trading cycle immediately (manual trigger).

        Reuses the same market-context + run_auto_cycle / run_shadow_cycle path
        as the background scheduler — does not duplicate trading logic.
        """
        t0 = time.perf_counter()
        self._manual_execution = True
        logger.warning("MANUAL EXECUTION STARTED")
        _pvm_vid = None
        _pvm_token = None
        try:
            from app.domain.institutional_trading.production_validation_mode import (
                ValidationStage,
                begin_validation,
                get_production_validation_recorder,
                stage as pvm_stage,
            )

            _pvm_vid = begin_validation(execution_mode=self.plane.mode.value)
            if _pvm_vid:
                _pvm_token = get_production_validation_recorder().bind_context(_pvm_vid)
            pvm_stage(
                ValidationStage.SCHEDULER,
                ok=True,
                reason="execute_now",
                validation_id=_pvm_vid,
            )
        except Exception:
            logger.exception("pvm_execute_now_begin_failed")
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
            symbol = await self._pick_executable_symbol_async()
            if not symbol:
                logger.warning(
                    "no_full_mode_symbol_available — manage-only execute-now"
                )
                open_syms = [
                    str(getattr(p, "symbol", "") or "")
                    for p in (
                        getattr(self.position_management.engine, "_positions", {}) or {}
                    ).values()
                ]
                symbol = next((s for s in open_syms if s), GOLD_SYMBOL)
                ctx = await build_ite_cycle_market_context(
                    self.mt5_adapter,
                    symbol=symbol,
                    position_engine=self.position_management.engine,
                )
                if ctx.ok and ctx.snapshot is not None and ctx.account is not None:
                    self._sync_and_manage_open_positions(
                        snapshot=ctx.snapshot,
                        account=ctx.account,
                        reason="execute_now_manage_only",
                    )
                return {
                    "success": False,
                    "status": "REJECTED",
                    "reason": "no_executable_symbol",
                    "message": "No full-mode / open-market symbol available",
                    "execution_ms": round((time.perf_counter() - t0) * 1000.0),
                }
            logger.warning("Scanning Symbols", symbol=symbol)
            ctx = await build_ite_cycle_market_context(
                self.mt5_adapter,
                symbol=symbol,
                position_engine=self.position_management.engine,
            )
            try:
                from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                    ValidationStage,
                    stage as pvm_stage,
                )

                market_ok = bool(ctx.ok) and ctx.snapshot is not None
                pvm_stage(
                    ValidationStage.MARKET_DATA,
                    ok=market_ok,
                    reason=ctx.reason or ("market data ok" if market_ok else "fail"),
                    latency_ms=getattr(ctx, "latency_ms", None),
                    validation_id=_pvm_vid,
                )
                pvm_stage(
                    ValidationStage.CONTEXT,
                    ok=bool(
                        ctx.ok and ctx.snapshot is not None and ctx.account is not None
                    ),
                    reason=ctx.reason or "context built",
                    validation_id=_pvm_vid,
                )
            except Exception:
                logger.exception("pvm_execute_now_market_stages_failed")
            if not ctx.ok or ctx.snapshot is None or ctx.account is None:
                health = self.tick_health()
                result = ShadowCycleResult(
                    ok=True,
                    trace_id=None,
                    mode=self.plane.mode.value,
                    detail=ctx.reason or "market context unavailable",
                    health=(health.get("health") if isinstance(health, dict) else None),
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
                    from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                        finalize as pvm_finalize,
                    )

                    pvm_finalize(validation_id=_pvm_vid)
                except Exception:
                    logger.exception("pvm_execute_now_no_context_finalize_failed")
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

            mt5_at = _cycle_flag_prefer_context(
                ctx_value=bool(ctx.mt5_autotrading_enabled),
                enrich=enrich,
                key="mt5_autotrading_enabled",
            )
            acct_ok = _cycle_flag_prefer_context(
                ctx_value=bool(ctx.account_trading_enabled),
                enrich=enrich,
                key="account_trading_enabled",
            )
            sym_ok = _cycle_flag_prefer_context(
                ctx_value=bool(ctx.symbol_tradable),
                enrich=enrich,
                key="symbol_tradable",
            )
            mkt_ok = _cycle_flag_prefer_context(
                ctx_value=bool(ctx.market_data_live),
                enrich=enrich,
                key="market_data_live",
            )
            no_restr = _cycle_flag_prefer_context(
                ctx_value=bool(ctx.no_broker_restrictions),
                enrich=enrich,
                key="no_broker_restrictions",
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
            try:
                from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                    finalize as pvm_finalize,
                )

                pvm_finalize(validation_id=_pvm_vid)
            except Exception:
                logger.exception("pvm_execute_now_exception_finalize_failed")
            return {
                "success": False,
                "status": "REJECTED",
                "reason": reason,
                "message": reason,
                "execution_ms": round(ms),
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
            try:
                if _pvm_token is not None:
                    from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                        get_production_validation_recorder as _pvm_rec_en,
                    )

                    _pvm_rec_en().unbind_context(_pvm_token)
            except Exception:
                logger.exception("pvm_execute_now_unbind_failed")

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        """Background loop — live market context → Decision→Risk→Safety→OMS."""
        import os

        # Continuous production cadence (default 5s). Override via ITE_CYCLE_INTERVAL_SECONDS.  # noqa: E501
        try:
            env_iv = float(os.environ.get("ITE_CYCLE_INTERVAL_SECONDS") or "")
            if env_iv > 0:
                self.interval_seconds = max(1.0, env_iv)
        except Exception:  # noqa: S110  # best-effort optional path
            pass
        if self.interval_seconds > 15:
            # Prefer continuous scanning; 60s legacy default is too slow for AUTO RUNNING.  # noqa: E501
            self.interval_seconds = 5.0

        from app.application.services.auto_trading_continuity import (
            ensure_auto_trading_running,
        )
        from core.config.settings import get_settings as _gs

        ensure_auto_trading_running(
            self.plane,
            settings=_gs(),
            reason="orchestrator_start_auto_resume",
        )
        logger.warning(
            "Scheduler Tick",
            interval_seconds=self.interval_seconds,
            mode=self.plane.mode.value,
            run_state=self.plane.auto_trading_run_state,
        )
        logger.info(
            "ite_orchestrator_started",
            interval_seconds=self.interval_seconds,
            mode=self.plane.mode.value,
            run_state=self.plane.auto_trading_run_state,
            autonomous=True,
            continuous_24_7=True,
        )
        # Mark open-book resume after process start / reconnect path.
        try:
            from app.domain.institutional_trading.ai_scalping.config import (
                DEFAULT_AI_SCALPING_CONFIG,
            )
            from app.domain.institutional_trading.ai_scalping.continuous_operation import (  # noqa: E501
                get_continuous_operation_controller,
            )

            if DEFAULT_AI_SCALPING_CONFIG.continuous_operation_enabled:
                get_continuous_operation_controller(
                    DEFAULT_AI_SCALPING_CONFIG
                ).mark_startup_resume()
        except Exception:
            logger.exception("continuous_ops_startup_resume_failed")
        while not self._stop.is_set():
            cycle_t0 = time.perf_counter()
            _pvm_vid = None
            _pvm_token = None
            try:
                ensure_auto_trading_running(
                    self.plane,
                    settings=_gs(),
                    reason="orchestrator_cycle_auto_resume",
                )
                logger.warning(
                    "Scheduler Tick",
                    run_state=self.plane.auto_trading_run_state,
                    mode=self.plane.mode.value,
                    execution_enabled=bool(getattr(_gs(), "execution_enabled", False)),
                )
                logger.warning("Cycle Started")
                from app.application.services.auto_trading_status import (
                    _enrich_from_adapter,
                )
                from app.application.services.ite_cycle_market_context import (
                    build_ite_cycle_market_context,
                )

                enrich = _enrich_from_adapter(self.probes)
                from app.domain.trading.gold_only import GOLD_SYMBOL

                try:
                    from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                        ValidationStage,
                        begin_validation,
                        get_production_validation_recorder,
                        stage as pvm_stage,
                        update_live_status,
                    )

                    _pvm_vid = begin_validation(
                        execution_mode=self.plane.mode.value,
                    )
                    if _pvm_vid:
                        _pvm_token = get_production_validation_recorder().bind_context(
                            _pvm_vid
                        )
                    pvm_stage(
                        ValidationStage.SCHEDULER,
                        ok=True,
                        reason=f"interval={self.interval_seconds}s",
                        validation_id=_pvm_vid,
                    )
                    update_live_status(
                        execution_state=str(self.plane.auto_trading_run_state),
                    )
                except Exception:
                    logger.exception("pvm_scheduler_stage_failed")

                symbol = await self._pick_executable_symbol_async()
                manage_only = False
                if not symbol:
                    # Never force a close-only / market-closed symbol into OMS.
                    # Still build context on gold (or any open PME symbol) for PME.
                    manage_only = True
                    open_syms = [
                        str(getattr(p, "symbol", "") or "")
                        for p in (
                            getattr(self.position_management.engine, "_positions", {})
                            or {}
                        ).values()
                    ]
                    symbol = next(
                        (s for s in open_syms if s),
                        GOLD_SYMBOL,
                    )
                    logger.warning(
                        "no_executable_symbol_manage_only",
                        context_symbol=symbol,
                    )
                logger.warning("Scanning Symbols", symbol=symbol)
                ctx = await build_ite_cycle_market_context(
                    self.mt5_adapter,
                    symbol=symbol,
                    position_engine=self.position_management.engine,
                )
                try:
                    from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                        ValidationStage,
                        finalize as pvm_finalize,
                        stage as pvm_stage,
                        update_live_status,
                    )

                    market_ok = bool(ctx.ok) and ctx.snapshot is not None
                    pvm_stage(
                        ValidationStage.MARKET_DATA,
                        ok=market_ok,
                        reason=ctx.reason
                        or ("market data ok" if market_ok else "fail"),
                        latency_ms=getattr(ctx, "latency_ms", None),
                        validation_id=_pvm_vid,
                    )
                    pvm_stage(
                        ValidationStage.CONTEXT,
                        ok=bool(
                            ctx.ok
                            and ctx.snapshot is not None
                            and ctx.account is not None
                        ),
                        reason=ctx.reason or "context built",
                        validation_id=_pvm_vid,
                    )
                    update_live_status(
                        gateway_status="PASS" if market_ok else "FAIL",
                        mt5_status="PASS" if market_ok else "UNKNOWN",
                    )
                except Exception:
                    logger.exception("pvm_market_context_stages_failed")
                if (
                    manage_only
                    and ctx.ok
                    and ctx.snapshot is not None
                    and ctx.account is not None
                ):
                    try:
                        self._sync_and_manage_open_positions(
                            snapshot=ctx.snapshot,
                            account=ctx.account,
                            reason="manage_only_no_executable_symbol",
                        )
                    except Exception:
                        logger.exception("manage_only_cycle_failed")
                    logger.warning(
                        "AI Decision",
                        action="NO_TRADE",
                        reason="no_executable_symbol",
                    )
                    logger.warning("Waiting Next Cycle", reason="no_executable_symbol")
                    try:
                        from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                            ValidationStage,
                            finalize as pvm_finalize,
                            stage as pvm_stage,
                        )
                        from app.domain.institutional_trading.production_validation_mode.recorder import (  # noqa: E501
                            get_production_validation_recorder as _pvm_get,
                        )

                        pvm_stage(
                            ValidationStage.AI,
                            ok=False,
                            reason="no_executable_symbol",
                            validation_id=_pvm_vid,
                        )
                        _pvm_get().record_no_trade_reasons(
                            ["no_executable_symbol"], validation_id=_pvm_vid
                        )
                        pvm_finalize(validation_id=_pvm_vid)
                    except Exception:
                        logger.exception("pvm_manage_only_finalize_failed")
                    finally:
                        try:
                            if _pvm_token is not None:
                                from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                                    get_production_validation_recorder as _pvm_rec,
                                )

                                _pvm_rec().unbind_context(_pvm_token)
                                _pvm_token = None
                        except Exception:
                            logger.exception("pvm_unbind_manage_only_failed")
                    await asyncio.sleep(self.interval_seconds)
                    continue

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
                    logger.warning(
                        "AI Decision",
                        action="NO_TRADE",
                        reason=ctx.reason or "NO_MARKET_CONTEXT",
                    )
                    logger.warning(
                        "Execution State",
                        run_state=self.plane.auto_trading_run_state,
                        outcome="no_snapshot",
                    )
                    logger.info(
                        "ite_cycle_outcome",
                        outcome="no_snapshot",
                        reason=ctx.reason,
                        bars=ctx.bars_loaded,
                        diagnostics=ctx.diagnostics,
                        mode=self.plane.mode.value,
                    )
                    try:
                        from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                            ValidationStage,
                            finalize as pvm_finalize,
                            stage as pvm_stage,
                        )
                        from app.domain.institutional_trading.production_validation_mode.recorder import (  # noqa: E501
                            get_production_validation_recorder as _pvm_get,
                        )

                        pvm_stage(
                            ValidationStage.AI,
                            ok=False,
                            reason=ctx.reason or "NO_MARKET_CONTEXT",
                            validation_id=_pvm_vid,
                        )
                        _pvm_get().record_no_trade_reasons(
                            [ctx.reason or "NO_MARKET_CONTEXT"],
                            validation_id=_pvm_vid,
                        )
                        pvm_finalize(validation_id=_pvm_vid)
                    except Exception:
                        logger.exception("pvm_no_market_context_finalize_failed")
                else:
                    mt5_at = _cycle_flag_prefer_context(
                        ctx_value=bool(ctx.mt5_autotrading_enabled),
                        enrich=enrich,
                        key="mt5_autotrading_enabled",
                    )
                    acct_ok = _cycle_flag_prefer_context(
                        ctx_value=bool(ctx.account_trading_enabled),
                        enrich=enrich,
                        key="account_trading_enabled",
                    )
                    sym_ok = _cycle_flag_prefer_context(
                        ctx_value=bool(ctx.symbol_tradable),
                        enrich=enrich,
                        key="symbol_tradable",
                    )
                    mkt_ok = _cycle_flag_prefer_context(
                        ctx_value=bool(ctx.market_data_live),
                        enrich=enrich,
                        key="market_data_live",
                    )
                    no_restr = _cycle_flag_prefer_context(
                        ctx_value=bool(ctx.no_broker_restrictions),
                        enrich=enrich,
                        key="no_broker_restrictions",
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
                        last = self._last_cycle
                        last_decision = self._last_decision
                    action = (
                        str(
                            getattr(
                                getattr(last_decision, "action", None),
                                "value",
                                None,
                            )
                            or getattr(last, "decision_action", None)
                            or "NO_TRADE"
                        )
                        if last_decision is not None or last is not None
                        else "NO_TRADE"
                    )
                    logger.warning(
                        "AI Decision",
                        action=action,
                        result="PASS" if action in {"BUY", "SELL"} else "FAIL",
                    )
                    # Never jump AI Decision → Waiting Next Cycle without outcome.
                    last_bridge = getattr(self, "_last_bridge_result", None)
                    if last_bridge is not None and last_decision is not None:
                        self._log_post_ai_execution_chain(
                            decision=last_decision,
                            bridge_result=last_bridge,
                            execution_enabled=bool(
                                getattr(_gs(), "execution_enabled", False)
                            ),
                            force_shadow=False,
                        )
                    elif getattr(last, "abort_reason", None):
                        logger.warning(
                            "Rejected because: %s",
                            getattr(last, "abort_reason", None),
                        )
                    logger.warning(
                        "Execution State",
                        run_state=self.plane.auto_trading_run_state,
                        outcome=getattr(last, "cycle_outcome", None),
                        abort=getattr(last, "abort_reason", None),
                        forwarded_to_oms=getattr(last, "forwarded_to_oms", False),
                    )
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
                try:
                    from app.application.services.cycle_evidence import (
                        record_cycle_evidence,
                    )

                    record_cycle_evidence(
                        cycle_outcome="error",
                        decision_action="NO_TRADE",
                        reasons=[f"cycle exception: {exc}"],
                        abort_reason="CYCLE_EXCEPTION",
                    )
                except Exception:
                    logger.exception("cycle_evidence_exception_record_failed")
                try:
                    from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                        ValidationStage,
                        finalize as pvm_finalize,
                        stage as pvm_stage,
                    )

                    pvm_stage(
                        ValidationStage.SCHEDULER,
                        ok=False,
                        reason=f"cycle exception: {exc}",
                        validation_id=_pvm_vid,
                    )
                    pvm_finalize(validation_id=_pvm_vid)
                except Exception:
                    logger.exception("pvm_cycle_exception_finalize_failed")
                # Never stop the autonomous engine — self-heal and continue scanning.
                logger.warning(
                    "Autonomous engine continuing after cycle error",
                    error=str(exc),
                    run_state=self.plane.auto_trading_run_state,
                )
            finally:
                try:
                    if _pvm_token is not None:
                        from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                            get_production_validation_recorder as _pvm_rec_end,
                        )

                        _pvm_rec_end().unbind_context(_pvm_token)
                except Exception:
                    logger.exception("pvm_unbind_orchestrator_cycle_failed")
            logger.warning(
                "Waiting Next Cycle",
                interval_seconds=self.interval_seconds,
                cycle_ms=round((time.perf_counter() - cycle_t0) * 1000.0, 1),
            )
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
    interval_seconds: float = 5.0,
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

    submit_port: Any = RetryingOmsSubmitPort(guarded_submit, on_retry=_on_oms_retry)

    config = ExecutionBridgeConfig(mode=ExecutionMode.SHADOW)
    execution = InstitutionalExecutionIntegration.create(
        submit_port, config=config, hydrate_hashes=True
    )
    execution.bridge.bind_ops(plane, reliability=reliability)

    pme = InstitutionalPositionManagement.create(guarded_manage, ops_plane=plane)

    probes = LiveProbeCollector(
        settings=settings, mt5_adapter=mt5_adapter, supabase=supabase
    )
    runtime = InstitutionalIteRuntime(
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
    # Plane defaults to scalping — PME must inherit BE@0.5R / partial / trail knobs
    # at bootstrap (ops apply_trading_mode is not required for LIVE loop).
    try:
        from app.application.services.ai_scalping_mode import (
            apply_trading_mode_to_runtime,
        )

        mode = str(getattr(plane, "trading_mode", "scalping") or "scalping")
        apply_trading_mode_to_runtime(runtime, mode=mode)
    except Exception:
        logger.exception("ite_runtime_bootstrap_trading_mode_failed")
    return runtime


_RUNTIME: InstitutionalIteRuntime | None = None
_RUNTIME_LOCK = Lock()


def get_ite_runtime() -> InstitutionalIteRuntime | None:
    with _RUNTIME_LOCK:
        return _RUNTIME


def set_ite_runtime(runtime: InstitutionalIteRuntime | None) -> None:
    global _RUNTIME
    with _RUNTIME_LOCK:
        _RUNTIME = runtime
