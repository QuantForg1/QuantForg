"""Application DTOs for MT5 connection layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.entities.mt5 import MT5AccountInfo, MT5Connection
from app.domain.entities.mt5_market import MT5Rate, MT5SymbolInfo, MT5Tick
from app.domain.entities.mt5_order import TradeValidation
from app.domain.interfaces.broker_adapter import BrokerSymbolInfo


@dataclass(frozen=True, slots=True)
class MT5ConnectCommand:
    user_id: UUID
    login: int
    password: str
    server: str
    path: str = ""
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class MT5DisconnectCommand:
    user_id: UUID
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class MT5StatusDTO:
    connected: bool
    status: str
    latency_ms: float | None
    terminal_build: int | None
    terminal_version: str
    server: str
    login: int | None
    login_status: str
    last_heartbeat_at: datetime | None
    last_error: str = ""
    session_ref: str = ""

    @classmethod
    def from_connection(cls, connection: MT5Connection | None) -> MT5StatusDTO:
        if connection is None:
            return cls(
                connected=False,
                status="disconnected",
                latency_ms=None,
                terminal_build=None,
                terminal_version="",
                server="",
                login=None,
                login_status="logged_out",
                last_heartbeat_at=None,
            )
        return cls(
            connected=connection.connected,
            status=connection.status.value,
            latency_ms=connection.latency_ms,
            terminal_build=connection.terminal_build,
            terminal_version=connection.terminal_version,
            server=connection.server,
            login=connection.login,
            login_status=connection.login_status,
            last_heartbeat_at=connection.last_heartbeat_at,
            last_error=connection.last_error,
            session_ref=connection.session_ref,
        )


@dataclass(frozen=True, slots=True)
class MT5AccountDTO:
    login: int
    name: str
    server: str
    currency: str
    leverage: int
    balance: str
    equity: str
    margin: str = "0"
    free_margin: str = "0"
    margin_level: str = "0"
    company: str = ""
    trade_mode: str = ""

    @classmethod
    def from_entity(cls, info: MT5AccountInfo) -> MT5AccountDTO:
        return cls(
            login=info.login,
            name=info.name,
            server=info.server,
            currency=info.currency,
            leverage=info.leverage,
            balance=str(info.balance),
            equity=str(info.equity),
            margin=str(info.margin),
            free_margin=str(info.free_margin),
            margin_level=str(info.margin_level),
            company=info.company,
            trade_mode=info.trade_mode,
        )


@dataclass(frozen=True, slots=True)
class MT5SymbolDTO:
    code: str
    description: str
    digits: int
    contract_size: str
    point: str = "0.00001"
    selected: bool = False
    trade_mode: str = ""
    currency_base: str = ""
    currency_profit: str = ""
    bid: str | None = None
    ask: str | None = None

    @classmethod
    def from_broker_symbol(cls, symbol: BrokerSymbolInfo) -> MT5SymbolDTO:
        return cls(
            code=symbol.code,
            description=symbol.description,
            digits=symbol.digits,
            contract_size=str(symbol.contract_size),
        )

    @classmethod
    def from_symbol_info(cls, info: MT5SymbolInfo) -> MT5SymbolDTO:
        return cls(
            code=info.code,
            description=info.description,
            digits=info.digits,
            contract_size=str(info.contract_size),
            point=str(info.point),
            selected=info.selected,
            trade_mode=info.trade_mode,
            currency_base=info.currency_base,
            currency_profit=info.currency_profit,
            bid=str(info.bid) if info.bid is not None else None,
            ask=str(info.ask) if info.ask is not None else None,
        )


@dataclass(frozen=True, slots=True)
class MT5SymbolsPageDTO:
    items: list[MT5SymbolDTO]
    total: int
    offset: int
    limit: int
    has_more: bool


@dataclass(frozen=True, slots=True)
class MT5TickDTO:
    symbol: str
    bid: str
    ask: str
    spread: str
    timestamp: datetime
    volume: str = "0"

    @classmethod
    def from_tick(cls, tick: MT5Tick) -> MT5TickDTO:
        return cls(
            symbol=tick.symbol,
            bid=str(tick.bid),
            ask=str(tick.ask),
            spread=str(tick.spread),
            timestamp=tick.timestamp,
            volume=str(tick.volume),
        )


@dataclass(frozen=True, slots=True)
class MT5CandleDTO:
    symbol: str
    timeframe: str
    open_time: datetime
    open: str
    high: str
    low: str
    close: str
    tick_volume: int = 0
    spread_points: int = 0

    @classmethod
    def from_rate(cls, rate: MT5Rate) -> MT5CandleDTO:
        return cls(
            symbol=rate.symbol,
            timeframe=rate.timeframe.value,
            open_time=rate.open_time,
            open=str(rate.open),
            high=str(rate.high),
            low=str(rate.low),
            close=str(rate.close),
            tick_volume=rate.tick_volume,
            spread_points=rate.spread_points,
        )


@dataclass(frozen=True, slots=True)
class MT5ConnectionDTO:
    id: UUID
    user_id: UUID
    login: int
    server: str
    status: str
    connected: bool
    terminal_build: int | None
    terminal_version: str
    latency_ms: float | None
    last_heartbeat_at: datetime | None
    login_status: str
    session_ref: str
    history: tuple[dict[str, object], ...] = field(default_factory=tuple)

    @classmethod
    def from_entity(cls, connection: MT5Connection) -> MT5ConnectionDTO:
        return cls(
            id=connection.id,
            user_id=connection.user_id,
            login=connection.login,
            server=connection.server,
            status=connection.status.value,
            connected=connection.connected,
            terminal_build=connection.terminal_build,
            terminal_version=connection.terminal_version,
            latency_ms=connection.latency_ms,
            last_heartbeat_at=connection.last_heartbeat_at,
            login_status=connection.login_status,
            session_ref=connection.session_ref,
            history=tuple(connection.history[-20:]),
        )


@dataclass(frozen=True, slots=True)
class MT5OrderValidateCommand:
    user_id: UUID
    symbol: str
    side: str
    order_type: str = "market"
    volume: str = "0.01"
    price: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    slippage: int = 10
    magic: int = 0
    comment: str = ""
    request_id: str | None = None
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class MT5OrderValidationDTO:
    id: UUID
    symbol: str
    side: str
    order_type: str
    volume: str
    valid: bool
    retcode: int
    expected_margin: str
    estimated_profit: str
    messages: tuple[str, ...]
    checks: dict[str, bool]
    request_snapshot: dict[str, object]
    validated_at: datetime

    @classmethod
    def from_entity(cls, entity: TradeValidation) -> MT5OrderValidationDTO:
        return cls(
            id=entity.id,
            symbol=entity.symbol,
            side=entity.side,
            order_type=entity.order_type,
            volume=str(entity.volume),
            valid=entity.valid,
            retcode=entity.retcode,
            expected_margin=str(entity.expected_margin),
            estimated_profit=str(entity.estimated_profit),
            messages=tuple(entity.messages),
            checks=dict(entity.checks),
            request_snapshot=dict(entity.request_snapshot),
            validated_at=entity.validated_at,
        )


@dataclass(frozen=True, slots=True)
class MT5OrderCalculateDTO:
    symbol: str
    side: str
    order_type: str
    volume: str
    price: str
    expected_margin: str
    estimated_profit: str
    retcode: int
    messages: tuple[str, ...]
    request_snapshot: dict[str, object]
