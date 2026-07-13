"""Strategy Runtime use cases — evaluate / list signals only. Never order_send."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.strategy_runtime import (
    ListStrategySignalsCommand,
    StrategyEvaluateCommand,
    StrategyEvaluateDTO,
    StrategySignalDTO,
    StrategySignalListDTO,
)
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.services.strategy_runtime import (
    StrategyEvaluateInput,
    StrategyRuntimeService,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.mt5_portfolio import AccountSnapshot, MT5Position
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.strategy import StrategyDecisionType
from app.domain.exceptions.base import ValidationError


@dataclass(frozen=True, slots=True)
class EvaluateStrategyUseCase:
    strategy_uow_factory: Any
    mt5_uow_factory: Any
    runtime: StrategyRuntimeService
    portfolio_sync: PortfolioSyncService | None
    audit: RecordAuditEventUseCase

    async def execute(self, command: StrategyEvaluateCommand) -> StrategyEvaluateDTO:
        request_id = command.request_id.strip()
        if not request_id:
            raise ValidationError(
                "request_id is required",
                details={"field": "request_id"},
            )
        symbol = command.symbol.strip()
        if not symbol:
            raise ValidationError(
                "symbol is required",
                details={"field": "symbol"},
            )
        try:
            requested = (
                Decimal(command.requested_lots) if command.requested_lots else None
            )
            stop = (
                Decimal(command.stop_loss_distance)
                if command.stop_loss_distance
                else None
            )
            entry = Decimal(command.entry_price) if command.entry_price else None
            equity = Decimal(command.equity) if command.equity else None
            balance = Decimal(command.balance) if command.balance else None
        except (ValueError, ArithmeticError) as exc:
            raise ValidationError(
                "Invalid strategy evaluate input",
                details={"error": str(exc)},
            ) from exc

        account, positions = await self._load_portfolio_context(
            command.user_id,
            equity_override=equity,
            balance_override=balance,
        )

        result = self.runtime.evaluate(
            StrategyEvaluateInput(
                user_id=command.user_id,
                request_id=request_id,
                symbol=symbol,
                timeframe=command.timeframe,
                analysis=command.to_analysis(),
                check_risk=command.check_risk,
                requested_lots=requested,
                stop_loss_distance=stop,
                entry_price=entry,
                equity=equity,
                balance=balance,
                tick_age_seconds=command.tick_age_seconds,
                candle_count=command.candle_count,
                last_price=command.last_price,
                mt5_connected=command.mt5_connected,
                position_count=command.position_count,
            ),
            account=account,
            positions=positions,
        )
        _ = self.runtime.drain_events()

        async with self.strategy_uow_factory() as uow:
            await uow.evaluations.add(result.evaluation)
            if result.signal is not None:
                await uow.signals.add(result.signal)
            await uow.decision_history.add(
                user_id=result.evaluation.user_id,
                evaluation_id=result.evaluation.id,
                decision=result.evaluation.decision.value,
                reasons=list(result.evaluation.reasons),
            )
            await uow.commit()

        outcome = (
            AuditOutcome.SUCCESS
            if result.evaluation.decision
            in {StrategyDecisionType.READY, StrategyDecisionType.WATCH}
            else (
                AuditOutcome.DENIED
                if result.evaluation.decision is StrategyDecisionType.BLOCKED
                else AuditOutcome.SUCCESS
            )
        )
        await self.audit.execute(
            RecordAuditEventCommand(
                actor_user_id=command.user_id,
                action=AuditAction.SUBMIT,
                outcome=outcome,
                resource_type="strategy_evaluation",
                resource_id=result.evaluation.id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                metadata={
                    "decision": result.evaluation.decision.value,
                    "request_id": request_id,
                    "symbol": result.evaluation.symbol,
                },
            )
        )
        return StrategyEvaluateDTO.from_entities(result.evaluation, result.signal)

    async def _load_portfolio_context(
        self,
        user_id: object,
        *,
        equity_override: Decimal | None,
        balance_override: Decimal | None,
    ) -> tuple[AccountSnapshot | None, list[MT5Position]]:
        if equity_override is not None:
            equity = equity_override
            balance = balance_override if balance_override is not None else equity
            account = AccountSnapshot(
                login=1,
                balance=balance,
                equity=equity,
                margin=Decimal("0"),
                free_margin=equity,
                margin_level=Decimal("0"),
                profit=Decimal("0"),
                leverage=100,
            )
            return account, []

        from uuid import UUID

        assert isinstance(user_id, UUID)
        connected = False
        session_ref = ""
        async with self.mt5_uow_factory() as uow:
            connection = await uow.connections.get_active_for_user(user_id)
            if connection is not None and connection.connected:
                session_ref = (connection.session_ref or "").strip()
                connected = True

        adapter = None
        if self.portfolio_sync is not None:
            adapter = getattr(self.portfolio_sync, "adapter", None)
        if (
            connected
            and self.portfolio_sync is not None
            and adapter is not None
            and adapter.is_live_session(session_ref)
        ):
            try:
                return (
                    self.portfolio_sync.account_snapshot(),
                    self.portfolio_sync.list_positions(),
                )
            except (OSError, RuntimeError, ValueError):
                pass
        return None, []


@dataclass(frozen=True, slots=True)
class ListStrategySignalsUseCase:
    strategy_uow_factory: Any

    async def execute(
        self, command: ListStrategySignalsCommand
    ) -> StrategySignalListDTO:
        limit = max(1, min(command.limit, 200))
        async with self.strategy_uow_factory() as uow:
            rows = await uow.signals.list_for_user(
                command.user_id,
                limit=limit,
                include_rejected=command.include_rejected,
            )
        items = [StrategySignalDTO.from_entity(s) for s in rows]
        return StrategySignalListDTO(items=items, count=len(items))
