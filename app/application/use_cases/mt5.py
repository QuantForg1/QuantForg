"""MT5 connection-layer use cases — no orders, positions, or streaming."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.mt5 import (
    MT5AccountDTO,
    MT5CandleDTO,
    MT5ConnectCommand,
    MT5ConnectionDTO,
    MT5DisconnectCommand,
    MT5StatusDTO,
    MT5SymbolDTO,
    MT5SymbolsPageDTO,
    MT5TickDTO,
)
from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.mt5_session_guard import require_live_mt5_connection
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.mt5 import MT5Connection
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.exceptions.base import NotFoundError, ValidationError
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.domain.market_data.timeframe import Timeframe
from app.infrastructure.brokers.mt5.adapter import MT5Adapter


@dataclass(frozen=True, slots=True)
class GetMT5StatusUseCase:
    uow_factory: Any
    adapter: MT5Adapter

    async def execute(self, *, user_id: UUID) -> MT5StatusDTO:
        async with self.uow_factory() as uow:
            connection = await uow.connections.get_active_for_user(user_id)
        if connection is not None and connection.connected:
            session_ref = (connection.session_ref or "").strip()
            if not session_ref or not self.adapter.is_live_session(session_ref):
                # Stale DB row after another tenant claimed the process terminal.
                return MT5StatusDTO.from_connection(None)
            try:
                snap = self.adapter.health()
                connection.mark_heartbeat(latency_ms=snap.latency_ms or 0.0)
                async with self.uow_factory() as uow:
                    await uow.connections.update(connection)
                    await uow.commit()
            except (OSError, RuntimeError, ValueError):
                pass
        return MT5StatusDTO.from_connection(connection)


@dataclass(frozen=True, slots=True)
class ConnectMT5UseCase:
    uow_factory: Any
    adapter: MT5Adapter
    audit: RecordAuditEventUseCase

    async def execute(self, command: MT5ConnectCommand) -> MT5ConnectionDTO:
        if command.login <= 0:
            raise ValidationError("MT5 login must be > 0")
        if not command.password:
            raise ValidationError("MT5 password is required")
        if not command.server.strip():
            raise ValidationError("MT5 server is required")

        connection = MT5Connection.create(
            user_id=command.user_id,
            login=command.login,
            server=command.server,
            terminal_path=command.path,
        )
        connection.mark_initializing()
        try:
            if not self.adapter.initialize(path=command.path):
                raise RuntimeError("MT5 initialize failed")
            connection.mark_logging_in()
            login_req = MT5LoginRequest(
                login=command.login,
                password=command.password,
                server=command.server.strip(),
                path=command.path,
            )
            session_ref = self.adapter.login(login_req)
            terminal = self.adapter.terminal_info()
            version = self.adapter.version()
            latency = self.adapter.ping()
            connection.mark_connected(
                session_ref=session_ref,
                terminal_build=terminal.build,
                terminal_version=f"{version[0]}.{version[1]}.{version[2]}",
                latency_ms=latency,
            )
        except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
            connection.mark_error(str(exc))
            async with self.uow_factory() as uow:
                await uow.connections.upsert_for_user(connection)
                await uow.commit()
            raise ValidationError(
                "MT5 connect failed",
                details={"error": str(exc)},
            ) from exc

        async with self.uow_factory() as uow:
            saved = await uow.connections.upsert_for_user(connection)
            await uow.commit()
            dto = MT5ConnectionDTO.from_entity(saved)

        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.ACTIVATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="mt5_connection",
                resource_id=dto.id,
                actor_user_id=command.user_id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                message="MT5 terminal connected",
                metadata={
                    "login": command.login,
                    "server": command.server,
                    "terminal_build": dto.terminal_build,
                },
            )
        )
        return dto


@dataclass(frozen=True, slots=True)
class DisconnectMT5UseCase:
    uow_factory: Any
    adapter: MT5Adapter
    audit: RecordAuditEventUseCase

    async def execute(self, command: MT5DisconnectCommand) -> MT5StatusDTO:
        async with self.uow_factory() as uow:
            connection = await uow.connections.get_active_for_user(command.user_id)
            if connection is None:
                # Never shut down a shared terminal for another tenant.
                return MT5StatusDTO.from_connection(None)
            session_ref = connection.session_ref
            if session_ref:
                await self.adapter.disconnect(session_ref=session_ref)
            connection.mark_disconnected()
            await uow.connections.update(connection)
            await uow.commit()
            status = MT5StatusDTO.from_connection(connection)

        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.DEACTIVATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="mt5_connection",
                resource_id=connection.id,
                actor_user_id=command.user_id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                message="MT5 terminal disconnected",
            )
        )
        return status


@dataclass(frozen=True, slots=True)
class GetMT5AccountUseCase:
    uow_factory: Any
    adapter: MT5Adapter

    async def execute(self, *, user_id: UUID) -> MT5AccountDTO:
        await require_live_mt5_connection(self.uow_factory, self.adapter, user_id)
        try:
            info = self.adapter.account_info()
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValidationError(
                "Failed to read MT5 account info",
                details={"error": str(exc)},
            ) from exc
        return MT5AccountDTO.from_entity(info)


@dataclass(frozen=True, slots=True)
class ListMT5SymbolsUseCase:
    uow_factory: Any
    adapter: MT5Adapter

    async def execute(
        self,
        *,
        user_id: UUID,
        q: str = "",
        offset: int = 0,
        limit: int = 100,
        include_quotes: bool = False,
        codes: list[str] | None = None,
    ) -> MT5SymbolsPageDTO:
        await require_live_mt5_connection(self.uow_factory, self.adapter, user_id)
        safe_offset = max(0, int(offset))
        safe_limit = max(1, min(500, int(limit)))
        query = (q or "").strip().upper()

        from app.domain.trading.gold_only import (
            default_trading_symbol,
            gold_only_enabled,
            is_gold_symbol,
        )

        if gold_only_enabled():
            focus = default_trading_symbol()
            if (
                query
                and not is_gold_symbol(query)
                and "XAU" not in query
                and "GOLD" not in query
            ):
                return MT5SymbolsPageDTO(
                    items=[],
                    total=0,
                    offset=safe_offset,
                    limit=safe_limit,
                    has_more=False,
                )
            # Prefer requesting the gold focus code; catalogue is still filtered below.
            if codes is None:
                codes = [focus]
            query = ""

        try:
            # Catalogue without quote fan-out; optional quotes only for the page.
            catalogue = self.adapter.list_symbols(
                include_quotes=False,
                codes=codes,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValidationError(
                "Failed to list MT5 symbols",
                details={"error": str(exc)},
            ) from exc

        # If broker uses an alternate gold code, fall back to full catalogue filter.
        if gold_only_enabled() and not catalogue and codes:
            try:
                catalogue = self.adapter.list_symbols(
                    include_quotes=False,
                    codes=None,
                )
            except (OSError, RuntimeError, ValueError):
                catalogue = []

        filtered: list[Any] = []
        for item in catalogue:
            code = (getattr(item, "code", "") or "").upper()
            desc = (getattr(item, "description", "") or "").upper()
            if gold_only_enabled() and not is_gold_symbol(code):
                continue
            if query and query not in code and query not in desc:
                continue
            filtered.append(item)

        total = len(filtered)
        page = filtered[safe_offset : safe_offset + safe_limit]
        if include_quotes and page:
            try:
                quoted = self.adapter.list_symbols(
                    include_quotes=True,
                    codes=[getattr(s, "code", "") for s in page],
                )
            except (OSError, RuntimeError, ValueError) as exc:
                raise ValidationError(
                    "Failed to fetch MT5 symbol quotes",
                    details={"error": str(exc)},
                ) from exc
            by_code = {s.code.upper(): s for s in quoted if s.code}
            page = [by_code.get(s.code.upper(), s) for s in page]

        items = [MT5SymbolDTO.from_symbol_info(s) for s in page]
        if not include_quotes:
            items = [
                MT5SymbolDTO(
                    code=i.code,
                    description=i.description,
                    digits=i.digits,
                    contract_size=i.contract_size,
                    point=i.point,
                    selected=i.selected,
                    trade_mode=i.trade_mode,
                    currency_base=i.currency_base,
                    currency_profit=i.currency_profit,
                    bid=None,
                    ask=None,
                )
                for i in items
            ]
        return MT5SymbolsPageDTO(
            items=items,
            total=total,
            offset=safe_offset,
            limit=safe_limit,
            has_more=safe_offset + safe_limit < total,
        )


@dataclass(frozen=True, slots=True)
class GetMT5SymbolUseCase:
    uow_factory: Any
    market_data: MT5MarketDataService

    async def execute(self, *, user_id: UUID, symbol: str) -> MT5SymbolDTO:
        from app.domain.trading.gold_only import resolve_trading_symbol

        symbol = resolve_trading_symbol(symbol)
        await require_live_mt5_connection(
            self.uow_factory, self.market_data.adapter, user_id
        )
        try:
            info = self.market_data.symbol_info(symbol)
        except (OSError, RuntimeError, ValueError) as exc:
            raise NotFoundError(
                "MT5 symbol not found",
                details={"symbol": symbol, "error": str(exc)},
            ) from exc
        return MT5SymbolDTO.from_symbol_info(info)


@dataclass(frozen=True, slots=True)
class GetMT5TickUseCase:
    uow_factory: Any
    market_data: MT5MarketDataService

    async def execute(self, *, user_id: UUID, symbol: str) -> MT5TickDTO:
        from app.domain.trading.gold_only import resolve_trading_symbol

        symbol = resolve_trading_symbol(symbol)
        await require_live_mt5_connection(
            self.uow_factory, self.market_data.adapter, user_id
        )
        try:
            tick = self.market_data.latest_tick(symbol)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValidationError(
                "Failed to read MT5 tick",
                details={"symbol": symbol, "error": str(exc)},
            ) from exc
        return MT5TickDTO.from_tick(tick)


@dataclass(frozen=True, slots=True)
class GetMT5CandlesUseCase:
    uow_factory: Any
    market_data: MT5MarketDataService

    async def execute(
        self,
        *,
        user_id: UUID,
        symbol: str,
        timeframe: str = "H1",
        count: int = 100,
        start_pos: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MT5CandleDTO]:
        await require_live_mt5_connection(
            self.uow_factory, self.market_data.adapter, user_id
        )
        from app.domain.trading.gold_only import resolve_trading_symbol

        symbol = resolve_trading_symbol(symbol)
        tf = Timeframe.parse(timeframe)
        if count < 1 or count > 5000:
            raise ValidationError(
                "count must be between 1 and 5000",
                details={"count": count},
            )
        try:
            rates = self.market_data.historical_candles(
                symbol,
                tf,
                date_from=date_from,
                date_to=date_to,
                count=count,
                start_pos=start_pos,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValidationError(
                "Failed to read MT5 candles",
                details={"symbol": symbol, "error": str(exc)},
            ) from exc
        return [MT5CandleDTO.from_rate(r) for r in rates]
