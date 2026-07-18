"""FastAPI dependencies for Quant AI (read-only advisory)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends

from app.application.dto.paper import PaperHistoryCommand
from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.services.quant_ai import QuantAIService
from app.application.use_cases.mt5 import GetMT5StatusUseCase, ListMT5SymbolsUseCase
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.presentation.dependencies.execution import get_execution_uow_factory
from app.presentation.dependencies.intelligence import (
    get_market_context_engine,
    get_news_intelligence,
    get_provider_registry,
)
from app.presentation.dependencies.mt5 import get_mt5_adapter, get_mt5_uow_factory
from core.config.settings import Settings, get_settings
from core.di.container import get_container


async def _load_attempts(user_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
    try:
        factory = get_execution_uow_factory()
    except RuntimeError:
        return []
    try:
        async with factory() as uow:
            rows = await uow.attempts.list_for_user(user_id, limit=limit)
            return [a.to_dict() for a in rows]
    except Exception:
        return []


async def _load_paper_trades(user_id: UUID) -> list[dict[str, Any]]:
    if getattr(get_container(), "paper_uow_factory", None) is None:
        return []
    try:
        from app.presentation.dependencies.paper import get_paper_history

        uc = get_paper_history()
        dto = await uc.execute(PaperHistoryCommand(user_id=user_id, limit=200))
        out: list[dict[str, Any]] = []
        for t in dto.trades:
            out.append(
                {
                    "symbol": t.symbol,
                    "side": t.side,
                    "pnl": t.pnl,
                    "profit": t.pnl,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "fill_price": t.exit_price,
                    "requested_price": t.entry_price,
                    "slippage": t.slippage,
                    "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                    "closed_at": t.closed_at.isoformat() if t.closed_at else None,
                    "data_source": "paper_trades",
                }
            )
        return out
    except Exception:
        return []


def get_quant_ai(
    settings: Annotated[Settings, Depends(get_settings)],
    adapter: Annotated[MT5Adapter, Depends(get_mt5_adapter)],
    uow_factory: Annotated[Any, Depends(get_mt5_uow_factory)],
) -> QuantAIService:
    _ = settings
    registry = get_provider_registry(settings, adapter)
    return QuantAIService(
        status=GetMT5StatusUseCase(uow_factory=uow_factory, adapter=adapter),
        symbols=ListMT5SymbolsUseCase(uow_factory=uow_factory, adapter=adapter),
        portfolio_sync=PortfolioSyncService(adapter=adapter),
        market_data=MT5MarketDataService(adapter=adapter),
        market_context=get_market_context_engine(),
        news=get_news_intelligence(registry),
        load_attempts=_load_attempts,
        load_paper_trades=_load_paper_trades,
    )


QuantAISvc = Annotated[QuantAIService, Depends(get_quant_ai)]
