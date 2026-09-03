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
from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    coerce_spread_value,
    safety_evaluation_symbol,
)
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


def _merge_cycle_diagnostics(
    ctx_diag: dict[str, Any] | None,
    cycle_diag: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep execution artefacts written during the cycle.

    Overwriting with the pre-cycle market-context dict dropped
    execution_contract / optimizer / EXECUTION_BLOCKED (silent TAKE stall).
    """
    merged = dict(ctx_diag or {})
    extra = dict(cycle_diag or {})
    merged.update(extra)
    return merged


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
    trade_class: str | None = None
    position_plan: dict[str, Any] | None = None
    stage_timings_ms: dict[str, Any] | None = None
    decision_cycle_latency_ms: float | None = None
    execution_blocked: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        diag = self.market_context_diagnostics
        if not isinstance(diag, dict):
            diag = {}
        from app.domain.institutional_trading.operations.min_lot_feasibility import (
            classify_cycle_execution_status,
        )

        execution_status = classify_cycle_execution_status(
            abort_reason=self.abort_reason,
            cycle_outcome=self.cycle_outcome,
            forwarded_to_oms=self.forwarded_to_oms,
            mt5_ticket=self.mt5_ticket,
            tradeability=diag.get("tradeability"),
        )
        ticket = self.mt5_ticket
        no_ticket = ticket in (None, "", 0, "0")
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
            "trade_class": self.trade_class,
            "position_plan": self.position_plan,
            "stage_timings_ms": self.stage_timings_ms,
            "decision_cycle_latency_ms": self.decision_cycle_latency_ms,
            "execute_now_required": False,
            "execution_blocked": dict(self.execution_blocked)
            if self.execution_blocked
            else None,
            "execution_handoff": (
                dict((self.market_context_diagnostics or {}).get("execution_handoff"))
                if isinstance(
                    (self.market_context_diagnostics or {}).get("execution_handoff"),
                    dict,
                )
                else None
            ),
            "tradeability": diag.get("tradeability"),
            "tradeability_reason": diag.get("tradeability_reason"),
            "execution_status": execution_status,
            "symbol": (
                str(diag.get("symbol") or "").strip()
                or str(diag.get("focus_symbol") or "").strip()
                or None
            ),
            "strategy_signal": self.decision_action,
            "estimated_risk_at_min_lot": diag.get("estimated_risk_at_min_lot"),
            "maximum_tradeable_stop_distance": diag.get(
                "maximum_tradeable_stop_distance"
            ),
            "broker_ticket": ticket if not no_ticket else None,
            "order_attempt": bool(self.forwarded_to_oms),
            "execution_result": (
                "BROKER_TICKET"
                if not no_ticket
                else "NO BROKER ORDER WAS SUBMITTED"
            ),
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
    _last_pick_abort: str | None = field(default=None, repr=False)
    _eligible_handoff_queue: list[str] = field(default_factory=list, repr=False)
    _eligible_consumed: set[str] = field(default_factory=set, repr=False)
    _entries_this_scan: int = field(default=0, repr=False)
    _manual_execution: bool = field(default=False, repr=False)
    _cycles: int = 0
    _started_mono: float = field(default_factory=time.monotonic, repr=False)
    _last_cycle_finished_mono: float = field(default=0.0, repr=False)
    _cycle_started_mono: float = field(default=0.0, repr=False)
    _last_successful_cycle_mono: float = field(default=0.0, repr=False)
    _last_successful_cycle_at: str | None = field(default=None, repr=False)
    _last_cycle_at: str | None = field(default=None, repr=False)
    _last_session_obs: dict[str, Any] | None = field(default=None, repr=False)
    _recovery_orders_blocked: bool = field(default=False, repr=False)
    _watchdog_restarts: int = field(default=0, repr=False)
    _watchdog_state: str = field(default="IDLE", repr=False)
    _watchdog_restart_reason: str | None = field(default=None, repr=False)
    _last_failure: str | None = field(default=None, repr=False)
    _cycle_started_at: str | None = field(default=None, repr=False)
    _last_cycle_duration_ms: float | None = field(default=None, repr=False)
    user_id: UUID = field(default_factory=uuid4)

    def _clear_ephemeral_cycle_state(self) -> None:
        """Drop in-cycle tickets/bridge results. Never invents the next signal."""
        with self._lock:
            self._last_bridge_result = None

    def _release_non_entry_slot(self) -> None:
        """WAIT / missing snapshot is not a filled entry — keep the handoff queue.

        ``max_entries_per_cycle`` counts OMS-bound entries, not data failures.
        """
        with self._lock:
            if self._entries_this_scan > 0:
                self._entries_this_scan -= 1

    def _emit_telegram_cycle(self, result: ShadowCycleResult) -> None:
        """Post-cycle observability only. Never raises into the trading path."""
        try:
            from app.application.services.telegram_dispatcher import notify_cycle

            notify_cycle(
                result,
                decision=self._last_decision,
                bridge=self._last_bridge_result,
                pipeline=self.decision_pipeline,
            )
        except Exception:
            logger.exception("telegram_cycle_notify_failed")

    def _gold_exec_symbol(self, snapshot: Any) -> str:
        from app.domain.trading.gold_only import canonical_gold_execution_symbol

        raw = str(getattr(snapshot, "symbol", "") or "")
        return canonical_gold_execution_symbol(raw or None)

    def _safety_cycle_diagnostics(
        self,
        *,
        snapshot: Any,
        safety: Any,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Attach symbol + spread facts to Safety diagnostics. Never fabricates."""
        from app.domain.institutional_trading.auto_trading import coerce_spread_value

        symbol = safety_evaluation_symbol(getattr(snapshot, "symbol", None))
        raw_spread = coerce_spread_value(getattr(snapshot, "spread", None))
        diag: dict[str, Any] = {
            "symbol": symbol or None,
            "safety_scope": getattr(safety, "failure_scope", None),
            "safety_failed_reasons": list(getattr(safety, "failed_reasons", ()) or ()),
            "spread": str(raw_spread) if raw_spread is not None else None,
        }
        spread_d = getattr(safety, "spread_diagnostics", None)
        if isinstance(spread_d, dict):
            diag["spread_raw"] = spread_d.get("spread_raw")
            diag["spread_normalized"] = spread_d.get("spread_normalized")
            diag["spread_limit"] = spread_d.get("spread_limit")
            diag["spread_unit"] = spread_d.get("spread_unit")
            diag["spread_asset_class"] = spread_d.get("asset_class")
            diag["spread_scope"] = spread_d.get("spread_scope") or "symbol"
            if diag.get("spread") is None and spread_d.get("spread_raw"):
                diag["spread"] = spread_d.get("spread_raw")
            if not diag.get("symbol") and spread_d.get("symbol"):
                diag["symbol"] = spread_d.get("symbol")
        if extra:
            diag.update(extra)
        return diag

    def mark_cycle_finished(self, *, successful: bool) -> None:
        """A finished tick (including WAITING_SESSION manage-only) is not a stall."""
        now = time.monotonic()
        wall = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._lock:
            self._last_cycle_finished_mono = now
            self._cycle_started_mono = 0.0
            self._last_cycle_at = wall
            if successful:
                self._last_successful_cycle_mono = now
                self._last_successful_cycle_at = wall
                self._recovery_orders_blocked = False
                self._last_failure = None
            else:
                self._last_failure = "cycle_unsuccessful"

    def note_scheduler_stalled(self) -> bool:
        from app.domain.institutional_trading.operations.worker_runtime_state import (
            SCHEDULER_STALLED,
            scheduler_is_stalled,
        )

        with self._lock:
            stalled = scheduler_is_stalled(
                last_cycle_finished_mono=self._last_cycle_finished_mono,
                now_mono=time.monotonic(),
                interval_seconds=self.interval_seconds,
                started_mono=self._started_mono,
                running=not self._stop.is_set(),
                cycle_started_mono=self._cycle_started_mono,
            )
            if stalled:
                self._recovery_orders_blocked = True
                self._last_failure = "SCHEDULER_STALLED"
        if stalled:
            logger.error(
                SCHEDULER_STALLED,
                interval_seconds=self.interval_seconds,
                cycles=self._cycles,
            )
            try:
                from app.domain.institutional_trading.ai_scalping.continuous_operation import (  # noqa: E501
                    get_continuous_operation_controller,
                )

                get_continuous_operation_controller().heal_dependencies(
                    gateway_ok=False,
                    mt5_ok=False,
                    oms_ok=True,
                    feed_ok=True,
                )
            except Exception:
                logger.exception("scheduler_stalled_heal_failed")
        return stalled

    def tick_health(self) -> dict[str, Any]:
        """Live probes → ReliabilityPlatform.tick (no POST body flags)."""
        # Trading-cycle health: Gateway/MT5/OMS only. Railway/Supabase/Cloudflare
        # HTTP self-probes are advisory and must not add 3–5s to every tick.
        probes = self.probes.collect(include_platform_probes=False)
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
        try:
            from app.application.services.telegram_dispatcher import (
                notify_connectivity,
            )

            notify_connectivity(
                mt5_connected=bool(probes.mt5_connected),
                gateway_available=bool(probes.gateway_available),
            )
        except Exception:
            logger.exception("telegram_connectivity_hook_failed")
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

                    from app.domain.trading.gold_only import (
                        autonomous_execution_symbols,
                        gold_only_enabled,
                    )

                    universe = (
                        autonomous_execution_symbols()
                        if gold_only_enabled()
                        else DEFAULT_SCALPING_UNIVERSE
                    )
                    for sym in universe:
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
        at_known = bool(
            (market_context_diagnostics or {}).get("mt5_autotrading_known", True)
        )
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
                    mt5_autotrading_known=at_known,
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
                self._last_bridge_result = None
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
        from app.application.services.market_closed_cooldown import (
            is_market_closed_cooled,
        )
        from app.domain.institutional_trading.operations.broker_session_truth import (
            SESSION_CLOSE_DETECTED,
            apply_session_close_side_effects,
            apply_session_open_side_effects,
            note_broker_session,
            overlay_snapshot_session,
            resolve_from_diagnostics,
        )

        diag_in = dict(market_context_diagnostics or {})
        session_obs = resolve_from_diagnostics(
            diag_in,
            utc_session=session_val,
            symbol_tradable=symbol_tradable,
            market_data_live=bool(market_data_live),
            cooled=is_market_closed_cooled(
                str(getattr(snapshot, "symbol", "") or "")
            ),
        )
        snapshot = overlay_snapshot_session(
            snapshot, broker_open=session_obs.broker_session_open
        )
        open_event = note_broker_session(session_obs.broker_session_open)
        apply_session_open_side_effects(
            symbol=self._gold_exec_symbol(snapshot),
            event=open_event,
        )
        apply_session_close_side_effects(
            symbol=self._gold_exec_symbol(snapshot),
            event=open_event,
        )
        self._last_session_obs = session_obs.to_dict()
        logger.warning(
            "session_truth",
            **session_obs.to_dict(),
            open_event=open_event,
            close_event=(
                open_event if open_event == SESSION_CLOSE_DETECTED else None
            ),
        )
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
                symbol=self._gold_exec_symbol(snapshot),
                internal_positions=prior_internal,
                position_engine=self.position_management.engine,
                fresh=False,
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

        cycle_daily_loss = bool(self.plane.daily_loss_exceeded)
        daily_pnl_verified = (
            diag_in.get("daily_pnl_fail_closed") is not True
            and diag_in.get("daily_pnl_trusted") is True
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
                mt5_autotrading_known=at_known,
                symbol=safety_evaluation_symbol(getattr(snapshot, "symbol", None)),
                symbol_tradable=symbol_tradable,
                margin_available=margin_ok,
                no_broker_restrictions=no_broker_restrictions,
                open_positions=account.open_positions,
                session=session_val,
                broker_session_open=session_obs.broker_session_open,
                session_source=session_obs.session_source,
                spread=coerce_spread_value(
                    getattr(snapshot, "spread", None)
                ),
                news_blocked=bool(news.blocked),
                news_reason=str(news.reason or ""),
                daily_loss_exceeded=cycle_daily_loss,
                daily_pnl_verified=daily_pnl_verified,
                deposit_verification=str(diag_in.get("deposit_verification") or ""),
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
                        symbol=self._gold_exec_symbol(snapshot),
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
                            mt5_autotrading_known=at_known,
                            symbol=safety_evaluation_symbol(
                                getattr(snapshot, "symbol", None)
                            ),
                            symbol_tradable=symbol_tradable,
                            margin_available=margin_ok,
                            no_broker_restrictions=no_broker_restrictions,
                            open_positions=account.open_positions,
                            session=session_val,
                            broker_session_open=session_obs.broker_session_open,
                            session_source=session_obs.session_source,
                            spread=coerce_spread_value(
                        getattr(snapshot, "spread", None)
                    ),
                            news_blocked=bool(news.blocked),
                            news_reason=str(news.reason or ""),
                            daily_loss_exceeded=cycle_daily_loss,
                            daily_pnl_verified=daily_pnl_verified,
                            deposit_verification=str(
                                diag_in.get("deposit_verification") or ""
                            ),
                            emergency_stop=self.plane.kill_switch_armed,
                            ops_mode=self.plane.mode.value,
                            execution_enabled=execution_on,
                        )
                    )
                except Exception:
                    logger.exception("force_sync_before_max_open_reject_failed")

        if self._recovery_orders_blocked:
            try:
                self._sync_and_manage_open_positions(
                    snapshot=snapshot,
                    account=account,
                    reason="scheduler_stalled_recovery_manage",
                )
            except Exception:
                logger.exception("recovery_manage_failed")
            result = ShadowCycleResult(
                ok=True,
                trace_id=None,
                mode=self.plane.mode.value,
                detail="SCHEDULER_STALLED recovery — new entries blocked, no order_send",
                health=health.get("health") if isinstance(health, dict) else None,
                cycle_outcome="recovering",
                abort_reason="RECOVERING",
                snapshot_present=True,
            )
            with self._lock:
                self._last_cycle = result
                self._cycles += 1
                self._last_bridge_result = None
            logger.warning(
                "recovery_new_entries_blocked",
                reason="SCHEDULER_STALLED recovery — no order mutation",
            )
            return result

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
                # Entry blocked — still manage open MT5 positions.
                try:
                    self._sync_and_manage_open_positions(
                        snapshot=snapshot,
                        account=account,
                        reason="safety_blocked_manage",
                    )
                except Exception:
                    logger.exception("safety_blocked_manage_failed")
                from app.domain.institutional_trading.auto_trading import (
                    safety_blocks_decision,
                    safety_failure_scope,
                )

                scope = safety_failure_scope(safety)
                if scope == "scan_continue":
                    logger.warning(
                        "risk_lock_scan_continues",
                        reasons=list(safety.failed_reasons),
                        daily_loss=bool(self.plane.daily_loss_exceeded),
                    )
                elif scope == "symbol" or safety_blocks_decision(safety):
                    symbol_skip = scope == "symbol"
                    safety_diag = self._safety_cycle_diagnostics(
                        snapshot=snapshot,
                        safety=safety,
                    )
                    result = ShadowCycleResult(
                        ok=True,
                        trace_id=None,
                        mode=self.plane.mode.value,
                        detail="; ".join(safety.failed_reasons)
                        or "Auto Trading Disabled",
                        health=health.get("health")
                        if isinstance(health, dict)
                        else None,
                        cycle_outcome="safety_blocked",
                        abort_reason="SAFETY_BLOCKED",
                        safety_failed_reasons=tuple(safety.failed_reasons),
                        snapshot_present=True,
                        market_context_diagnostics=safety_diag,
                    )
                    with self._lock:
                        self._last_cycle = result
                        self._cycles += 1
                        self._last_bridge_result = None
                    primary = (
                        safety.failed_reasons[0]
                        if safety.failed_reasons
                        else "SAFETY_BLOCKED"
                    )
                    logger.warning(
                        "execution_path_step",
                        step="Safety",
                        result="FAIL",
                        abort_reason="SAFETY_BLOCKED",
                        primary_blocker=primary,
                        reasons=list(result.safety_failed_reasons),
                        gateway=gw,
                        broker=mt5,
                        execution_enabled=execution_on,
                        mt5_autotrading_enabled=mt5_autotrading_enabled,
                        forwarded_to_oms=False,
                    )
                    logger.warning(
                        "execution_first_blocking_gate",
                        gate="SAFETY",
                        reason=primary,
                        safety_scope=scope,
                        symbol=safety_diag.get("symbol")
                        or getattr(account, "symbol", None)
                        or getattr(snapshot, "symbol", None),
                        forwarded_to_oms=False,
                    )
                    try:
                        from app.domain.institutional_trading.production_hardening.lifecycle import (
                            get_lifecycle_store,
                        )

                        get_lifecycle_store().record(
                            stage="FIRST_BLOCKING_GATE",
                            status="failed",
                            detail=f"SAFETY: {primary}",
                            symbol=str(
                                safety_diag.get("symbol")
                                or getattr(account, "symbol", None)
                                or getattr(snapshot, "symbol", None)
                                or ""
                            )
                            or None,
                        )
                    except Exception:
                        logger.exception("first_blocking_gate_lifecycle_failed")
                    logger.info(
                        "ite_cycle_outcome",
                        outcome=result.cycle_outcome,
                        reasons=list(result.safety_failed_reasons),
                        mode=result.mode,
                        pme_positions=len(
                            getattr(
                                self.position_management.engine, "_positions", {}
                            )
                            or {}
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
                            market_context_diagnostics=safety_diag,
                            signal_id=None,
                            forwarded_to_oms=False,
                            trace_id=None,
                        )
                    except Exception:
                        logger.exception("strategy_diagnostics_safety_blocked_failed")
                    self._emit_telegram_cycle(result)
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
                    if symbol_skip:
                        self._release_non_entry_slot()
                        try:
                            from app.domain.institutional_trading.operations.fast_decision_path import (  # noqa: E501
                                set_focus,
                            )

                            # Symbol-scoped Safety miss must not keep hysteresis
                            # focus. Next cycle may take the next eligible desk.
                            set_focus(None, reason="SYMBOL_SAFETY_RELEASE")
                        except Exception:
                            logger.exception("symbol_safety_focus_release_failed")
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

    def _protect_open_positions(self, *, reason: str) -> None:
        """Keep SL/TP/breakeven work off the scan critical path.

        Never submits a new order. Uses cached cycle context when present.
        """
        snapshot = None
        account = None
        open_syms: list[str] = []
        try:
            from app.application.services.ite_cycle_market_context import (
                peek_cycle_market_context,
            )
            from app.domain.trading.gold_only import GOLD_SYMBOL

            try:
                open_syms = [
                    str(getattr(p, "symbol", "") or "")
                    for p in (
                        getattr(self.position_management.engine, "_positions", {})
                        or {}
                    ).values()
                ]
            except Exception:
                open_syms = []
            for sym in [*open_syms, GOLD_SYMBOL]:
                ctx = peek_cycle_market_context(sym)
                if ctx is not None and ctx.ok and ctx.snapshot is not None:
                    snapshot = ctx.snapshot
                    account = ctx.account
                    break
        except Exception:
            logger.exception("cycle_protect_peek_context_failed")
        if snapshot is not None and account is not None:
            self._sync_and_manage_open_positions(
                snapshot=snapshot,
                account=account,
                reason=reason,
            )
            return
        try:
            from app.domain.institutional_trading.production_hardening.position_recovery import (  # noqa: E501
                recover_positions_from_mt5,
            )
            from app.domain.trading.gold_only import GOLD_SYMBOL

            recover_syms: list[str] = []
            seen: set[str] = set()
            for raw in [*open_syms, GOLD_SYMBOL]:
                key = str(raw or "").strip().upper()
                if not key or key in seen:
                    continue
                seen.add(key)
                recover_syms.append(str(raw).strip())
            if self.mt5_adapter is not None:
                for sym in recover_syms:
                    recover_positions_from_mt5(
                        mt5_adapter=self.mt5_adapter,
                        engine=self.position_management.engine,
                        symbol=sym,
                    )
        except Exception:
            logger.exception("cycle_protect_position_recovery_failed")

    def _manage_open_positions_after_timeout(self) -> None:
        """PME must not starve when the scan overruns the cycle budget."""
        self._protect_open_positions(reason="cycle_timeout_manage")

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
        symbol = self._gold_exec_symbol(snapshot)
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
                # Repair understated 1R from bad PME snapshot (inflates R / skips BE).
                # Never treat a profit-side (already-BE) broker SL as the original 1R.
                try:
                    broker_sl = Decimal(
                        str(
                            getattr(live, "stop_loss", 0)
                            or getattr(live, "sl", 0)
                            or 0
                        )
                    )
                    entry_px = Decimal(str(getattr(pos, "entry_price", 0) or 0))
                    side_l = str(getattr(pos, "side", "") or "").lower()
                    if broker_sl > 0 and entry_px > 0:
                        be_on_broker = (side_l == "sell" and broker_sl < entry_px) or (
                            side_l == "buy" and broker_sl > entry_px
                        )
                        if be_on_broker:
                            if not bool(getattr(pos, "be_moved", False)):
                                pos.be_moved = True
                                from app.domain.institutional_trading.management.models import (
                                    PositionLifecycleState,
                                )

                                if getattr(pos, "state", None) is PositionLifecycleState.OPEN:
                                    pos.state = PositionLifecycleState.BE_MOVED
                                logger.warning(
                                    "pme_be_detected_on_broker",
                                    ticket=ticket,
                                    broker_sl=str(broker_sl),
                                    entry=str(entry_px),
                                )
                        else:
                            broker_risk = abs(entry_px - broker_sl)
                            cur_risk = Decimal(
                                str(getattr(pos, "risk_distance", 0) or 0)
                            )
                            if broker_risk > cur_risk * Decimal("1.2"):
                                logger.warning(
                                    "pme_risk_distance_repaired",
                                    ticket=ticket,
                                    old_risk=str(cur_risk),
                                    new_risk=str(broker_risk),
                                    broker_sl=str(broker_sl),
                                )
                                pos.risk_distance = broker_risk
                                pos.initial_stop = broker_sl
                except Exception:
                    logger.exception("pme_risk_distance_repair_failed", ticket=ticket)
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
                spread=coerce_spread_value(
                    getattr(snapshot, "spread", None)
                ),
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
                from app.application.services.telegram_dispatcher import notify_pme

                notify_pme(result, current_price=current_px)
            except Exception:
                logger.exception("telegram_pme_hook_failed")
            # Phase B — live MAE/MFE mark (observe-only; never changes PME action)
            try:
                from app.domain.institutional_trading.phase_b import get_phase_b_plane

                pb = get_phase_b_plane()
                tid = str(ticket)
                if tid not in pb.mae_mfe.open:
                    entry = float(getattr(pos, "entry_price", 0) or 0)
                    stop = float(
                        getattr(pos, "current_stop", 0)
                        or getattr(pos, "initial_stop", 0)
                        or 0
                    ) or None
                    if entry > 0:
                        pb.mae_mfe.observe_entry(
                            trade_id=tid,
                            symbol=str(getattr(pos, "symbol", "") or ""),
                            strategy="live",
                            direction=str(
                                getattr(pos, "side", None)
                                or getattr(pos, "direction", "")
                                or ""
                            ),
                            entry_price=entry,
                            initial_stop=stop,
                            initial_target=float(
                                getattr(pos, "current_tp", 0) or 0
                            )
                            or None,
                        )
                mark = float(current_px) if current_px is not None else None
                pb.mae_mfe.observe_mark(tid, mark_price=mark)
                # Seed MFE from PME max_favorable_r when available
                mfr = getattr(pos, "max_favorable_r", None)
                rec = pb.mae_mfe.open.get(tid)
                if rec is not None and mfr is not None and rec.mfe_r is None:
                    try:
                        rec.mfe_r = float(mfr)
                    except Exception:
                        pass
            except Exception:
                logger.exception("phase_b_mae_mfe_mark_failed")
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
                    plan_reason = str(
                        getattr(getattr(result, "record", None), "reason", "")
                        or getattr(result, "reason", "")
                        or ""
                    )
                    logger.warning(
                        "Position Managed",
                        ticket=ticket,
                        action=str(action_v),
                        reason=reason,
                        mid=str(current_px),
                        plan_reason=plan_reason,
                    )
                    act = str(action_v).lower()
                    if act in {"break_even", "break-even"}:
                        logger.warning(
                            "BREAK_EVEN",
                            ticket=ticket,
                            mid=str(current_px),
                            plan_reason=plan_reason,
                        )
                    elif act in {"partial_close", "partial"}:
                        logger.warning(
                            "PARTIAL_TP",
                            ticket=ticket,
                            mid=str(current_px),
                            plan_reason=plan_reason,
                        )
                    elif act in {"trail", "trailing"}:
                        logger.warning(
                            "TRAILING",
                            ticket=ticket,
                            mid=str(current_px),
                            plan_reason=plan_reason,
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
                        # Phase B — observe-only post-trade / MAE-MFE close
                        try:
                            from app.domain.institutional_trading.phase_b import (
                                get_phase_b_plane,
                            )

                            pb = get_phase_b_plane()
                            tid = str(ticket)
                            exit_px = None
                            try:
                                exit_px = float(
                                    getattr(pos, "exit_price", None)
                                    or getattr(account, "mid_price", None)
                                    or 0
                                ) or None
                            except Exception:
                                exit_px = None
                            closed = pb.mae_mfe.observe_close(
                                tid,
                                exit_price=exit_px,
                                exit_reason=str(
                                    _close_reason or reason or "closed"
                                ),
                            )
                            rr = None
                            if closed and closed.realized_r is not None:
                                rr = closed.realized_r
                            elif getattr(pos, "r_multiple", None) is not None:
                                try:
                                    rr = float(pos.r_multiple)
                                except Exception:
                                    rr = None
                            pb.post_trade.record(
                                trade_id=tid,
                                symbol=str(getattr(pos, "symbol", "") or ""),
                                realized_r=rr,
                                mae_r=closed.final_mae_r if closed else None,
                                mfe_r=closed.final_mfe_r if closed else None,
                                holding_time=(
                                    closed.holding_time_s if closed else None
                                ),
                                exit_reason=str(
                                    _close_reason or reason or "closed"
                                ),
                                entry_risk=(
                                    closed.risk_distance if closed else None
                                ),
                            )
                            pb.matrix.record(
                                strategy=str(
                                    ai_d.get("strategy")
                                    or ai_d.get("setup_family")
                                    or "scalping"
                                ),
                                symbol=str(getattr(pos, "symbol", "") or ""),
                                regime=str(
                                    (pb.last_regime or {}).get("operational_regime")
                                    or ai_d.get("market_regime")
                                    or ai_d.get("regime")
                                    or "UNKNOWN"
                                ),
                                session=str(trade_rec.session or ""),
                                direction=direction,
                                realized_r=rr,
                                win=bool(pnl_f > 0),
                                mae_r=closed.final_mae_r if closed else None,
                                mfe_r=closed.final_mfe_r if closed else None,
                            )
                            pb.parity.record_live(
                                strategy=str(
                                    ai_d.get("strategy")
                                    or ai_d.get("setup_family")
                                    or "ALL"
                                ),
                                realized_r=rr,
                                win=bool(pnl_f > 0),
                                mae_r=closed.final_mae_r if closed else None,
                                mfe_r=closed.final_mfe_r if closed else None,
                                holding_time_s=(
                                    closed.holding_time_s if closed else None
                                ),
                            )
                            pb.model_monitor.observe(
                                confidence=float(
                                    ai_d.get("ai_confidence")
                                    or ai_d.get("confidence")
                                    or 0
                                )
                                or None,
                                quality=float(
                                    ai_d.get("trade_quality")
                                    or ai_d.get("quality")
                                    or 0
                                )
                                or None,
                                signal=direction,
                                realized_r=rr,
                            )
                            pb.observe_regime(
                                str(
                                    ai_d.get("market_regime")
                                    or ai_d.get("regime")
                                    or ""
                                )
                                or None
                            )
                        except Exception:
                            logger.exception("phase_b_post_close_observe_failed")
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
                            try:
                                from app.domain.institutional_trading.ai_scalping.daily_opportunity_target import (  # noqa: E501
                                    ClosedTradeRecord,
                                    get_daily_opportunity_tracker,
                                )
                                from app.domain.institutional_trading.ai_scalping.same_symbol_requalification import (  # noqa: E501
                                    fingerprint_from_snapshot,
                                )
                                from app.domain.institutional_trading.ai_scalping.symbol_state import (  # noqa: E501
                                    get_symbol_state_book,
                                )

                                _ai = getattr(
                                    self.decision_pipeline, "_last_ai_score", None
                                )
                                _ai_d = _ai if isinstance(_ai, dict) else {}
                                closed_sym = str(
                                    getattr(pos, "symbol", "")
                                    or getattr(snapshot, "symbol", "")
                                    or ""
                                ).upper()
                                if closed_sym:
                                    fp = fingerprint_from_snapshot(
                                        snapshot,
                                        direction=str(
                                            getattr(pos, "side", None)
                                            or getattr(pos, "direction", None)
                                            or ""
                                        ),
                                        setup_family=(
                                            str(_ai_d.get("setup_family") or "")
                                            or None
                                        ),
                                        opportunity_score=_ai_d.get(
                                            "opportunity_score"
                                        ),
                                        regime=str(
                                            _ai_d.get("market_regime")
                                            or _ai_d.get("regime")
                                            or ""
                                        )
                                        or None,
                                    )
                                    pnl_close = float(
                                        getattr(pos, "realized_pnl", None)
                                        or getattr(pos, "profit", None)
                                        or 0.0
                                    )
                                    get_symbol_state_book().note_closed(
                                        closed_sym,
                                        pnl=pnl_close,
                                        fingerprint=fp,
                                    )
                                # Opportunity target: close stats (observe only).
                                try:
                                    pnl = float(
                                        getattr(pos, "realized_pnl", None)
                                        or getattr(pos, "profit", None)
                                        or 0.0
                                    )
                                    r_mult = float(
                                        getattr(pos, "r_multiple", None) or 0.0
                                    )
                                    hold_m = float(
                                        getattr(pos, "holding_time_minutes", None) or 0.0
                                    )
                                    get_daily_opportunity_tracker(
                                        target_trades_per_day=int(
                                            getattr(
                                                DEFAULT_AI_SCALPING_CONFIG,
                                                "target_trades_per_day",
                                                3,
                                            )
                                            or 3
                                        )
                                    ).note_trade_closed(
                                        ClosedTradeRecord(
                                            symbol=closed_sym or "",
                                            strategy=str(
                                                getattr(
                                                    self.plane, "trading_mode", "swing"
                                                )
                                                or "swing"
                                            ),
                                            session="",
                                            market_regime=str(
                                                _ai_d.get("market_regime")
                                                or _ai_d.get("regime")
                                                or ""
                                            ),
                                            realized_pnl=pnl,
                                            risk_pct_at_entry=0.0,
                                            equity_at_exit=0.0,
                                            realized_r=r_mult,
                                            expected_r=0.0,
                                            holding_seconds=hold_m * 60.0,
                                            exit_reason=str(
                                                _close_reason or reason or "closed"
                                            ),
                                            won=pnl > 0,
                                            closed_at=datetime.now(UTC).isoformat(),
                                        )
                                    )
                                    try:
                                        from app.application.services.strategy_performance_telemetry import (  # noqa: E501
                                            get_strategy_performance_telemetry,
                                        )

                                        _tel = get_strategy_performance_telemetry()
                                        _tel.observe_close(
                                            ticket=ticket,
                                            exit_price=getattr(pos, "exit_price", None),
                                            realized_pnl=pnl,
                                            realized_r=r_mult,
                                            exit_reason=str(
                                                _close_reason or reason or "closed"
                                            ),
                                            hold_seconds=hold_m * 60.0,
                                        )
                                    except Exception:
                                        logger.exception(
                                            "strategy_performance_close_observe_failed"
                                        )
                                except Exception:
                                    logger.exception(
                                        "daily_opportunity_target_close_record_failed"
                                    )
                                # Invalidate handoff queue — force full parallel rescan
                                with self._lock:
                                    self._eligible_handoff_queue = []
                                    self._eligible_consumed = set()
                                    self._entries_this_scan = 0
                                logger.warning(
                                    "Immediate Rescan armed after Position Closed",
                                    symbol=closed_sym,
                                    ticket=ticket,
                                )
                                try:
                                    from app.application.services.mt5_position_truth import (
                                        _invalidate_adapter_position_cache,
                                    )

                                    _invalidate_adapter_position_cache(self.mt5_adapter)
                                except Exception:
                                    logger.exception(
                                        "position_close_cache_invalidate_failed"
                                    )
                                try:
                                    from app.domain.institutional_trading.operations.decision_cycle import (  # noqa: E501
                                        note_cycle_event,
                                    )

                                    note_cycle_event("position_close")
                                except Exception:
                                    logger.exception("position_close_wakeup_failed")
                            except Exception:
                                logger.exception(
                                    "post_close_cooldown_symbol_clear_failed"
                                )
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

    def _submit_same_cycle_batch(
        self,
        *,
        decision: Any,
        ctx: Any,
        tid: str,
        contract: Any,
        snapshot: Any,
        account: Any,
        diagnostics: dict[str, Any],
        signal_t0: float,
    ) -> tuple[Any, dict[str, Any]]:
        """One thesis → one plan → existing OMS handle per authorized leg."""
        import time as _time
        from dataclasses import replace as _dc_replace
        from decimal import Decimal as _Dec

        from app.domain.institutional_trading.operations.batch_execution import (
            submit_position_plan_batch,
        )
        from app.domain.institutional_trading.operations.decision_cycle import (
            build_authoritative_snapshot,
            note_opportunity_change,
            stale_authorization,
        )
        from app.domain.institutional_trading.operations.position_plan import (
            build_position_plan,
        )

        ai = getattr(self.decision_pipeline, "_last_ai_score", None)
        ai = ai if isinstance(ai, dict) else {}
        from app.domain.institutional_trading.management.class_policy import (
            remember_fill_metadata,
        )
        from app.domain.institutional_trading.operations.trade_classifier import (
            TradeClass,
        )

        raw_class = str(getattr(contract, "trade_class", "") or "").upper()
        trade_class = (
            raw_class
            if raw_class in {TradeClass.SCALP.value, TradeClass.HOLD.value}
            else str(TradeClass.NO_TRADE.value)
        )
        score = int(
            getattr(contract, "opportunity_score", None)
            or ai.get("opportunity_score")
            or 0
        )
        direction = str(
            getattr(contract, "direction", None)
            or getattr(getattr(decision, "direction", None), "value", None)
            or "NONE"
        )
        qf_count = int(getattr(account, "open_positions", 0) or 0)
        try:
            engine = getattr(getattr(self, "position_management", None), "engine", None)
            if self.mt5_adapter is not None:
                from app.application.services.mt5_position_truth import (
                    apply_mt5_position_truth,
                    force_sync_positions,
                )
                from app.domain.trading.gold_only import GOLD_SYMBOL

                sync = force_sync_positions(
                    self.mt5_adapter,
                    symbol=str(getattr(snapshot, "symbol", "") or GOLD_SYMBOL),
                    position_engine=engine,
                )
                account = apply_mt5_position_truth(account, sync)
                qf_count = int(getattr(account, "open_positions", 0) or 0)
                if hasattr(ctx, "__dataclass_fields__"):
                    ctx = _dc_replace(ctx, account=account)
        except Exception:
            qf_count = int(getattr(account, "open_positions", 0) or 0)
        snap = build_authoritative_snapshot(
            cycle_id=diagnostics.get("cycle_id")
            or getattr(contract, "cycle_id", None),
            snapshot_id=diagnostics.get("snapshot_id")
            or getattr(contract, "snapshot_id", None),
            snapshot=snapshot,
            account=account,
            diagnostics=diagnostics,
            opportunity={
                **ai,
                "opportunity_score": score,
                "direction": direction,
                "confidence": getattr(contract, "confidence", None),
                "quality": getattr(contract, "quality", None),
            },
            quantforg_count=qf_count,
            broker_ready=True,
        )
        diagnostics["authoritative_snapshot"] = snap.to_dict()
        stale = stale_authorization(snap)
        if stale:
            logger.warning(
                "same_cycle_stale_block",
                reason=stale,
                cycle_id=snap.cycle_id,
                snapshot_id=snap.snapshot_id,
            )
            diagnostics["stale_authorization"] = stale
            from app.domain.institutional_trading.operations.execution_chain_log import (
                execution_blocked_event as _blk_stale,
            )

            diagnostics["execution_blocked"] = _blk_stale(
                stage="MARKET",
                reason_code=str(stale),
                human_reason=str(stale),
                correlation_id=tid,
            )
            from app.domain.institutional_trading.decision_models import (
                DecisionAction as _DA_stale,
            )

            blocked = _dc_replace(
                decision,
                action=_DA_stale.NO_TRADE,
                reasons=(*decision.reasons, stale),
            )
            return (
                self.execution.bridge.handle(blocked, ctx, trace_id=tid),
                diagnostics,
            )

        lots = getattr(decision, "approved_lots", None) or _Dec("0")
        stop = None
        target = None
        try:
            stop = str(decision.stop_zone.mid or decision.stop_zone.low)
        except Exception:
            stop = None
        try:
            target = str(decision.target_zone.mid or decision.target_zone.high)
        except Exception:
            target = None
        free = getattr(account, "free_margin", None)
        from app.domain.trading.xauusd_specs import (
            VOLUME_MAX as _VMAX,
            VOLUME_MIN as _VMIN,
            VOLUME_STEP as _VSTEP,
        )

        def _diag_dec(key: str, fallback: _Dec) -> _Dec:
            raw = diagnostics.get(key)
            if raw is None or raw == "":
                return fallback
            try:
                val = _Dec(str(raw))
            except Exception:
                return fallback
            return val if val > 0 else fallback

        min_lot = _diag_dec("broker_min_lot", _diag_dec("volume_min", _VMIN))
        lot_step = _diag_dec("broker_lot_step", _diag_dec("volume_step", _VSTEP))
        max_lot = _diag_dec("broker_max_lot", _diag_dec("volume_max", _VMAX))

        def _diag_int(key: str) -> int | None:
            raw = diagnostics.get(key)
            if raw is None or raw == "":
                return None
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None

        margin_per_lot = _diag_dec("margin_per_lot", _Dec("0"))
        plan = build_position_plan(
            cycle_id=snap.cycle_id,
            snapshot_id=snap.snapshot_id,
            symbol=snap.canonical_symbol,
            direction=direction,
            trade_class=trade_class,
            opportunity_score=score,
            confidence=getattr(contract, "confidence", None),
            aggregate_lots=lots,
            current_quantforg_count=snap.existing_quantforg_positions,
            ite_config=self.decision_pipeline.config,
            risk_allowed_count=_diag_int("risk_allowed_count"),
            portfolio_allowed_count=_diag_int("portfolio_allowed_count"),
            broker_allowed_count=_diag_int("broker_allowed_count"),
            sl=stop,
            tp=target,
            base_input_hash=str(decision.input_hash),
            free_margin=free,
            margin_per_lot=margin_per_lot if margin_per_lot > 0 else None,
            min_lot=min_lot,
            lot_step=lot_step,
            max_lot=max_lot,
        )
        note_opportunity_change(
            score=score,
            direction=direction,
            trade_class=trade_class,
        )
        diagnostics["position_plan"] = plan.to_dict()
        diagnostics["trade_class"] = trade_class
        if plan.effective_count <= 0:
            from dataclasses import replace as _dc_replace2

            from app.domain.institutional_trading.decision_models import (
                DecisionAction as _DA_zero,
            )

            hold = plan.min_lot_constraint_reason or "effective_position_count=0"
            from app.domain.institutional_trading.operations.execution_chain_log import (
                execution_blocked_event as _blk_plan,
            )

            min_lot_hold = "min_lot" in str(hold).lower()
            diagnostics["execution_blocked"] = _blk_plan(
                stage="RISK" if min_lot_hold else "OMS",
                reason_code=(
                    "MIN_LOT_INFEASIBLE" if min_lot_hold else "POSITION_LIMIT"
                ),
                human_reason=str(hold),
                correlation_id=tid,
            )
            blocked = _dc_replace2(
                decision,
                action=_DA_zero.NO_TRADE,
                reasons=(*decision.reasons, hold),
            )
            return (
                self.execution.bridge.handle(blocked, ctx, trace_id=tid),
                diagnostics,
            )

        t_first = _time.perf_counter()

        def _submit(leg_decision: Any, leg_ctx: Any) -> Any:
            return self.execution.bridge.handle(
                leg_decision, leg_ctx, trace_id=tid
            )

        plan, tally, last = submit_position_plan_batch(
            plan=plan,
            decision=decision,
            context=ctx,
            submit=_submit,
            trade_class=trade_class,
        )
        diagnostics["position_plan"] = plan.to_dict()
        diagnostics["batch_tally"] = tally.to_dict()
        remember_fill_metadata(
            {
                "trade_class": trade_class,
                "cycle_id": plan.cycle_id,
                "snapshot_id": plan.snapshot_id,
                "position_plan_id": plan.position_plan_id,
                "opportunity_score": score,
                "comment_hash": str(getattr(decision, "input_hash", "") or "")[:12],
                "management_profile": "scalp" if trade_class == "SCALP" else "hold",
            }
        )
        diagnostics["time_from_signal_to_first_order_send"] = round(
            (t_first - signal_t0) * 1000.0, 3
        )
        diagnostics["time_from_signal_to_last_order_send"] = round(
            (_time.perf_counter() - signal_t0) * 1000.0, 3
        )
        if last is None:
            from app.domain.institutional_trading.decision_models import (
                DecisionAction as _DA_dup,
            )

            blocked = _dc_replace(
                decision,
                action=_DA_dup.NO_TRADE,
                reasons=(*decision.reasons, "duplicate_or_empty_batch"),
            )
            from app.domain.institutional_trading.operations.execution_chain_log import (
                execution_blocked_event as _blk_dup,
            )

            diagnostics["execution_blocked"] = _blk_dup(
                stage="OMS",
                reason_code="DUPLICATE_SIGNAL",
                human_reason="duplicate_or_empty_batch",
                correlation_id=tid,
            )
            last = self.execution.bridge.handle(blocked, ctx, trace_id=tid)
        return last, diagnostics

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
                self._last_bridge_result = None
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
        if market_context_diagnostics is None:
            market_context_diagnostics = {}
        market_context_diagnostics.setdefault("cycle_id", f"cycle-{tid[:12]}")
        market_context_diagnostics.setdefault("snapshot_id", f"snap-{tid[:12]}")
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
            record_lifecycle(
                stage="SIGNAL_CREATED",
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
            ai_score = getattr(self.decision_pipeline, "_last_ai_score", None)
            if isinstance(ai_score, dict) and isinstance(
                market_context_diagnostics, dict
            ):
                if ai_score.get("opportunity_score") is not None:
                    market_context_diagnostics["opportunity_score"] = int(
                        ai_score["opportunity_score"]
                    )
                    market_context_diagnostics["opportunity_score_source"] = (
                        "ai_payload"
                    )
                if ai_score.get("opportunity_threshold") is not None:
                    market_context_diagnostics["opportunity_threshold"] = ai_score.get(
                        "opportunity_threshold"
                    )
                for key in (
                    "entry",
                    "stop_loss",
                    "take_profit",
                    "expected_rr",
                    "setup_family",
                    "market_regime",
                    "structure_score",
                    "sniper_entry",
                    "signal_action",
                    "direction",
                ):
                    if key in ai_score and market_context_diagnostics.get(key) is None:
                        market_context_diagnostics[key] = ai_score.get(key)
        except Exception:
            logger.exception("canonical_opportunity_score_attach_failed")
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
            )

            if _scalp_cfg.continuous_operation_enabled:
                ctrl = _get_co(_scalp_cfg)
                # Soft 30-minute opportunity review (continuous ~5s scan still runs).
                try:
                    import time as _time

                    from app.domain.institutional_trading.ai_scalping.daily_opportunity_target import (
                        get_daily_opportunity_tracker as _get_dot,
                    )

                    _dot = _get_dot(
                        target_trades_per_day=int(
                            getattr(_scalp_cfg, "target_trades_per_day", 3) or 3
                        )
                    )
                    if _dot.due_for_opportunity_review(now_mono=_time.monotonic()):
                        _dot.note_analysis(decision="opportunity_review_tick")
                        logger.info(
                            "opportunity_review_tick",
                            trades_today=_dot.trades_today,
                            target=_dot.target_trades_per_day,
                            seeking_mode=_dot.seeking_mode(),
                        )
                except Exception:
                    logger.exception("opportunity_review_tick_failed")
                # After close: scan for a NEW valid setup. Same-symbol re-entry
                # requires fresh structure (per-symbol requalification), not a
                # wiped cooldown.
                if _scalp_cfg.post_close_rescan_enabled:
                    ctrl.consume_rescan()
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
                        symbol=str(
                            getattr(decision, "symbol", "")
                            or getattr(snapshot, "symbol", "")
                            or ""
                        ),
                        bid=(
                            float(account.bid)
                            if getattr(account, "bid", None) is not None
                            else None
                        ),
                        ask=(
                            float(account.ask)
                            if getattr(account, "ask", None) is not None
                            else None
                        ),
                        quote_age_seconds=getattr(account, "quote_age_seconds", None),
                        strategy=str(
                            getattr(decision, "strategy_id", "")
                            or getattr(decision, "strategy", "")
                            or ""
                        ),
                        direction=str(
                            getattr(
                                getattr(decision, "direction", None),
                                "value",
                                decision.direction,
                            )
                            or ""
                        ),
                    ).to_dict()
                if pause.get("pause_new_entries") and decision.action in {
                    _DA.BUY,
                    _DA.SELL,
                }:
                    why = tuple(str(r) for r in (pause.get("reasons") or ()))
                    # Keep BUY/SELL. Wiping to NO_TRADE/NONE mislabels DIRECTION_NONE
                    # and hides EXECUTION_REJECT_BURST. OMS is still blocked via
                    # eligibility + zero lots + the execution contract.
                    decision = _dc_replace(
                        decision,
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
                )

                if decision.action in {_DA_fc.BUY, _DA_fc.SELL}:
                    decision = _dc_replace_fc(
                        decision,
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
            _ai_opp_lab = getattr(self.decision_pipeline, "_last_ai_score", None)
            _ai_opp_lab = _ai_opp_lab if isinstance(_ai_opp_lab, dict) else {}
            get_opportunity_outcome_store().record_evaluation(
                symbol=str(
                    getattr(decision, "symbol", "") or getattr(snapshot, "symbol", "")
                ),
                ai_confidence=int(getattr(decision, "confidence", 0) or 0),
                opportunity_score=int(
                    (duel.champion.get("opportunity_score") if duel else None)
                    or _ai_opp_lab.get("opportunity_score")
                    or getattr(decision, "opportunity_score", None)
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
        portfolio_allow = True
        portfolio_reasons: tuple[str, ...] = ()
        try:
            from app.domain.institutional_trading.portfolio_intelligence import (
                build_portfolio_state,
                evaluate_capital_protection,
                get_dynamic_risk_budget,
                get_opportunity_queue,
            )

            from app.domain.institutional_trading.operations.quantforg_position_cap import (
                engine_position_rows,
                quantforg_open_symbols,
            )

            open_syms = sorted(
                quantforg_open_symbols(
                    engine_position_rows(self.position_management.engine)
                )
            )
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
            _ai_opp_q = getattr(self.decision_pipeline, "_last_ai_score", None)
            _ai_opp_q = _ai_opp_q if isinstance(_ai_opp_q, dict) else {}
            get_opportunity_queue().rebuild(
                [
                    {
                        "symbol": getattr(decision, "symbol", ""),
                        "direction": str(
                            getattr(getattr(decision, "direction", None), "value", "")
                        ),
                        "opportunity_score": int(
                            _ai_opp_q.get("opportunity_score")
                            or getattr(decision, "opportunity_score", None)
                            or 0
                        ),
                        "ai_confidence": int(getattr(decision, "confidence", 0) or 0),
                        "expected_rr": float(getattr(decision, "estimated_rr", 0) or 0),
                    }
                ],
                st,
                risk_budget_pct=float(budget["risk_budget_pct"]),
            )
            if not prot.allow_new_exposure:
                portfolio_allow = False
                portfolio_reasons = tuple(str(r) for r in (prot.reasons or ()) if r)
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
            if decision.eligibility.eligible:
                record_lifecycle(
                    stage="RISK_PASSED",
                    status="ok",
                    detail="eligible",
                    trace_id=tid,
                    symbol=str(getattr(decision, "symbol", "") or ""),
                )
                lots_txt = getattr(decision, "approved_lots", None)
                if lots_txt is None:
                    lots_txt = getattr(decision, "lots", None)
                record_lifecycle(
                    stage="SIZE_APPROVED",
                    status="ok",
                    detail=f"lots={lots_txt}",
                    trace_id=tid,
                    symbol=str(getattr(decision, "symbol", "") or ""),
                )
            else:
                reason = (
                    ";".join(decision.eligibility.rejection_reasons)
                    or "risk_ineligible"
                )
                from app.domain.institutional_trading.phase_a.execution_reject import (
                    first_blocking_gate_from_reasons as _pause_gate,
                )

                gate = _pause_gate(
                    decision.eligibility.rejection_reasons,
                    default="RISK_REJECTED",
                )
                record_lifecycle(
                    stage="FIRST_BLOCKING_GATE",
                    status="failed",
                    detail=f"{gate}: {reason}",
                    trace_id=tid,
                    symbol=str(getattr(decision, "symbol", "") or ""),
                )
                logger.warning(
                    "execution_first_blocking_gate",
                    gate=gate,
                    reason=reason,
                    symbol=str(getattr(decision, "symbol", "") or ""),
                    forwarded_to_oms=False,
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
        # Prefer the pipeline-sized stop — never overwrite with a wider ATR
        # preview that disagrees with Risk / min-lot.
        sizing_diag: dict[str, Any] = dict(market_context_diagnostics or {})
        feas_pipe = (
            self.decision_pipeline.last_min_lot_feasibility()
            if hasattr(self.decision_pipeline, "last_min_lot_feasibility")
            else None
        ) or {}
        atr_val = getattr(account, "atr", None)
        existing_stop = feas_pipe.get("stop_distance") or sizing_diag.get(
            "stop_distance"
        )
        entry_atr_raw = sizing_diag.get("entry_atr")
        atr_for_stop = None
        try:
            if entry_atr_raw not in (None, ""):
                atr_for_stop = Decimal(str(entry_atr_raw))
        except (TypeError, ValueError):
            atr_for_stop = None
        if atr_for_stop is None or atr_for_stop <= 0:
            atr_for_stop = atr_val
        scalp_cfg = bool(
            getattr(self.decision_pipeline.config, "is_scalping", lambda: False)()
        )
        stop_mult = Decimal("1.10") if scalp_cfg else Decimal("1.5")
        stop_dist = None
        if existing_stop not in (None, ""):
            stop_dist = existing_stop
        elif atr_for_stop is not None and atr_for_stop > 0:
            stop_dist = (atr_for_stop * stop_mult).quantize(Decimal("0.0001"))
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
                "strategy_signal": str(
                    getattr(decision.action, "value", decision.action) or ""
                ),
            }
        )
        for key in (
            "tradeability",
            "tradeability_reason",
            "estimated_risk_at_min_lot",
            "maximum_tradeable_stop_distance",
            "broker_min_lot",
            "broker_lot_step",
            "broker_max_lot",
        ):
            if feas_pipe.get(key) not in (None, ""):
                sizing_diag[key] = feas_pipe[key]
        if feas_pipe.get("tradeability") == "NOT_TRADEABLE":
            sizing_diag["execution_status"] = "WAITING_FOR_SETUP"
        elif feas_pipe.get("tradeability") == "TRADEABLE":
            sizing_diag["execution_status"] = "TRADEABLE"
            # Drop ATR-preview min-lot leftovers; pipeline stop is authoritative.
            from app.domain.institutional_trading.operations.min_lot_feasibility import (
                CODE_MIN_LOT_CONSTRAINT,
                CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
            )

            leftover = str(sizing_diag.get("block_reason") or "")
            if leftover in {
                CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
                CODE_MIN_LOT_CONSTRAINT,
            }:
                sizing_diag["block_reason"] = None
                sizing_diag["rejection_reason"] = None
                sizing_diag["sizing_status"] = "ok"
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

        from app.application.services.market_closed_cooldown import (
            is_market_closed_cooled,
        )
        from app.domain.institutional_trading.operations.broker_session_truth import (
            overlay_snapshot_session,
            resolve_from_diagnostics,
        )

        sess = getattr(getattr(snapshot, "session", None), "session", None)
        utc_sess = str(getattr(sess, "value", None) or sess or "off_hours")
        session_obs = resolve_from_diagnostics(
            market_context_diagnostics,
            utc_session=utc_sess,
            symbol_tradable=symbol_tradable,
            market_data_live=market_data_live,
            cooled=is_market_closed_cooled(
                str(getattr(snapshot, "symbol", "") or "")
            ),
        )
        snapshot = overlay_snapshot_session(
            snapshot, broker_open=session_obs.broker_session_open
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
            broker_session_open=(
                True if force_shadow else session_obs.broker_session_open
            ),
            session_source=session_obs.session_source,
            daily_pnl_trusted=(
                market_context_diagnostics.get("daily_pnl_fail_closed")
                is not True
                and market_context_diagnostics.get("daily_pnl_trusted") is True
            ),
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
                should_defer_submit,
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
                    spread=coerce_spread_value(
                        getattr(snapshot, "spread", None)
                    ),
                    optimizer=optimizer_payload,
                )
                rec = str(optimizer_payload.get("recommendation") or "")
                final_state = str(optimizer_payload.get("final_state") or "")
                # Soft wait is optimizer-owned. SOR must not add a second wait loop.
                if should_defer_submit(optimizer_payload):
                    defer_submit = True
                    logger.warning(
                        "execution_optimizer_defer_tick",
                        symbol=optimizer_payload.get("symbol"),
                        score=optimizer_payload.get("execution_quality_score"),
                        reason=optimizer_payload.get("reason"),
                        final_state=final_state,
                        defer_count=optimizer_payload.get("defer_count"),
                        remaining_wait_ms=optimizer_payload.get(
                            "remaining_wait_ms"
                        ),
                        remaining_attempts=optimizer_payload.get(
                            "remaining_attempts"
                        ),
                    )
                elif final_state == "EXECUTE_NOW" or rec in {
                    "PROCEED",
                    "PROCEED_DEGRADED",
                }:
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
            opt = optimizer_payload or {}
            detail = (
                f"execution_optimizer_defer:"
                f"{opt.get('reason') or 'wait_for_better_tick_within_limits'}"
                f":count={opt.get('defer_count') or 0}"
                f":remaining_wait_ms={opt.get('remaining_wait_ms') or 0}"
            )
            from app.domain.institutional_trading.operations.execution_chain_log import (
                execution_blocked_event,
            )

            blocked_ev = execution_blocked_event(
                stage="OPTIMIZER",
                reason_code="EXECUTION_OPTIMIZER_DEFER",
                human_reason=detail,
                correlation_id=tid,
            )
            if isinstance(market_context_diagnostics, dict):
                market_context_diagnostics["execution_blocked"] = blocked_ev
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
                execution_blocked=blocked_ev,
            )
            with self._lock:
                self._last_cycle = result
                self._last_decision = decision
                self._cycles += 1
                self._last_bridge_result = None
            return result

        from app.domain.institutional_trading.operations.gold_execution_contract import (
            evaluate_gold_execution_contract,
            facts_from_cycle,
        )

        contract = evaluate_gold_execution_contract(
            facts_from_cycle(
                snapshot=snapshot,
                account=account,
                decision=decision,
                optimizer=optimizer_payload,
                execution_enabled=execution_enabled,
                force_shadow=force_shadow,
                gateway_connected=gateway_connected,
                broker_connected=broker_connected,
                symbol_tradable=symbol_tradable,
                auto_running=str(self.plane.auto_trading_run_state or "") == "running",
                kill_switch=bool(self.plane.kill_switch_armed),
                oms_orders_allowed=bool(self.plane.oms_orders_allowed()),
                safety_allowed=not force_shadow,
                portfolio_allow=portfolio_allow,
                portfolio_reasons=portfolio_reasons,
                last_ai_score=(
                    getattr(self.decision_pipeline, "_last_ai_score", None)
                    if isinstance(
                        getattr(self.decision_pipeline, "_last_ai_score", None),
                        dict,
                    )
                    else None
                ),
                daily_loss_exceeded=bool(self.plane.daily_loss_exceeded),
            )
        )
        if market_context_diagnostics is None:
            market_context_diagnostics = {}
        market_context_diagnostics["execution_contract"] = contract.to_dict()
        if not contract.may_submit_oms and not force_shadow:
            logger.warning(
                "execution_contract_hold",
                decision_state=contract.decision_state,
                fault_code=contract.fault_code,
                blocking_stage=contract.blocking_stage,
                may_submit_oms=False,
                execute_now_required=False,
            )
            from app.domain.institutional_trading.operations.execution_chain_log import (
                execution_blocked_event,
            )

            blocked_ev = execution_blocked_event(
                stage=str(contract.blocking_stage or "RISK"),
                reason_code=str(contract.fault_code or "EXECUTION_BLOCKED"),
                human_reason=str(contract.fault_reason or ""),
                correlation_id=tid,
                symbol=str(getattr(snapshot, "symbol", "") or ""),
                direction=str(
                    getattr(getattr(decision, "action", None), "value", None)
                    or getattr(decision, "action", "")
                    or ""
                ),
                signal_id=str(tid or ""),
            )
            market_context_diagnostics["execution_blocked"] = blocked_ev
            from app.domain.institutional_trading.operations.execution_chain_log import (
                build_execution_handoff,
            )

            market_context_diagnostics["execution_handoff"] = build_execution_handoff(
                take=str(getattr(decision.action, "value", decision.action) or "")
                .upper()
                in {"BUY", "SELL"},
                abort_reason=str(contract.fault_code or ""),
                blocking_stage=str(contract.blocking_stage or ""),
                forwarded_to_oms=False,
            )
            logger.warning(
                "EXECUTION_BLOCKED",
                stage=blocked_ev["stage"],
                reason_code=blocked_ev["reason_code"],
                human_reason=blocked_ev["human_reason"],
                correlation_id=tid,
            )
            result = ShadowCycleResult(
                ok=True,
                trace_id=tid,
                mode=self.plane.mode.value,
                decision_action=decision.action.value,
                forwarded_to_oms=False,
                detail=contract.fault_reason,
                health=health.get("health") if isinstance(health, dict) else None,
                cycle_outcome="execution_contract",
                abort_reason=contract.fault_code,
                decision_reasons=(contract.fault_reason,),
                snapshot_present=True,
                market_context_diagnostics=dict(market_context_diagnostics),
                signal_id=str(getattr(decision, "id", "") or "") or None,
                execution_blocked=blocked_ev,
            )
            with self._lock:
                self._last_cycle = result
                self._last_decision = decision
                self._cycles += 1
                self._last_bridge_result = None
            self._emit_telegram_cycle(result)
            return result

        from app.application.services.ite_cycle_market_context import (
            refresh_execution_gateway_reads,
        )

        refresh_execution_gateway_reads(self.mt5_adapter)
        bridge_result, market_context_diagnostics = self._submit_same_cycle_batch(
            decision=decision,
            ctx=ctx,
            tid=tid,
            contract=contract,
            snapshot=snapshot,
            account=account,
            diagnostics=dict(market_context_diagnostics),
            signal_t0=t0,
        )
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
            this_cycle_forwarded=bool(
                getattr(bridge_result, "forwarded_to_oms", False)
            ),
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
                    _ai_opp = getattr(self.decision_pipeline, "_last_ai_score", None)
                    _ai_opp = _ai_opp if isinstance(_ai_opp, dict) else {}
                    get_opportunity_outcome_store().record_evaluation(
                        symbol=str(getattr(decision, "symbol", "") or ""),
                        ai_confidence=int(getattr(decision, "confidence", 0) or 0),
                        opportunity_score=int(
                            _ai_opp.get("opportunity_score")
                            or getattr(decision, "opportunity_score", None)
                            or 0
                        ),
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
                    # Daily opportunity target — observe only; never forces next entry.
                    try:
                        from app.domain.institutional_trading.ai_scalping.config import (
                            DEFAULT_AI_SCALPING_CONFIG as _tgt_cfg,
                        )
                        from app.domain.institutional_trading.ai_scalping.continuous_operation import (
                            get_continuous_operation_controller as _tgt_co,
                        )
                        from app.domain.institutional_trading.ai_scalping.daily_opportunity_target import (
                            get_daily_opportunity_tracker,
                        )

                        get_daily_opportunity_tracker(
                            target_trades_per_day=int(
                                getattr(_tgt_cfg, "target_trades_per_day", 3) or 3
                            )
                        ).note_trade_executed(
                            symbol=str(getattr(decision, "symbol", "") or "")
                        )
                        try:
                            from app.application.services.strategy_performance_telemetry import (  # noqa: E501
                                get_strategy_performance_telemetry,
                            )

                            _ai_fill = getattr(
                                self.decision_pipeline, "_last_ai_score", None
                            )
                            _ai_fd = _ai_fill if isinstance(_ai_fill, dict) else {}
                            _feas = (
                                self.decision_pipeline.last_min_lot_feasibility()
                                if hasattr(
                                    self.decision_pipeline,
                                    "last_min_lot_feasibility",
                                )
                                else None
                            ) or {}
                            get_strategy_performance_telemetry().observe_fill(
                                ticket=ticket,
                                signal_quality=_ai_fd.get("trade_quality")
                                or _ai_fd.get("quality")
                                or getattr(decision, "quality", None),
                                confidence=getattr(decision, "confidence", None)
                                or _ai_fd.get("ai_confidence")
                                or _ai_fd.get("confidence"),
                                direction=str(
                                    getattr(
                                        getattr(decision, "direction", None),
                                        "value",
                                        None,
                                    )
                                    or getattr(decision, "direction", None)
                                    or ""
                                ),
                                strategy_id=_ai_fd.get("strategy")
                                or _ai_fd.get("setup_family")
                                or getattr(self.plane, "trading_mode", None),
                                approved_stop=_ai_fd.get("stop_distance")
                                or _feas.get("stop_distance"),
                                approved_lot=getattr(decision, "approved_lots", None),
                                trade_class=getattr(decision, "trade_class", None),
                                entry=_ai_fd.get("entry")
                                or getattr(decision, "entry", None),
                            )
                        except Exception:
                            logger.exception(
                                "strategy_performance_fill_observe_failed"
                            )
                        if getattr(_tgt_cfg, "post_event_rescan_enabled", True):
                            _tgt_co(_tgt_cfg).request_opportunity_rescan("position_opened")
                    except Exception:
                        logger.exception("daily_opportunity_target_post_fill_failed")
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
            mt5_ticket = (
                getattr(entry, "mt5_ticket", None)
                or getattr(entry, "ticket", None)
                or getattr(entry, "order_ticket", None)
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

        blocked_ev = None
        if not bool(bridge_result.forwarded_to_oms):
            if isinstance(market_context_diagnostics, dict):
                raw_b = market_context_diagnostics.get("execution_blocked")
                if isinstance(raw_b, dict):
                    blocked_ev = raw_b
            action_now = str(getattr(decision.action, "value", decision.action) or "")
            if blocked_ev is None and action_now in {"BUY", "SELL"}:
                from app.domain.institutional_trading.operations.execution_chain_log import (
                    execution_blocked_event as _blk_bridge,
                )

                abort_s = str(
                    getattr(
                        getattr(bridge_result, "abort_reason", None),
                        "value",
                        getattr(bridge_result, "abort_reason", None),
                    )
                    or "UNKNOWN_EXECUTION_ERROR"
                )
                from app.domain.institutional_trading.operations.execution_chain_log import (
                    bridge_abort_stage as _abort_stage,
                )

                blocked_ev = _blk_bridge(
                    stage=_abort_stage(abort_s),
                    reason_code=abort_s,
                    human_reason=str(detail or abort_s),
                    correlation_id=tid,
                )
                if isinstance(market_context_diagnostics, dict):
                    market_context_diagnostics["execution_blocked"] = blocked_ev

        try:
            from app.domain.institutional_trading.phase_a.execution_reject import (
                execution_observability as _exec_obs,
            )

            oms_for_obs = getattr(bridge_result, "oms_result", None)
            entry_for_obs = getattr(bridge_result, "journal_entry", None)
            obs = _exec_obs(
                oms_result=oms_for_obs,
                abort_reason=getattr(bridge_result, "abort_reason", None),
                forwarded_to_oms=bool(
                    getattr(bridge_result, "forwarded_to_oms", False)
                ),
                oms_submit_called=oms_for_obs is not None,
                gateway_status=(
                    getattr(entry_for_obs, "gateway_status", None)
                    if entry_for_obs is not None
                    else None
                ),
                reject_reason=str(detail or "") or None,
                reject_timestamp=(
                    getattr(entry_for_obs, "timestamp", None).isoformat()
                    if entry_for_obs is not None
                    and getattr(entry_for_obs, "timestamp", None) is not None
                    else None
                ),
            )
            if isinstance(market_context_diagnostics, dict):
                market_context_diagnostics["execution_observability"] = obs
        except Exception:
            logger.exception("execution_observability_attach_failed")

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
            trade_class=(
                (market_context_diagnostics or {}).get("trade_class")
                if isinstance(market_context_diagnostics, dict)
                else None
            ),
            position_plan=(
                (market_context_diagnostics or {}).get("position_plan")
                if isinstance(market_context_diagnostics, dict)
                else None
            ),
            stage_timings_ms=(
                (market_context_diagnostics or {}).get("stage_timings_ms")
                if isinstance(market_context_diagnostics, dict)
                else None
            ),
            decision_cycle_latency_ms=round(latency_ms, 3),
            execution_blocked=blocked_ev,
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
                mt5_ticket=result.mt5_ticket,
                trace_id=result.trace_id,
            )
        except Exception:
            logger.exception("strategy_diagnostics_record_failed")
        self._emit_telegram_cycle(result)
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
        this_cycle_forwarded: bool | None = None,
        may_submit_oms: bool | None = None,
        blocking_stage: str | None = None,
    ) -> None:
        """After AI Decision: Gate → Risk → OMS → MT5 → Broker.

        A cycle that did not submit must log NOT_ATTEMPTED. It must never
        reprint a prior ticket as if this cycle reached OMS.
        """
        from app.domain.institutional_trading.operations.execution_chain_log import (
            classify_post_ai_execution_chain,
        )

        action = str(getattr(getattr(decision, "action", None), "value", "") or "")
        elig = getattr(decision, "eligibility", None)
        elig_ok = bool(getattr(elig, "eligible", False))
        elig_reasons = list(getattr(elig, "rejection_reasons", ()) or ())
        risk_reasons = list(getattr(decision, "risk_reasons", ()) or ())
        abort = getattr(bridge_result, "abort_reason", None) if bridge_result else None
        abort_val = str(getattr(abort, "value", abort) or "")
        forwarded = False
        if bridge_result is not None:
            forwarded = bool(getattr(bridge_result, "forwarded_to_oms", False))
        oms = getattr(bridge_result, "oms_result", None) if bridge_result else None
        oms_msg = str(getattr(oms, "message", "") or "") if oms is not None else ""
        oms_ret = getattr(oms, "retcode", None) if oms is not None else None
        ticket = None
        if oms is not None:
            ticket = getattr(oms, "order_ticket", None) or getattr(
                oms, "deal_ticket", None
            )
        journal = None
        if bridge_result is not None:
            journal = getattr(bridge_result, "journal_entry", None)
        journal_comment = str(getattr(journal, "comment", "") or "")
        chain = classify_post_ai_execution_chain(
            forwarded_to_oms=forwarded,
            may_submit_oms=may_submit_oms,
            blocking_stage=blocking_stage,
            ticket=ticket,
            retcode=oms_ret,
            this_cycle_forwarded=this_cycle_forwarded,
        )

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
            and bool(chain["forwarded_to_oms"])
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

        risk_blocked = str(blocking_stage or "").upper() == "RISK" or (
            this_cycle_forwarded is False and not elig_ok
        )
        risk_pass = bool(elig_ok) and not risk_blocked
        if abort_val == "eligibility_failed":
            risk_pass = False
        if chain["forwarded_to_oms"]:
            risk_pass = True
        risk_detail = (
            "; ".join(elig_reasons)
            or "; ".join(risk_reasons)
            or journal_comment
            or abort_val
            or "eligible"
        )
        logger.warning(
            "Risk Engine",
            result="PASS" if risk_pass else "FAIL",
            eligible=elig_ok,
            detail=risk_detail[:500],
        )
        try:
            from app.application.services.strategy_performance_telemetry import (
                get_strategy_performance_telemetry,
            )

            ai = getattr(self.decision_pipeline, "_last_ai_score", None)
            ai_d = ai if isinstance(ai, dict) else {}
            feas = (
                self.decision_pipeline.last_min_lot_feasibility()
                if hasattr(self.decision_pipeline, "last_min_lot_feasibility")
                else None
            ) or {}
            sig_dir = str(
                getattr(getattr(decision, "direction", None), "value", None)
                or getattr(decision, "direction", None)
                or ""
            )
            tel_row = get_strategy_performance_telemetry().observe_cycle(
                cycle_key=str(
                    ai_d.get("cycle_id")
                    or getattr(decision, "id", "")
                    or abort_val
                    or ""
                )
                or None,
                forwarded_to_oms=bool(chain["forwarded_to_oms"]),
                blocking_stage=blocking_stage,
                fault_code=abort_val or None,
                ticket=chain.get("ticket"),
                this_cycle_forwarded=this_cycle_forwarded,
                trace_id=str(getattr(decision, "id", "") or "") or None,
                eligible=elig_ok,
                reasons=risk_detail,
                signal={
                    "symbol": str(getattr(decision, "symbol", "") or "") or None,
                    "signal_quality": ai_d.get("trade_quality")
                    or ai_d.get("quality")
                    or getattr(decision, "quality", None),
                    "confidence": getattr(decision, "confidence", None)
                    or ai_d.get("ai_confidence")
                    or ai_d.get("confidence"),
                    "direction": sig_dir,
                    "strategy_id": ai_d.get("strategy") or ai_d.get("setup_family"),
                    "trade_class": getattr(decision, "trade_class", None),
                    "approved_stop": ai_d.get("stop_distance")
                    or feas.get("stop_distance"),
                    "approved_lot": str(
                        getattr(decision, "approved_lots", "") or ""
                    )
                    or None,
                    "min_lot_feasibility": feas.get("classification"),
                    "risk_result": "PASS" if risk_pass else "FAIL",
                    "execution_allowed": bool(chain["forwarded_to_oms"]),
                },
            )
            try:
                from app.application.services.aggressive_compounding_observer import (
                    observe_aggressive_compounding_shadow,
                )

                observe_aggressive_compounding_shadow(
                    signal={
                        "symbol": str(getattr(decision, "symbol", "") or "") or None,
                        "signal_quality": ai_d.get("trade_quality")
                        or ai_d.get("quality")
                        or getattr(decision, "quality", None),
                        "confidence": getattr(decision, "confidence", None)
                        or ai_d.get("ai_confidence")
                        or ai_d.get("confidence"),
                        "direction": sig_dir,
                        "trade_class": getattr(decision, "trade_class", None),
                        "expected_rr": ai_d.get("expected_rr")
                        or getattr(decision, "estimated_rr", None),
                        "approved_lot": str(
                            getattr(decision, "approved_lots", "") or ""
                        )
                        or None,
                        "min_lot_feasibility": feas.get("classification"),
                    },
                    score=ai_d,
                    forwarded_to_oms=bool(chain["forwarded_to_oms"]),
                    blocking_stage=blocking_stage,
                    fault_code=abort_val or None,
                    risk_approved_volume=getattr(decision, "approved_lots", None),
                    cycle_id=str(getattr(decision, "id", "") or "") or None,
                )
            except Exception:
                logger.exception("aggressive_compounding_shadow_hook_failed")
            logger.warning(
                "Signal Lifecycle",
                final_state=tel_row.get("final_state"),
                final_blocker=tel_row.get("final_blocker"),
                direction=tel_row.get("direction") or sig_dir,
                action=action,
                high_quality=tel_row.get("high_quality"),
                forwarded_to_oms=bool(chain["forwarded_to_oms"]),
            )
        except Exception:
            logger.exception("strategy_performance_cycle_observe_failed")

        if not chain["forwarded_to_oms"]:
            hold_reason = abort_val or risk_detail or "OMS not attempted"
            logger.warning(
                "OMS Submit",
                result=chain["oms_submit"],
                forwarded_to_oms=False,
                detail="OMS not attempted — cycle did not submit",
                abort=abort_val or "none",
            )
            logger.warning(
                "MT5 Gateway",
                result=chain["mt5_gateway"],
                detail="not reached",
                retcode=None,
            )
            logger.warning(
                "Broker",
                result=chain["broker"],
                ticket=None,
                detail="not reached",
            )
            logger.warning("Rejected because: %s", hold_reason)
            return

        logger.warning(
            "OMS Submit",
            result=chain["oms_submit"],
            forwarded_to_oms=True,
        )
        if chain["submitting_order"]:
            logger.warning("Submitting Order...")

        logger.warning(
            "MT5 Gateway",
            result=chain["mt5_gateway"],
            retcode=chain["retcode"],
            message=(oms_msg or abort_val or "none")[:400],
        )
        logger.warning(
            "Broker",
            result=chain["broker"],
            ticket=chain["ticket"],
            required="non-null ticket",
            message=(oms_msg or journal_comment or abort_val or "none")[:400],
        )
        if chain["mt5_accepted"]:
            logger.warning(
                "MT5 Accepted",
                ticket=chain["ticket"],
            )
        else:
            reject = (
                oms_msg
                or journal_comment
                or abort_val
                or "OMS forwarded but broker did not accept"
            )
            logger.warning("Rejected because: %s", reject)
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
        if not forwarded:
            ticket = None
            oms_ret = None
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
            last_finished = self._last_cycle_finished_mono
            last_ok_at = self._last_successful_cycle_at
            last_at = self._last_cycle_at
            session_obs = dict(self._last_session_obs or {})
            recovering = self._recovery_orders_blocked
            last_failure = self._last_failure
            restart_reason = self._watchdog_restart_reason
            watchdog_restarts = self._watchdog_restarts
            watchdog_state = self._watchdog_state
            started_mono = self._started_mono
            cycle_started = self._cycle_started_mono
            daily_loss_latched = bool(self.plane.daily_loss_exceeded)
            last_scan = (
                dict(self._last_multi_asset_scan)
                if isinstance(self._last_multi_asset_scan, dict)
                else None
            )
        settings = get_settings()
        gold = {}
        try:
            from app.domain.trading.gold_only import gold_only_diagnostics

            gold = gold_only_diagnostics()
        except Exception:
            gold = {"gold_only_mode": True, "execution_universe": ["XAUUSD_i"]}
        fd = self._fast_decision_snapshot()
        from app.application.runtime_identity import (
            runtime_deployment_id,
            runtime_git_commit,
        )
        from app.domain.institutional_trading.operations.worker_runtime_state import (
            build_cycle_ops_summary,
            derive_scheduler_state,
            derive_worker_state,
            last_blocker_from_cycle,
            scheduler_is_stalled,
        )
        from app.domain.institutional_trading.phase_a import get_phase_a_plane
        from app.domain.institutional_trading.phase_a.kill_state import HaltKind

        stalled = scheduler_is_stalled(
            last_cycle_finished_mono=last_finished,
            now_mono=time.monotonic(),
            interval_seconds=self.interval_seconds,
            started_mono=started_mono,
            running=not self._stop.is_set(),
            cycle_started_mono=cycle_started,
        )
        halt_kind = HaltKind.NONE
        try:
            halt_kind = get_phase_a_plane().halt.kind
        except Exception:
            halt_kind = HaltKind.NONE
        broker_open = session_obs.get("broker_session_open")
        if broker_open is not True and broker_open is not False:
            broker_open = None
        worker_state = derive_worker_state(
            running=not self._stop.is_set(),
            cycles=cycles,
            broker_session_open=broker_open,
            operator_halt=halt_kind is HaltKind.OPERATOR_HALT,
            risk_halt=halt_kind is HaltKind.RISK_HALT,
            recovering=recovering,
            degraded=stalled or bool(self.plane.kill_switch_armed),
            last_outcome=getattr(last, "cycle_outcome", None) if last else None,
            stalled=stalled,
        )
        scheduler_state = derive_scheduler_state(
            running=not self._stop.is_set(),
            stalled=stalled,
            broker_session_open=broker_open,
        )
        blocker, blocker_stage = last_blocker_from_cycle(last)
        diag = (
            getattr(last, "market_context_diagnostics", None)
            if last is not None
            else None
        )
        if not isinstance(diag, dict):
            diag = {}
        last_error = (
            getattr(last, "detail", None)
            if last is not None
            and str(getattr(last, "cycle_outcome", "") or "") == "error"
            else None
        ) or last_failure
        if stalled:
            recovery_state = "STALLED"
        elif recovering:
            recovery_state = "BLOCKED_NEW_ENTRIES"
        else:
            recovery_state = "CLEAR"
        if daily_loss_latched:
            risk_state = "DAILY_LOSS_EXCEEDED"
        elif last is None:
            risk_state = "UNKNOWN"
        elif str(getattr(last, "cycle_outcome", "") or "") == "safety_blocked":
            risk_state = "BLOCKED"
        elif diag.get("daily_pnl_fail_closed") is True or (
            diag.get("daily_pnl_trusted") is False
        ):
            risk_state = "UNAVAILABLE"
        elif diag.get("daily_pnl_trusted") is True:
            risk_state = "EVALUATED"
        else:
            risk_state = "UNKNOWN"
        payload = {
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
            "fast_decision": fd,
            "current_scan": self._current_scan_snapshot(),
            "last_pipeline": self._last_pipeline_snapshot(),
            "system_coherence": (
                fd.get("system_coherence") if isinstance(fd, dict) else None
            ),
            "gold_only": gold,
            "execution_universe_mode": gold.get("execution_universe_mode"),
            "catalogue_source": gold.get("catalogue_source"),
            "catalogue_symbol_count": gold.get("catalogue_symbol_count"),
            "execution_candidate_count": gold.get("execution_candidate_count"),
            "execution_rejected_count": gold.get("execution_rejected_count"),
            "execution_unavailable_reason": gold.get("execution_unavailable_reason"),
            "worker_state": worker_state,
            "scheduler_state": scheduler_state,
            "session_state": session_obs.get("session_state"),
            "session_source": session_obs.get("session_source"),
            "broker_server_time": session_obs.get("broker_server_time"),
            "last_session_check": session_obs.get("last_session_check"),
            "session_transition_at": session_obs.get("session_transition_at"),
            "next_expected_transition": session_obs.get("next_expected_transition"),
            "trade_mode": session_obs.get("trade_mode"),
            "trade_allowed": session_obs.get("trade_allowed"),
            "last_cycle_at": last_at,
            "last_completed_cycle_at": last_at,
            "last_successful_cycle_at": last_ok_at,
            "last_blocker": blocker,
            "last_blocker_stage": blocker_stage,
            "last_error": last_error,
            "recovery_state": recovery_state,
            "risk_state": risk_state,
            "daily_pnl_status": (
                "UNAVAILABLE"
                if diag.get("daily_pnl_fail_closed") is True
                or diag.get("daily_pnl_trusted") is False
                else (
                    "TRUSTED"
                    if diag.get("daily_pnl_trusted") is True
                    else None
                )
            ),
            "capital_baseline": diag.get("capital_baseline"),
            "deposit_verification": diag.get("deposit_verification"),
            "cycle_id": cycles,
            "cycle_start": self._cycle_started_at,
            "cycle_end": last_at,
            "cycle_duration": self._last_cycle_duration_ms,
            "gateway_state": (
                "UNAVAILABLE"
                if last is not None
                and (
                    "GATEWAY"
                    in str(getattr(last, "abort_reason", "") or "").upper()
                    or str(getattr(last, "abort_reason", "") or "")
                    == "NO_MARKET_CONTEXT"
                )
                else ("UNKNOWN" if last is None else "READY")
            ),
            "mt5_state": (
                "UNAVAILABLE"
                if last is not None
                and str(getattr(last, "abort_reason", "") or "")
                in {"NO_MARKET_CONTEXT", "CYCLE_EXCEPTION", "CYCLE_TIMEOUT"}
                else ("UNKNOWN" if last is None else "READY")
            ),
            "next_cycle_at": last_at,
            "watchdog_state": watchdog_state,
            "watchdog_restarts": watchdog_restarts,
            "restart_count": watchdog_restarts,
            "restart_reason": restart_reason,
            "runtime_git_sha": runtime_git_commit(),
            "deployment_id": runtime_deployment_id(),
            "scheduler_stalled": stalled,
            "scanner_running": bool(not self._stop.is_set() and not stalled),
            "last_cycle_timestamp": last_at,
            "cycle_age_seconds": (
                round(time.monotonic() - last_finished, 3)
                if last_finished > 0
                else round(time.monotonic() - started_mono, 3)
            ),
            "last_successful_cycle": last_ok_at,
            "last_failure": last_error,
            "scanner_unhealthy": bool(stalled),
            "new_entries_blocked_for_recovery": bool(recovering or stalled),
        }
        last_d = payload.get("last_cycle")
        if isinstance(last_d, dict):
            payload["execution_status"] = last_d.get("execution_status")
            payload["timeout_stage"] = last_d.get("timeout_stage") or diag.get(
                "timeout_stage"
            )
            payload["symbols_evaluated"] = diag.get("symbols_evaluated")
            payload["signals_found"] = diag.get("signals_found")
            payload["eligible_opportunities"] = diag.get("eligible_opportunities")
            payload["tradeability"] = last_d.get("tradeability") or diag.get(
                "tradeability"
            )
            payload["tradeability_reason"] = last_d.get(
                "tradeability_reason"
            ) or diag.get("tradeability_reason")
            payload["strategy_signal"] = last_d.get("strategy_signal") or last_d.get(
                "decision_action"
            )
            payload["estimated_risk_at_min_lot"] = last_d.get(
                "estimated_risk_at_min_lot"
            ) or diag.get("estimated_risk_at_min_lot")
            payload["maximum_tradeable_stop_distance"] = last_d.get(
                "maximum_tradeable_stop_distance"
            ) or diag.get("maximum_tradeable_stop_distance")
            if last_d.get("mt5_ticket") in (None, "", 0, "0"):
                payload.setdefault(
                    "execution_result",
                    last_d.get("execution_result")
                    or "NO BROKER ORDER WAS SUBMITTED",
                )
        positions_n = 0
        try:
            positions_n = len(
                getattr(self.position_management.engine, "_positions", {}) or {}
            )
        except Exception:
            positions_n = 0
        cycle_ops = build_cycle_ops_summary(
            cycle_id=cycles,
            cycle_start=self._cycle_started_at,
            cycle_end=last_at,
            last_cycle=last.to_dict() if last else None,
            last_scan=last_scan,
            positions_managed=positions_n,
        )
        payload["cycle_ops"] = cycle_ops
        if isinstance(last_scan, dict):
            payload["last_scan_summary"] = {
                "as_of": last_scan.get("as_of"),
                "enabled": last_scan.get("enabled"),
                "note": last_scan.get("note"),
                "scan_incomplete": last_scan.get("scan_incomplete"),
                "eligible_count": last_scan.get("eligible_count"),
                "eligible_symbols": list(last_scan.get("eligible_symbols") or [])[:16],
                "symbols_queued": last_scan.get("symbols_queued"),
                "symbols_evaluated": last_scan.get("symbols_evaluated"),
                "symbols_completed": last_scan.get("symbols_completed"),
                "first_blocking_gate": last_scan.get("first_blocking_gate"),
                "blocked_by_portfolio": last_scan.get("blocked_by_portfolio"),
                "scanner_duration_ms": last_scan.get("scanner_duration_ms"),
            }
        else:
            payload["last_scan_summary"] = None
        for key in (
            "symbols_targeted",
            "symbols_ready",
            "tradeable_count",
            "risk_approved",
            "risk_rejected",
            "oms_approved",
            "oms_rejected",
            "orders_attempted",
            "orders_submitted",
            "tickets_confirmed",
            "positions_managed",
            "symbols_failed",
            "cycle_status",
        ):
            payload.setdefault(key, cycle_ops.get(key))
        if payload.get("symbols_evaluated") is None:
            payload["symbols_evaluated"] = cycle_ops.get("symbols_evaluated")
        if payload.get("signals_found") is None:
            payload["signals_found"] = cycle_ops.get("signals_found")
        try:
            from app.domain.institutional_trading.operations.infrastructure_heartbeats import (
                RAILWAY_ITE_HEARTBEAT,
                note_heartbeat,
            )

            note_heartbeat(
                RAILWAY_ITE_HEARTBEAT,
                ok=bool(not stalled and not self._stop.is_set()),
                state=(
                    "UNHEALTHY"
                    if stalled
                    else ("RUNNING" if not self._stop.is_set() else "STOPPED")
                ),
                reason=last_failure if stalled else None,
            )
        except Exception:
            logger.exception("ite_heartbeat_note_failed")
        return payload

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
            # MT5 TRADE_RETCODE_DONE is 0. A policy reject never called
            # order_send — do not print retcode=0 as a broker execution.
            send_reached = False
            oms_raw = getattr(oms, "raw", None) if oms is not None else None
            if isinstance(oms_raw, dict):
                send_reached = bool(oms_raw.get("order_send_reached"))
            if send_reached or int(cycle.broker_retcode) != 0:
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
                return sym or None
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
        """Institutional Multi-Asset Scanner — parallel score, multi-symbol handoff.

        Does not invoke Risk / PRE / OMS / MT5. Eligible winners are queued for
        the existing single-symbol cycle (up to max_entries_per_cycle).
        """
        try:
            from app.application.services.institutional_multi_asset_scanner import (
                run_institutional_multi_asset_scan,
            )
            from app.domain.institutional_trading.ai_scalping.config import (
                DEFAULT_AI_SCALPING_CONFIG,
                scalping_ite_config,
            )

            scan_on = bool(
                getattr(DEFAULT_AI_SCALPING_CONFIG, "multi_asset_scan_enabled", True)
            )
            try:
                from app.domain.trading.gold_only import gold_only_enabled

                if gold_only_enabled():
                    # Gold-only is a universe restriction, not a scanner bypass.
                    scan_on = True
            except Exception:
                logger.exception("gold_only_scanner_required_flag_failed")
            if not scan_on:
                return None
            open_n = 0
            try:
                open_n = len(
                    getattr(self.position_management.engine, "_positions", {}) or {}
                )
            except Exception:
                open_n = 0
            t_scan = time.perf_counter()
            ite = getattr(self.decision_pipeline, "config", None)
            if ite is None or not bool(getattr(ite, "is_scalping", lambda: False)()):
                ite = scalping_ite_config()
            from app.domain.institutional_trading.operations.worker_runtime_state import (  # noqa: E501
                cycle_hard_timeout_seconds,
                cycle_scan_budget_seconds,
            )

            hard = cycle_hard_timeout_seconds(self.interval_seconds)
            started = self._cycle_started_mono or time.monotonic()
            remaining = hard - (time.monotonic() - started)
            _scan_budget = cycle_scan_budget_seconds(
                self.interval_seconds, remaining=remaining
            )
            scan: dict[str, Any] | None = None
            try:
                scan = await run_institutional_multi_asset_scan(
                    self.mt5_adapter,
                    position_engine=getattr(self.position_management, "engine", None),
                    open_positions=open_n,
                    plane=self.plane,
                    config=DEFAULT_AI_SCALPING_CONFIG,
                    ite_config=ite,
                    scan_budget_seconds=_scan_budget,
                )
            except Exception:
                logger.exception("multi_asset_scan_call_failed")
                try:
                    from app.application.services.institutional_multi_asset_scanner import (
                        get_last_multi_asset_scan,
                    )

                    prior = get_last_multi_asset_scan()
                    scan = prior if isinstance(prior, dict) else None
                except Exception:
                    scan = None
            scan_ms = round((time.perf_counter() - t_scan) * 1000.0, 1)
            if not isinstance(scan, dict):
                scan = {
                    "as_of": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "enabled": True,
                    "universe": [],
                    "rows": [],
                    "ranked": [],
                    "opportunity_ranked": [],
                    "eligible_symbols": [],
                    "eligible_count": 0,
                    "scan_incomplete": True,
                    "note": "multi_asset_scan_unavailable",
                    "scanner_duration_ms": scan_ms,
                }
            if scan.get("scanner_duration_ms") is None:
                scan["scanner_duration_ms"] = scan_ms
            logger.warning(
                "multi_asset_scan_timing",
                scanner_duration_ms=scan.get("scanner_duration_ms"),
            )
            with self._lock:
                self._last_multi_asset_scan = dict(scan)
            eligible = [
                str(s).upper()
                for s in (scan.get("eligible_symbols") or [])
                if str(s).strip()
            ]
            best = str(scan.get("best_symbol") or "").upper() or None
            try:
                from app.domain.trading.gold_only import (
                    filter_autonomous_symbols,
                    gold_only_enabled,
                    is_gold_symbol,
                )

                if gold_only_enabled():
                    eligible = list(filter_autonomous_symbols(eligible))
                    if best and not is_gold_symbol(best):
                        best = eligible[0] if eligible else None
            except Exception:
                logger.exception("gold_only_handoff_filter_failed")
            if best and best not in eligible:
                eligible = [best, *[s for s in eligible if s != best]]
            # Prefer desk-allowlisted symbols for execution handoff (Safety still
            # applies). Avoids spending cycles on CADCHF/AEXEUR SAFETY_BLOCKED
            # before EURUSD_I / other approved desks that can size on micro equity.
            try:
                from app.domain.institutional_trading.ai_scalping.config import (
                    DEFAULT_SCALPING_UNIVERSE,
                )
                from app.domain.institutional_trading.auto_trading import (
                    prefer_allowlisted_handoff,
                )
                from app.domain.trading.gold_only import gold_only_enabled

                if not gold_only_enabled():
                    # BROKER_DISCOVERED catalogue membership is not execution
                    # priority. Using the full catalogue as the seed made
                    # prefer_allowlisted_handoff a no-op, so oil/index desks
                    # without specs kept first focus. Seed the expected
                    # scalping desks; other liquid catalogue symbols stay in
                    # the queue after them. Gates are unchanged.
                    eligible = prefer_allowlisted_handoff(
                        eligible, DEFAULT_SCALPING_UNIVERSE
                    )
            except Exception:
                logger.exception("prefer_allowlisted_handoff_failed")
            try:
                from app.application.services.research_execution_bridge import (
                    merge_research_into_execution_handoff,
                )

                uni = [
                    str(s).strip().upper()
                    for s in (scan.get("universe") or [])
                    if str(s).strip()
                ]
                if not uni:
                    try:
                        from app.domain.trading.gold_only import (
                            gold_only_diagnostics,
                        )

                        g = gold_only_diagnostics() or {}
                        uni = [
                            str(s).strip().upper()
                            for s in (
                                g.get("execution_universe_gateway")
                                or g.get("execution_universe")
                                or []
                            )
                            if str(s).strip()
                        ]
                    except Exception:
                        uni = []
                eligible = merge_research_into_execution_handoff(
                    eligible,
                    universe=uni,
                )
            except Exception:
                logger.exception("research_execution_handoff_failed")
            try:
                from app.domain.trading.gold_only import (
                    filter_autonomous_symbols,
                    gold_only_enabled,
                )

                if gold_only_enabled():
                    eligible = list(filter_autonomous_symbols(eligible))
            except Exception:
                logger.exception("gold_only_post_research_handoff_failed")
            if not eligible and isinstance(scan, dict):
                try:
                    from app.application.services.institutional_multi_asset_scanner import (
                        independent_evaluation_symbols,
                    )

                    ranked_rows: list[Any] = []
                    for key in ("opportunity_ranked", "ranked", "rows"):
                        block = scan.get(key)
                        if isinstance(block, list):
                            ranked_rows.extend(
                                r for r in block if isinstance(r, dict)
                            )
                    open_for_eval: set[str] = set()
                    try:
                        from app.domain.institutional_trading.operations.quantforg_position_cap import (
                            engine_position_rows,
                            quantforg_open_symbols,
                        )

                        open_for_eval = quantforg_open_symbols(
                            engine_position_rows(self.position_management.engine)
                        )
                    except Exception:
                        open_for_eval = set()
                    eligible = independent_evaluation_symbols(
                        ranked_rows,
                        existing=(),
                        open_symbols=open_for_eval,
                        cap=int(
                            getattr(
                                DEFAULT_AI_SCALPING_CONFIG,
                                "max_universe_symbols",
                                36,
                            )
                            or 36
                        ),
                    )
                except Exception:
                    logger.exception("independent_evaluation_fallback_failed")
            try:
                from app.domain.institutional_trading.ai_scalping.config import (
                    DEFAULT_SCALPING_UNIVERSE,
                )
                from app.domain.institutional_trading.auto_trading import (
                    ensure_scalping_universe_handoff,
                )
                from app.domain.trading.gold_only import gold_only_enabled as _go2

                if not _go2():
                    cat = [
                        str(s).strip().upper()
                        for s in (
                            (scan.get("universe") if isinstance(scan, dict) else None)
                            or []
                        )
                        if str(s).strip()
                    ]
                    # Research merge can re-prefer oil/crosses and scan-eligible
                    # often omits majors without a BUY/SELL row. Re-seed expected
                    # desks from the live catalogue; unspecified commodity desks
                    # stay fail-closed and cannot keep first focus.
                    eligible = ensure_scalping_universe_handoff(
                        eligible,
                        DEFAULT_SCALPING_UNIVERSE,
                        catalogue=cat,
                    )
            except Exception:
                logger.exception("ensure_scalping_universe_handoff_failed")
            scan["eligible_symbols"] = list(eligible)
            scan["eligible_count"] = len(eligible)
            with self._lock:
                self._last_multi_asset_scan = dict(scan)
                self._eligible_handoff_queue = list(eligible)
                self._eligible_consumed = set()
                self._entries_this_scan = 0
            if eligible:
                first = eligible[0]
                with self._lock:
                    self._eligible_consumed.add(first)
                    self._entries_this_scan = 1
                logger.warning(
                    "multi_asset_opportunity_selected",
                    symbol=first,
                    eligible_count=len(eligible),
                    eligible_symbols=eligible[:8],
                    blocked_by_portfolio=scan.get("blocked_by_portfolio"),
                    handoff="multi_symbol_independent",
                    max_entries_per_cycle=int(
                        getattr(DEFAULT_AI_SCALPING_CONFIG, "max_entries_per_cycle", 5)
                        or 5
                    ),
                    max_open_trades=int(
                        getattr(DEFAULT_AI_SCALPING_CONFIG, "max_open_trades", 5) or 5
                    ),
                    open_positions=open_n,
                )
                return first
            logger.warning(
                "multi_asset_scan_no_executable_opportunity",
                eligible_count=scan.get("eligible_count"),
                blocked_by_portfolio=scan.get("blocked_by_portfolio"),
                reason=scan.get("portfolio_block_reason") or scan.get("note"),
            )
            return None
        except Exception:
            logger.exception("multi_asset_preferred_symbol_failed")
            with self._lock:
                if not isinstance(self._last_multi_asset_scan, dict):
                    self._last_multi_asset_scan = {
                        "as_of": datetime.now(UTC).isoformat().replace(
                            "+00:00", "Z"
                        ),
                        "enabled": True,
                        "scan_incomplete": True,
                        "note": "multi_asset_scan_exception",
                        "eligible_symbols": [],
                        "eligible_count": 0,
                        "universe": [],
                        "rows": [],
                    }
            return None

    def _take_next_handoff_symbol(self) -> str | None:
        """Next eligible independent symbol from last parallel scan (no rescan)."""
        from app.domain.institutional_trading.ai_scalping.config import (
            DEFAULT_AI_SCALPING_CONFIG,
        )

        max_e = max(1, int(getattr(DEFAULT_AI_SCALPING_CONFIG, "max_entries_per_cycle", 3) or 3))
        max_open = max(1, int(getattr(DEFAULT_AI_SCALPING_CONFIG, "max_open_trades", 5) or 5))
        from app.domain.institutional_trading.operations.quantforg_position_cap import (
            count_quantforg_positions,
            engine_position_rows,
            is_quantforg_same_symbol_open,
            quantforg_open_symbols,
            same_symbol_ownership_facts,
        )

        rows: list[Any] = []
        try:
            rows = engine_position_rows(self.position_management.engine)
            open_syms = quantforg_open_symbols(rows)
            open_n = count_quantforg_positions(rows)
        except Exception:
            open_syms = set()
            open_n = 0
        if open_n >= max_open:
            logger.warning(
                "multi_asset_handoff_blocked_max_open",
                open_positions=open_n,
                max_open_trades=max_open,
            )
            return None
        with self._lock:
            if self._entries_this_scan >= max_e:
                return None
            for sym in self._eligible_handoff_queue:
                if not sym or sym in self._eligible_consumed:
                    continue
                try:
                    from app.domain.trading.gold_only import (
                        gold_only_enabled,
                        is_gold_symbol,
                    )

                    if gold_only_enabled() and not is_gold_symbol(sym):
                        self._eligible_consumed.add(sym)
                        continue
                except Exception:
                    pass
                # Never drop a NEW independent continuation on an open
                # QuantForg gold ticket — Risk/PRE enforce winner-only
                # scale-in and reject averaging down.
                if is_quantforg_same_symbol_open(sym, open_syms):
                    self._eligible_consumed.add(sym)
                    self._entries_this_scan += 1
                    facts = same_symbol_ownership_facts(rows, candidate_symbol=sym)
                    logger.warning(
                        "multi_asset_handoff_scale_in_candidate",
                        symbol=sym,
                        reason="QUANTFORG_SAME_SYMBOL_OPEN_SCALE_IN",
                        **facts,
                    )
                    return sym
                self._eligible_consumed.add(sym)
                self._entries_this_scan += 1
                logger.warning(
                    "multi_asset_handoff_next",
                    symbol=sym,
                    entries_this_scan=self._entries_this_scan,
                    max_entries_per_cycle=max_e,
                    open_positions=open_n,
                    max_open_trades=max_open,
                    remaining_independent=[
                        s
                        for s in self._eligible_handoff_queue
                        if s
                        and s not in self._eligible_consumed
                        and not is_quantforg_same_symbol_open(s, open_syms)
                    ][:8],
                )
                return sym
        return None

    def last_multi_asset_scan(self) -> dict[str, Any] | None:
        with self._lock:
            return (
                dict(self._last_multi_asset_scan)
                if isinstance(self._last_multi_asset_scan, dict)
                else None
            )

    def _last_pipeline_snapshot(self) -> dict[str, Any] | None:
        from app.domain.institutional_trading.operations.fast_decision_path import (
            build_last_pipeline_snapshot,
        )

        with self._lock:
            last = self._last_cycle
        return build_last_pipeline_snapshot(last.to_dict() if last else None)

    def _current_scan_snapshot(self) -> dict[str, Any] | None:
        from app.domain.institutional_trading.operations.fast_decision_path import (
            build_current_scan_decision,
        )

        with self._lock:
            scan = (
                dict(self._last_multi_asset_scan)
                if isinstance(self._last_multi_asset_scan, dict)
                else None
            )
        if not scan:
            try:
                from app.application.services.institutional_multi_asset_scanner import (
                    get_last_multi_asset_scan,
                )

                scan = get_last_multi_asset_scan()
            except Exception:
                scan = None
        if not isinstance(scan, dict):
            return None
        current = scan.get("current_scan")
        if isinstance(current, dict) and current.get("label") == "CURRENT_SCAN":
            return dict(current)
        return build_current_scan_decision(scan)

    def _fast_decision_snapshot(self) -> dict[str, Any]:
        """Observability only — never becomes an execution gate."""
        try:
            from app.domain.institutional_trading.operations.fast_decision_path import (
                is_ignored_action_value,
                opportunity_window_snapshot,
            )

            current = self._current_scan_snapshot()
            snap = opportunity_window_snapshot(
                current_scan=current
                if isinstance(current, dict) and current.get("label") == "CURRENT_SCAN"
                else None
            )
            last_pipeline = self._last_pipeline_snapshot()
            with self._lock:
                last = self._last_cycle
                queue = list(self._eligible_handoff_queue)
            snap["eligible_symbols"] = queue[:16]
            snap["last_abort_reason"] = getattr(last, "abort_reason", None) if last else None
            snap["last_cycle_outcome"] = (
                getattr(last, "cycle_outcome", None) if last else None
            )
            snap["current_scan"] = (
                current
                if isinstance(current, dict) and current.get("label") == "CURRENT_SCAN"
                else None
            )
            snap["last_pipeline"] = last_pipeline
            snap["current_scan_symbol"] = (
                current.get("current_scan_symbol")
                if isinstance(current, dict)
                else snap.get("symbol")
            )
            snap["last_pipeline_symbol"] = (
                last_pipeline.get("last_pipeline_symbol") if last_pipeline else None
            )
            snap["last_safety_symbol"] = (
                last_pipeline.get("last_safety_symbol") if last_pipeline else None
            )
            snap["last_optimizer_symbol"] = (
                last_pipeline.get("last_optimizer_symbol") if last_pipeline else None
            )
            if is_ignored_action_value(snap.get("last_abort_reason")):
                # Last ITE NO_TRADE abort is not the current-scan blocking gate.
                snap["last_abort_reason_class"] = "NO_TRADE_EVENT"
            try:
                from app.domain.institutional_trading.operations.system_coherence import (
                    compose_system_snapshot,
                )

                contract = None
                if last is not None:
                    diag = getattr(last, "market_context_diagnostics", None)
                    if isinstance(diag, dict):
                        contract = diag.get("execution_contract")
                snap["system_coherence"] = compose_system_snapshot(
                    current_scan=current
                    if isinstance(current, dict)
                    else None,
                    last_pipeline=last_pipeline,
                    contract=contract if isinstance(contract, dict) else None,
                )
            except Exception:
                logger.exception("system_coherence_compose_failed")
            return snap
        except Exception:
            logger.exception("fast_decision_snapshot_failed")
            return {"window": "FIRST_TRADE_OPPORTUNITY_WINDOW", "forces_trades": False}

    def _remember_pick_abort(self, reason: str | None) -> None:
        """Stamp why pick returned None. Observability only — does not send orders."""
        with self._lock:
            self._last_pick_abort = str(reason).strip() if reason else None

    async def _pick_executable_symbol_async(self) -> str | None:
        """Highest-ranked full-mode symbol after institutional multi-asset scan.

        Gold-only is a universe restriction, not a scanner bypass. CURRENT_SCAN
        is published by ``run_institutional_multi_asset_scan`` before any
        executable symbol is returned.

        Reuses the last parallel scan's eligible queue when max_entries_per_cycle
        still has capacity — continuous multi-symbol handoff without re-scoring.
        """
        from app.application.services.closeonly_symbol_router import (
            resolve_executable_symbol,
        )
        from app.domain.trading.gold_only import (
            canonical_gold_execution_symbol,
            filter_autonomous_symbols,
            gold_only_enabled,
            is_bare_gold_symbol,
            is_gold_symbol,
        )

        self._remember_pick_abort(None)
        preferred = self._take_next_handoff_symbol()
        if not preferred:
            preferred = await self._multi_asset_preferred_symbol()

        if gold_only_enabled():
            if preferred and not is_gold_symbol(preferred):
                logger.warning(
                    "GOLD_ONLY_SYMBOL_REJECTED",
                    symbol=preferred,
                    next_action="NO_EXECUTABLE_FOCUS",
                )
                preferred = None
            gold_desk = canonical_gold_execution_symbol(preferred)
            if is_bare_gold_symbol(preferred or ""):
                preferred = gold_desk
            symbol, skipped = await self._offload_blocking_io(
                resolve_executable_symbol,
                self.mt5_adapter,
                preferred=preferred or gold_desk,
                plane=self.plane,
                alpha_ranking=None,
            )
            if skipped:
                logger.warning(
                    "gold_only_closeonly_or_blocked",
                    skipped=skipped,
                    preferred=preferred or gold_desk,
                )
            if symbol is not None and (
                not is_gold_symbol(symbol) or is_bare_gold_symbol(symbol)
            ):
                logger.warning(
                    "GOLD_ONLY_SYMBOL_REJECTED",
                    symbol=symbol,
                    next_action="NO_EXECUTABLE_FOCUS",
                    reason="SYMBOL_ROUTING_BLOCK",
                )
                self._remember_pick_abort("NO_EXECUTABLE_SYMBOL")
                return None
            with self._lock:
                last = (
                    dict(self._last_multi_asset_scan)
                    if isinstance(self._last_multi_asset_scan, dict)
                    else None
                )
            scan_complete = bool(
                last
                and last.get("as_of")
                and last.get("note") != "multi_asset_scan_disabled"
                and last.get("note") != "scan_in_flight_no_prior_snapshot"
                and not last.get("scan_incomplete")
            )
            eligible = list(
                filter_autonomous_symbols(last.get("eligible_symbols") or [])
            ) if last else []
            if scan_complete and not eligible:
                # Rejected / ineligible Gold — CURRENT_SCAN already published.
                from app.domain.institutional_trading.operations.fast_decision_path import (
                    scan_ineligible_abort_reason,
                )

                self._remember_pick_abort(scan_ineligible_abort_reason(last))
                return None
            if symbol is None:
                logger.warning(
                    "no_full_mode_gold_symbol_available",
                    preferred=preferred or gold_desk,
                    skipped=skipped,
                    selected=symbol,
                )
                self._remember_pick_abort("NO_EXECUTABLE_SYMBOL")
                return None
            logger.warning("Submitting Order...", symbol=symbol)
            self._remember_pick_abort(None)
            return symbol

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
            and last.get("note") != "scan_in_flight_no_prior_snapshot"
            and not last.get("scan_incomplete")
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
                self._remember_pick_abort("NO_EXECUTABLE_SYMBOL")
                return None
            preferred = (
                await self._offload_blocking_io(self._alpha_preferred_symbol)
            )
            if not preferred:
                self._remember_pick_abort("NO_EXECUTABLE_SYMBOL")
                return None
        alpha_ranking = await self._offload_blocking_io(self._alpha_ranking_rows)
        symbol, skipped = await self._offload_blocking_io(
            resolve_executable_symbol,
            self.mt5_adapter,
            preferred=preferred,
            plane=self.plane,
            alpha_ranking=alpha_ranking,
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
            self._remember_pick_abort("NO_EXECUTABLE_SYMBOL")
        else:
            logger.warning("Submitting Order...", symbol=symbol)
            self._remember_pick_abort(None)
        return symbol

    def _pick_executable_symbol(self) -> str | None:
        """Sync fallback — prefer Alpha / gold when async scan is not awaited."""
        from app.application.services.closeonly_symbol_router import (
            resolve_executable_symbol,
        )
        from app.domain.trading.gold_only import (
            canonical_gold_execution_symbol,
            gold_only_enabled,
            is_bare_gold_symbol,
            is_gold_symbol,
        )

        if gold_only_enabled():
            preferred = canonical_gold_execution_symbol()
            symbol, skipped = resolve_executable_symbol(
                self.mt5_adapter,
                preferred=preferred,
                plane=self.plane,
                alpha_ranking=None,
            )
            if (
                symbol is None
                or not is_gold_symbol(symbol)
                or is_bare_gold_symbol(symbol)
            ):
                return None
            return symbol

        preferred = self._alpha_preferred_symbol()
        with self._lock:
            last = self._last_multi_asset_scan
        if isinstance(last, dict):
            best = str(last.get("best_symbol") or "").upper()
            if best:
                preferred = best
        if not preferred:
            return None
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
        stage_timings_ms: dict[str, float] = {}
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
            t_pick = time.perf_counter()
            enrich = _enrich_from_adapter(self.probes)
            symbol = await self._pick_executable_symbol_async()
            stage_timings_ms["signal_focus_pick_ms"] = round(
                (time.perf_counter() - t_pick) * 1000.0, 1
            )
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
            t_md = time.perf_counter()
            ctx = await build_ite_cycle_market_context(
                self.mt5_adapter,
                symbol=symbol,
                position_engine=self.position_management.engine,
            )
            stage_timings_ms["market_context_ms"] = round(
                float(getattr(ctx, "latency_ms", 0.0) or 0.0)
                or (time.perf_counter() - t_md) * 1000.0,
                1,
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
                health = await self._offload_blocking_io(self.tick_health)
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
                t_cycle = time.perf_counter()
                cycle = await self._await_cycle_budget(
                    self._offload_blocking_io(
                        self.run_shadow_cycle,
                        snapshot=ctx.snapshot,
                        account=ctx.account,
                        market_context_diagnostics=dict(ctx.diagnostics),
                    ),
                    what="run_shadow_cycle",
                    cancel_on_timeout=False,
                )
            else:
                t_cycle = time.perf_counter()
                cycle = await self._await_cycle_budget(
                    self._offload_blocking_io(
                        self.run_auto_cycle,
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
                    ),
                    what="run_auto_cycle",
                    cancel_on_timeout=False,
                )
            stage_timings_ms["decision_safety_risk_oms_ms"] = round(
                (time.perf_counter() - t_cycle) * 1000.0, 1
            )
            oms_latency = None
            with self._lock:
                if self._last_cycle is not None:
                    self._last_cycle.market_context_diagnostics = (
                        _merge_cycle_diagnostics(
                            ctx.diagnostics,
                            self._last_cycle.market_context_diagnostics,
                        )
                    )
                    self._last_cycle.market_context_reason = ctx.reason
                    self._last_cycle.snapshot_present = True
                    cycle = self._last_cycle
                bridge = self._last_bridge_result
            oms = getattr(bridge, "oms_result", None) if bridge is not None else None
            if oms is not None:
                oms_latency = getattr(oms, "latency_ms", None)
                raw = getattr(oms, "raw", None)
                if isinstance(raw, dict):
                    stages = raw.get("stages") or []
                    for row in stages:
                        if not isinstance(row, dict):
                            continue
                        name = str(row.get("stage") or "").strip().lower().replace(
                            " ", "_"
                        )
                        if name:
                            stage_timings_ms[f"oms_{name}_ms"] = float(
                                row.get("elapsed_ms") or 0.0
                            )
                if oms_latency is not None:
                    stage_timings_ms["oms_pipeline_ms"] = round(float(oms_latency), 1)
            stage_timings_ms["execute_now_total_ms"] = round(
                (time.perf_counter() - t0) * 1000.0, 1
            )
            payload = self.build_execute_now_payload(
                cycle,
                execution_ms=(time.perf_counter() - t0) * 1000.0,
            )
            payload["stage_timings_ms"] = dict(stage_timings_ms)
            if oms is not None and isinstance(getattr(oms, "raw", None), dict):
                raw_flags = oms.raw
                payload["oms_reached"] = bool(raw_flags.get("oms_reached", True))
                payload["gateway_reached"] = bool(raw_flags.get("gateway_reached"))
                payload["order_check_reached"] = bool(
                    raw_flags.get("order_check_reached")
                )
                payload["order_send_reached"] = bool(raw_flags.get("order_send_reached"))
            logger.warning(
                "[QF][EXEC_STAGE_TIMING]",
                **{
                    k: v
                    for k, v in stage_timings_ms.items()
                    if isinstance(v, (int, float))
                },
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

    async def _offload_blocking_io(self, fn: Any, /, *args: Any, **kwargs: Any) -> Any:
        """Run sync ITE/Gateway work on the bounded I/O pool.

        Keeps the FastAPI event loop free for /health/live and /auth/me.
        Does not change trading decisions — only the executing thread.
        """
        from app.application.services.blocking_io_offload import offload_blocking

        return await offload_blocking(fn, *args, **kwargs)

    async def _await_cycle_budget(
        self,
        awaitable: Any,
        *,
        what: str,
        cancel_on_timeout: bool = True,
    ) -> Any:
        """Bound one cycle step so a hung Gateway/scan cannot freeze the loop.

        Risk→OMS→MT5 (``run_auto_cycle``) is not cancelled: an in-flight
        order_send must not be aborted by the scan budget.
        """
        from app.domain.institutional_trading.operations.worker_runtime_state import (
            cycle_hard_timeout_seconds,
        )

        started = self._cycle_started_mono or time.monotonic()
        timeout = cycle_hard_timeout_seconds(self.interval_seconds)
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            if cancel_on_timeout:
                if asyncio.iscoroutine(awaitable):
                    awaitable.close()
                raise TimeoutError(f"cycle_budget_exhausted:{what}")
            return await awaitable
        if not cancel_on_timeout:
            return await awaitable
        try:
            return await asyncio.wait_for(awaitable, timeout=remaining)
        except TimeoutError:
            raise TimeoutError(f"cycle_budget_exhausted:{what}") from None

    async def watch_orchestrator_task(
        self,
        orch: asyncio.Task[Any],
        *,
        poll_seconds: float = 5.0,
    ) -> str:
        """Poll the existing run_forever task. Does not start a second loop.

        Returns ``done`` when the task finishes, ``hung`` when the scheduler
        is stalled so the watchdog can cancel and restart it.
        """
        poll = max(0.05, float(poll_seconds or 5.0))
        while not orch.done():
            try:
                await asyncio.wait_for(asyncio.shield(orch), timeout=poll)
            except TimeoutError:
                stalled = False
                try:
                    stalled = bool(self.note_scheduler_stalled())
                except Exception:
                    logger.exception("ite_watchdog_stall_check_failed")
                if stalled:
                    return "hung"
        return "done"

    async def run_forever(self) -> None:
        """Background loop — live market context → Decision→Risk→Safety→OMS."""
        import os

        self._started_mono = time.monotonic()
        self._cycle_started_mono = 0.0

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
        try:
            from app.application.services.telegram_dispatcher import (
                notify_robot_started,
            )

            notify_robot_started()
        except Exception:
            logger.exception("telegram_robot_started_hook_failed")
        try:
            from app.domain.institutional_trading.operations.fast_decision_path import (
                ensure_opportunity_window,
            )

            ensure_opportunity_window()
        except Exception:
            logger.exception("opportunity_window_start_failed")
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
            self._cycle_started_mono = time.monotonic()
            self._cycle_started_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
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
                    bind_cycle_gateway_reads,
                    build_ite_cycle_market_context,
                )

                bind_cycle_gateway_reads(self.mt5_adapter)

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

                try:
                    self._protect_open_positions(reason="pre_scan_manage")
                except Exception:
                    logger.exception("pre_scan_position_protect_failed")

                t_pick = time.perf_counter()
                # Dedicated scan window — never leftover cycle remainder.
                # Wrapping pick in remaining hard time aborted the universe as
                # cycle_budget_exhausted:pick_executable_symbol when PME already
                # consumed the budget. Inner scan still isolates per-symbol
                # timeouts; this outer bound only prevents a hung pick.
                from app.domain.institutional_trading.operations.worker_runtime_state import (
                    cycle_hard_timeout_seconds as _hard_to,
                    cycle_scan_budget_seconds as _scan_to,
                )

                pick_timeout = min(
                    _scan_to(self.interval_seconds),
                    _hard_to(self.interval_seconds),
                )
                try:
                    symbol = await asyncio.wait_for(
                        self._pick_executable_symbol_async(),
                        timeout=max(0.05, float(pick_timeout)),
                    )
                except TimeoutError:
                    raise TimeoutError(
                        "cycle_budget_exhausted:pick_executable_symbol"
                    ) from None
                pick_ms = round((time.perf_counter() - t_pick) * 1000.0, 1)
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
                if self._recovery_orders_blocked:
                    try:
                        from app.application.services.ite_cycle_market_context import (
                            refresh_execution_gateway_reads,
                        )

                        refresh_execution_gateway_reads(self.mt5_adapter)
                    except Exception:
                        logger.exception("recovery_fresh_history_failed")
                ctx = await self._await_cycle_budget(
                    build_ite_cycle_market_context(
                        self.mt5_adapter,
                        symbol=symbol,
                        position_engine=self.position_management.engine,
                    ),
                    what="build_ite_cycle_market_context",
                )
                try:
                    with self._lock:
                        last_scan = (
                            dict(self._last_multi_asset_scan)
                            if isinstance(self._last_multi_asset_scan, dict)
                            else None
                        )
                    gw_snap: dict[str, Any] = {}
                    try:
                        from app.infrastructure.brokers.mt5.metrics import (
                            gateway_metrics as _gw_metrics,
                        )

                        gw_snap = _gw_metrics.snapshot()
                    except Exception:
                        gw_snap = {}
                    slow_ep = str(gw_snap.get("slowest_endpoint") or "")
                    slow_stats = (gw_snap.get("by_endpoint") or {}).get(slow_ep) or {}
                    signal_age_ms = None
                    built_at = getattr(ctx, "snapshot_built_at", None)
                    if built_at:
                        try:
                            created = datetime.fromisoformat(
                                str(built_at).replace("Z", "+00:00")
                            )
                            signal_age_ms = round(
                                (datetime.now(UTC) - created).total_seconds() * 1000.0,
                                1,
                            )
                        except Exception:
                            signal_age_ms = None
                    logger.warning(
                        "ite_cycle_stage_timings",
                        scanner_duration_ms=(
                            last_scan.get("scanner_duration_ms") if last_scan else None
                        ),
                        signal_focus_pick_ms=pick_ms,
                        market_context_duration_ms=round(
                            float(getattr(ctx, "latency_ms", 0.0) or 0.0), 1
                        ),
                        market_context_reused=bool(getattr(ctx, "reused", False)),
                        cycle_signal_age_ms=signal_age_ms,
                        gateway_p50=slow_stats.get("p50"),
                        gateway_p95=slow_stats.get("p95"),
                        gateway_p99=slow_stats.get("p99"),
                        slowest_endpoint=gw_snap.get("slowest_endpoint"),
                        slowest_latency_ms=gw_snap.get("slowest_latency_ms"),
                    )
                except Exception:
                    logger.exception("ite_cycle_stage_timings_failed")
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
                    pick_abort = (
                        str(getattr(self, "_last_pick_abort", None) or "").strip()
                        or "NO_EXECUTABLE_SYMBOL"
                    )
                    scan_diag: dict[str, Any] = {}
                    try:
                        with self._lock:
                            last_scan_m = (
                                dict(self._last_multi_asset_scan)
                                if isinstance(self._last_multi_asset_scan, dict)
                                else None
                            )
                        if isinstance(last_scan_m, dict):
                            rows = last_scan_m.get("rows") or last_scan_m.get("noc_rows") or []
                            scan_diag = {
                                "symbols_queued": last_scan_m.get("symbols_queued"),
                                "symbols_evaluated": last_scan_m.get(
                                    "symbols_evaluated"
                                ),
                                "eligible_count": last_scan_m.get("eligible_count"),
                                "universe": list(last_scan_m.get("universe") or [])[:36],
                                "first_blocking_gate": last_scan_m.get(
                                    "first_blocking_gate"
                                ),
                                "context_reject_sample": [
                                    {
                                        "symbol": r.get("symbol"),
                                        "broker_symbol": r.get("broker_symbol"),
                                        "context_status": r.get("context_status"),
                                        "context_reason": r.get("context_reason")
                                        or r.get("reject_reason"),
                                        "direction": r.get("direction"),
                                    }
                                    for r in rows[:12]
                                    if isinstance(r, dict)
                                ],
                            }
                    except Exception:
                        scan_diag = {}
                    logger.warning(
                        "AI Decision",
                        action="NO_TRADE",
                        reason=pick_abort.lower(),
                    )
                    logger.warning("Waiting Next Cycle", reason=pick_abort.lower())
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
                            reason=pick_abort.lower(),
                            validation_id=_pvm_vid,
                        )
                        _pvm_get().record_no_trade_reasons(
                            [pick_abort.lower()], validation_id=_pvm_vid
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
                    result = ShadowCycleResult(
                        ok=True,
                        trace_id=None,
                        mode=self.plane.mode.value,
                        detail=(
                            "WAITING_NEXT_CYCLE — no executable symbol"
                            if pick_abort == "NO_EXECUTABLE_SYMBOL"
                            else f"WAITING_NEXT_CYCLE — {pick_abort}"
                        ),
                        cycle_outcome="waiting_next_cycle",
                        abort_reason=pick_abort,
                        snapshot_present=True,
                        market_context_diagnostics=scan_diag or None,
                        market_context_reason=(
                            str(scan_diag.get("first_blocking_gate") or "")
                            or None
                        ),
                    )
                    with self._lock:
                        self._last_cycle = result
                        self._cycles += 1
                    self._clear_ephemeral_cycle_state()

                elif not ctx.ok or ctx.snapshot is None or ctx.account is None:
                    health = await self._offload_blocking_io(self.tick_health)
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
                    if not manage_only:
                        self._release_non_entry_slot()
                    self._clear_ephemeral_cycle_state()
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
                        await self._await_cycle_budget(
                            self._offload_blocking_io(
                                self.run_shadow_cycle,
                                snapshot=ctx.snapshot,
                                account=ctx.account,
                                market_context_diagnostics=dict(ctx.diagnostics),
                            ),
                            what="run_shadow_cycle",
                            cancel_on_timeout=False,
                        )
                    else:
                        await self._await_cycle_budget(
                            self._offload_blocking_io(
                                self.run_auto_cycle,
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
                            ),
                            what="run_auto_cycle",
                            cancel_on_timeout=False,
                        )
                    with self._lock:
                        if self._last_cycle is not None:
                            self._last_cycle.market_context_diagnostics = (
                                _merge_cycle_diagnostics(
                                    ctx.diagnostics,
                                    self._last_cycle.market_context_diagnostics,
                                )
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
                    # Never replay a prior OMS ticket on a cycle that did not submit.
                    last_bridge = getattr(self, "_last_bridge_result", None)
                    last_fwd = False
                    if last is not None:
                        last_fwd = bool(getattr(last, "forwarded_to_oms", False))
                    contract = {}
                    diag = (
                        getattr(last, "market_context_diagnostics", None)
                        if last is not None
                        else None
                    )
                    if isinstance(diag, dict):
                        raw_c = diag.get("execution_contract")
                        if isinstance(raw_c, dict):
                            contract = raw_c
                    if last_decision is not None:
                        self._log_post_ai_execution_chain(
                            decision=last_decision,
                            bridge_result=last_bridge if last_fwd else None,
                            execution_enabled=bool(
                                getattr(_gs(), "execution_enabled", False)
                            ),
                            force_shadow=False,
                            this_cycle_forwarded=last_fwd,
                            may_submit_oms=contract.get("may_submit_oms"),
                            blocking_stage=contract.get("blocking_stage"),
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
                    if not last_fwd:
                        self._release_non_entry_slot()
            except TimeoutError as exc:
                from datetime import timedelta

                from app.domain.institutional_trading.operations.worker_runtime_state import (  # noqa: E501
                    cycle_hard_timeout_seconds,
                )

                stage = str(exc) if str(exc) else "unknown"
                last_scan: dict[str, Any] = {}
                with self._lock:
                    if isinstance(self._last_multi_asset_scan, dict):
                        last_scan = dict(self._last_multi_asset_scan)
                hard = cycle_hard_timeout_seconds(self.interval_seconds)
                deadline_iso = None
                try:
                    started_at = self._cycle_started_at
                    if started_at:
                        started_dt = datetime.strptime(
                            started_at, "%Y-%m-%dT%H:%M:%SZ"
                        ).replace(tzinfo=UTC)
                        deadline_iso = (
                            started_dt + timedelta(seconds=hard)
                        ).strftime("%Y-%m-%dT%H:%M:%SZ")
                except Exception:
                    deadline_iso = None
                ranked = last_scan.get("ranked") or last_scan.get("rows") or []
                signals_found = 0
                if isinstance(ranked, list):
                    signals_found = sum(
                        1
                        for row in ranked
                        if isinstance(row, dict)
                        and str(row.get("direction") or "").upper() in {"BUY", "SELL"}
                    )
                timeout_diag = {
                    "timeout_stage": stage,
                    "cycle_started_at": self._cycle_started_at,
                    "cycle_deadline": deadline_iso,
                    "cycle_duration_ms": round(
                        (time.perf_counter() - cycle_t0) * 1000.0, 1
                    ),
                    "symbols_discovered": len(last_scan.get("universe") or []),
                    "symbols_queued": last_scan.get("symbols_queued"),
                    "symbols_evaluated": last_scan.get("symbols_evaluated"),
                    "symbols_completed": last_scan.get("symbols_completed"),
                    "symbols_timed_out": last_scan.get("symbols_timed_out"),
                    "symbols_budget_skipped": last_scan.get("symbols_budget_skipped"),
                    "signals_found": signals_found,
                    "eligible_opportunities": last_scan.get("eligible_count"),
                    "risk_evaluations": 0,
                    "oms_attempts": 0,
                    "orders_submitted": 0,
                    "scanner_duration_ms": last_scan.get("scanner_duration_ms"),
                    "execution_result": "NO BROKER ORDER WAS SUBMITTED",
                }
                logger.warning(
                    "ite_orchestrator_cycle_timeout",
                    error=str(exc),
                    timeout_stage=stage,
                    run_state=self.plane.auto_trading_run_state,
                    symbols_evaluated=timeout_diag.get("symbols_evaluated"),
                    symbols_timed_out=timeout_diag.get("symbols_timed_out"),
                )
                try:
                    self._manage_open_positions_after_timeout()
                    timeout_diag["position_management_after_timeout"] = True
                except Exception:
                    logger.exception("cycle_timeout_position_manage_failed")
                    timeout_diag["position_management_after_timeout"] = False
                with self._lock:
                    self._last_cycle = ShadowCycleResult(
                        ok=False,
                        trace_id=None,
                        mode=self.plane.mode.value,
                        detail=f"cycle timeout: {exc}",
                        cycle_outcome="error",
                        abort_reason="CYCLE_TIMEOUT",
                        market_context_diagnostics=timeout_diag,
                        forwarded_to_oms=False,
                        mt5_ticket=None,
                    )
                    self._cycles += 1
                    self._last_failure = "CYCLE_TIMEOUT"
                self._release_non_entry_slot()
                self._clear_ephemeral_cycle_state()
                try:
                    from app.application.services.cycle_evidence import (
                        record_cycle_evidence,
                    )

                    record_cycle_evidence(
                        cycle_outcome="error",
                        decision_action="NO_TRADE",
                        reasons=[f"cycle timeout: {exc}"],
                        abort_reason="CYCLE_TIMEOUT",
                    )
                except Exception:
                    logger.exception("cycle_evidence_timeout_record_failed")
                logger.warning(
                    "Autonomous engine continuing after cycle timeout",
                    error=str(exc),
                    timeout_stage=stage,
                    run_state=self.plane.auto_trading_run_state,
                )
            except Exception as exc:
                logger.exception("ite_orchestrator_cycle_failed", error=str(exc))
                try:
                    self._protect_open_positions(reason="cycle_exception_manage")
                except Exception:
                    logger.exception("cycle_exception_position_manage_failed")
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
                    self._last_failure = "CYCLE_EXCEPTION"
                self._clear_ephemeral_cycle_state()
                try:
                    self._emit_telegram_cycle(self._last_cycle)
                except Exception:
                    logger.exception("telegram_cycle_exception_notify_failed")
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
                    from app.application.services.ite_cycle_market_context import (
                        unbind_cycle_gateway_reads as _unbind_cycle_reads,
                    )

                    _unbind_cycle_reads(self.mt5_adapter)
                except Exception:
                    logger.exception("cycle_gateway_reads_unbind_failed")
                try:
                    if _pvm_token is not None:
                        from app.domain.institutional_trading.production_validation_mode import (  # noqa: E501
                            get_production_validation_recorder as _pvm_rec_end,
                        )

                        _pvm_rec_end().unbind_context(_pvm_token)
                except Exception:
                    logger.exception("pvm_unbind_orchestrator_cycle_failed")
            last_out = None
            last_ok = False
            try:
                with self._lock:
                    last_out = getattr(self._last_cycle, "cycle_outcome", None)
                    last_ok = bool(getattr(self._last_cycle, "ok", False))
                cycle_ms = round((time.perf_counter() - cycle_t0) * 1000.0, 1)
                self._last_cycle_duration_ms = cycle_ms
                self.mark_cycle_finished(
                    successful=last_ok
                    or last_out
                    in {
                        "safety_blocked",
                        "recovering",
                        "waiting_next_cycle",
                        "no_snapshot",
                        "error",
                    }
                )
                logger.warning(
                    "Waiting Next Cycle",
                    interval_seconds=self.interval_seconds,
                    cycle_ms=cycle_ms,
                    worker_state=(self.status() or {}).get("worker_state"),
                )
            except Exception:
                logger.exception("cycle_completion_tail_failed")
            # Continuous scalping cadence:
            # 1) More eligible symbols from last parallel scan → no idle sleep
            # 2) PME just closed → immediate rescan (post_close_rescan)
            sleep_s = float(self.interval_seconds)
            try:
                from app.domain.institutional_trading.operations.decision_cycle import (
                    consume_immediate_wakeup,
                )

                wakeup = consume_immediate_wakeup()
                if wakeup:
                    sleep_s = 0.0
                    logger.warning(
                        "event_driven_decision_wakeup",
                        reason=wakeup,
                    )
            except Exception:
                logger.exception("event_driven_wakeup_failed")
            try:
                from app.domain.institutional_trading.ai_scalping.config import (
                    DEFAULT_AI_SCALPING_CONFIG as _sc,
                )
                from app.domain.institutional_trading.ai_scalping.continuous_operation import (
                    get_continuous_operation_controller,
                )
                from app.domain.institutional_trading.operations.fast_decision_path import (
                    classify_candidate_outcome,
                    record_cycle_classification,
                )

                last_for_cls = None
                last_decision = None
                with self._lock:
                    last_for_cls = self._last_cycle
                    last_decision = self._last_decision
                cls = classify_candidate_outcome(
                    abort_reason=getattr(last_for_cls, "abort_reason", None)
                    if last_for_cls
                    else None,
                    failed_reasons=tuple(
                        getattr(last_for_cls, "safety_failed_reasons", ()) or ()
                    )
                    + tuple(getattr(last_for_cls, "decision_reasons", ()) or ())
                    if last_for_cls
                    else (),
                    cycle_outcome=getattr(last_for_cls, "cycle_outcome", None)
                    if last_for_cls
                    else None,
                    forwarded_to_oms=bool(
                        getattr(last_for_cls, "forwarded_to_oms", False)
                    )
                    if last_for_cls
                    else False,
                    decision_action=str(
                        getattr(
                            getattr(last_decision, "action", None),
                            "value",
                            None,
                        )
                        or getattr(last_for_cls, "decision_action", None)
                        or ""
                    )
                    if last_for_cls or last_decision
                    else "",
                )
                diag = (
                    getattr(last_for_cls, "market_context_diagnostics", None)
                    if last_for_cls
                    else None
                )
                contract = diag.get("execution_contract") if isinstance(diag, dict) else None
                if isinstance(contract, dict):
                    if contract.get("decision_state"):
                        cls["decision_state"] = contract["decision_state"]
                    if contract.get("fault_code"):
                        cls["fault_code"] = contract["fault_code"]
                    if contract.get("fault_class"):
                        cls["fault_class"] = contract["fault_class"]
                    if contract.get("fault_reason"):
                        cls["fault_reason"] = contract["fault_reason"]
                    if contract.get("next_action"):
                        cls["next_action"] = contract["next_action"]
                    if contract.get("blocking_stage"):
                        cls["blocking_stage"] = contract["blocking_stage"]
                    cls["execution_readiness"] = contract.get("execution_readiness")
                    cls["first_authoritative_blocker"] = contract.get(
                        "first_authoritative_blocker"
                    )
                    cls["all_failed_conditions"] = contract.get(
                        "all_failed_conditions"
                    )
                    cls["stages"] = contract.get("stages")
                    cls["execute_now_required"] = False
                record_cycle_classification(
                    cls,
                    cycle_ms=round((time.perf_counter() - cycle_t0) * 1000.0, 1),
                    forwarded_to_oms=bool(
                        getattr(last_for_cls, "forwarded_to_oms", False)
                    )
                    if last_for_cls
                    else False,
                    fill_symbol=str(
                        getattr(last_for_cls, "symbol", None)
                        or getattr(last_decision, "symbol", None)
                        or ""
                    )
                    or None,
                )
                if cls.get("release_entry_budget"):
                    with self._lock:
                        if self._entries_this_scan > 0:
                            self._entries_this_scan -= 1

                nxt = None
                with self._lock:
                    open_now: set[str] = set()
                    try:
                        for p in (
                            getattr(self.position_management.engine, "_positions", {})
                            or {}
                        ).values():
                            s = str(getattr(p, "symbol", "") or "").upper()
                            if s:
                                open_now.add(s)
                    except Exception:
                        open_now = set()
                    for sym in self._eligible_handoff_queue:
                        if (
                            sym
                            and sym not in self._eligible_consumed
                            and sym not in open_now
                        ):
                            nxt = sym
                            break
                    entries = int(self._entries_this_scan)
                max_e = max(1, int(getattr(_sc, "max_entries_per_cycle", 3) or 3))
                if cls.get("skip_idle_sleep") and nxt:
                    sleep_s = 0.0
                    logger.warning(
                        "fast_decision_rotate_or_continue",
                        next_symbol=nxt,
                        next_action=cls.get("next_action"),
                        fault_code=cls.get("fault_code"),
                        decision_state=cls.get("decision_state"),
                    )
                elif nxt and entries < max_e:
                    sleep_s = 0.0
                    logger.warning(
                        "multi_symbol_continue_no_idle",
                        next_symbol=nxt,
                        entries_this_scan=entries,
                        max_entries_per_cycle=max_e,
                    )
                elif bool(getattr(_sc, "post_close_rescan_enabled", True)):
                    ctrl = get_continuous_operation_controller(_sc)
                    if bool(getattr(ctrl, "pending_rescan", False)):
                        sleep_s = float(
                            getattr(_sc, "post_close_rescan_delay_seconds", 0.0) or 0.0
                        )
                        logger.warning(
                            "post_close_immediate_rescan",
                            delay_seconds=sleep_s,
                        )
            except Exception:
                logger.exception("continuous_scalp_cadence_failed")
            if sleep_s <= 0:
                await asyncio.sleep(0)
                continue
            for _ in range(int(max(1, sleep_s))):
                if self._stop.is_set():
                    break
                await asyncio.sleep(1)
        logger.info("ite_orchestrator_stopped")
        try:
            from app.application.services.telegram_dispatcher import (
                notify_robot_stopped,
            )

            notify_robot_stopped(reason="orchestrator_stopped")
        except Exception:
            logger.exception("telegram_robot_stopped_hook_failed")


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
    from dataclasses import replace as dc_replace

    from app.application.services.execution_intelligence import (
        ExecutionIntelligenceService,
    )
    from app.application.services.institutional_decision_pipeline import (
        oms_risk_engine_from_ite,
    )
    from app.application.services.institutional_execution_engine import (
        InstitutionalExecutionEngine,
    )
    from app.domain.execution_engine.journal import ExecutionJournalStore
    from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
    from app.domain.institutional_trading.execution.config import (
        ExecutionBridgeConfig,
    )

    plane = get_control_plane()
    try:
        from app.domain.institutional_trading.ai_scalping.profiles.scalping_v1 import (
            align_live_scalp_cap,
        )

        plane.max_open_trades = align_live_scalp_cap(
            plane.max_open_trades,
            trading_mode=str(plane.trading_mode or ""),
        )
    except Exception:
        logger.exception("scalp_cap_align_failed")
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
        risk_engine=oms_risk_engine_from_ite(
            dc_replace(
                DEFAULT_ITE_CONFIG,
                max_daily_loss_pct=plane.max_daily_loss_pct,
            )
        ),
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
