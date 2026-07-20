"""Execution Bridge — sole path from TradeDecision to Institutional OMS.

Re-verifies gates before any OMS call. Never retries. No AI.
Does not modify Phase A/B or the OMS.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from threading import Lock
from app.application.services.institutional_execution_engine import parse_order_intent
from app.domain.entities.mt5_order import OrderIntent
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
    _executed_hashes: set[str] = field(default_factory=set, repr=False)
    _canary_day: date | None = field(default=None, repr=False)
    _canary_count: int = field(default=0, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def handle(
        self,
        decision: TradeDecision,
        context: ExecutionBridgeContext,
    ) -> ExecutionBridgeResult:
        """Evaluate a decision. Only BUY/SELL may reach OMS (never WATCH/NO_TRADE)."""
        t0 = time.perf_counter()
        d_hash = compute_decision_hash(decision)
        actionable = decision.action in {DecisionAction.BUY, DecisionAction.SELL}
        self.metrics.record_decision(
            confidence=decision.confidence, actionable=actionable
        )

        if not actionable:
            return self._abort(
                decision=decision,
                context=context,
                decision_hash=d_hash,
                reason=BridgeAbortReason.IGNORED_ACTION,
                comment=f"Ignored action {decision.action.value}",
                t0=t0,
                status=ExecutionAttemptStatus.ABORTED,
            )

        # --- Duplicate protection (before anything else that could call OMS) ---
        with self._lock:
            is_duplicate = d_hash in self._executed_hashes
        if is_duplicate:
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

        # 6. PositionEligibility still passes
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
        if (
            self.config.mode is not ExecutionMode.SHADOW
            and not context.execution_enabled
        ):
            return self._abort(
                decision=decision,
                context=context,
                decision_hash=d_hash,
                reason=BridgeAbortReason.EXECUTION_DISABLED,
                comment="EXECUTION_ENABLED=false — OMS not called",
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

        # Canary daily cap
        if self.config.mode is ExecutionMode.CANARY_LIVE:
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
        if self.config.mode is ExecutionMode.SHADOW:
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
            )
            self.metrics.record_executed(latency)
            return ExecutionBridgeResult(
                forwarded_to_oms=False,
                aborted=False,
                abort_reason=BridgeAbortReason.NONE,
                decision_hash=d_hash,
                journal_entry=entry,
                oms_result=None,
            )

        # Build intent and forward exactly once
        intent = self._build_intent(decision, context)
        request_id = context.request_id or f"ite_{d_hash[:16]}"

        # Mark hash BEFORE OMS call so retries are impossible even on failure
        self._mark_executed(d_hash)
        if self.config.mode is ExecutionMode.CANARY_LIVE:
            with self._lock:
                self._canary_count += 1

        oms_result = self.oms.submit_market(
            user_id=context.user_id,
            request_id=request_id,
            intent=intent,
            connected=context.connected,
            login=context.login,
        )
        latency = (time.perf_counter() - t0) * 1000.0
        abort_reason, status, exec_result = self._map_oms_outcome(oms_result)

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
        )

        if status is ExecutionAttemptStatus.OMS_SUCCESS:
            self.metrics.record_executed(latency)
        else:
            self.metrics.record_rejected(latency)

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
        self, decision: TradeDecision, context: ExecutionBridgeContext
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
            mode=self.config.mode,
            status=status,
            symbol=decision.symbol,
            request_id=context.request_id or "",
        )
        return self.journal.append(entry)
