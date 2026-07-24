"""Position Management Engine — manages EXISTING positions only.

Never opens trades. Never modifies OMS / Phase A / B / C.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from decimal import Decimal
from threading import Lock

from app.domain.institutional_trading.management.config import (
    DEFAULT_PME_CONFIG,
    PositionManagementConfig,
)
from app.domain.institutional_trading.management.journal import PositionManageJournal
from app.domain.institutional_trading.management.metrics import PositionManageMetrics
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    ManageOutcome,
    OmsManageResult,
    PositionLifecycleState,
    PositionManageContext,
    PositionManageRecord,
    PositionManageResult,
)
from app.domain.institutional_trading.management.oms_port import OmsManagePort
from app.domain.institutional_trading.management.policies import (
    PlannedAction,
    plan_action,
)
from app.domain.institutional_trading.management.r_math import opposite_side, signed_r
from app.domain.institutional_trading.management.state_machine import (
    PositionStateMachine,
)


def _fingerprint(
    ticket: int,
    kind: ManageActionKind,
    *,
    sl: Decimal | None,
    tp: Decimal | None,
    volume: Decimal | None,
) -> str:
    payload = f"{ticket}|{kind.value}|{sl}|{tp}|{volume}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


@dataclass
class PositionManagementEngine:
    """Institutional PME orchestrator — one action per evaluate tick."""

    oms: OmsManagePort
    config: PositionManagementConfig = field(default_factory=lambda: DEFAULT_PME_CONFIG)
    journal: PositionManageJournal = field(default_factory=PositionManageJournal)
    metrics: PositionManageMetrics = field(default_factory=PositionManageMetrics)
    _positions: dict[int, ManagedPosition] = field(default_factory=dict, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def register(self, position: ManagedPosition) -> ManagedPosition:
        """Track a newly filled ITE position (never opens — registration only)."""
        if position.current_stop <= 0:
            position.current_stop = position.initial_stop
        with self._lock:
            self._positions[position.ticket] = position
        return position

    def get(self, ticket: int) -> ManagedPosition | None:
        with self._lock:
            return self._positions.get(ticket)

    def drop_missing_tickets(self, live_tickets: set[int]) -> int:
        """Remove managed tickets absent from live MT5. Returns removed count."""
        live = {int(t) for t in live_tickets}
        removed = 0
        with self._lock:
            stale = [t for t in list(self._positions.keys()) if int(t) not in live]
            for ticket in stale:
                if self._positions.pop(ticket, None) is not None:
                    removed += 1
        return removed

    def evaluate(
        self,
        ticket: int,
        context: PositionManageContext,
    ) -> PositionManageResult:
        self.metrics.record_evaluation()
        with self._lock:
            position = self._positions.get(ticket)
        if position is None:
            skip = PositionManageRecord(
                ticket=ticket,
                action=ManageActionKind.SKIP,
                from_state=PositionLifecycleState.EXITED,
                to_state=PositionLifecycleState.EXITED,
                reason="Unknown ticket — not under PME control",
                timestamp=context.now,
                latency_ms=0.0,
                outcome=ManageOutcome.SKIPPED,
            )
            self.journal.append(skip)
            ghost = ManagedPosition(
                ticket=ticket,
                symbol=self.config.symbol,
                side="buy",
                entry_price=Decimal("0"),
                initial_volume=Decimal("0"),
                remaining_volume=Decimal("0"),
                initial_stop=Decimal("0"),
                risk_distance=Decimal("0"),
                opened_at=context.now,
                state=PositionLifecycleState.EXITED,
                exit_reason="unknown_ticket",
            )
            return PositionManageResult(
                position=ghost,
                action=ManageActionKind.SKIP,
                record=skip,
                skipped=True,
            )

        # Sync book volume if provided
        if context.book_volume is not None and context.book_volume >= 0:
            position.remaining_volume = context.book_volume
        if context.book_stop is not None and context.book_stop > 0:
            position.current_stop = context.book_stop

        # Update max favorable excursion
        r_now = signed_r(position, context.current_price)
        if r_now > position.max_favorable_r:
            position.max_favorable_r = r_now

        if position.state is PositionLifecycleState.EXITED:
            return self._skip(position, context, "Already exited — no management")

        # Manually closed / missing from book
        if not context.position_still_open or position.remaining_volume <= 0:
            return self._local_exit(
                position,
                context,
                reason="Manually closed or zero volume — local EXITED",
            )

        plan = plan_action(position, context, self.config)
        if plan.kind in {ManageActionKind.NOOP, ManageActionKind.SKIP}:
            if (
                plan.target_state is PositionLifecycleState.EXITED
                and plan.kind is ManageActionKind.SKIP
            ):
                return self._local_exit(position, context, reason=plan.reason)
            return self._skip(position, context, plan.reason)

        assert plan.target_state is not None
        PositionStateMachine.assert_transition(position.state, plan.target_state)

        fp = _fingerprint(
            position.ticket,
            plan.kind,
            sl=plan.new_sl,
            tp=plan.new_tp,
            volume=plan.volume,
        )
        if position.last_manage_fingerprint == fp:
            self.metrics.record_duplicate()
            rec = self._record(
                position=position,
                context=context,
                plan=plan,
                outcome=ManageOutcome.DUPLICATE,
                latency_ms=0.0,
                fingerprint=fp,
                to_state=position.state,
                comment="Duplicate manage request suppressed",
            )
            return PositionManageResult(
                position=position,
                action=plan.kind,
                record=rec,
                skipped=True,
            )

        t0 = time.perf_counter()
        oms_result = self._dispatch(position, context, plan)
        latency = (time.perf_counter() - t0) * 1000.0

        if not oms_result.ok:
            self.metrics.record_oms_failure()
            outcome = self._map_failure(oms_result)
            if plan.kind is ManageActionKind.BREAK_EVEN:
                self.metrics.record_be(success=False)
            elif plan.kind is ManageActionKind.TRAIL:
                self.metrics.record_trail(success=False)
            elif plan.kind is ManageActionKind.PARTIAL_CLOSE:
                self.metrics.record_partial(success=False)
            rec = self._record(
                position=position,
                context=context,
                plan=plan,
                outcome=outcome,
                latency_ms=latency,
                fingerprint=fp,
                to_state=position.state,
                comment=oms_result.message,
                retcode=oms_result.retcode,
                oms=oms_result,
            )
            # Mark fingerprint so identical retries are blocked
            position.last_manage_fingerprint = fp
            return PositionManageResult(
                position=position,
                action=plan.kind,
                record=rec,
                oms_result=oms_result,
            )

        # Success — apply local state
        from_state = position.state
        old_sl = position.current_stop
        old_tp = position.current_tp
        self._apply_success(position, plan)
        position.last_manage_fingerprint = fp

        if plan.kind is ManageActionKind.BREAK_EVEN:
            self.metrics.record_be(success=True)
        elif plan.kind is ManageActionKind.TRAIL:
            self.metrics.record_trail(success=True)
        elif plan.kind is ManageActionKind.PARTIAL_CLOSE:
            self.metrics.record_partial(success=True)
        elif plan.target_state is PositionLifecycleState.EXITED:
            hold = (context.now - position.opened_at).total_seconds()
            self.metrics.record_exit(
                reason=plan.kind.value,
                hold_seconds=hold,
                exit_r=r_now,
            )

        rec = PositionManageRecord(
            ticket=position.ticket,
            action=plan.kind,
            from_state=from_state,
            to_state=position.state,
            reason=plan.reason,
            timestamp=context.now,
            latency_ms=latency,
            outcome=ManageOutcome.SUCCESS,
            old_sl=old_sl,
            new_sl=plan.new_sl if plan.new_sl is not None else position.current_stop,
            old_tp=old_tp,
            new_tp=plan.new_tp,
            volume=plan.volume,
            r_multiple=r_now,
            retcode=oms_result.retcode,
            comment=oms_result.message or plan.reason,
            fingerprint=fp,
            symbol=position.symbol,
        )
        self.journal.append(rec)
        return PositionManageResult(
            position=position,
            action=plan.kind,
            record=rec,
            oms_result=oms_result,
        )

    def _apply_success(self, position: ManagedPosition, plan: PlannedAction) -> None:
        assert plan.target_state is not None
        PositionStateMachine.assert_transition(position.state, plan.target_state)
        if plan.new_sl is not None:
            position.current_stop = plan.new_sl
        if plan.new_tp is not None:
            position.current_tp = plan.new_tp
        if plan.kind is ManageActionKind.BREAK_EVEN:
            position.be_moved = True
        if plan.kind is ManageActionKind.PARTIAL_CLOSE and plan.volume:
            position.remaining_volume = (
                position.remaining_volume - plan.volume
            ).quantize(Decimal("0.01"))
            position.partial_done = True
        if plan.kind is ManageActionKind.TRAIL:
            position.trailing_active = True
        if plan.target_state is PositionLifecycleState.EXITED:
            position.remaining_volume = Decimal("0")
            position.exit_reason = plan.reason
        position.state = plan.target_state

    def _dispatch(
        self,
        position: ManagedPosition,
        context: PositionManageContext,
        plan: PlannedAction,
    ) -> OmsManageResult:
        rid = context.request_id or f"pme_{position.ticket}_{plan.kind.value}"
        comment = f"{self.config.comment_prefix}:{plan.kind.value}:{position.ticket}"
        close_side = opposite_side(position.side)

        if (
            plan.kind is ManageActionKind.BREAK_EVEN
            or plan.kind is ManageActionKind.TRAIL
        ):
            assert plan.new_sl is not None
            return self.oms.modify_sltp(
                user_id=context.user_id,
                request_id=rid,
                symbol=position.symbol,
                side=position.side,
                position=position.ticket,
                stop_loss=plan.new_sl,
                take_profit=plan.new_tp,
                comment=comment,
                connected=context.connected,
                login=context.login,
            )

        if plan.kind is ManageActionKind.PARTIAL_CLOSE:
            assert plan.volume is not None
            return self.oms.partial_close(
                user_id=context.user_id,
                request_id=rid,
                symbol=position.symbol,
                side=close_side,
                position=position.ticket,
                volume=plan.volume,
                comment=comment,
                connected=context.connected,
                login=context.login,
            )

        # Flatten paths
        assert plan.volume is not None
        return self.oms.close_position(
            user_id=context.user_id,
            request_id=rid,
            symbol=position.symbol,
            side=close_side,
            position=position.ticket,
            volume=plan.volume,
            comment=comment,
            connected=context.connected,
            login=context.login,
        )

    @staticmethod
    def _map_failure(result: OmsManageResult) -> ManageOutcome:
        outcome = (result.outcome or "").lower()
        if "gateway" in outcome or result.retcode in {10031, 10012}:
            return ManageOutcome.GATEWAY_FAILURE
        if result.retcode and 10000 <= result.retcode < 20000:
            return ManageOutcome.MT5_FAILURE
        return ManageOutcome.OMS_FAILURE

    def _skip(
        self,
        position: ManagedPosition,
        context: PositionManageContext,
        reason: str,
    ) -> PositionManageResult:
        rec = PositionManageRecord(
            ticket=position.ticket,
            action=ManageActionKind.NOOP,
            from_state=position.state,
            to_state=position.state,
            reason=reason,
            timestamp=context.now,
            latency_ms=0.0,
            outcome=ManageOutcome.SKIPPED,
            r_multiple=signed_r(position, context.current_price),
            symbol=position.symbol,
        )
        self.journal.append(rec)
        return PositionManageResult(
            position=position,
            action=ManageActionKind.NOOP,
            record=rec,
            skipped=True,
        )

    def _local_exit(
        self,
        position: ManagedPosition,
        context: PositionManageContext,
        *,
        reason: str,
    ) -> PositionManageResult:
        from_state = position.state
        if from_state is not PositionLifecycleState.EXITED:
            PositionStateMachine.assert_transition(
                from_state, PositionLifecycleState.EXITED
            )
            position.state = PositionLifecycleState.EXITED
            position.remaining_volume = Decimal("0")
            position.exit_reason = reason
            hold = (context.now - position.opened_at).total_seconds()
            self.metrics.record_exit(
                reason="manual_or_local",
                hold_seconds=hold,
                exit_r=signed_r(position, context.current_price),
            )
        rec = PositionManageRecord(
            ticket=position.ticket,
            action=ManageActionKind.SKIP,
            from_state=from_state,
            to_state=PositionLifecycleState.EXITED,
            reason=reason,
            timestamp=context.now,
            latency_ms=0.0,
            outcome=ManageOutcome.SKIPPED,
            symbol=position.symbol,
        )
        self.journal.append(rec)
        return PositionManageResult(
            position=position,
            action=ManageActionKind.SKIP,
            record=rec,
            skipped=True,
        )

    def _record(
        self,
        *,
        position: ManagedPosition,
        context: PositionManageContext,
        plan: PlannedAction,
        outcome: ManageOutcome,
        latency_ms: float,
        fingerprint: str,
        to_state: PositionLifecycleState,
        comment: str,
        retcode: int | None = None,
        oms: OmsManageResult | None = None,  # noqa: ARG002
    ) -> PositionManageRecord:
        rec = PositionManageRecord(
            ticket=position.ticket,
            action=plan.kind,
            from_state=position.state,
            to_state=to_state,
            reason=plan.reason,
            timestamp=context.now,
            latency_ms=latency_ms,
            outcome=outcome,
            old_sl=position.current_stop,
            new_sl=plan.new_sl,
            old_tp=position.current_tp,
            new_tp=plan.new_tp,
            volume=plan.volume,
            r_multiple=signed_r(position, context.current_price),
            retcode=retcode,
            comment=comment,
            fingerprint=fingerprint,
            symbol=position.symbol,
        )
        self.journal.append(rec)
        return rec
