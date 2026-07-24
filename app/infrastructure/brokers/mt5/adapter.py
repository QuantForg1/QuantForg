"""Production MT5 adapter — connection, market data, validation, portfolio, gateway.

Implements ``BrokerAdapterPort`` plus MT5-specific APIs.
``order_send`` only reaches the client when ``execution_enabled=True``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from app.domain.entities.execution_gateway import RETCODE_EXECUTION_DISABLED
from app.domain.entities.mt5 import MT5AccountInfo, MT5Terminal
from app.domain.entities.mt5_market import MT5Rate, MT5SymbolInfo, MT5Tick
from app.domain.entities.mt5_order import TradeRequest
from app.domain.entities.mt5_portfolio import (
    AccountSnapshot,
    MT5Deal,
    MT5HistoryOrder,
    MT5PendingOrder,
    MT5Position,
)
from app.domain.enums.broker import BrokerCapabilityCode
from app.domain.interfaces.broker_adapter import (
    BrokerAccountInfo,
    BrokerBalanceInfo,
    BrokerConnectRequest,
    BrokerOrderInfo,
    BrokerPositionInfo,
    BrokerSymbolInfo,
)
from app.domain.interfaces.mt5_client import (
    MT5ClientPort,
    MT5HealthSnapshot,
    MT5LoginRequest,
)
from app.domain.interfaces.mt5_order import (
    MT5MarginResult,
    MT5OrderCheckResult,
    MT5OrderSendResult,
    MT5ProfitResult,
)
from app.domain.market_data.timeframe import Timeframe
from app.infrastructure.brokers.mt5.client import MockMT5Client


class MT5Adapter:
    """MetaTrader 5 adapter (reads + gated execution)."""

    platform_code: str = "mt5"

    def __init__(
        self,
        client: MT5ClientPort | None = None,
        *,
        execution_enabled: bool = False,
    ) -> None:
        self._client: MT5ClientPort = client or MockMT5Client()
        self._sessions: dict[str, MT5LoginRequest] = {}
        # Single live binding: process-global MT5 client holds one login at a time.
        self._live_session_ref: str | None = None
        self._execution_enabled = bool(execution_enabled)

    @property
    def execution_enabled(self) -> bool:
        return self._execution_enabled

    def set_execution_enabled(self, enabled: bool) -> None:
        """Test/runtime toggle — production default remains False."""
        self._execution_enabled = bool(enabled)

    @property
    def client(self) -> MT5ClientPort:
        return self._client

    def _mt5_failure_message(self, prefix: str) -> str:
        """Preserve gateway upstream detail so HTTP 503s are not generic."""
        detail_parts: list[str] = []
        last_fn = getattr(self._client, "last_upstream", None)
        if callable(last_fn):
            upstream = last_fn() or {}
            for key in (
                "diagnostic",
                "error",
                "status_code",
                "body_preview",
                "path",
            ):
                value = upstream.get(key)
                if value not in (None, "", {}):
                    detail_parts.append(f"{key}={value}")
        if not detail_parts:
            return prefix
        return f"{prefix}: {'; '.join(detail_parts)}"

    def discover_capabilities(self) -> list[BrokerCapabilityCode]:
        return [
            BrokerCapabilityCode.CONNECT,
            BrokerCapabilityCode.DISCONNECT,
            BrokerCapabilityCode.VALIDATE,
            BrokerCapabilityCode.REFRESH,
            BrokerCapabilityCode.ACCOUNT_INFO,
            BrokerCapabilityCode.SYMBOLS,
            BrokerCapabilityCode.BALANCES,
            BrokerCapabilityCode.MARKET_DATA,
            BrokerCapabilityCode.HISTORY,
            BrokerCapabilityCode.POSITIONS,
            BrokerCapabilityCode.ORDERS,
        ]

    # -- Connection lifecycle (MT5-specific) ---------------------------------

    def initialize(self, *, path: str = "") -> bool:
        return self._client.initialize(path=path)

    def login(self, request: MT5LoginRequest) -> str:
        if not self._client.login(request):
            raise RuntimeError(self._mt5_failure_message("MT5 login failed"))
        session_ref = getattr(self._client, "session_token", "") or (
            f"mt5-{uuid.uuid4().hex}"
        )
        # When credentials live only on the Windows gateway, keep a redacted
        # login record on Railway (never store broker passwords here).
        if getattr(self._client, "stores_credentials_remotely", False):
            stored = MT5LoginRequest(
                login=request.login,
                password="",
                server=request.server,
                path=request.path,
            )
        else:
            stored = request
        self._sessions[session_ref] = stored
        self._live_session_ref = session_ref
        return session_ref

    def attach(self, *, path: str = "") -> str:
        """Bind to an already logged-in terminal session (gateway clients only)."""
        attach_fn = getattr(self._client, "attach", None)
        if attach_fn is None:
            raise RuntimeError("MT5 attach is not supported by this client")
        if not attach_fn(path=path):
            raise RuntimeError(self._mt5_failure_message("MT5 attach failed"))
        session_ref = getattr(self._client, "session_token", "") or (
            f"mt5-{uuid.uuid4().hex}"
        )
        login = int(getattr(self._client, "_login", 0) or 0)
        server = str(getattr(self._client, "_server", "") or "")
        self._sessions[session_ref] = MT5LoginRequest(
            login=login or 1,
            password="",
            server=server or "attached",
            path=path,
        )
        self._live_session_ref = session_ref
        return session_ref

    def is_live_session(self, session_ref: str) -> bool:
        """True if ``session_ref`` is bound to the live terminal login."""
        return (
            bool(session_ref)
            and session_ref == self._live_session_ref
            and bool(getattr(self._client, "is_connected", False))
        )

    def shutdown(self) -> None:
        self._client.shutdown()
        self._sessions.clear()
        self._live_session_ref = None

    def reconnect(self, request: MT5LoginRequest) -> str:
        if not self._client.reconnect(request):
            msg = "MT5 reconnect failed"
            raise RuntimeError(msg)
        self._sessions.clear()
        session_ref = getattr(self._client, "session_token", "") or (
            f"mt5-{uuid.uuid4().hex}"
        )
        if getattr(self._client, "stores_credentials_remotely", False):
            stored = MT5LoginRequest(
                login=request.login,
                password="",
                server=request.server,
                path=request.path,
            )
        else:
            stored = request
        self._sessions[session_ref] = stored
        self._live_session_ref = session_ref
        return session_ref

    def ping(self) -> float:
        return self._client.ping()

    def terminal_info(self) -> MT5Terminal:
        return self._client.terminal_info()

    def version(self) -> tuple[int, int, int]:
        return self._client.version()

    def account_info(self) -> MT5AccountInfo:
        return self._client.account_info()

    def symbols(self) -> list[BrokerSymbolInfo]:
        return self._client.symbols()

    def health(self) -> MT5HealthSnapshot:
        return self._client.health()

    # -- Market data (Sprint 2) ----------------------------------------------

    def list_symbols(
        self,
        *,
        include_quotes: bool = False,
        codes: list[str] | None = None,
    ) -> list[MT5SymbolInfo]:
        return self._client.list_symbols(
            include_quotes=include_quotes,
            codes=codes,
        )

    def symbol_info(self, symbol: str) -> MT5SymbolInfo:
        return self._client.symbol_info(symbol)

    def symbol_select(self, symbol: str, *, enable: bool = True) -> bool:
        return self._client.symbol_select(symbol, enable=enable)

    def latest_tick(self, symbol: str) -> MT5Tick:
        return self._client.latest_tick(symbol)

    def copy_rates_from(
        self,
        symbol: str,
        timeframe: Timeframe,
        date_from: datetime,
        count: int,
    ) -> list[MT5Rate]:
        return self._client.copy_rates_from(symbol, timeframe, date_from, count)

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: Timeframe,
        date_from: datetime,
        date_to: datetime,
    ) -> list[MT5Rate]:
        return self._client.copy_rates_range(symbol, timeframe, date_from, date_to)

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_pos: int,
        count: int,
    ) -> list[MT5Rate]:
        return self._client.copy_rates_from_pos(symbol, timeframe, start_pos, count)

    # -- Order validation (Sprint 3) — never order_send ----------------------

    def order_check(self, request: TradeRequest) -> MT5OrderCheckResult:
        return self._client.order_check(request)

    def order_calc_margin(self, request: TradeRequest) -> MT5MarginResult:
        return self._client.order_calc_margin(request)

    def order_calc_profit(
        self,
        request: TradeRequest,
        *,
        close_price: Decimal | None = None,
    ) -> MT5ProfitResult:
        return self._client.order_calc_profit(request, close_price=close_price)

    def order_send(self, request: TradeRequest) -> MT5OrderSendResult:
        """Send only when ``execution_enabled`` is True; otherwise never call client."""
        if not self._execution_enabled:
            return MT5OrderSendResult(
                retcode=RETCODE_EXECUTION_DISABLED,
                comment="execution disabled",
                request=request,
                volume=request.volume,
                price=request.price,
            )
        return self._client.order_send(request)

    def order_cancel(self, ticket: int) -> MT5OrderSendResult:
        """Cancel a pending order — gated by the same execution flag."""
        if not self._execution_enabled:
            return MT5OrderSendResult(
                retcode=RETCODE_EXECUTION_DISABLED,
                comment="execution disabled",
                order_ticket=ticket,
            )
        cancel = getattr(self._client, "order_cancel", None)
        if cancel is None:
            return MT5OrderSendResult(
                retcode=RETCODE_EXECUTION_DISABLED,
                comment="cancel not supported by client",
                order_ticket=ticket,
            )
        return cancel(ticket)  # type: ignore[no-any-return]

    # -- Portfolio / positions (read-only sync) ------------------------------

    def list_positions(self) -> list[MT5Position]:
        return self._client.list_positions()

    def force_refresh_positions(self) -> list[MT5Position]:
        """Bypass client cache and re-query live MT5 positions."""
        client = self._client
        invalidate = getattr(client, "invalidate_positions_cache", None)
        if callable(invalidate):
            invalidate()
        else:
            clear = getattr(client, "_clear_data_caches", None)
            if callable(clear):
                clear()
        return self.list_positions()

    def position_by_ticket(self, ticket: int) -> MT5Position | None:
        return self._client.position_by_ticket(ticket)

    def position_by_symbol(self, symbol: str) -> list[MT5Position]:
        return self._client.position_by_symbol(symbol)

    def list_orders(self) -> list[MT5PendingOrder]:
        return self._client.list_orders()

    def order_by_ticket(self, ticket: int) -> MT5PendingOrder | None:
        return self._client.order_by_ticket(ticket)

    def history_orders(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MT5HistoryOrder]:
        return self._client.history_orders(date_from=date_from, date_to=date_to)

    def history_deals(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MT5Deal]:
        return self._client.history_deals(date_from=date_from, date_to=date_to)

    def account_snapshot(self) -> AccountSnapshot:
        return self._client.account_snapshot()

    # -- BrokerAdapterPort ---------------------------------------------------

    async def connect(self, request: BrokerConnectRequest) -> str:
        login = self._parse_login(request)
        path = request.extra.get("path", "") or request.extra.get("terminal_path", "")
        login_req = MT5LoginRequest(
            login=login,
            password=request.password,
            server=request.server,
            path=path,
        )
        if not self.initialize(path=path):
            msg = "MT5 initialize failed"
            raise RuntimeError(msg)
        return self.login(login_req)

    async def disconnect(self, *, session_ref: str) -> None:
        self._sessions.pop(session_ref, None)
        if session_ref == self._live_session_ref:
            # Only tear down the terminal when the live tenant disconnects.
            self.shutdown()
        elif not self._sessions and self._live_session_ref is None:
            self.shutdown()

    async def validate_credentials(self, request: BrokerConnectRequest) -> bool:
        login = self._parse_login(request)
        path = request.extra.get("path", "") or request.extra.get("terminal_path", "")
        login_req = MT5LoginRequest(
            login=login,
            password=request.password,
            server=request.server,
            path=path,
        )
        # Disposable probe — never leave validate() connected.
        probe = MockMT5Client(
            fail_initialize=getattr(self._client, "fail_initialize", False),
            fail_login=getattr(self._client, "fail_login", False),
        )
        try:
            ok = probe.initialize(path=path) and probe.login(login_req)
        except (OSError, RuntimeError, ValueError):
            return False
        finally:
            probe.shutdown()
        return bool(ok)

    async def refresh_session(self, *, session_ref: str) -> str:
        request = self._sessions.get(session_ref)
        if request is None:
            msg = f"Unknown MT5 session: {session_ref}"
            raise ValueError(msg)
        return self.reconnect(request)

    async def list_accounts(self, *, session_ref: str) -> list[BrokerAccountInfo]:
        self._require_session(session_ref)
        return [await self.get_account_info(session_ref=session_ref)]

    async def get_account_info(self, *, session_ref: str) -> BrokerAccountInfo:
        self._require_session(session_ref)
        info = self._client.account_info()
        return BrokerAccountInfo(
            external_account_id=str(info.login),
            currency=info.currency,
            leverage=info.leverage,
            name=info.name,
            server=info.server,
            environment=info.trade_mode or "demo",
            raw={"company": info.company},
        )

    async def get_balance(self, *, session_ref: str) -> BrokerBalanceInfo:
        self._require_session(session_ref)
        snap = self._client.account_snapshot()
        return BrokerBalanceInfo(
            currency=snap.currency,
            balance=snap.balance,
            equity=snap.equity,
            margin=snap.margin,
            free_margin=snap.free_margin,
        )

    async def get_equity(self, *, session_ref: str) -> Decimal:
        self._require_session(session_ref)
        return self._client.account_snapshot().equity

    async def get_symbols(self, *, session_ref: str) -> list[BrokerSymbolInfo]:
        self._require_session(session_ref)
        return self._client.symbols()

    async def get_positions(self, *, session_ref: str) -> list[BrokerPositionInfo]:
        self._require_session(session_ref)
        return [
            BrokerPositionInfo(
                ticket=str(p.ticket),
                symbol=p.symbol,
                side=p.side,
                volume=p.volume,
                open_price=p.open_price,
                profit=p.profit,
                raw={"comment": p.comment, "magic": str(p.magic)},
            )
            for p in self._client.list_positions()
        ]

    async def get_orders(self, *, session_ref: str) -> list[BrokerOrderInfo]:
        self._require_session(session_ref)
        return [
            BrokerOrderInfo(
                ticket=str(o.ticket),
                symbol=o.symbol,
                side=o.side,
                order_type=o.order_type,
                volume=o.volume,
                price=o.price,
                status="pending",
                raw={"comment": o.comment, "magic": str(o.magic)},
            )
            for o in self._client.list_orders()
        ]

    def _require_session(self, session_ref: str) -> None:
        if not self.is_live_session(session_ref):
            msg = f"Unknown or inactive MT5 session: {session_ref}"
            raise ValueError(msg)

    @staticmethod
    def _parse_login(request: BrokerConnectRequest) -> int:
        raw = request.external_account_id.strip()
        try:
            login = int(raw)
        except ValueError as exc:
            msg = "MT5 external_account_id must be a numeric login"
            raise ValueError(msg) from exc
        if login <= 0:
            msg = "MT5 login must be > 0"
            raise ValueError(msg)
        return login
