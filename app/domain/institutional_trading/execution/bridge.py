"""Execution Bridge — sole path from TradeDecision to Institutional OMS.

Re-verifies gates before any OMS call. Never retries. No AI.
Does not modify Phase A/B or the OMS.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from threading import Lock
from typing import TYPE_CHECKING

from app.application.services.institutional_execution_engine import parse_order_intent
from app.domain.entities.mt5_order import OrderIntent
from app.domain.institutional_trading.auto_trading import AutoTradeLiveFacts
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.decision_models import (
    DecisionAction,
    TradeDecision,
)
from app.domain.institutional_trading.eligibility import PositionEligibilityEngine
from app.domain.institutional_trading.execution.config import (
    DEFAULT_EXECUTION_BRIDGE_CONFIG,
    ExecutionBridgeConfig,
)
from app.domain.institutional_trading.execution.hashing import compute_decision_hash
from app.domain.institutional_trading.execution.journal import ExecutionAttemptJournal
from app.domain.institutional_trading.execution.kill_switch import KillSwitch
from app.domain.institutional_trading.execution.metrics import ExecutionBridgeMetrics
from app.domain.institutional_trading.execution.models import (
    BridgeAbortReason,
    ExecutionAttemptRecord,
    ExecutionAttemptStatus,
    ExecutionBridgeContext,
    ExecutionBridgeResult,
    ExecutionMode,
    OmsSubmitResult,
)
from app.domain.institutional_trading.execution.oms_port import OmsSubmitPort
from app.domain.institutional_trading.operations.models import OpsExecutionMode
from core.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from app.domain.institutional_trading.operations.control_plane import (
        OperationsControlPlane,
    )
    from app.domain.institutional_trading.reliability.platform import (
        ReliabilityPlatform,
    )


@dataclass
class ExecutionBridge:
    """Safe bridge: Decision → re-verify → (optional) OMS → journal."""

    oms: OmsSubmitPort
    config: ExecutionBridgeConfig = field(
        default_factory=lambda: DEFAULT_EXECUTION_BRIDGE_CONFIG
    )
    ite_config: ITEConfig = field(default_factory=lambda: DEFAULT_ITE_CONFIG)
    kill_switch: KillSwitch = field(default_factory=KillSwitch)
    journal: ExecutionAttemptJournal = field(default_factory=ExecutionAttemptJournal)
    metrics: ExecutionBridgeMetrics = field(default_factory=ExecutionBridgeMetrics)
    ops_plane: OperationsControlPlane | None = None
    reliability: ReliabilityPlatform | None = None
    _executed_hashes: set[str] = field(default_factory=set, repr=False)
    _executed_hash_order: list[str] = field(default_factory=list, repr=False)
    _max_executed_hashes: int = field(default=10_000, repr=False)
    _canary_day: date | None = field(default=None, repr=False)
    _canary_count: int = field(default=0, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def bind_ops(
        self,
        plane: OperationsControlPlane,
        *,
        reliability: ReliabilityPlatform | None = None,
    ) -> ExecutionBridge:
        """Wire shared kill switch + mode source of truth from ops plane."""
        self.ops_plane = plane
        self.kill_switch.bind(plane)
        if reliability is not None:
            self.reliability = reliability
        return self

    def effective_mode(self) -> ExecutionMode:
        """Ops plane mode wins when bound; else bridge config."""
        if self.ops_plane is not None:
            m = self.ops_plane.mode
            if m is OpsExecutionMode.SHADOW:
                return ExecutionMode.SHADOW
            if m is OpsExecutionMode.CANARY:
                return ExecutionMode.CANARY_LIVE
            return ExecutionMode.LIVE
        return self.config.mode

    def handle(
        self,
        decision: TradeDecision,
        context: ExecutionBridgeContext,
        *,
        trace_id: str | None = None,
    ) -> ExecutionBridgeResult:
        """Evaluate a decision. Only BUY/SELL may reach OMS (never WATCH/NO_TRADE)."""
        t0 = time.perf_counter()
        mode = self.effective_mode()
        d_hash = compute_decision_hash(decision)
        actionable = decision.action in {DecisionAction.BUY, DecisionAction.SELL}
        self.metrics.record_decision(
            confidence=decision.confidence, actionable=actionable
        )
        tid = self._ensure_trace(trace_id, decision_id=str(decision.id))

        if not actionable:
            reasons = tuple(getattr(decision, "reasons", ()) or ())
            reason_txt = "; ".join(reasons) if reasons else "no reasons"
            result = self._abort(
                decision=decision,
                context=context,
                decision_hash=d_hash,
                reason=BridgeAbortReason.IGNORED_ACTION,
                comment=(
                    f"Ignored action {decision.action.value}: {reason_txt}"
                ),
                t0=t0,
                status=ExecutionAttemptStatus.ABORTED,
            )
            self._span_bridge(tid, t0, ok=True, detail="ignored_action")
            return result

        # --- Duplicate protection (before anything else that could call OMS) ---
        with self._lock:
            is_duplicate = d_hash in self._executed_hashes
        if is_duplicate:
            self.metrics.record_duplicate()
            result = self._abort(
                decision=decision,
                context=context,
                decision_hash=d_hash,
                reason=BridgeAbortReason.DUPLICATE_DECISION,
                comment="Duplicate decision hash — execution not allowed",
                t0=t0,
                status=ExecutionAttemptStatus.DUPLICATE,
                count_reject=False,
            )
            self._span_bridge(tid, t0, ok=False, detail="duplicate")
            return result

        # 1. input_hash unchanged
        if decision.input_hash != context.expected_input_hash:
            return self._abort(
                decision=decision,
                context=context,
                decision_hash=d_hash,
                reason=BridgeAbortReason.INPUT_HASH_MISMATCH,
                comment=(
                    f"input_hash mismatch decision={decision.input_hash} "
                    f"expected={context.expected_input_hash}"
                ),
                t0=t0,
            )

        # 2. Decision age < TTL
        age = context.now - decision.as_of
        if age > timedelta(seconds=self.config.decision_ttl_seconds) or age < timedelta(
            0
        ):
            return self._abort(
                decision=decision,
                context=context,
                decision_hash=d_hash,
                reason=BridgeAbortReason.DECISION_EXPIRED,
                comment=(
                    f"Decision age {age.total_seconds():.1f}s exceeds "
                    f"TTL {self.config.decision_ttl_seconds}s"
                ),
                t0=t0,
            )

        # 3. Session still valid
        if not context.session_valid:
            from app.domain.institutional_trading.force_first_trade import (
                is_forced_test_decision,
            )

            if is_forced_test_decision(decision):
                logger.warning(
                    "FORCE_FIRST_TRADE continuing with session invalid: %s",
                    context.snapshot.session.reason or "Session invalid",
                )
            else:
                return self._abort(
                    decision=decision,
                    context=context,
                    decision_hash=d_hash,
                    reason=BridgeAbortReason.SESSION_INVALID,
                    comment=context.snapshot.session.reason or "Session invalid",
                    t0=t0,
                )

        # 4. Market still open
        if not context.market_open:
            return self._abort(
                decision=decision,
                context=context,
                decision_hash=d_hash,
                reason=BridgeAbortReason.MARKET_CLOSED,
                comment="Market is closed",
                t0=t0,
            )

        # 5. Spread still acceptable
        spread = context.spread
        if spread is not None and spread > self.config.max_spread_accept:
            return self._abort(
                decision=decision,
                context=context,
                decision_hash=d_hash,
                reason=BridgeAbortReason.SPREAD_UNACCEPTABLE,
                comment=f"Spread {spread} exceeds {self.config.max_spread_accept}",
                t0=t0,
            )

        # 5b. Canary hard limits (before eligibility — explicit abort reasons)
        if mode is ExecutionMode.CANARY_LIVE:
            if (
                decision.approved_lots is not None
                and decision.approved_lots > self.config.canary_max_lots
            ):
                return self._abort(
                    decision=decision,
                    context=context,
                    decision_hash=d_hash,
                    reason=BridgeAbortReason.CANARY_LOT_LIMIT,
                    comment=(
                        f"Canary lot limit {self.config.canary_max_lots} "
                        f"(got {decision.approved_lots})"
                    ),
                    t0=t0,
                )
            if (
                context.account.open_positions
                >= self.config.canary_max_open_positions
            ):
                return self._abort(
                    decision=decision,
                    context=context,
                    decision_hash=d_hash,
                    reason=BridgeAbortReason.CANARY_POSITION_LIMIT,
                    comment=(
                        f"Canary max open positions "
                        f"{self.config.canary_max_open_positions} "
                        f"(open={context.account.open_positions})"
                    ),
                    t0=t0,
                )

        # 6. PositionEligibility still passes
        from app.domain.institutional_trading.force_first_trade import (
            is_forced_test_decision,
        )

        if is_forced_test_decision(decision):
            # Force First Trade: trust eligibility built with signal gates waived.
            # Still enforces market/session/spread/margin via decision.eligibility.
            eligibility = decision.eligibility
        else:
            eligibility = PositionEligibilityEngine(self.ite_config).evaluate(
                snapshot=context.snapshot,
                confluence=decision.confluence,
                account=context.account,
                risk_allowed=context.risk_allowed,
                risk_reasons=context.risk_reasons,
            )
        if not eligibility.eligible:
            return self._abort(
                decision=decision,
                context=context,
                decision_hash=d_hash,
                reason=BridgeAbortReason.ELIGIBILITY_FAILED,
                comment="; ".join(eligibility.rejection_reasons)
                or "Eligibility failed",
                t0=t0,
            )
        self.metrics.record_eligible()

        # 7. EXECUTION_ENABLED (required for live/canary; shadow skips OMS)
        if mode is not ExecutionMode.SHADOW and not context.execution_enabled:
            return self._abort(
                decision=decision,
                context=context,
                decision_hash=d_hash,
                reason=BridgeAbortReason.EXECUTION_DISABLED,
                comment="EXECUTION_ENABLED=false — OMS not called",
                t0=t0,
            )

        # 7b. Auto-trading safety gate (LIVE/CANARY only — never bypass)
        if mode is not ExecutionMode.SHADOW and self.ops_plane is not None:
            safety = self.ops_plane.evaluate_auto_trading(
                self._auto_trade_facts(context)
            )
            if not safety.allowed:
                from app.domain.institutional_trading.force_first_trade import (
                    is_forced_test_decision,
                )

                if is_forced_test_decision(decision):
                    logger.warning(
                        "FORCE_FIRST_TRADE continuing past safety gate: %s",
                        "; ".join(safety.failed_reasons) or "Auto Trading blocked",
                    )
                else:
                    return self._abort(
                        decision=decision,
                        context=context,
                        decision_hash=d_hash,
                        reason=BridgeAbortReason.AUTO_TRADING_BLOCKED,
                        comment="; ".join(safety.failed_reasons)
                        or "Auto Trading safety gate blocked",
                        t0=t0,
                    )

        # 8. Kill switch
        if self.kill_switch.enabled:
            return self._abort(
                decision=decision,
                context=context,
                decision_hash=d_hash,
                reason=BridgeAbortReason.KILL_SWITCH,
                comment="Kill switch armed — OMS receives nothing",
                t0=t0,
            )

        # Geometry / lots
        if decision.approved_lots is None or decision.approved_lots <= 0:
            return self._abort(
                decision=decision,
                context=context,
                decision_hash=d_hash,
                reason=BridgeAbortReason.MISSING_LOTS,
                comment="No approved_lots on decision",
                t0=t0,
            )
        if (
            decision.stop_zone is None
            or decision.target_zone is None
            or decision.entry_zone is None
        ):
            return self._abort(
                decision=decision,
                context=context,
                decision_hash=d_hash,
                reason=BridgeAbortReason.MISSING_ZONES,
                comment="Missing entry/stop/target zones",
                t0=t0,
            )

        # Canary daily cap (after geometry — ready to size)
        if mode is ExecutionMode.CANARY_LIVE:
            day = context.now.date()
            with self._lock:
                if self._canary_day != day:
                    self._canary_day = day
                    self._canary_count = 0
                canary_blocked = (
                    self._canary_count >= self.config.canary_max_trades_per_day
                )
            if canary_blocked:
                return self._abort(
                    decision=decision,
                    context=context,
                    decision_hash=d_hash,
                    reason=BridgeAbortReason.CANARY_DAILY_CAP,
                    comment=(
                        f"Canary daily cap "
                        f"{self.config.canary_max_trades_per_day} reached"
                    ),
                    t0=t0,
                )

        # --- Shadow mode: journal only, never OMS ---
        if mode is ExecutionMode.SHADOW:
            latency = (time.perf_counter() - t0) * 1000.0
            self._mark_executed(d_hash)
            entry = self._record(
                decision=decision,
                context=context,
                decision_hash=d_hash,
                abort_reason=BridgeAbortReason.NONE,
                comment="Shadow mode — journal only, OMS not called",
                latency_ms=latency,
                status=ExecutionAttemptStatus.SHADOW,
                oms_status="shadow",
                gateway_status="not_called",
                execution_result="shadow",
                mode=mode,
            )
            self.metrics.record_executed(latency)
            self._complete_shadow_trace(tid, t0)
            return ExecutionBridgeResult(
                forwarded_to_oms=False,
                aborted=False,
                abort_reason=BridgeAbortReason.NONE,
                decision_hash=d_hash,
                journal_entry=entry,
                oms_result=None,
            )

        # Build intent and forward exactly once
        from app.domain.institutional_trading.force_first_trade import (
            is_forced_test_decision,
        )

        if is_forced_test_decision(decision):
            logger.warning("Submitting order...")
        intent = self._build_intent(decision, context)
        request_id = context.request_id or f"ite_{d_hash[:16]}"

        # Atomic reserve immediately before OMS — prevents concurrent double-send.
        with self._lock:
            if d_hash in self._executed_hashes:
                self.metrics.record_duplicate()
                return self._abort(
                    decision=decision,
                    context=context,
                    decision_hash=d_hash,
                    reason=BridgeAbortReason.DUPLICATE_DECISION,
                    comment="Duplicate decision hash — execution not allowed",
                    t0=t0,
                    status=ExecutionAttemptStatus.DUPLICATE,
                    count_reject=False,
                )
            self._executed_hashes.add(d_hash)
            self._executed_hash_order.append(d_hash)
            while len(self._executed_hash_order) > self._max_executed_hashes:
                old = self._executed_hash_order.pop(0)
                self._executed_hashes.discard(old)
            if (
                mode is ExecutionMode.CANARY_LIVE
                and self._canary_day != context.now.date()
            ):
                self._canary_day = context.now.date()
                self._canary_count = 0

        oms_result = self.oms.submit_market(
            user_id=context.user_id,
            request_id=request_id,
            intent=intent,
            connected=context.connected,
            login=context.login,
        )
        latency = (time.perf_counter() - t0) * 1000.0
        abort_reason, status, exec_result = self._map_oms_outcome(oms_result)

        # Once OMS was invoked, keep the decision hash (idempotency). Clear
        # rejects before submit never reach this path; do not free the hash
        # here or a second execute() could double-send after a failed respond.

        if (
            mode is ExecutionMode.CANARY_LIVE
            and status is ExecutionAttemptStatus.OMS_SUCCESS
        ):
            with self._lock:
                if self._canary_day != context.now.date():
                    self._canary_day = context.now.date()
                    self._canary_count = 0
                self._canary_count += 1

        entry = self._record(
            decision=decision,
            context=context,
            decision_hash=d_hash,
            abort_reason=abort_reason,
            comment=oms_result.message,
            latency_ms=latency,
            status=status,
            oms_status=oms_result.oms_status or oms_result.outcome,
            gateway_status=oms_result.gateway_status or oms_result.outcome,
            execution_result=exec_result,
            mt5_ticket=oms_result.order_ticket,
            mt5_deal=oms_result.deal_ticket,
            retcode=oms_result.retcode,
            mode=mode,
        )

        if status is ExecutionAttemptStatus.OMS_SUCCESS:
            self.metrics.record_executed(latency)
        else:
            self.metrics.record_rejected(latency)
            # Canary: immediate stop after abnormal execution
            if (
                mode is ExecutionMode.CANARY_LIVE
                and self.ops_plane is not None
                and status
                in {
                    ExecutionAttemptStatus.OMS_REJECTED,
                    ExecutionAttemptStatus.ABORTED,
                }
            ):
                self.ops_plane.halt_on_abnormal_execution(
                    reason=(
                        f"Canary abnormal execution: {abort_reason.value} "
                        f"— {oms_result.message}"
                    )
                )

        self._complete_live_trace(
            tid,
            t0,
            oms_result=oms_result,
            ok=status is ExecutionAttemptStatus.OMS_SUCCESS,
        )
        return ExecutionBridgeResult(
            forwarded_to_oms=True,
            aborted=status is not ExecutionAttemptStatus.OMS_SUCCESS,
            abort_reason=abort_reason,
            decision_hash=d_hash,
            journal_entry=entry,
            oms_result=oms_result,
        )

    def _map_oms_outcome(
        self, result: OmsSubmitResult
    ) -> tuple[BridgeAbortReason, ExecutionAttemptStatus, str]:
        outcome = (result.outcome or "").lower()
        if outcome in {"success", "filled", "done"}:
            return (
                BridgeAbortReason.NONE,
                ExecutionAttemptStatus.OMS_SUCCESS,
                "success",
            )
        if outcome in {"disabled"}:
            return (
                BridgeAbortReason.EXECUTION_DISABLED,
                ExecutionAttemptStatus.OMS_REJECTED,
                "disabled",
            )
        # Gateway / connectivity class (MT5 10031 = no connection)
        if (
            "gateway" in outcome
            or outcome in {"timeout", "unavailable"}
            or result.retcode in {10031, 10012}
        ):
            return (
                BridgeAbortReason.GATEWAY_FAILURE,
                ExecutionAttemptStatus.OMS_REJECTED,
                outcome or "gateway_failure",
            )
        if outcome in {"rejected", "failed", "invalid"}:
            if result.retcode and 10000 <= result.retcode < 20000:
                return (
                    BridgeAbortReason.MT5_REJECTION,
                    ExecutionAttemptStatus.OMS_REJECTED,
                    outcome,
                )
            return (
                BridgeAbortReason.OMS_FAILURE,
                ExecutionAttemptStatus.OMS_REJECTED,
                outcome,
            )
        return (
            BridgeAbortReason.OMS_FAILURE,
            ExecutionAttemptStatus.OMS_REJECTED,
            outcome or "oms_failure",
        )

    def _build_intent(
        self, decision: TradeDecision, _context: ExecutionBridgeContext
    ) -> OrderIntent:
        assert decision.stop_zone is not None
        assert decision.target_zone is not None
        side = "buy" if decision.action is DecisionAction.BUY else "sell"
        if decision.action is DecisionAction.BUY:
            sl = str(decision.stop_zone.low)
            tp = str(decision.target_zone.high)
        else:
            sl = str(decision.stop_zone.high)
            tp = str(decision.target_zone.low)
        comment = f"{self.config.comment_prefix}:{decision.input_hash[:12]}"
        from app.domain.institutional_trading.force_first_trade import (
            is_forced_test_decision,
        )

        if is_forced_test_decision(decision):
            comment = f"FORCE:{decision.input_hash[:12]}"
        return parse_order_intent(
            symbol=decision.symbol or self.config.symbol,
            side=side,
            order_type="market",
            volume=str(decision.approved_lots),
            stop_loss=sl,
            take_profit=tp,
            slippage=self.config.slippage,
            magic=self.config.magic,
            comment=comment,
        )

    def _auto_trade_facts(self, context: ExecutionBridgeContext) -> AutoTradeLiveFacts:
        """Map bridge context → safety-gate facts (None → fail-closed False)."""
        session = getattr(context.snapshot.session, "session", None)
        session_val = str(getattr(session, "value", None) or session or "off_hours")
        news = context.snapshot.news
        free = context.account.free_margin
        margin_ok = free is None or free > 0

        def _flag(value: bool | None, *, fallback: bool = False) -> bool:
            return fallback if value is None else value

        return AutoTradeLiveFacts(
            gateway_connected=_flag(context.gateway_connected),
            broker_connected=_flag(
                context.broker_connected, fallback=context.connected
            ),
            market_data_live=_flag(
                context.market_data_live, fallback=context.market_open
            ),
            risk_engine_pass=context.risk_allowed,
            risk_engine_reasons=context.risk_reasons,
            account_trading_enabled=_flag(context.account_trading_enabled),
            mt5_autotrading_enabled=_flag(context.mt5_autotrading_enabled),
            symbol=context.snapshot.symbol,
            symbol_tradable=_flag(context.symbol_tradable),
            margin_available=margin_ok,
            no_broker_restrictions=_flag(context.no_broker_restrictions),
            open_positions=context.account.open_positions,
            session=session_val,
            spread=context.spread,
            news_blocked=bool(news.blocked),
            news_reason=str(news.reason or ""),
            daily_loss_exceeded=False,
            emergency_stop=False,
            ops_mode=(
                self.ops_plane.mode.value if self.ops_plane is not None else "SHADOW"
            ),
            execution_enabled=context.execution_enabled,
        )

    def _mark_executed(self, decision_hash: str) -> None:
        with self._lock:
            self._executed_hashes.add(decision_hash)

    def _abort(
        self,
        *,
        decision: TradeDecision,
        context: ExecutionBridgeContext,
        decision_hash: str,
        reason: BridgeAbortReason,
        comment: str,
        t0: float,
        status: ExecutionAttemptStatus = ExecutionAttemptStatus.ABORTED,
        count_reject: bool = True,
    ) -> ExecutionBridgeResult:
        latency = (time.perf_counter() - t0) * 1000.0
        if count_reject and status is not ExecutionAttemptStatus.DUPLICATE:
            self.metrics.record_rejected(latency)
        entry = self._record(
            decision=decision,
            context=context,
            decision_hash=decision_hash,
            abort_reason=reason,
            comment=comment,
            latency_ms=latency,
            status=status,
            oms_status="not_called",
            gateway_status="not_called",
            execution_result=reason.value,
        )
        return ExecutionBridgeResult(
            forwarded_to_oms=False,
            aborted=True,
            abort_reason=reason,
            decision_hash=decision_hash,
            journal_entry=entry,
            oms_result=None,
        )

    def _record(
        self,
        *,
        decision: TradeDecision,
        context: ExecutionBridgeContext,
        decision_hash: str,
        abort_reason: BridgeAbortReason,
        comment: str,
        latency_ms: float,
        status: ExecutionAttemptStatus,
        oms_status: str,
        gateway_status: str,
        execution_result: str,
        mt5_ticket: int | None = None,
        mt5_deal: int | None = None,
        retcode: int | None = None,
        mode: ExecutionMode | None = None,
    ) -> ExecutionAttemptRecord:
        entry = ExecutionAttemptRecord(
            decision_hash=decision_hash,
            input_hash=decision.input_hash,
            timestamp=context.now,
            decision_action=decision.action,
            confidence=decision.confidence,
            quality=decision.quality,
            approved_lots=decision.approved_lots,
            oms_status=oms_status,
            gateway_status=gateway_status,
            mt5_ticket=mt5_ticket,
            mt5_deal=mt5_deal,
            retcode=retcode,
            comment=comment,
            latency_ms=latency_ms,
            execution_result=execution_result,
            abort_reason=abort_reason,
            mode=mode or self.effective_mode(),
            status=status,
            symbol=decision.symbol,
            request_id=context.request_id or "",
        )
        return self.journal.append(entry)

    def _ensure_trace(
        self, trace_id: str | None, *, decision_id: str | None
    ) -> str | None:
        if self.reliability is None:
            return None
        if trace_id:
            if self.reliability.traces.get(trace_id) is None:
                self.reliability.traces.start(
                    trace_id=trace_id, decision_id=decision_id
                )
            return trace_id
        return self.reliability.traces.start(decision_id=decision_id).trace_id

    def _span_bridge(
        self, tid: str | None, t0: float, *, ok: bool, detail: str = ""
    ) -> None:
        if tid is None or self.reliability is None:
            return
        from app.domain.institutional_trading.reliability.models import TraceStage

        latency = (time.perf_counter() - t0) * 1000.0
        self.reliability.traces.span(
            tid, TraceStage.BRIDGE, latency_ms=latency, ok=ok, detail=detail
        )

    def _complete_shadow_trace(self, tid: str | None, t0: float) -> None:
        if tid is None or self.reliability is None:
            return
        from datetime import UTC, datetime

        from app.domain.institutional_trading.reliability.models import (
            TimelineEvent,
            TraceStage,
        )

        latency = (time.perf_counter() - t0) * 1000.0
        for stage, detail, ok in (
            (TraceStage.BRIDGE, "shadow_journal", True),
            (TraceStage.OMS, "not_called_shadow", True),
            (TraceStage.GATEWAY, "not_called_shadow", True),
            (TraceStage.MT5, "not_called_shadow", True),
            (TraceStage.PME, "no_open_position", True),
            (TraceStage.JOURNAL, "shadow_journal", True),
        ):
            self.reliability.traces.span(
                tid, stage, latency_ms=latency / 6.0, ok=ok, detail=detail
            )
        self.reliability.timeline.append(
            TimelineEvent(
                timestamp=datetime.now(UTC),
                category="trace",
                action="shadow_path",
                detail=f"trace={tid}",
                severity="INFO",
                trace_id=tid,
            )
        )

    def _complete_live_trace(
        self,
        tid: str | None,
        t0: float,
        *,
        oms_result: OmsSubmitResult,
        ok: bool,
    ) -> None:
        if tid is None or self.reliability is None:
            return
        from app.domain.institutional_trading.reliability.models import TraceStage

        latency = (time.perf_counter() - t0) * 1000.0
        self.reliability.traces.span(
            tid, TraceStage.BRIDGE, latency_ms=latency * 0.2, ok=True
        )
        self.reliability.traces.span(
            tid,
            TraceStage.OMS,
            latency_ms=float(oms_result.latency_ms or latency * 0.3),
            ok=ok,
            detail=oms_result.outcome,
        )
        self.reliability.traces.span(
            tid,
            TraceStage.GATEWAY,
            latency_ms=latency * 0.2,
            ok=ok,
            detail=oms_result.gateway_status,
        )
        self.reliability.traces.span(
            tid,
            TraceStage.MT5,
            latency_ms=latency * 0.2,
            ok=ok,
            detail=str(oms_result.retcode),
        )
        self.reliability.traces.span(
            tid, TraceStage.PME, latency_ms=0.0, ok=True, detail="pending_manage"
        )
        self.reliability.traces.span(
            tid, TraceStage.JOURNAL, latency_ms=latency * 0.1, ok=True
        )
