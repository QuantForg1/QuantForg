"""MT5 terminal client port — infrastructure implements; domain stays pure.

Connection lifecycle + market-data read APIs. No order execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.domain.entities.mt5 import MT5AccountInfo, MT5Server, MT5Terminal
from app.domain.entities.mt5_market import MT5Rate, MT5SymbolInfo, MT5Tick
from app.domain.entities.mt5_order import TradeRequest
from app.domain.entities.mt5_portfolio import (
    AccountSnapshot,
    MT5Deal,
    MT5HistoryOrder,
    MT5PendingOrder,
    MT5Position,
)
from app.domain.interfaces.broker_adapter import BrokerSymbolInfo
from app.domain.interfaces.mt5_order import (
    MT5MarginResult,
    MT5OrderCheckResult,
    MT5OrderSendResult,
    MT5ProfitResult,
)
from app.domain.market_data.timeframe import Timeframe


@dataclass(frozen=True, slots=True)
class MT5LoginRequest:
    """Credentials for an MT5 login attempt — never log this object."""

    login: int
    password: str
    server: str
    path: str = ""
    timeout_ms: int = 60_000
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MT5HealthSnapshot:
    """Health probe result from the MT5 client."""

    connected: bool
    latency_ms: float | None
    terminal_build: int | None
    server: str
    login_status: str
    last_heartbeat_at: str | None = None
    version: str = ""


class MT5ClientPort(Protocol):
    """Low-level MetaTrader 5 terminal operations."""

    def initialize(self, *, path: str = "") -> bool: ...

    def login(self, request: MT5LoginRequest) -> bool: ...

    def shutdown(self) -> None: ...

    def reconnect(self, request: MT5LoginRequest) -> bool: ...

    def ping(self) -> float: ...

    def terminal_info(self) -> MT5Terminal: ...

    def version(self) -> tuple[int, int, int]: ...

    def account_info(self) -> MT5AccountInfo: ...

    def server_info(self) -> MT5Server: ...

    def symbols(self) -> list[BrokerSymbolInfo]: ...

    def health(self) -> MT5HealthSnapshot: ...

    # -- Market data (Sprint 2) ----------------------------------------------

    def list_symbols(
        self,
        *,
        include_quotes: bool = False,
        codes: list[str] | None = None,
    ) -> list[MT5SymbolInfo]: ...

    def symbol_info(self, symbol: str) -> MT5SymbolInfo: ...

    def symbol_select(self, symbol: str, *, enable: bool = True) -> bool: ...

    def latest_tick(self, symbol: str) -> MT5Tick: ...

    def copy_rates_from(
        self,
        symbol: str,
        timeframe: Timeframe,
        date_from: datetime,
        count: int,
    ) -> list[MT5Rate]: ...

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: Timeframe,
        date_from: datetime,
        date_to: datetime,
    ) -> list[MT5Rate]: ...

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_pos: int,
        count: int,
    ) -> list[MT5Rate]: ...

    # -- Order validation (Sprint 3) — never order_send ---------------------

    def order_check(self, request: TradeRequest) -> MT5OrderCheckResult: ...

    def order_calc_margin(self, request: TradeRequest) -> MT5MarginResult: ...

    def order_calc_profit(
        self,
        request: TradeRequest,
        *,
        close_price: Decimal | None = None,
    ) -> MT5ProfitResult: ...

    def order_send(self, request: TradeRequest) -> MT5OrderSendResult: ...

    # -- Portfolio / positions (read-only sync) ------------------------------

    def list_positions(self) -> list[MT5Position]: ...

    def position_by_ticket(self, ticket: int) -> MT5Position | None: ...

    def position_by_symbol(self, symbol: str) -> list[MT5Position]: ...

    def list_orders(self) -> list[MT5PendingOrder]: ...

    def order_by_ticket(self, ticket: int) -> MT5PendingOrder | None: ...

    def history_orders(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MT5HistoryOrder]: ...

    def history_deals(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MT5Deal]: ...

    def account_snapshot(self) -> AccountSnapshot: ...

    @property
    def is_connected(self) -> bool: ...
