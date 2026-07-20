"""Mock MT5 terminal client — no real MetaTrader 5 required.

Used in CI, local development, and as the default runtime client when
the Windows MetaTrader5 package is unavailable.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import TypedDict

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
from app.domain.interfaces.mt5_client import MT5HealthSnapshot, MT5LoginRequest
from app.domain.interfaces.mt5_order import (
    RETCODE_DONE,
    RETCODE_INVALID,
    RETCODE_INVALID_STOPS,
    RETCODE_INVALID_VOLUME,
    RETCODE_NO_MONEY,
    MT5MarginResult,
    MT5OrderCheckResult,
    MT5OrderSendResult,
    MT5ProfitResult,
)
from app.domain.market_data.timeframe import Timeframe


class _SymbolMeta(TypedDict):
    description: str
    digits: int
    point: Decimal
    contract_size: Decimal
    base: str
    profit: str
    bid: Decimal
    ask: Decimal


_MOCK_CATALOGUE: dict[str, _SymbolMeta] = {
    "EURUSD": {
        "description": "Euro vs US Dollar",
        "digits": 5,
        "point": Decimal("0.00001"),
        "contract_size": Decimal("100000"),
        "base": "EUR",
        "profit": "USD",
        "bid": Decimal("1.08500"),
        "ask": Decimal("1.08520"),
    },
    "GBPUSD": {
        "description": "Great Britain Pound vs US Dollar",
        "digits": 5,
        "point": Decimal("0.00001"),
        "contract_size": Decimal("100000"),
        "base": "GBP",
        "profit": "USD",
        "bid": Decimal("1.26500"),
        "ask": Decimal("1.26530"),
    },
    "XAUUSD": {
        "description": "Gold vs US Dollar",
        "digits": 2,
        "point": Decimal("0.01"),
        "contract_size": Decimal("100"),
        "base": "XAU",
        "profit": "USD",
        "bid": Decimal("2320.50"),
        "ask": Decimal("2320.80"),
    },
}


@dataclass
class MockMT5Client:
    """In-process fake of the MetaTrader 5 Python API surface."""

    default_build: int = 3815
    default_version: tuple[int, int, int] = (5, 0, 3815)
    simulated_latency_ms: float = 4.5
    fail_initialize: bool = False
    fail_login: bool = False
    force_send_retcode: int | None = None  # test hook for failure/retry mapping
    _initialized: bool = field(default=False, init=False)
    _connected: bool = field(default=False, init=False)
    _login: int = field(default=0, init=False)
    _server: str = field(default="", init=False)
    _path: str = field(default="", init=False)
    _last_heartbeat: datetime | None = field(default=None, init=False)
    _session_token: str = field(default="", init=False)
    _selected: set[str] = field(default_factory=set, init=False)
    _positions: list[MT5Position] = field(default_factory=list, init=False)
    _pending_orders: list[MT5PendingOrder] = field(default_factory=list, init=False)
    _history_orders: list[MT5HistoryOrder] = field(default_factory=list, init=False)
    _history_deals: list[MT5Deal] = field(default_factory=list, init=False)
    _next_order_ticket: int = field(default=500000, init=False)

    def initialize(self, *, path: str = "") -> bool:
        if self.fail_initialize:
            return False
        self._path = path.strip()
        self._initialized = True
        self._connected = False
        return True

    def login(self, request: MT5LoginRequest) -> bool:
        if not self._initialized and not self.initialize(path=request.path):
            return False
        if self.fail_login:
            return False
        if request.login <= 0 or not request.password or not request.server.strip():
            return False
        self._login = request.login
        self._server = request.server.strip()
        if request.path:
            self._path = request.path.strip()
        self._connected = True
        self._session_token = f"mock-mt5-{uuid.uuid4().hex[:12]}"
        self._last_heartbeat = datetime.now(UTC)
        # Default Market Watch selection
        self._selected = {"EURUSD", "GBPUSD"}
        self._seed_portfolio()
        return True

    def shutdown(self) -> None:
        self._connected = False
        self._initialized = False
        self._session_token = ""
        self._login = 0
        self._selected.clear()
        self._positions.clear()
        self._pending_orders.clear()
        self._history_orders.clear()
        self._history_deals.clear()

    def reconnect(self, request: MT5LoginRequest) -> bool:
        self.shutdown()
        if not self.initialize(path=request.path or self._path):
            return False
        return self.login(request)

    def ping(self) -> float:
        self._require_connected()
        time.sleep(0)
        self._last_heartbeat = datetime.now(UTC)
        return float(self.simulated_latency_ms)

    def terminal_info(self) -> MT5Terminal:
        return MT5Terminal(
            build=self.default_build,
            name="MetaTrader 5 (Mock)",
            path=self._path,
            company="QuantForg Mock",
            language="en",
            connected=self._connected,
        )

    def version(self) -> tuple[int, int, int]:
        return self.default_version

    def account_info(self) -> MT5AccountInfo:
        self._require_connected()
        snap = self.account_snapshot()
        return MT5AccountInfo(
            login=self._login,
            name=f"Mock Account {self._login}",
            server=self._server,
            currency=snap.currency,
            leverage=snap.leverage,
            balance=snap.balance,
            equity=snap.equity,
            margin=snap.margin,
            free_margin=snap.free_margin,
            margin_level=snap.margin_level,
            profit=snap.profit,
            company="QuantForg Mock Broker",
            trade_mode="demo",
        )

    def server_info(self) -> MT5Server:
        return MT5Server(
            name=self._server or "Mock-Server",
            company="QuantForg Mock Broker",
            trade_mode="demo",
        )

    def symbols(self) -> list[BrokerSymbolInfo]:
        self._require_connected()
        return [
            BrokerSymbolInfo(
                code=code,
                description=meta["description"],
                digits=meta["digits"],
                contract_size=meta["contract_size"],
            )
            for code, meta in _MOCK_CATALOGUE.items()
        ]

    def health(self) -> MT5HealthSnapshot:
        latency: float | None = None
        if self._connected:
            latency = self.ping()
        major, minor, build = self.version()
        return MT5HealthSnapshot(
            connected=self._connected,
            latency_ms=latency,
            terminal_build=build,
            server=self._server,
            login_status="logged_in" if self._connected else "logged_out",
            last_heartbeat_at=(
                self._last_heartbeat.isoformat() if self._last_heartbeat else None
            ),
            version=f"{major}.{minor}.{build}",
        )

    # -- Market data ---------------------------------------------------------

    def list_symbols(
        self,
        *,
        include_quotes: bool = True,
        codes: list[str] | None = None,
    ) -> list[MT5SymbolInfo]:
        self._require_connected()
        wanted = (
            {c.strip().upper() for c in codes if c and c.strip()} if codes else None
        )
        out: list[MT5SymbolInfo] = []
        for code in _MOCK_CATALOGUE:
            if wanted is not None and code not in wanted:
                continue
            info = self.symbol_info(code)
            if not include_quotes:
                info = MT5SymbolInfo(
                    code=info.code,
                    description=info.description,
                    digits=info.digits,
                    point=info.point,
                    contract_size=info.contract_size,
                    selected=info.selected,
                    trade_mode=info.trade_mode,
                    currency_base=info.currency_base,
                    currency_profit=info.currency_profit,
                    bid=Decimal("0"),
                    ask=Decimal("0"),
                )
            out.append(info)
        return out

    def symbol_info(self, symbol: str) -> MT5SymbolInfo:
        self._require_connected()
        code = symbol.strip().upper()
        meta = _MOCK_CATALOGUE.get(code)
        if meta is None:
            msg = f"Unknown symbol: {symbol}"
            raise ValueError(msg)
        return MT5SymbolInfo(
            code=code,
            description=meta["description"],
            digits=meta["digits"],
            point=meta["point"],
            contract_size=meta["contract_size"],
            selected=code in self._selected,
            trade_mode="full",
            currency_base=meta["base"],
            currency_profit=meta["profit"],
            bid=meta["bid"],
            ask=meta["ask"],
            volume_min=Decimal("0.01"),
            volume_max=Decimal("100"),
            volume_step=Decimal("0.01"),
            stops_level=0 if code != "XAUUSD" else 50,
            freeze_level=0,
            filling_mode=2,  # IOC
            execution_mode="market",
            margin_calc_mode="cfd",
            visible=True,
            market_open=True,
            trade_allowed=True,
        )

    def symbol_select(self, symbol: str, *, enable: bool = True) -> bool:
        self._require_connected()
        code = symbol.strip().upper()
        if code not in _MOCK_CATALOGUE:
            return False
        if enable:
            self._selected.add(code)
        else:
            self._selected.discard(code)
        return True

    def latest_tick(self, symbol: str) -> MT5Tick:
        self._require_connected()
        info = self.symbol_info(symbol)
        assert info.bid is not None and info.ask is not None
        return MT5Tick(
            symbol=info.code,
            bid=info.bid,
            ask=info.ask,
            timestamp=datetime.now(UTC),
            volume=Decimal("1"),
        )

    def copy_rates_from(
        self,
        symbol: str,
        timeframe: Timeframe,
        date_from: datetime,
        count: int,
    ) -> list[MT5Rate]:
        self._require_connected()
        if count < 1:
            return []
        self.symbol_info(symbol)  # validate
        start = date_from if date_from.tzinfo else date_from.replace(tzinfo=UTC)
        return self._generate_rates(
            symbol=symbol.strip().upper(),
            timeframe=timeframe,
            start=start,
            count=count,
        )

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: Timeframe,
        date_from: datetime,
        date_to: datetime,
    ) -> list[MT5Rate]:
        self._require_connected()
        self.symbol_info(symbol)
        start = date_from if date_from.tzinfo else date_from.replace(tzinfo=UTC)
        end = date_to if date_to.tzinfo else date_to.replace(tzinfo=UTC)
        if end <= start:
            return []
        step = timeframe.duration
        count = max(1, int((end - start) / step))
        count = min(count, 5000)
        rates = self._generate_rates(
            symbol=symbol.strip().upper(),
            timeframe=timeframe,
            start=start,
            count=count,
        )
        return [r for r in rates if r.open_time <= end]

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_pos: int,
        count: int,
    ) -> list[MT5Rate]:
        self._require_connected()
        if count < 1 or start_pos < 0:
            return []
        self.symbol_info(symbol)
        # Position 0 = most recent bar
        now = datetime.now(UTC)
        newest_open = now - timeframe.duration
        start = newest_open - (timeframe.duration * (start_pos + count - 1))
        rates = self._generate_rates(
            symbol=symbol.strip().upper(),
            timeframe=timeframe,
            start=start,
            count=start_pos + count,
        )
        # Return the window ending at start_pos from the end
        if start_pos == 0:
            return rates[-count:]
        end_idx = len(rates) - start_pos
        begin_idx = max(0, end_idx - count)
        return rates[begin_idx:end_idx]

    def _generate_rates(
        self,
        *,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        count: int,
    ) -> list[MT5Rate]:
        meta = _MOCK_CATALOGUE[symbol]
        base = meta["bid"]
        point = meta["point"]
        rates: list[MT5Rate] = []
        cursor = start
        for i in range(count):
            drift = point * Decimal(i % 7)
            open_px = base + drift
            high_px = open_px + point * Decimal("5")
            low_px = open_px - point * Decimal("3")
            close_px = open_px + point * Decimal((i % 3) - 1)
            rates.append(
                MT5Rate(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=cursor,
                    open=open_px,
                    high=high_px,
                    low=low_px,
                    close=close_px,
                    tick_volume=100 + i,
                    spread_points=2,
                )
            )
            cursor = cursor + timeframe.duration
        return rates

    # -- Order validation (Sprint 3) — never order_send ----------------------

    def order_check(self, request: TradeRequest) -> MT5OrderCheckResult:
        self._require_connected()
        account = self.account_info()
        margin_res = self.order_calc_margin(request)
        profit_res = self.order_calc_profit(request)

        retcode = RETCODE_DONE
        comment = "done"
        code = request.symbol.strip().upper()
        if code not in _MOCK_CATALOGUE:
            retcode = RETCODE_INVALID
            comment = "invalid symbol"
        elif request.volume <= 0:
            retcode = RETCODE_INVALID_VOLUME
            comment = "invalid volume"
        elif margin_res.margin > account.equity:
            retcode = RETCODE_NO_MONEY
            comment = "not enough money"
        elif request.stop_loss < 0 or request.take_profit < 0:
            retcode = RETCODE_INVALID_STOPS
            comment = "invalid stops"

        free = account.equity - margin_res.margin
        return MT5OrderCheckResult(
            retcode=retcode,
            comment=comment,
            request=request,
            balance=account.balance,
            equity=account.equity,
            margin=margin_res.margin,
            margin_free=max(Decimal("0"), free),
            profit=profit_res.profit,
        )

    def order_calc_margin(self, request: TradeRequest) -> MT5MarginResult:
        self._require_connected()
        code = request.symbol.strip().upper()
        if code not in _MOCK_CATALOGUE:
            return MT5MarginResult(
                margin=Decimal("0"),
                retcode=RETCODE_INVALID,
                comment="invalid symbol",
            )
        meta = _MOCK_CATALOGUE[code]
        # Simplified: margin ≈ volume * contract_size * price * 0.01
        price = request.price if request.price > 0 else meta["bid"]
        margin = (
            request.volume * meta["contract_size"] * price * Decimal("0.01")
        ).quantize(Decimal("0.01"))
        return MT5MarginResult(margin=margin, retcode=RETCODE_DONE, comment="done")

    def order_calc_profit(
        self,
        request: TradeRequest,
        *,
        close_price: Decimal | None = None,
    ) -> MT5ProfitResult:
        self._require_connected()
        code = request.symbol.strip().upper()
        if code not in _MOCK_CATALOGUE:
            return MT5ProfitResult(
                profit=Decimal("0"),
                retcode=RETCODE_INVALID,
                comment="invalid symbol",
            )
        meta = _MOCK_CATALOGUE[code]
        entry = request.price if request.price > 0 else meta["ask"]
        if close_price is None:
            # Estimate against opposite side of the spread
            exit_px = meta["bid"] if "buy" in request.action else meta["ask"]
        else:
            exit_px = close_price
        direction = Decimal("1") if "buy" in request.action else Decimal("-1")
        profit = (
            direction * (exit_px - entry) * request.volume * meta["contract_size"]
        ).quantize(Decimal("0.01"))
        return MT5ProfitResult(profit=profit, retcode=RETCODE_DONE, comment="done")

    def order_send(self, request: TradeRequest) -> MT5OrderSendResult:
        """Mock broker send — only invoked when Execution Gateway flag is on."""
        self._require_connected()
        if self.force_send_retcode is not None:
            return MT5OrderSendResult(
                retcode=self.force_send_retcode,
                comment=f"forced retcode {self.force_send_retcode}",
                request=request,
                volume=request.volume,
                price=request.price,
            )
        check = self.order_check(request)
        if not check.ok:
            return MT5OrderSendResult(
                retcode=check.retcode,
                comment=check.comment,
                request=request,
                volume=request.volume,
                price=request.price,
            )
        self._next_order_ticket += 1
        ticket = self._next_order_ticket
        deal = ticket + 100000
        if request.action in {"buy", "sell"}:
            self._positions.append(
                MT5Position(
                    ticket=ticket,
                    symbol=request.symbol,
                    side="buy" if "buy" in request.action else "sell",
                    volume=request.volume,
                    open_price=request.price,
                    current_price=request.price,
                    stop_loss=request.stop_loss,
                    take_profit=request.take_profit,
                    profit=Decimal("0"),
                    magic=request.magic,
                    comment=request.comment or "mock-fill",
                )
            )
        return MT5OrderSendResult(
            retcode=RETCODE_DONE,
            comment="done",
            order_ticket=ticket,
            deal_ticket=deal,
            volume=request.volume,
            price=request.price,
            request=request,
        )

    def order_cancel(self, ticket: int) -> MT5OrderSendResult:
        """Remove a pending mock order by ticket."""
        self._require_connected()
        if self.force_send_retcode is not None:
            return MT5OrderSendResult(
                retcode=self.force_send_retcode,
                comment=f"forced retcode {self.force_send_retcode}",
                order_ticket=ticket,
            )
        remaining = [o for o in self._pending_orders if o.ticket != ticket]
        if len(remaining) == len(self._pending_orders):
            return MT5OrderSendResult(
                retcode=RETCODE_INVALID,
                comment="order not found",
                order_ticket=ticket,
            )
        self._pending_orders = remaining
        return MT5OrderSendResult(
            retcode=RETCODE_DONE,
            comment="cancelled",
            order_ticket=ticket,
        )

    # -- Portfolio / positions (read-only) -----------------------------------

    def list_positions(self) -> list[MT5Position]:
        self._require_connected()
        return list(self._positions)

    def position_by_ticket(self, ticket: int) -> MT5Position | None:
        self._require_connected()
        for pos in self._positions:
            if pos.ticket == ticket:
                return pos
        return None

    def position_by_symbol(self, symbol: str) -> list[MT5Position]:
        self._require_connected()
        code = symbol.strip().upper()
        return [p for p in self._positions if p.symbol == code]

    def list_orders(self) -> list[MT5PendingOrder]:
        self._require_connected()
        return list(self._pending_orders)

    def order_by_ticket(self, ticket: int) -> MT5PendingOrder | None:
        self._require_connected()
        for order in self._pending_orders:
            if order.ticket == ticket:
                return order
        return None

    def history_orders(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MT5HistoryOrder]:
        self._require_connected()
        rows = self._history_orders
        if date_from is not None:
            rows = [o for o in rows if o.time_setup >= date_from]
        if date_to is not None:
            rows = [o for o in rows if o.time_setup <= date_to]
        return list(rows)

    def history_deals(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MT5Deal]:
        self._require_connected()
        rows = self._history_deals
        if date_from is not None:
            rows = [d for d in rows if d.time >= date_from]
        if date_to is not None:
            rows = [d for d in rows if d.time <= date_to]
        return list(rows)

    def account_snapshot(self) -> AccountSnapshot:
        self._require_connected()
        balance = Decimal("10000.00")
        floating = sum((p.profit for p in self._positions), Decimal("0"))
        margin = sum(
            (p.volume * Decimal("100") for p in self._positions),
            Decimal("0"),
        ).quantize(Decimal("0.01"))
        equity = (balance + floating).quantize(Decimal("0.01"))
        free = (equity - margin).quantize(Decimal("0.01"))
        level = (
            (equity / margin * Decimal("100")).quantize(Decimal("0.01"))
            if margin > 0
            else Decimal("0")
        )
        return AccountSnapshot(
            login=self._login,
            balance=balance,
            equity=equity,
            margin=margin,
            free_margin=free,
            margin_level=level,
            profit=floating.quantize(Decimal("0.01")),
            leverage=100,
            currency="USD",
            server=self._server,
        )

    def _seed_portfolio(self) -> None:
        now = datetime.now(UTC)
        eurusd = _MOCK_CATALOGUE["EURUSD"]
        gbpusd = _MOCK_CATALOGUE["GBPUSD"]
        self._positions = [
            MT5Position(
                ticket=100001,
                symbol="EURUSD",
                side="buy",
                volume=Decimal("0.10"),
                open_price=Decimal("1.08400"),
                current_price=eurusd["bid"],
                stop_loss=Decimal("1.08000"),
                take_profit=Decimal("1.09000"),
                profit=Decimal("12.50"),
                magic=42,
                comment="mock-open",
                opened_at=now,
            ),
            MT5Position(
                ticket=100002,
                symbol="GBPUSD",
                side="sell",
                volume=Decimal("0.05"),
                open_price=Decimal("1.26600"),
                current_price=gbpusd["ask"],
                profit=Decimal("-3.20"),
                magic=42,
                comment="mock-open",
                opened_at=now,
            ),
        ]
        self._pending_orders = [
            MT5PendingOrder(
                ticket=200001,
                symbol="EURUSD",
                side="buy",
                order_type="buy_limit",
                volume=Decimal("0.20"),
                price=Decimal("1.08000"),
                stop_loss=Decimal("1.07500"),
                take_profit=Decimal("1.09000"),
                magic=7,
                comment="mock-pending",
                created_at=now,
            )
        ]
        self._history_orders = [
            MT5HistoryOrder(
                ticket=300001,
                symbol="EURUSD",
                side="buy",
                order_type="market",
                volume=Decimal("0.10"),
                price=Decimal("1.08300"),
                state="filled",
                profit=Decimal("8.00"),
                time_setup=now,
                time_done=now,
            )
        ]
        self._history_deals = [
            MT5Deal(
                ticket=400001,
                order_ticket=300001,
                symbol="EURUSD",
                side="buy",
                volume=Decimal("0.10"),
                price=Decimal("1.08300"),
                profit=Decimal("8.00"),
                commission=Decimal("-0.50"),
                deal_type="entry_in",
                time=now,
            )
        ]

    def _require_connected(self) -> None:
        if not self._connected:
            msg = "MT5 client is not connected"
            raise RuntimeError(msg)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def session_token(self) -> str:
        return self._session_token
