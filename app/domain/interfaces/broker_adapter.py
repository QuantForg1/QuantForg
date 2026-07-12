"""Broker adapter port — future multi-broker integration contract.

Adapters (MT5, MT4, cTrader, DXtrade, …) implement this protocol.
The Broker Foundation defines the contract only — no live adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class BrokerAccountInfo:
    """Normalized account snapshot returned by an adapter."""

    external_account_id: str
    currency: str
    leverage: int
    name: str = ""
    server: str = ""
    environment: str = "demo"
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BrokerSymbolInfo:
    """Normalized tradable symbol metadata."""

    code: str
    description: str = ""
    digits: int = 5
    contract_size: Decimal = Decimal("1")
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BrokerBalanceInfo:
    """Normalized balance / equity snapshot."""

    currency: str
    balance: Decimal
    equity: Decimal
    margin: Decimal = Decimal("0")
    free_margin: Decimal = Decimal("0")
    as_of: datetime | None = None


@dataclass(frozen=True, slots=True)
class BrokerPositionInfo:
    """Normalized open position snapshot (read-only foundation view)."""

    ticket: str
    symbol: str
    side: str
    volume: Decimal
    open_price: Decimal
    profit: Decimal = Decimal("0")
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BrokerOrderInfo:
    """Normalized order snapshot (read-only foundation view)."""

    ticket: str
    symbol: str
    side: str
    order_type: str
    volume: Decimal
    price: Decimal | None = None
    status: str = ""
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BrokerConnectRequest:
    """Opaque connection parameters passed to an adapter.

    Secrets must already be decrypted by the application layer and must
    never be logged.
    """

    broker_account_id: UUID
    external_account_id: str
    server: str
    password: str = ""
    api_key: str = ""
    api_secret: str = ""
    token: str = ""
    extra: dict[str, str] = field(default_factory=dict)


class BrokerAdapterPort(Protocol):
    """Port implemented by concrete broker adapters.

    Method contracts are intentional and stable. Foundation ships **no**
    live implementations — placeholders raise ``NotImplementedError``.
    """

    @property
    def platform_code(self) -> str:
        """Platform identifier matching :class:`BrokerPlatform` values."""
        ...

    async def connect(self, request: BrokerConnectRequest) -> str:
        """Establish a session; return an opaque adapter session reference."""
        ...

    async def disconnect(self, *, session_ref: str) -> None:
        """Tear down an adapter session."""
        ...

    async def validate_credentials(self, request: BrokerConnectRequest) -> bool:
        """Validate credentials / reachability without retaining a session."""
        ...

    async def refresh_session(self, *, session_ref: str) -> str:
        """Refresh a session; return the (possibly new) session reference."""
        ...

    async def list_accounts(self, *, session_ref: str) -> list[BrokerAccountInfo]:
        """List accounts visible to the connected session."""
        ...

    async def get_account_info(self, *, session_ref: str) -> BrokerAccountInfo:
        """Fetch account metadata for the connected session."""
        ...

    async def get_balance(self, *, session_ref: str) -> BrokerBalanceInfo:
        """Fetch balance snapshot (includes equity when available)."""
        ...

    async def get_equity(self, *, session_ref: str) -> Decimal:
        """Fetch equity only."""
        ...

    async def get_symbols(self, *, session_ref: str) -> list[BrokerSymbolInfo]:
        """List symbols available on the connected account."""
        ...

    async def get_positions(self, *, session_ref: str) -> list[BrokerPositionInfo]:
        """List open positions (read-only)."""
        ...

    async def get_orders(self, *, session_ref: str) -> list[BrokerOrderInfo]:
        """List working / recent orders (read-only)."""
        ...
