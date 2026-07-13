"""Risk engine use case — check only, never order_send / never enable execution."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.risk_engine import RiskCheckCommand, RiskCheckDTO
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.mt5_portfolio import AccountSnapshot, MT5Position
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.risk import PositionSizingMethod
from app.domain.exceptions.base import ValidationError


@dataclass(frozen=True, slots=True)
class CheckRiskUseCase:
    risk_uow_factory: Any
    mt5_uow_factory: Any
    risk_engine: RiskEngine
    portfolio_sync: PortfolioSyncService | None
    audit: RecordAuditEventUseCase

    async def execute(self, command: RiskCheckCommand) -> RiskCheckDTO:
        request_id = command.request_id.strip()
        if not request_id:
            raise ValidationError(
                "request_id is required",
                details={"field": "request_id"},
            )
        try:
            side = command.side.strip().lower()
            if side not in {"buy", "sell"}:
                raise ValueError("side must be buy or sell")
            method = PositionSizingMethod(command.sizing_method.strip().lower())
            requested = (
                Decimal(command.requested_lots) if command.requested_lots else None
            )
            stop = (
                Decimal(command.stop_loss_distance)
                if command.stop_loss_distance
                else None
            )
            atr = Decimal(command.atr) if command.atr else None
            entry = Decimal(command.entry_price)
            peak = Decimal(command.peak_equity) if command.peak_equity else None
            daily = Decimal(command.daily_pnl)
            weekly = Decimal(command.weekly_pnl)
            monthly = Decimal(command.monthly_pnl)
        except (ValidationError, ValueError, ArithmeticError) as exc:
            raise ValidationError(
                "Invalid risk check input",
                details={"error": str(exc)},
            ) from exc

        account, positions = await self._load_portfolio_context(
            command.user_id,
            equity_override=command.equity,
            balance_override=command.balance,
        )

        check = RiskCheckInput(
            user_id=command.user_id,
            request_id=request_id,
            symbol=command.symbol,
            side=side,
            requested_lots=requested,
            stop_loss_distance=stop,
            atr=atr,
            sizing_method=method,
            entry_price=entry,
        )
        assessment = self.risk_engine.evaluate(
            check,
            account=account,
            positions=positions,
            peak_equity=peak,
            daily_pnl=daily,
            weekly_pnl=weekly,
            monthly_pnl=monthly,
        )
        _ = self.risk_engine.drain_events()

        async with self.risk_uow_factory() as uow:
            await uow.assessments.add(assessment)
            await uow.commit()

        outcome = (
            AuditOutcome.SUCCESS
            if assessment.decision.value == "allow"
            else (
                AuditOutcome.DENIED
                if assessment.decision.value == "reject"
                else AuditOutcome.FAILURE
            )
        )
        await self.audit.execute(
            RecordAuditEventCommand(
                actor_user_id=command.user_id,
                action=AuditAction.SUBMIT,
                outcome=outcome,
                resource_type="risk_assessment",
                resource_id=assessment.id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                metadata={
                    "decision": assessment.decision.value,
                    "risk_score": assessment.risk_score,
                    "request_id": request_id,
                    "symbol": assessment.symbol,
                },
            )
        )
        return RiskCheckDTO.from_entity(assessment)

    async def _load_portfolio_context(
        self,
        user_id: UUID,
        *,
        equity_override: str | None,
        balance_override: str | None,
    ) -> tuple[AccountSnapshot, list[MT5Position]]:
        if equity_override is not None:
            equity = Decimal(equity_override)
            balance = (
                Decimal(balance_override) if balance_override is not None else equity
            )
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
                account = self.portfolio_sync.account_snapshot()
                positions = self.portfolio_sync.list_positions()
                return account, positions
            except (OSError, RuntimeError, ValueError):
                pass

        # Safe defaults when no live portfolio context (still evaluates)
        account = AccountSnapshot(
            login=1,
            balance=Decimal("10000"),
            equity=Decimal("10000"),
            margin=Decimal("0"),
            free_margin=Decimal("10000"),
            margin_level=Decimal("0"),
            profit=Decimal("0"),
            leverage=100,
        )
        return account, []
