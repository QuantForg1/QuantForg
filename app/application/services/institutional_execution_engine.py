"""Institutional Execution Engine — single observable order pipeline.

One path for prepare / check / submit / cancel / OMS actions.
Never bypasses EXECUTION_ENABLED. Never invents broker fills.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.application.services.execution_gateway import ExecutionGateway
from app.application.services.execution_intelligence import ExecutionIntelligenceService
from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.live_account_risk_tracker import (
    LiveAccountRiskTracker,
    get_live_account_risk_tracker,
)
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.execution_gateway import ExecutionResult
from app.domain.entities.execution_safety import ExecutionDecisionRecord
from app.domain.entities.mt5_order import OrderIntent
from app.domain.enums.execution import ExecutionDecision, ExecutionOutcome
from app.domain.enums.order import OrderSide, OrderType
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.exceptions.base import ValidationError
from app.domain.execution_engine.journal import ExecutionJournalStore
from app.domain.execution_engine.pipeline import STAGE_TO_LIFECYCLE, PipelineStage
from app.domain.execution_engine.reasons import humanize_reason, humanize_reasons
from app.domain.value_objects.mt5_order import (
    LotSize,
    MagicNumber,
    Slippage,
    StopLoss,
    TakeProfit,
)
from core.logging import get_logger

logger = get_logger(__name__)


def _default_oms_risk_engine() -> RiskEngine:
    """OMS RiskEngine consumes ITE MAX_DAILY_LOSS_PCT — never a parallel 5% cap."""
    from app.application.services.institutional_decision_pipeline import (
        oms_risk_engine_from_ite,
    )

    return oms_risk_engine_from_ite()


@dataclass
class PipelineStageRecord:
    stage: str
    status: str  # ok | failed | skipped | blocked
    reason: str
    elapsed_ms: float
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "reason": self.reason,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "meta": dict(self.meta),
        }


@dataclass
class PipelineResult:
    """Observable outcome of one institutional pipeline run."""

    request_id: str
    action: str
    outcome: str
    message: str
    stages: list[PipelineStageRecord]
    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)
    calculated_risk: dict[str, object] = field(default_factory=dict)
    execution_result: ExecutionResult | None = None
    journal_entry: dict[str, Any] | None = None
    decision: str | None = None
    latency_ms: float = 0.0
    idempotent_replay: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action": self.action,
            "outcome": self.outcome,
            "message": self.message,
            "decision": self.decision,
            "stages": [s.to_dict() for s in self.stages],
            "rejection_reasons": list(self.rejection_reasons),
            "warnings": list(self.warnings),
            "checks": dict(self.checks),
            "calculated_risk": dict(self.calculated_risk),
            "execution": (
                self.execution_result.to_dict() if self.execution_result else None
            ),
            "journal_entry": self.journal_entry,
            "latency_ms": round(self.latency_ms, 3),
            "idempotent_replay": self.idempotent_replay,
        }


def parse_order_intent(
    *,
    symbol: str,
    side: str,
    order_type: str,
    volume: str,
    price: str | None = None,
    stop_loss: str | None = None,
    take_profit: str | None = None,
    slippage: int = 10,
    magic: int = 0,
    comment: str = "",
    position: int = 0,
    order_ticket: int = 0,
    oms_kind: str = "",
) -> OrderIntent:
    from app.domain.trading.gold_only import (
        DISABLED_AUTONOMOUS_SYMBOL,
        DisabledAutonomousSymbolError,
        require_xauusd,
    )

    try:
        symbol_u = require_xauusd(symbol)
        return OrderIntent(
            symbol=symbol_u,
            side=OrderSide(side.strip().lower()),
            order_type=OrderType(order_type.strip().lower()),
            volume=LotSize.of(volume),
            price=Decimal(str(price)) if price else None,
            stop_loss=StopLoss.of(stop_loss) if stop_loss else None,
            take_profit=TakeProfit.of(take_profit) if take_profit else None,
            slippage=Slippage.of(slippage),
            magic=MagicNumber.of(magic),
            comment=comment,
            position=int(position or 0),
            order_ticket=int(order_ticket or 0),
            oms_kind=(oms_kind or "").strip().lower(),
        )
    except DisabledAutonomousSymbolError as exc:
        raise ValidationError(
            humanize_reason(str(exc)) if str(exc) else "Invalid order intent",
            code=DISABLED_AUTONOMOUS_SYMBOL,
            details={
                "error": str(exc),
                "code": DISABLED_AUTONOMOUS_SYMBOL,
                "component": "validation.intent",
                "symbol": symbol,
            },
        ) from exc
    except (ValidationError, ValueError) as exc:
        raise ValidationError(
            humanize_reason(str(exc)) if str(exc) else "Invalid order intent",
            details={"error": str(exc), "component": "validation.intent"},
        ) from exc


def mask_account_login(login: int | str | None) -> str | None:
    """Mask MT5 login for logs — never emit the full account number."""
    if login is None or login == "":
        return None
    text = str(login).strip()
    if not text:
        return None
    if len(text) <= 3:
        return "***"
    return f"{text[:2]}***{text[-2:]}"


def retcode_description(retcode: int | None) -> str | None:
    """Human MT5 retcode text. None when order_send was never called."""
    if retcode is None:
        return None
    try:
        from app.domain.entities.execution_gateway import map_retcode_to_outcome

        _, _, message = map_retcode_to_outcome(int(retcode))
        return message
    except (TypeError, ValueError):
        return None


def _opt_positive_decimal(value: object) -> Decimal | None:
    try:
        if value is None:
            return None
        parsed = Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def _ticks_from_symbol_info(info: object) -> tuple[Decimal | None, Decimal | None]:
    tick_size = _opt_positive_decimal(
        getattr(info, "trade_tick_size", None) or getattr(info, "tick_size", None)
    )
    tick_value = _opt_positive_decimal(
        getattr(info, "trade_tick_value", None) or getattr(info, "tick_value", None)
    )
    return tick_size, tick_value


def _is_manage_intent(intent: OrderIntent) -> bool:
    manage_kinds = {"sltp", "modify_sltp", "close", "partial_close"}
    return intent.oms_kind in manage_kinds or int(intent.position or 0) > 0


def order_attempt_execution_result(
    *,
    order_send_reached: bool,
    ticket: int | None,
    outcome: str,
    retcode: int | None,
    message: str,
) -> str:
    """Honest fill/fail label — never call a failed send a fill."""
    success = (outcome or "").strip().lower() in {"success", "filled", "done"}
    if success and ticket:
        return f"FILLED ticket={ticket}"
    if success and not ticket:
        return "OMS reported success without MT5 ticket"
    if order_send_reached:
        rc = f"retcode={retcode}" if retcode is not None else "retcode=null"
        return f"ORDER_SEND_FAILED {rc} {message}".strip()
    return f"NO BROKER ORDER WAS SUBMITTED: {message}".strip()


@dataclass
class InstitutionalExecutionEngine:
    """Single execution pipeline — validation → risk → gate → broker → journal."""

    gateway: ExecutionGateway
    safety: ExecutionSafetyService
    order_validation: MT5OrderValidationService
    intelligence: ExecutionIntelligenceService
    journal: ExecutionJournalStore
    risk_engine: RiskEngine = field(default_factory=_default_oms_risk_engine)
    risk_tracker: LiveAccountRiskTracker = field(
        default_factory=get_live_account_risk_tracker
    )
    gateway_name: str = "execution-gateway"
    broker_name: str = "mt5"

    def _observe(
        self,
        *,
        user_id: str,
        request_id: str,
        symbol: str,
        side: str,
        order_type: str,
        volume: str,
        stage: PipelineStage,
        reason: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        lifecycle = STAGE_TO_LIFECYCLE[stage]
        self.intelligence.observe(
            user_id=user_id,
            request_id=request_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            volume=volume,
            state=lifecycle.value,
            reason=reason,
            source="institutional_execution_engine",
            meta={"pipeline_stage": stage.value, **(meta or {})},
            force=True,
        )

    def _record_order_attempt(
        self,
        *,
        intent: OrderIntent,
        request: Any,
        constraints: Any,
        login: int | None,
        oms_result: str,
        execution_result: str,
        mt5_retcode: int | None,
        broker_comment: str,
        mt5_ticket: int | None,
        order_send_reached: bool,
    ) -> None:
        filling = ""
        tif = ""
        price = ""
        sl = ""
        tp = ""
        broker_symbol = intent.symbol
        if request is not None:
            filling = str(getattr(request, "type_filling", "") or "")
            tif = str(getattr(request, "type_time", "") or "")
            price = str(getattr(request, "price", "") or "")
            sl = str(getattr(request, "stop_loss", "") or "")
            tp = str(getattr(request, "take_profit", "") or "")
            broker_symbol = str(getattr(request, "symbol", "") or intent.symbol)
        elif intent.stop_loss is not None:
            sl = str(intent.stop_loss.value)
        if intent.take_profit is not None and not tp:
            tp = str(intent.take_profit.value)
        if intent.price is not None and not price:
            price = str(intent.price)
        if constraints is not None:
            from app.application.services.mt5_order_validation import _filling_label

            if not filling:
                filling = _filling_label(
                    int(getattr(constraints, "filling_mode", 0) or 0),
                    execution_mode=str(
                        getattr(constraints, "execution_mode", "") or ""
                    ),
                )
            broker_symbol = str(getattr(constraints, "symbol", "") or broker_symbol)
        logger.info(
            "ORDER_ATTEMPT",
            symbol=intent.symbol,
            side=intent.side.value,
            volume=str(intent.volume.value),
            price=price or None,
            sl=sl or None,
            tp=tp or None,
            order_type=intent.order_type.value,
            filling_mode=filling or None,
            time_in_force=tif or None,
            broker_symbol=broker_symbol,
            account_login_masked=mask_account_login(login),
            mt5_retcode=mt5_retcode,
            retcode_description=retcode_description(mt5_retcode),
            broker_comment=broker_comment or None,
            oms_result=oms_result,
            execution_result=execution_result,
            order_send_reached=bool(order_send_reached),
            mt5_ticket=mt5_ticket,
        )

    def _stage(
        self,
        stages: list[PipelineStageRecord],
        *,
        stage: PipelineStage,
        status: str,
        reason: str,
        t0: float,
        meta: dict[str, Any] | None = None,
    ) -> PipelineStageRecord:
        rec = PipelineStageRecord(
            stage=stage.value,
            status=status,
            reason=reason,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            meta=dict(meta or {}),
        )
        stages.append(rec)
        return rec

    def evaluate_safety(
        self,
        *,
        user_id: UUID,
        request_id: str,
        intent: OrderIntent,
        connected: bool,
        login: int | None,
        recent: list[ExecutionDecisionRecord],
        existing: ExecutionDecisionRecord | None = None,
    ) -> ExecutionDecisionRecord:
        record = self.safety.decide(
            user_id=user_id,
            request_id=request_id,
            intent=intent,
            connected=connected,
            login=login,
            recent=recent,
            existing_by_request_id=existing,
        )
        if not record.rejection_reasons:
            return record
        human = humanize_reasons(record.rejection_reasons)
        return ExecutionDecisionRecord.record(
            user_id=record.user_id,
            request_id=record.request_id,
            decision=record.decision,
            symbol=record.symbol,
            side=record.side,
            order_type=record.order_type,
            volume=record.volume,
            rejection_reasons=human,
            warnings=list(record.warnings),
            calculated_risk=dict(record.calculated_risk),
            checks=dict(record.checks),
            request_fingerprint=record.request_fingerprint,
            request_snapshot=dict(record.request_snapshot),
            idempotent_replay=record.idempotent_replay,
            entity_id=record.id,
        )

    def run_submit(
        self,
        *,
        user_id: UUID,
        request_id: str,
        intent: OrderIntent,
        connected: bool,
        login: int | None,
        recent_decisions: list[ExecutionDecisionRecord],
        existing_decision: ExecutionDecisionRecord | None = None,
        skip_broker: bool = False,
        action: str = "submit",
    ) -> tuple[PipelineResult, ExecutionDecisionRecord | None]:
        """Full institutional submit pipeline (optionally stop before broker)."""
        t_pipeline = time.perf_counter()
        stages: list[PipelineStageRecord] = []
        uid = str(user_id)
        symbol = intent.symbol
        side = intent.side.value
        order_type = intent.order_type.value
        volume = str(intent.volume.value)

        t0 = time.perf_counter()
        self._observe(
            user_id=uid,
            request_id=request_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            volume=volume,
            stage=PipelineStage.DRAFT,
            reason="order draft created",
            meta={"action": action},
        )
        self._stage(
            stages,
            stage=PipelineStage.DRAFT,
            status="ok",
            reason="Draft accepted",
            t0=t0,
        )

        t0 = time.perf_counter()
        check_res: Any = None
        request: Any = None
        constraints: Any = None
        try:
            canonical = self.order_validation.resolve_canonical_broker_symbol(
                intent.symbol
            )
            if canonical:
                intent = self.order_validation._intent_with_symbol(intent, canonical)
                symbol = intent.symbol
            intent, norm_notes = self.order_validation.normalize_intent(intent)
            volume = str(intent.volume.value)
            constraints = self.order_validation.constraints_for(intent.symbol)
            ok_vol, msg_vol = self.order_validation.validate_volume(intent, constraints)
            request = self.order_validation.build_order_request(intent)
            ok_stops, msg_stops = self.order_validation.validate_stops(
                intent, constraints, entry_price=request.price
            )
            val_reasons: list[str] = list(norm_notes)
            manage_kinds = {"sltp", "modify_sltp", "close", "partial_close"}
            is_manage = intent.oms_kind in manage_kinds or int(intent.position or 0) > 0
            # Fail closed BEFORE order_check when broker only allows closes.
            # Prevents gateway HTTP 500 (ValueError) from masking MT5 retcode 10044.
            trade_mode = str(constraints.trade_mode or "").strip().lower()
            if trade_mode in {"closeonly", "close_only"} and not is_manage:
                validation_ok = False
                ok_check = False
                check_res = None
                closeonly_reason = (
                    f"Broker {intent.symbol} trade_mode={trade_mode} "
                    f"(current={trade_mode}, required=full). "
                    "MT5 rejects new entries with retcode 10044: "
                    "Only position closing is allowed."
                )
                val_reasons.append(closeonly_reason)
                logger.warning("Rejected because: %s", closeonly_reason)
                logger.warning(
                    "oms_validation_abort",
                    result="FAIL",
                    function="InstitutionalExecutionEngine.run_submit",
                    file=(
                        "app/application/services/" "institutional_execution_engine.py"
                    ),
                    line=309,
                    condition=(
                        "trade_mode in {'closeonly','close_only'} " "and not is_manage"
                    ),
                    current=trade_mode,
                    required="full",
                    reason=closeonly_reason,
                )
            else:
                check_res = self.order_validation.adapter.order_check(request)
                ok_check = check_res.ok
                validation_ok = ok_vol and ok_stops and ok_check
                if not ok_check:
                    val_reasons.append(
                        check_res.comment
                        or f"MT5 order_check retcode {check_res.retcode}"
                    )
            if not ok_vol:
                validation_ok = False
                val_reasons.append(msg_vol)
            if not ok_stops:
                validation_ok = False
                val_reasons.append(msg_stops)
            if not connected:
                validation_ok = False
                val_reasons.append("broker connection not active")
            if (
                not constraints.trade_allowed
                and not is_manage
                and not any("retcode 10044" in r for r in val_reasons)
            ):
                validation_ok = False
                val_reasons.append(
                    f"symbol not tradable (trade_mode={trade_mode or 'unknown'}, "
                    f"trade_allowed={constraints.trade_allowed})"
                )
            if (
                not constraints.market_open
                and intent.order_type is OrderType.MARKET
                and intent.oms_kind not in {"sltp", "modify_sltp"}
            ):
                validation_ok = False
                val_reasons.append("market closed")
        except (OSError, RuntimeError, ValueError, ValidationError) as exc:
            validation_ok = False
            val_reasons = [str(exc)]

        human_val = humanize_reasons(val_reasons)
        if not validation_ok:
            self._observe(
                user_id=uid,
                request_id=request_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                volume=volume,
                stage=PipelineStage.REJECTED,
                reason="; ".join(human_val) or "validation failed",
            )
            self._stage(
                stages,
                stage=PipelineStage.VALIDATION,
                status="failed",
                reason="; ".join(human_val) or "Validation failed",
                t0=t0,
                meta={
                    "component": "validation",
                    "order_check_retcode": getattr(check_res, "retcode", None),
                    "order_check_comment": getattr(check_res, "comment", None),
                    "request": (
                        request.to_dict() if request is not None else intent.to_dict()
                    ),
                },
            )
            result = PipelineResult(
                request_id=request_id,
                action=action,
                outcome="rejected",
                message="; ".join(human_val) or "Validation failed",
                stages=stages,
                rejection_reasons=human_val,
                latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
            )
            result.journal_entry = self._write_journal(result, intent, None, uid)
            self._record_order_attempt(
                intent=intent,
                request=request,
                constraints=constraints,
                login=login,
                oms_result="rejected",
                execution_result=order_attempt_execution_result(
                    order_send_reached=False,
                    ticket=None,
                    outcome="rejected",
                    retcode=None,
                    message=result.message,
                ),
                mt5_retcode=None,
                broker_comment=result.message,
                mt5_ticket=None,
                order_send_reached=False,
            )
            return result, None

        self._observe(
            user_id=uid,
            request_id=request_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            volume=volume,
            stage=PipelineStage.VALIDATION,
            reason="order validated",
        )
        self._stage(
            stages,
            stage=PipelineStage.VALIDATION,
            status="ok",
            reason="Validation passed",
            t0=t0,
            meta={
                "component": "validation",
                "order_check_retcode": getattr(check_res, "retcode", None),
                "order_check_comment": getattr(check_res, "comment", None),
                "request": (
                    request.to_dict() if request is not None else intent.to_dict()
                ),
                "constraints": constraints.to_dict() if constraints else {},
            },
        )

        t0 = time.perf_counter()
        decision = self.evaluate_safety(
            user_id=user_id,
            request_id=request_id,
            intent=intent,
            connected=connected,
            login=login,
            recent=recent_decisions,
            existing=existing_decision,
        )
        risk_ok = decision.decision is not ExecutionDecision.REJECT
        self._stage(
            stages,
            stage=PipelineStage.RISK_CHECK,
            status="ok" if risk_ok else "failed",
            reason=(
                "Risk approved"
                if decision.decision is ExecutionDecision.ALLOW
                else (
                    "; ".join(decision.rejection_reasons)
                    if decision.rejection_reasons
                    else decision.decision.value
                )
            ),
            t0=t0,
            meta={"decision": decision.decision.value, "checks": dict(decision.checks)},
        )
        self._observe(
            user_id=uid,
            request_id=request_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            volume=volume,
            stage=(PipelineStage.RISK_CHECK if risk_ok else PipelineStage.REJECTED),
            reason=f"safety={decision.decision.value}",
            meta={"decision": decision.decision.value},
        )

        t0 = time.perf_counter()
        if decision.decision is ExecutionDecision.REJECT:
            self._stage(
                stages,
                stage=PipelineStage.EXECUTION_CHECK,
                status="failed",
                reason="; ".join(decision.rejection_reasons)
                or "Execution check rejected",
                t0=t0,
            )
            self._observe(
                user_id=uid,
                request_id=request_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                volume=volume,
                stage=PipelineStage.REJECTED,
                reason="; ".join(decision.rejection_reasons) or "rejected",
            )
            result = PipelineResult(
                request_id=request_id,
                action=action,
                outcome="rejected",
                message="; ".join(decision.rejection_reasons)
                or "Execution check rejected",
                stages=stages,
                rejection_reasons=list(decision.rejection_reasons),
                warnings=list(decision.warnings),
                checks=dict(decision.checks),
                calculated_risk=dict(decision.calculated_risk),
                decision=decision.decision.value,
                latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
                idempotent_replay=decision.idempotent_replay,
            )
            result.journal_entry = self._write_journal(result, intent, None, uid)
            return result, decision

        if decision.decision is ExecutionDecision.RETRY:
            self._stage(
                stages,
                stage=PipelineStage.EXECUTION_CHECK,
                status="blocked",
                reason="; ".join(decision.rejection_reasons) or "Retry required",
                t0=t0,
            )
            result = PipelineResult(
                request_id=request_id,
                action=action,
                outcome="retry",
                message="; ".join(decision.rejection_reasons) or "Retry required",
                stages=stages,
                rejection_reasons=list(decision.rejection_reasons),
                warnings=list(decision.warnings),
                checks=dict(decision.checks),
                calculated_risk=dict(decision.calculated_risk),
                decision=decision.decision.value,
                latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
                idempotent_replay=decision.idempotent_replay,
            )
            result.journal_entry = self._write_journal(result, intent, None, uid)
            return result, decision

        # Authoritative Risk Engine — never skip on live submit path
        t0 = time.perf_counter()
        risk_reject: list[str] = []
        try:
            account = self.gateway.adapter.account_snapshot()
            positions = list(self.gateway.adapter.list_positions())
            entry = Decimal("0")
            try:
                tick = self.gateway.adapter.latest_tick(intent.symbol)
                entry = (
                    Decimal(str(tick.bid))
                    if intent.side is OrderSide.SELL
                    else Decimal(str(tick.ask))
                )
                spread_val = Decimal(str(tick.ask)) - Decimal(str(tick.bid))
            except (OSError, RuntimeError, ValueError):
                spread_val = None
            if intent.price is not None:
                entry = intent.price
            stop_dist = None
            if intent.stop_loss is not None and entry > 0:
                stop_dist = abs(entry - intent.stop_loss.value)
            if entry <= 0:
                risk_reject = [
                    "Risk Engine unavailable — fail-closed: "
                    "entry price unresolved from tick/intent"
                ]
            else:
                # Authoritative peak (persisted HWM) + daily PnL from MT5 deals.
                deals: list[Any] = []
                try:
                    from datetime import UTC, datetime, timedelta

                    day_start = datetime.now(UTC).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    deals = list(
                        self.gateway.adapter.history_deals(
                            date_from=day_start,
                            date_to=datetime.now(UTC) + timedelta(days=1),
                        )
                    )
                except (OSError, RuntimeError, ValueError, TypeError, AttributeError):
                    deals = []
                peak, daily_pnl = self.risk_tracker.resolve_for_risk(
                    login=int(account.login or 0),
                    equity=account.equity,
                    balance=account.balance,
                    deals=deals,
                )
                from app.domain.entities.risk_engine import contract_size_for_symbol

                live_constraints = self.order_validation.constraints_for(
                    intent.symbol
                )
                live_cs = (
                    live_constraints.contract_size
                    if live_constraints.contract_size > 0
                    else contract_size_for_symbol(
                        intent.symbol, default=Decimal("0")
                    )
                )
                live_tick_size: Decimal | None = None
                live_tick_value: Decimal | None = None
                try:
                    info = self.order_validation.adapter.symbol_info(intent.symbol)
                    live_tick_size, live_tick_value = _ticks_from_symbol_info(info)
                    info_cs = _opt_positive_decimal(
                        getattr(info, "contract_size", None)
                    )
                    if info_cs is not None:
                        live_cs = info_cs
                except (OSError, RuntimeError, ValueError, TypeError, AttributeError):
                    pass
                live_risk = RiskEngine(
                    config=replace(
                        self.risk_engine.config,
                        min_lot=live_constraints.min_volume,
                        lot_step=live_constraints.volume_step,
                        max_lot=live_constraints.max_volume,
                        contract_size=live_cs,
                    )
                )
                assessment = live_risk.evaluate(
                    RiskCheckInput(
                        user_id=user_id,
                        request_id=request_id,
                        symbol=intent.symbol,
                        side=intent.side.value,
                        requested_lots=intent.volume.value,
                        stop_loss_distance=stop_dist,
                        sizing_method=PositionSizingMethod.FIXED_LOT,
                        entry_price=entry,
                        spread=spread_val,
                        contract_size=live_cs,
                        tick_size=live_tick_size,
                        tick_value=live_tick_value,
                    ),
                    account=account,
                    positions=positions,
                    peak_equity=peak if peak > 0 else None,
                    daily_pnl=daily_pnl,
                )
                # Log TEST MODE override on the live trade path only.
                try:
                    from app.domain.institutional_trading.risk_lock_override import (
                        log_risk_lock_overridden,
                        risk_lock_override_enabled,
                    )

                    warn_txt = " ".join(assessment.warnings or ())
                    if (
                        risk_lock_override_enabled()
                        and "daily loss lock overridden" in warn_txt.lower()
                    ):
                        dd = assessment.drawdown or {}
                        loss_pct = dd.get("daily_loss_pct")
                        log_risk_lock_overridden(
                            current_daily_loss_pct=(
                                loss_pct
                                if isinstance(loss_pct, (int, float, str, Decimal))
                                or loss_pct is None
                                else str(loss_pct)
                            ),
                        )
                except Exception:  # noqa: S110  # best-effort optional path
                    pass
                if assessment.decision is RiskDecision.REJECT:
                    risk_reject = list(assessment.reasons) or ["Risk Engine REJECT"]
                    # Belt-and-suspenders: strip daily-loss if still present.
                    from app.domain.institutional_trading.risk_lock_override import (
                        apply_daily_loss_lock_override,
                    )

                    dd2 = assessment.drawdown or {}
                    loss_pct2 = dd2.get("daily_loss_pct")
                    remaining, did_override = apply_daily_loss_lock_override(
                        risk_reject,
                        current_daily_loss_pct=(
                            loss_pct2
                            if isinstance(loss_pct2, (int, float, str, Decimal))
                            or loss_pct2 is None
                            else str(loss_pct2)
                        ),
                        log=True,
                    )
                    if did_override:
                        risk_reject = remaining
                elif assessment.decision is RiskDecision.REDUCE_SIZE:
                    approved = assessment.approved_lots
                    if approved is None or approved <= 0:
                        risk_reject = list(assessment.reasons) or [
                            "Risk Engine REDUCE_SIZE without approved lots"
                        ]
                    elif approved != intent.volume.value:
                        intent = replace(intent, volume=LotSize.of(str(approved)))
                        volume = str(intent.volume.value)
                else:
                    approved = assessment.approved_lots
                    if approved is None or approved <= 0:
                        risk_reject = list(assessment.reasons) or [
                            "Risk Engine ALLOW without approved lots"
                        ]
                    elif approved != intent.volume.value:
                        intent = replace(intent, volume=LotSize.of(str(approved)))
                        volume = str(intent.volume.value)
                if not risk_reject and not _is_manage_intent(intent):
                    intent, _post_notes = self.order_validation.normalize_intent(
                        intent
                    )
                    volume = str(intent.volume.value)
                    post_constraints = self.order_validation.constraints_for(
                        intent.symbol
                    )
                    ok_final_vol, msg_final_vol = (
                        self.order_validation.validate_volume(
                            intent, post_constraints
                        )
                    )
                    if not ok_final_vol:
                        risk_reject = [
                            "final volume invalid after Risk approval: "
                            f"{msg_final_vol}"
                        ]
        except (OSError, RuntimeError, ValueError, TypeError, ArithmeticError) as exc:
            risk_reject = [f"Risk Engine unavailable — fail-closed: {exc}"]

        self._stage(
            stages,
            stage=PipelineStage.RISK_CHECK,
            status="failed" if risk_reject else "ok",
            reason=("; ".join(risk_reject) if risk_reject else "Risk Engine PASS"),
            t0=t0,
            meta={"component": "risk_engine"},
        )
        if risk_reject:
            self._observe(
                user_id=uid,
                request_id=request_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                volume=volume,
                stage=PipelineStage.REJECTED,
                reason="; ".join(risk_reject),
            )
            result = PipelineResult(
                request_id=request_id,
                action=action,
                outcome="rejected",
                message="; ".join(risk_reject),
                stages=stages,
                rejection_reasons=risk_reject,
                warnings=list(decision.warnings),
                checks=dict(decision.checks),
                calculated_risk=dict(decision.calculated_risk),
                decision=ExecutionDecision.REJECT.value,
                latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
                idempotent_replay=decision.idempotent_replay,
            )
            result.journal_entry = self._write_journal(result, intent, None, uid)
            return result, decision

        self._stage(
            stages,
            stage=PipelineStage.EXECUTION_CHECK,
            status="ok",
            reason="Policy passed — broker send still gated by EXECUTION_ENABLED",
            t0=t0,
            meta={"execution_enabled": bool(self.gateway.adapter.execution_enabled)},
        )
        self._observe(
            user_id=uid,
            request_id=request_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            volume=volume,
            stage=PipelineStage.EXECUTION_CHECK,
            reason="execution check passed",
        )

        if skip_broker:
            result = PipelineResult(
                request_id=request_id,
                action=action,
                outcome="prepared",
                message="Pipeline prepared — broker submission skipped",
                stages=stages,
                warnings=list(decision.warnings),
                checks=dict(decision.checks),
                calculated_risk=dict(decision.calculated_risk),
                decision=decision.decision.value,
                latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
                idempotent_replay=decision.idempotent_replay,
            )
            result.journal_entry = self._write_journal(result, intent, None, uid)
            return result, decision

        if not _is_manage_intent(intent) and intent.volume.value > 0:
            from app.domain.entities.risk_engine import contract_size_for_symbol
            from app.domain.institutional_trading.operations.min_lot_feasibility import (  # noqa: E501
                actual_planned_sl_band_reason,
                format_planned_sl_reject_detail,
                lot_dollar_risk,
            )

            stop_for_band = Decimal("0")
            entry_for_band = Decimal("0")
            if intent.price is not None and intent.price > 0:
                entry_for_band = intent.price
            else:
                try:
                    tick = self.gateway.adapter.latest_tick(intent.symbol)
                    entry_for_band = (
                        Decimal(str(tick.bid))
                        if intent.side is OrderSide.SELL
                        else Decimal(str(tick.ask))
                    )
                except (OSError, RuntimeError, ValueError, TypeError):
                    entry_for_band = Decimal("0")
            if intent.stop_loss is not None and entry_for_band > 0:
                stop_for_band = abs(entry_for_band - intent.stop_loss.value)
            if stop_for_band > 0:
                try:
                    band_constraints = self.order_validation.constraints_for(
                        intent.symbol
                    )
                    band_cs = (
                        band_constraints.contract_size
                        if band_constraints.contract_size > 0
                        else contract_size_for_symbol(
                            intent.symbol, default=Decimal("0")
                        )
                    )
                    if band_cs <= 0:
                        fail_closed = (
                            "INVALID_BROKER_SPEC: contract_size missing "
                            f"for {intent.symbol}"
                        )
                        self._observe(
                            user_id=uid,
                            request_id=request_id,
                            symbol=symbol,
                            side=side,
                            order_type=order_type,
                            volume=str(intent.volume.value),
                            stage=PipelineStage.REJECTED,
                            reason=fail_closed,
                        )
                        result = PipelineResult(
                            request_id=request_id,
                            action=action,
                            outcome="rejected",
                            message=fail_closed,
                            stages=stages,
                            rejection_reasons=[fail_closed],
                            warnings=list(decision.warnings),
                            checks=dict(decision.checks),
                            calculated_risk=dict(decision.calculated_risk),
                            decision=ExecutionDecision.REJECT.value,
                            latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
                            idempotent_replay=decision.idempotent_replay,
                        )
                        result.journal_entry = self._write_journal(
                            result, intent, None, uid
                        )
                        return result, decision
                    band_tick_size: Decimal | None = None
                    band_tick_value: Decimal | None = None
                    try:
                        band_info = self.order_validation.adapter.symbol_info(
                            intent.symbol
                        )
                        band_tick_size, band_tick_value = _ticks_from_symbol_info(
                            band_info
                        )
                        info_cs = _opt_positive_decimal(
                            getattr(band_info, "contract_size", None)
                        )
                        if info_cs is not None:
                            band_cs = info_cs
                    except (
                        OSError,
                        RuntimeError,
                        ValueError,
                        TypeError,
                        AttributeError,
                    ):
                        pass
                    actual = lot_dollar_risk(
                        intent.volume.value,
                        stop_distance=stop_for_band,
                        contract_size=band_cs,
                        tick_size=band_tick_size,
                        tick_value=band_tick_value,
                    )
                    remaining_cap = None
                    try:
                        open_positions = list(self.gateway.adapter.list_positions())
                        remaining_cap = (
                            self.risk_engine.config.max_total_planned_risk_usd
                            - self.risk_engine.aggregate_planned_sl_risk(open_positions)
                        )
                        if remaining_cap < 0:
                            remaining_cap = Decimal("0")
                    except (
                        OSError,
                        RuntimeError,
                        ValueError,
                        TypeError,
                        AttributeError,
                    ):
                        remaining_cap = (
                            self.risk_engine.config.max_total_planned_risk_usd
                        )
                    band_reason = actual_planned_sl_band_reason(
                        actual,
                        remaining_portfolio_risk=remaining_cap,
                    )
                    if band_reason is not None:
                        detail = format_planned_sl_reject_detail(
                            reason=band_reason,
                            symbol=intent.symbol,
                            volume=intent.volume.value,
                            actual=actual,
                            stop_distance=stop_for_band,
                            min_lot=band_constraints.min_volume,
                            lot_step=band_constraints.volume_step,
                            max_lot=band_constraints.max_volume,
                        )
                        logger.info(
                            "planned_initial_sl_risk_rejected",
                            symbol=intent.symbol,
                            calculated_volume=str(intent.volume.value),
                            actual_planned_initial_sl_risk=str(actual),
                            initial_sl_distance=str(stop_for_band),
                            broker_volume_min=str(band_constraints.min_volume),
                            broker_volume_step=str(band_constraints.volume_step),
                            broker_volume_max=str(band_constraints.max_volume),
                            rejection_reason=band_reason,
                            stage="pre_order_send",
                        )
                        self._stage(
                            stages,
                            stage=PipelineStage.RISK_CHECK,
                            status="failed",
                            reason=detail,
                            t0=t0,
                            meta={"component": "pre_order_send_planned_sl_band"},
                        )
                        self._observe(
                            user_id=uid,
                            request_id=request_id,
                            symbol=symbol,
                            side=side,
                            order_type=order_type,
                            volume=str(intent.volume.value),
                            stage=PipelineStage.REJECTED,
                            reason=detail,
                        )
                        result = PipelineResult(
                            request_id=request_id,
                            action=action,
                            outcome="rejected",
                            message=detail,
                            stages=stages,
                            rejection_reasons=[detail],
                            warnings=list(decision.warnings),
                            checks=dict(decision.checks),
                            calculated_risk=dict(decision.calculated_risk),
                            decision=ExecutionDecision.REJECT.value,
                            latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
                            idempotent_replay=decision.idempotent_replay,
                        )
                        result.journal_entry = self._write_journal(
                            result, intent, None, uid
                        )
                        return result, decision
                    tp_for_band = (
                        intent.take_profit.value
                        if intent.take_profit is not None
                        else Decimal("0")
                    )
                    tp_dist = (
                        abs(tp_for_band - entry_for_band)
                        if tp_for_band > 0 and entry_for_band > 0
                        else Decimal("0")
                    )
                    if tp_dist <= stop_for_band:
                        fail_closed = (
                            "TP_PROFIT_NOT_GREATER_THAN_SL_LOSS: "
                            f"tp_distance={tp_dist} sl_distance={stop_for_band}"
                        )
                        self._observe(
                            user_id=uid,
                            request_id=request_id,
                            symbol=symbol,
                            side=side,
                            order_type=order_type,
                            volume=str(intent.volume.value),
                            stage=PipelineStage.REJECTED,
                            reason=fail_closed,
                        )
                        result = PipelineResult(
                            request_id=request_id,
                            action=action,
                            outcome="rejected",
                            message=fail_closed,
                            stages=stages,
                            rejection_reasons=[fail_closed],
                            warnings=list(decision.warnings),
                            checks=dict(decision.checks),
                            calculated_risk=dict(decision.calculated_risk),
                            decision=ExecutionDecision.REJECT.value,
                            latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
                            idempotent_replay=decision.idempotent_replay,
                        )
                        result.journal_entry = self._write_journal(
                            result, intent, None, uid
                        )
                        return result, decision
                    logger.info(
                        "pre_order_send_planned_sl_ok",
                        symbol=intent.symbol,
                        final_volume=str(intent.volume.value),
                        planned_initial_sl_risk_usd=str(actual),
                        stop_distance=str(stop_for_band),
                        tp_distance=str(tp_dist),
                        contract_size=str(band_cs),
                    )
                except Exception:
                    logger.exception("pre_order_send_planned_sl_band_failed")
                    fail_closed = (
                        "pre_order_send planned SL band unavailable — fail closed"
                    )
                    self._observe(
                        user_id=uid,
                        request_id=request_id,
                        symbol=symbol,
                        side=side,
                        order_type=order_type,
                        volume=str(intent.volume.value),
                        stage=PipelineStage.REJECTED,
                        reason=fail_closed,
                    )
                    result = PipelineResult(
                        request_id=request_id,
                        action=action,
                        outcome="rejected",
                        message=fail_closed,
                        stages=stages,
                        rejection_reasons=[fail_closed],
                        warnings=list(decision.warnings),
                        checks=dict(decision.checks),
                        calculated_risk=dict(decision.calculated_risk),
                        decision=ExecutionDecision.REJECT.value,
                        latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
                        idempotent_replay=decision.idempotent_replay,
                    )
                    result.journal_entry = self._write_journal(
                        result, intent, None, uid
                    )
                    return result, decision
            else:
                fail_closed = (
                    "pre_order_send missing valid initial stop — fail closed"
                )
                self._observe(
                    user_id=uid,
                    request_id=request_id,
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    volume=str(intent.volume.value),
                    stage=PipelineStage.REJECTED,
                    reason=fail_closed,
                )
                result = PipelineResult(
                    request_id=request_id,
                    action=action,
                    outcome="rejected",
                    message=fail_closed,
                    stages=stages,
                    rejection_reasons=[fail_closed],
                    warnings=list(decision.warnings),
                    checks=dict(decision.checks),
                    calculated_risk=dict(decision.calculated_risk),
                    decision=ExecutionDecision.REJECT.value,
                    latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
                    idempotent_replay=decision.idempotent_replay,
                )
                result.journal_entry = self._write_journal(
                    result, intent, None, uid
                )
                return result, decision

        t0 = time.perf_counter()
        send_request = self.gateway.prepare(intent)
        if (
            not _is_manage_intent(intent)
            and intent.volume.value > 0
            and send_request.volume != intent.volume.value
        ):
            fail_closed = (
                "final volume mutated after Risk approval: "
                f"approved={intent.volume.value} prepared={send_request.volume}"
            )
            self._observe(
                user_id=uid,
                request_id=request_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                volume=str(intent.volume.value),
                stage=PipelineStage.REJECTED,
                reason=fail_closed,
            )
            result = PipelineResult(
                request_id=request_id,
                action=action,
                outcome="rejected",
                message=fail_closed,
                stages=stages,
                rejection_reasons=[fail_closed],
                warnings=list(decision.warnings),
                checks=dict(decision.checks),
                calculated_risk=dict(decision.calculated_risk),
                decision=ExecutionDecision.REJECT.value,
                latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
                idempotent_replay=decision.idempotent_replay,
            )
            result.journal_entry = self._write_journal(result, intent, None, uid)
            return result, decision
        self._observe(
            user_id=uid,
            request_id=request_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            volume=volume,
            stage=PipelineStage.BROKER_SUBMISSION,
            reason="submitting to broker via Execution Gateway",
        )
        exec_result = self.gateway.submit(
            intent, user_id=user_id, request_id=request_id
        )
        _ = self.gateway.drain_events()
        self._stage(
            stages,
            stage=PipelineStage.BROKER_SUBMISSION,
            status=(
                "ok"
                if exec_result.outcome
                not in {ExecutionOutcome.FAILED, ExecutionOutcome.DISABLED}
                else "failed"
            ),
            reason=exec_result.message,
            t0=t0,
            meta={
                "component": "gateway.mt5_order_send",
                "outcome": exec_result.outcome.value,
                "retcode": exec_result.retcode,
                "comment": exec_result.message,
                "order_ticket": exec_result.order_ticket,
                "deal_ticket": exec_result.deal_ticket,
                "request": intent.to_dict(),
                "response": exec_result.to_dict(),
            },
        )

        if exec_result.outcome is ExecutionOutcome.DISABLED:
            blocked = humanize_reasons([exec_result.message])[0]
            self._observe(
                user_id=uid,
                request_id=request_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                volume=volume,
                stage=PipelineStage.REJECTED,
                reason=blocked,
            )
            self._stage(
                stages,
                stage=PipelineStage.REJECTED,
                status="blocked",
                reason=blocked,
                t0=t0,
            )
            result = PipelineResult(
                request_id=request_id,
                action=action,
                outcome=exec_result.outcome.value,
                message=exec_result.message,
                stages=stages,
                rejection_reasons=[blocked],
                warnings=list(decision.warnings),
                checks=dict(decision.checks),
                calculated_risk=dict(decision.calculated_risk),
                execution_result=exec_result,
                decision=decision.decision.value,
                latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
            )
            result.journal_entry = self._write_journal(result, intent, exec_result, uid)
            self._record_order_attempt(
                intent=intent,
                request=request,
                constraints=constraints,
                login=login,
                oms_result=exec_result.outcome.value,
                execution_result=order_attempt_execution_result(
                    order_send_reached=False,
                    ticket=exec_result.order_ticket,
                    outcome=exec_result.outcome.value,
                    retcode=exec_result.retcode,
                    message=exec_result.message,
                ),
                mt5_retcode=exec_result.retcode,
                broker_comment=exec_result.message,
                mt5_ticket=exec_result.order_ticket,
                order_send_reached=False,
            )
            return result, decision

        if exec_result.outcome is ExecutionOutcome.SUCCESS:
            self._observe(
                user_id=uid,
                request_id=request_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                volume=volume,
                stage=PipelineStage.BROKER_ACCEPTANCE,
                reason="broker accepted order",
                meta={"ticket": exec_result.order_ticket},
            )
            self._stage(
                stages,
                stage=PipelineStage.BROKER_ACCEPTANCE,
                status="ok",
                reason="Broker accepted",
                t0=t0,
                meta={"ticket": exec_result.order_ticket},
            )
            if intent.order_type is OrderType.MARKET:
                self._observe(
                    user_id=uid,
                    request_id=request_id,
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    volume=volume,
                    stage=PipelineStage.BROKER_FILL,
                    reason="broker fill reported",
                    meta={
                        "price": str(exec_result.price),
                        "deal": exec_result.deal_ticket,
                    },
                )
                self._stage(
                    stages,
                    stage=PipelineStage.BROKER_FILL,
                    status="ok",
                    reason=f"Filled @ {exec_result.price}",
                    t0=t0,
                )
            for post in (
                PipelineStage.PORTFOLIO_UPDATE,
                PipelineStage.HISTORY,
                PipelineStage.JOURNAL,
                PipelineStage.ANALYTICS,
            ):
                self._observe(
                    user_id=uid,
                    request_id=request_id,
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    volume=volume,
                    stage=post,
                    reason=f"post-trade {post.value}",
                )
                self._stage(
                    stages,
                    stage=post,
                    status="ok",
                    reason=f"{post.value} marked for clients (invalidate / refresh)",
                    t0=t0,
                )
        elif exec_result.outcome is ExecutionOutcome.CANCELLED:
            self._observe(
                user_id=uid,
                request_id=request_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                volume=volume,
                stage=PipelineStage.CANCELLED,
                reason=exec_result.message,
            )
            self._stage(
                stages,
                stage=PipelineStage.CANCELLED,
                status="ok",
                reason=exec_result.message,
                t0=t0,
            )
        else:
            self._observe(
                user_id=uid,
                request_id=request_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                volume=volume,
                stage=PipelineStage.REJECTED,
                reason=exec_result.message,
            )
            self._stage(
                stages,
                stage=PipelineStage.REJECTED,
                status="failed",
                reason=exec_result.message,
                t0=t0,
            )

        result = PipelineResult(
            request_id=request_id,
            action=action,
            outcome=exec_result.outcome.value,
            message=exec_result.message,
            stages=stages,
            warnings=list(decision.warnings),
            checks=dict(decision.checks),
            calculated_risk=dict(decision.calculated_risk),
            execution_result=exec_result,
            decision=decision.decision.value,
            latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
            rejection_reasons=(
                humanize_reasons([exec_result.message])
                if exec_result.outcome
                in {ExecutionOutcome.FAILED, ExecutionOutcome.DISABLED}
                else []
            ),
        )
        result.journal_entry = self._write_journal(result, intent, exec_result, uid)
        send_reached = exec_result.outcome is not ExecutionOutcome.DISABLED
        self._record_order_attempt(
            intent=intent,
            request=request,
            constraints=constraints,
            login=login,
            oms_result=exec_result.outcome.value,
            execution_result=order_attempt_execution_result(
                order_send_reached=send_reached,
                ticket=exec_result.order_ticket,
                outcome=exec_result.outcome.value,
                retcode=exec_result.retcode,
                message=exec_result.message,
            ),
            mt5_retcode=exec_result.retcode if send_reached else None,
            broker_comment=exec_result.message,
            mt5_ticket=exec_result.order_ticket,
            order_send_reached=send_reached,
        )
        return result, decision

    def run_cancel(
        self,
        *,
        user_id: UUID,
        request_id: str,
        ticket: int,
        symbol: str = "",
        connected: bool,
    ) -> PipelineResult:
        """Cancel a pending order through the same gated gateway."""
        t_pipeline = time.perf_counter()
        stages: list[PipelineStageRecord] = []
        uid = str(user_id)
        side = "cancel"
        order_type = "pending"
        volume = "0"

        t0 = time.perf_counter()
        self._observe(
            user_id=uid,
            request_id=request_id,
            symbol=symbol or f"ticket:{ticket}",
            side=side,
            order_type=order_type,
            volume=volume,
            stage=PipelineStage.DRAFT,
            reason=f"cancel draft ticket={ticket}",
        )
        self._stage(
            stages,
            stage=PipelineStage.DRAFT,
            status="ok",
            reason=f"Cancel pending ticket {ticket}",
            t0=t0,
        )

        if not connected:
            reason = humanize_reasons(["broker connection not active"])[0]
            self._stage(
                stages,
                stage=PipelineStage.VALIDATION,
                status="failed",
                reason=reason,
                t0=t0,
            )
            result = PipelineResult(
                request_id=request_id,
                action="cancel",
                outcome="rejected",
                message=reason,
                stages=stages,
                rejection_reasons=[reason],
                latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
            )
            result.journal_entry = self.journal.record(
                user_id=uid,
                request_id=request_id,
                latency_ms=result.latency_ms,
                gateway=self.gateway_name,
                broker=self.broker_name,
                order_id=None,
                ticket=ticket,
                volume=volume,
                price="0",
                slippage=None,
                commission=None,
                swap=None,
                reason=reason,
                execution_result="rejected",
                symbol=symbol,
                side=side,
                order_type=order_type,
                action="cancel",
                stages=[s.to_dict() for s in stages],
            )
            return result

        t0 = time.perf_counter()
        self._observe(
            user_id=uid,
            request_id=request_id,
            symbol=symbol or f"ticket:{ticket}",
            side=side,
            order_type=order_type,
            volume=volume,
            stage=PipelineStage.BROKER_SUBMISSION,
            reason="cancel via Execution Gateway",
        )
        exec_result = self.gateway.cancel(
            ticket, user_id=user_id, request_id=request_id, symbol=symbol
        )
        _ = self.gateway.drain_events()
        self._stage(
            stages,
            stage=PipelineStage.BROKER_SUBMISSION,
            status=(
                "ok" if exec_result.outcome is ExecutionOutcome.SUCCESS else "failed"
            ),
            reason=exec_result.message,
            t0=t0,
            meta={"outcome": exec_result.outcome.value, "retcode": exec_result.retcode},
        )
        if exec_result.outcome is ExecutionOutcome.SUCCESS:
            self._observe(
                user_id=uid,
                request_id=request_id,
                symbol=symbol or f"ticket:{ticket}",
                side=side,
                order_type=order_type,
                volume=volume,
                stage=PipelineStage.CANCELLED,
                reason="pending order cancelled",
            )
            self._stage(
                stages,
                stage=PipelineStage.CANCELLED,
                status="ok",
                reason="Cancelled",
                t0=t0,
            )
        elif exec_result.outcome is ExecutionOutcome.DISABLED:
            self._observe(
                user_id=uid,
                request_id=request_id,
                symbol=symbol or f"ticket:{ticket}",
                side=side,
                order_type=order_type,
                volume=volume,
                stage=PipelineStage.REJECTED,
                reason=humanize_reasons([exec_result.message])[0],
            )

        result = PipelineResult(
            request_id=request_id,
            action="cancel",
            outcome=exec_result.outcome.value,
            message=exec_result.message,
            stages=stages,
            execution_result=exec_result,
            latency_ms=(time.perf_counter() - t_pipeline) * 1000.0,
            rejection_reasons=(
                humanize_reasons([exec_result.message])
                if exec_result.outcome
                in {ExecutionOutcome.FAILED, ExecutionOutcome.DISABLED}
                else []
            ),
        )
        result.journal_entry = self.journal.record(
            user_id=uid,
            request_id=request_id,
            latency_ms=result.latency_ms,
            gateway=self.gateway_name,
            broker=self.broker_name,
            order_id=(
                str(exec_result.order_ticket) if exec_result.order_ticket else None
            ),
            ticket=ticket,
            volume=volume,
            price=str(exec_result.price),
            slippage=None,
            commission=None,
            swap=None,
            reason=result.message,
            execution_result=result.outcome,
            symbol=symbol,
            side=side,
            order_type=order_type,
            action="cancel",
            stages=[s.to_dict() for s in stages],
        )
        return result

    def _write_journal(
        self,
        result: PipelineResult,
        intent: OrderIntent,
        exec_result: ExecutionResult | None,
        user_id: str,
    ) -> dict[str, Any]:
        slip = None
        if exec_result is not None and intent.price is not None and exec_result.price:
            try:
                slip = str(abs(exec_result.price - intent.price))
            except Exception:
                slip = None
        return self.journal.record(
            user_id=user_id,
            request_id=result.request_id,
            latency_ms=result.latency_ms,
            gateway=self.gateway_name,
            broker=self.broker_name,
            order_id=(
                str(exec_result.order_ticket)
                if exec_result and exec_result.order_ticket
                else None
            ),
            ticket=exec_result.order_ticket if exec_result else None,
            volume=str(intent.volume.value),
            price=str(exec_result.price) if exec_result else "0",
            slippage=slip,
            commission=None,
            swap=None,
            reason=result.message,
            execution_result=result.outcome,
            symbol=intent.symbol,
            side=intent.side.value,
            order_type=intent.order_type.value,
            action=result.action,
            stages=[s.to_dict() for s in result.stages],
            meta={
                "decision": result.decision,
                "oms_kind": intent.oms_kind,
                "position": intent.position,
                "retcode": exec_result.retcode if exec_result else None,
                "deal_ticket": exec_result.deal_ticket if exec_result else None,
                "request_payload": intent.to_dict(),
                "response_payload": exec_result.to_dict() if exec_result else None,
                "rejection_reasons": list(result.rejection_reasons),
            },
        )
