"""Execution Gateway — prepare / submit / cancel with flag-gated order_send."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.domain.entities.execution_gateway import (
    ExecutionResult,
    map_retcode_to_outcome,
)
from app.domain.entities.mt5_order import OrderIntent, TradeRequest
from app.domain.enums.execution import ExecutionOutcome
from app.domain.events.base import DomainEvent
from app.domain.events.execution import (
    ExecutionDisabled,
    ExecutionFailed,
    ExecutionRequested,
    ExecutionSubmitted,
)
from app.domain.interfaces.mt5_order import MT5OrderSendResult
from app.infrastructure.brokers.mt5.adapter import MT5Adapter


@dataclass
class ExecutionGateway:
    """Infrastructure gateway for MT5 order submission.

    ``order_send`` is invoked only when ``adapter.execution_enabled`` is True.
    Default production configuration keeps the flag False.
    """

    adapter: MT5Adapter
    order_validation: MT5OrderValidationService
    _events: list[DomainEvent] = field(default_factory=list, init=False)

    def drain_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def prepare(self, intent: OrderIntent) -> TradeRequest:
        """Build a normalized TradeRequest without sending."""
        return self.order_validation.build_order_request(intent)

    def submit(
        self,
        intent: OrderIntent,
        *,
        user_id: UUID,
        request_id: str,
    ) -> ExecutionResult:
        """Prepare + optionally send. Never sends when execution is disabled."""
        self._events.append(
            ExecutionRequested(
                user_id=user_id,
                request_id=request_id,
                symbol=intent.symbol,
            )
        )
        request = self.prepare(intent)

        if not self.adapter.execution_enabled:
            result = ExecutionResult.disabled(
                request_id=request_id, symbol=intent.symbol
            )
            self._events.append(
                ExecutionDisabled(
                    user_id=user_id,
                    request_id=request_id,
                    symbol=intent.symbol,
                )
            )
            return result

        raw = self.adapter.order_send(request)
        return self._map_send_result(
            raw,
            user_id=user_id,
            request_id=request_id,
            symbol=intent.symbol,
        )

    def cancel(
        self,
        ticket: int,
        *,
        user_id: UUID,
        request_id: str,
        symbol: str = "",
    ) -> ExecutionResult:
        """Cancel a pending order — gated by the same execution flag."""
        self._events.append(
            ExecutionRequested(
                user_id=user_id,
                request_id=request_id,
                symbol=symbol or f"ticket:{ticket}",
            )
        )
        if not self.adapter.execution_enabled:
            result = ExecutionResult.disabled(request_id=request_id, symbol=symbol)
            self._events.append(
                ExecutionDisabled(
                    user_id=user_id,
                    request_id=request_id,
                    symbol=symbol or f"ticket:{ticket}",
                )
            )
            return result

        raw = self.adapter.order_cancel(ticket)
        return self._map_send_result(
            raw,
            user_id=user_id,
            request_id=request_id,
            symbol=symbol,
        )

    def _map_send_result(
        self,
        raw: MT5OrderSendResult,
        *,
        user_id: UUID,
        request_id: str,
        symbol: str,
    ) -> ExecutionResult:
        outcome, retryable, default_msg = map_retcode_to_outcome(raw.retcode)
        message = raw.comment or default_msg
        result = ExecutionResult(
            outcome=outcome,
            retcode=raw.retcode,
            message=message,
            order_ticket=raw.order_ticket or None,
            deal_ticket=raw.deal_ticket or None,
            volume=raw.volume,
            price=raw.price,
            symbol=symbol or (raw.request.symbol if raw.request else ""),
            request_id=request_id,
            retryable=retryable,
        )
        if outcome is ExecutionOutcome.SUCCESS:
            self._events.append(
                ExecutionSubmitted(
                    user_id=user_id,
                    request_id=request_id,
                    symbol=result.symbol,
                    order_ticket=result.order_ticket,
                    retcode=result.retcode,
                )
            )
        elif outcome is ExecutionOutcome.DISABLED:
            self._events.append(
                ExecutionDisabled(
                    user_id=user_id,
                    request_id=request_id,
                    symbol=result.symbol,
                )
            )
        else:
            self._events.append(
                ExecutionFailed(
                    user_id=user_id,
                    request_id=request_id,
                    symbol=result.symbol,
                    retcode=result.retcode,
                    message=result.message,
                    retryable=result.retryable,
                )
            )
        return result
