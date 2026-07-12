"""Application facade for MT5 connection + market-data endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.use_cases.mt5 import (
    ConnectMT5UseCase,
    DisconnectMT5UseCase,
    GetMT5AccountUseCase,
    GetMT5CandlesUseCase,
    GetMT5StatusUseCase,
    GetMT5SymbolUseCase,
    GetMT5TickUseCase,
    ListMT5SymbolsUseCase,
)
from app.application.use_cases.mt5_order import (
    CalculateMT5OrderUseCase,
    ValidateMT5OrderUseCase,
)


@dataclass(frozen=True, slots=True)
class MT5Service:
    get_status: GetMT5StatusUseCase
    connect: ConnectMT5UseCase
    disconnect: DisconnectMT5UseCase
    get_account: GetMT5AccountUseCase
    list_symbols: ListMT5SymbolsUseCase
    get_symbol: GetMT5SymbolUseCase
    get_tick: GetMT5TickUseCase
    get_candles: GetMT5CandlesUseCase
    market_data: MT5MarketDataService
    order_validation: MT5OrderValidationService
    validate_order: ValidateMT5OrderUseCase
    calculate_order: CalculateMT5OrderUseCase
