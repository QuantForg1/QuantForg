"""HTTP MT5 client — Railway → Windows MT5 Gateway (no local MetaTrader5).

Broker passwords are forwarded once to ``POST /session/connect`` and never
retained on this process. Prefer ``attach()`` when the terminal is already
logged in. Does not invent market data.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx

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
    RETCODE_INVALID,
    MT5MarginResult,
    MT5OrderCheckResult,
    MT5OrderSendResult,
    MT5ProfitResult,
)
from app.domain.market_data.timeframe import Timeframe

# Gateway does not expose order_send in v1 — refuse without inventing fills.
_RETCODE_GATEWAY_NO_TRADE = 10027


def _dec(value: Any, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass
class GatewayMT5Client:
    """Sync httpx client implementing ``MT5ClientPort`` against gateway REST."""

    base_url: str
    token: str
    timeout_seconds: float = 30.0
    stores_credentials_remotely: bool = field(default=True, init=False)
    _initialized: bool = field(default=False, init=False)
    _connected: bool = field(default=False, init=False)
    _login: int = field(default=0, init=False)
    _server: str = field(default="", init=False)
    _path: str = field(default="", init=False)
    _session_token: str = field(default="", init=False)
    _last_heartbeat: datetime | None = field(default=None, init=False)
    _session_mode: str = field(default="none", init=False)
    _last_gateway_health: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.token = (self.token or "").strip()

    @property
    def session_token(self) -> str:
        return self._session_token

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def session_mode(self) -> str:
        return self._session_mode

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        if not self.token and auth and path != "/health":
            raise RuntimeError(
                "MT5_GATEWAY_CALLER_TOKEN is not configured on the API "
                "(must match Windows MT5_GATEWAY_TOKEN)"
            )
        url = f"{self.base_url}{path}"
        headers = self._headers() if auth else {"Accept": "application/json"}
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    json=json_body,
                    params=params,
                )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Gateway unreachable: {exc}") from exc
        if response.status_code >= 400:
            detail: Any
            try:
                payload = response.json()
                detail = payload.get("detail", payload)
            except Exception:
                detail = response.text
            raise RuntimeError(
                f"Gateway {path} failed ({response.status_code}): {detail}"
            )
        if not response.content:
            return {}
        data = response.json()
        if isinstance(data, dict):
            return data
        return {"data": data}

    def gateway_health(self) -> dict[str, Any]:
        data = self._request("GET", "/health", auth=False)
        self._last_gateway_health = data
        return data

    def initialize(self, *, path: str = "") -> bool:
        if not self.base_url:
            return False
        try:
            health = self.gateway_health()
        except RuntimeError:
            return False
        if health.get("status") != "ok":
            return False
        if health.get("bridge_available") is False:
            return False
        self._path = path.strip()
        self._initialized = True
        return True

    def login(self, request: MT5LoginRequest) -> bool:
        if not self._initialized and not self.initialize(path=request.path):
            return False
        body = {
            "login": int(request.login),
            "password": request.password,
            "server": request.server.strip(),
            "path": (request.path or self._path or "").strip(),
        }
        try:
            data = self._request("POST", "/session/connect", json_body=body)
        except RuntimeError:
            return False
        if not data.get("connected"):
            return False
        self._apply_session(
            login=int(data.get("login") or request.login),
            server=str(data.get("server") or request.server),
            mode=str(data.get("session_mode") or "connected"),
        )
        return True

    def attach(self, *, path: str = "") -> bool:
        """Reuse an already logged-in terminal — no broker password on Railway."""
        term_path = (path or self._path or "").strip()
        if not self._initialized and not self.initialize(path=term_path):
            return False
        try:
            data = self._request(
                "POST",
                "/session/attach",
                json_body={"path": term_path},
            )
        except RuntimeError:
            return False
        if not data.get("connected"):
            return False
        self._apply_session(
            login=int(data.get("login") or 0),
            server=str(data.get("server") or ""),
            mode=str(data.get("session_mode") or "attached"),
        )
        return True

    def _apply_session(self, *, login: int, server: str, mode: str) -> None:
        self._login = login
        self._server = server
        self._connected = True
        self._session_mode = mode
        self._session_token = f"gw-mt5-{uuid4().hex[:12]}"
        self._last_heartbeat = datetime.now(UTC)

    def shutdown(self) -> None:
        if self._initialized and self.token:
            with contextlib.suppress(RuntimeError):
                self._request("POST", "/session/disconnect", json_body={})
        self._connected = False
        self._initialized = False
        self._session_token = ""
        self._login = 0
        self._server = ""
        self._session_mode = "none"

    def reconnect(self, request: MT5LoginRequest) -> bool:
        if request.password:
            self.shutdown()
            if not self.initialize(path=request.path or self._path):
                return False
            return self.login(request)
        # Password-free reconnect: ask gateway to re-bind terminal session.
        try:
            status = self._request("GET", "/session/status")
            if status.get("connected"):
                health = _as_dict(status.get("health"))
                self._apply_session(
                    login=int(status.get("login") or self._login or 0),
                    server=str(status.get("server") or self._server or ""),
                    mode=str(status.get("session_mode") or "attached"),
                )
                if health.get("latency_ms") is not None:
                    self._last_heartbeat = datetime.now(UTC)
                return True
        except RuntimeError:
            pass
        return self.attach(path=request.path or self._path)

    def ping(self) -> float:
        self._require_connected()
        data = self._request("GET", "/heartbeat")
        self._last_heartbeat = datetime.now(UTC)
        return float(data.get("ping_ms") or 0.0)

    def terminal_info(self) -> MT5Terminal:
        health = self.health()
        return MT5Terminal(
            build=int(health.terminal_build or 0),
            name="MetaTrader 5 (Gateway)",
            path=self._path,
            company="Weltrade via QuantForg Gateway",
            language="en",
            connected=self._connected,
        )

    def version(self) -> tuple[int, int, int]:
        raw = ""
        try:
            snap = self.health()
            raw = snap.version or ""
        except Exception:
            raw = ""
        parts = [*raw.split("."), "0", "0", "0"][:3]
        try:
            return int(parts[0] or 0), int(parts[1] or 0), int(parts[2] or 0)
        except ValueError:
            return (0, 0, 0)

    def account_info(self) -> MT5AccountInfo:
        self._require_connected()
        data = self._request("GET", "/account")
        return MT5AccountInfo(
            login=int(data.get("login") or self._login),
            name=str(data.get("name") or f"Account {data.get('login', '')}"),
            server=str(data.get("server") or self._server),
            currency=str(data.get("currency") or "USD"),
            leverage=int(data.get("leverage") or 1),
            balance=_dec(data.get("balance")),
            equity=_dec(data.get("equity")),
            margin=_dec(data.get("margin")),
            free_margin=_dec(data.get("free_margin")),
            margin_level=_dec(data.get("margin_level")),
            profit=_dec(data.get("profit")),
            company="Weltrade",
            trade_mode="demo",
        )

    def server_info(self) -> MT5Server:
        return MT5Server(
            name=self._server or "Weltrade",
            company="Weltrade",
            trade_mode="demo",
        )

    def symbols(self) -> list[BrokerSymbolInfo]:
        self._require_connected()
        data = self._request("GET", "/symbols")
        items = data.get("items") or []
        return [
            BrokerSymbolInfo(
                code=str(row.get("code") or ""),
                description=str(row.get("description") or ""),
                digits=int(row.get("digits") or 0),
                contract_size=Decimal("100000"),
            )
            for row in items
            if row.get("code")
        ]

    def health(self) -> MT5HealthSnapshot:
        latency: float | None = None
        terminal_build: int | None = None
        version = ""
        login_status = "logged_out"
        server = self._server
        connected = self._connected
        try:
            if self.token:
                status = self._request("GET", "/session/status")
                connected = bool(status.get("connected"))
                self._connected = connected
                server = str(status.get("server") or server)
                if status.get("login") is not None:
                    self._login = int(status["login"])
                mode = status.get("session_mode")
                if mode:
                    self._session_mode = str(mode)
                h = _as_dict(status.get("health"))
                latency = (
                    float(h["latency_ms"]) if h.get("latency_ms") is not None else None
                )
                terminal_build = (
                    int(h["terminal_build"])
                    if h.get("terminal_build") is not None
                    else None
                )
                version = str(h.get("version") or "")
                login_status = str(
                    h.get("login_status")
                    or ("logged_in" if connected else "logged_out")
                )
                if h.get("last_heartbeat_at"):
                    self._last_heartbeat = datetime.now(UTC)
            else:
                gw = self.gateway_health()
                mt5 = _as_dict(gw.get("mt5"))
                connected = bool(mt5.get("connected"))
                latency = (
                    float(mt5["latency_ms"])
                    if mt5.get("latency_ms") is not None
                    else None
                )
        except RuntimeError:
            connected = False
            login_status = "error"
        return MT5HealthSnapshot(
            connected=connected,
            latency_ms=latency,
            terminal_build=terminal_build,
            server=server,
            login_status=login_status,
            last_heartbeat_at=(
                self._last_heartbeat.isoformat() if self._last_heartbeat else None
            ),
            version=version,
        )

    def list_symbols(self) -> list[MT5SymbolInfo]:
        return [self.symbol_info(s.code) for s in self.symbols() if s.code]

    def symbol_info(self, symbol: str) -> MT5SymbolInfo:
        self._require_connected()
        code = symbol.strip().upper()
        tick = self._request("GET", f"/quotes/{code}")
        meta = next((s for s in self.symbols() if s.code.upper() == code), None)
        return MT5SymbolInfo(
            code=code,
            description=meta.description if meta else code,
            digits=meta.digits if meta else 5,
            point=Decimal("0.00001"),
            contract_size=Decimal("100000"),
            selected=True,
            trade_mode="full",
            currency_base="",
            currency_profit="",
            bid=_dec(tick.get("bid")),
            ask=_dec(tick.get("ask")),
        )

    def symbol_select(self, symbol: str, *, enable: bool = True) -> bool:
        _ = enable
        self._require_connected()
        try:
            self._request("GET", f"/quotes/{symbol.strip().upper()}")
            return True
        except RuntimeError:
            return False

    def latest_tick(self, symbol: str) -> MT5Tick:
        self._require_connected()
        data = self._request("GET", f"/quotes/{symbol.strip().upper()}")
        ts = data.get("time")
        timestamp = (
            datetime.fromtimestamp(int(ts), tz=UTC)
            if ts
            else datetime.now(UTC)
        )
        return MT5Tick(
            symbol=str(data.get("symbol") or symbol).upper(),
            bid=_dec(data.get("bid")),
            ask=_dec(data.get("ask")),
            timestamp=timestamp,
            volume=Decimal("0"),
        )

    def copy_rates_from(
        self,
        symbol: str,
        timeframe: Timeframe,
        date_from: datetime,
        count: int,
    ) -> list[MT5Rate]:
        _ = date_from
        return self.copy_rates_from_pos(symbol, timeframe, 0, count)

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: Timeframe,
        date_from: datetime,
        date_to: datetime,
    ) -> list[MT5Rate]:
        _ = date_from, date_to
        return self.copy_rates_from_pos(symbol, timeframe, 0, 500)

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_pos: int,
        count: int,
    ) -> list[MT5Rate]:
        _ = start_pos
        self._require_connected()
        if count < 1:
            return []
        data = self._request(
            "GET",
            f"/candles/{symbol.strip().upper()}",
            params={"timeframe": timeframe.value, "count": min(count, 5000)},
        )
        items = data.get("items") or []
        rates: list[MT5Rate] = []
        for row in items:
            rates.append(
                MT5Rate(
                    symbol=symbol.strip().upper(),
                    timeframe=timeframe,
                    open_time=datetime.fromtimestamp(int(row["time"]), tz=UTC),
                    open=_dec(row.get("open")),
                    high=_dec(row.get("high")),
                    low=_dec(row.get("low")),
                    close=_dec(row.get("close")),
                    tick_volume=0,
                    spread_points=0,
                    real_volume=Decimal("0"),
                )
            )
        return rates

    def order_check(self, request: TradeRequest) -> MT5OrderCheckResult:
        return MT5OrderCheckResult(
            retcode=RETCODE_INVALID,
            comment="order_check is performed by Execution Gateway locally",
            request=request,
        )

    def order_calc_margin(self, request: TradeRequest) -> MT5MarginResult:
        _ = request
        return MT5MarginResult(
            margin=Decimal("0"),
            retcode=RETCODE_INVALID,
            comment="margin calc unavailable via gateway bridge",
        )

    def order_calc_profit(
        self,
        request: TradeRequest,
        *,
        close_price: Decimal | None = None,
    ) -> MT5ProfitResult:
        _ = request, close_price
        return MT5ProfitResult(
            profit=Decimal("0"),
            retcode=RETCODE_INVALID,
            comment="profit calc unavailable via gateway bridge",
        )

    def order_send(self, request: TradeRequest) -> MT5OrderSendResult:
        """Gateway v1 has no trade routes — never invent fills."""
        return MT5OrderSendResult(
            retcode=_RETCODE_GATEWAY_NO_TRADE,
            comment=(
                "Windows MT5 Gateway v1 is session/market-data only. "
                "Live order_send requires EXECUTION_ENABLED and a trade-capable path."
            ),
            request=request,
            volume=request.volume,
            price=request.price,
        )

    def order_cancel(self, ticket: int) -> MT5OrderSendResult:
        return MT5OrderSendResult(
            retcode=_RETCODE_GATEWAY_NO_TRADE,
            comment="cancel not available on gateway v1 bridge",
            order_ticket=ticket,
        )

    def list_positions(self) -> list[MT5Position]:
        self._require_connected()
        data = self._request("GET", "/positions")
        out: list[MT5Position] = []
        for row in data.get("items") or []:
            typ = int(row.get("type") or 0)
            out.append(
                MT5Position(
                    ticket=int(row["ticket"]),
                    symbol=str(row.get("symbol") or ""),
                    side="buy" if typ == 0 else "sell",
                    volume=_dec(row.get("volume"), "0.01"),
                    open_price=_dec(row.get("price_open")),
                    current_price=_dec(row.get("price_current")),
                    profit=_dec(row.get("profit")),
                )
            )
        return out

    def position_by_ticket(self, ticket: int) -> MT5Position | None:
        for pos in self.list_positions():
            if pos.ticket == ticket:
                return pos
        return None

    def position_by_symbol(self, symbol: str) -> list[MT5Position]:
        code = symbol.strip().upper()
        return [p for p in self.list_positions() if p.symbol == code]

    def list_orders(self) -> list[MT5PendingOrder]:
        self._require_connected()
        data = self._request("GET", "/orders")
        out: list[MT5PendingOrder] = []
        for row in data.get("items") or []:
            typ = int(row.get("type") or 0)
            out.append(
                MT5PendingOrder(
                    ticket=int(row["ticket"]),
                    symbol=str(row.get("symbol") or ""),
                    side="buy" if typ % 2 == 0 else "sell",
                    order_type="limit",
                    volume=_dec(row.get("volume_current"), "0.01"),
                    price=_dec(row.get("price_open")),
                )
            )
        return out

    def order_by_ticket(self, ticket: int) -> MT5PendingOrder | None:
        for order in self.list_orders():
            if order.ticket == ticket:
                return order
        return None

    def history_orders(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MT5HistoryOrder]:
        _ = date_to
        self._require_connected()
        days = 30
        if date_from is not None:
            delta = datetime.now(UTC) - (
                date_from if date_from.tzinfo else date_from.replace(tzinfo=UTC)
            )
            days = max(1, min(365, int(delta.total_seconds() // 86400) or 1))
        data = self._request("GET", "/history/orders", params={"days": days})
        out: list[MT5HistoryOrder] = []
        for row in data.get("items") or []:
            symbol = str(row.get("symbol") or "").strip()
            ticket = int(row.get("ticket") or 0)
            if ticket <= 0 or not symbol:
                continue
            out.append(
                MT5HistoryOrder(
                    ticket=ticket,
                    symbol=symbol,
                    side="buy",
                    order_type="market",
                    volume=Decimal("0"),
                    price=Decimal("0"),
                    state="filled",
                )
            )
        return out

    def history_deals(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MT5Deal]:
        _ = date_to
        self._require_connected()
        days = 30
        if date_from is not None:
            delta = datetime.now(UTC) - (
                date_from if date_from.tzinfo else date_from.replace(tzinfo=UTC)
            )
            days = max(1, min(365, int(delta.total_seconds() // 86400) or 1))
        data = self._request("GET", "/history/deals", params={"days": days})
        out: list[MT5Deal] = []
        for row in data.get("items") or []:
            symbol = str(row.get("symbol") or "").strip()
            ticket = int(row.get("ticket") or 0)
            if ticket <= 0 or not symbol:
                continue
            vol = _dec(row.get("volume"), "0.01")
            if vol <= 0:
                vol = Decimal("0.01")
            out.append(
                MT5Deal(
                    ticket=ticket,
                    order_ticket=ticket,
                    symbol=symbol,
                    side="buy",
                    volume=vol,
                    price=Decimal("0"),
                    profit=_dec(row.get("profit")),
                    deal_type="deal",
                )
            )
        return out

    def account_snapshot(self) -> AccountSnapshot:
        info = self.account_info()
        return AccountSnapshot(
            login=info.login,
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.free_margin,
            margin_level=info.margin_level,
            profit=info.profit,
            leverage=info.leverage,
            currency=info.currency,
            server=info.server,
        )

    def diagnostics(self) -> dict[str, Any]:
        if not self.token:
            return {"error": "caller token not configured"}
        return self._request("GET", "/diagnostics")

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("MT5 gateway session not connected")
