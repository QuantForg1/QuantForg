"""Calculation-path diagnostics and canonical broker symbols — not live OMS."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.application.dto.mt5 import MT5ConnectCommand, MT5OrderValidateCommand
from app.application.services.execution_gateway import ExecutionGateway
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.use_cases.mt5 import ConnectMT5UseCase
from app.application.use_cases.mt5_order import (
    CalculateMT5OrderUseCase,
    ValidateMT5OrderUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.mt5_order import OrderIntent
from app.domain.enums.order import OrderSide, OrderType
from app.domain.exceptions.base import ValidationError
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.domain.interfaces.mt5_order import (
    RETCODE_DONE,
    RETCODE_INVALID,
    MT5MarginResult,
    MT5OrderCheckResult,
)
from app.domain.value_objects.mt5_order import LotSize
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory

REPO = Path(__file__).resolve().parents[2]
WELTRADE_CATALOGUE = ("EURUSD_i", "GBPUSD_i", "XAUUSD_i", "USDJPY_i", "NZDCHF_i")


def _wire() -> tuple[
    MemoryMT5UnitOfWorkFactory,
    MT5Adapter,
    MT5OrderValidationService,
    RecordAuditEventUseCase,
    MockMT5Client,
]:
    mt5_factory = MemoryMT5UnitOfWorkFactory()
    broker_factory = MemoryBrokerUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(uow_factory=broker_factory)  # type: ignore[arg-type]
    client = MockMT5Client()
    adapter = MT5Adapter(client=client)
    validation = MT5OrderValidationService(adapter=adapter)
    return mt5_factory, adapter, validation, audit, client


async def _connect(factory: Any, adapter: MT5Adapter, audit: Any, user_id: Any) -> None:
    await ConnectMT5UseCase(
        uow_factory=factory, adapter=adapter, audit=audit
    ).execute(
        MT5ConnectCommand(
            user_id=user_id,
            login=3003,
            password="secret",
            server="Demo-Server",
        )
    )


class _CatalogueProbe:
    """Adapter surface for catalogue mapping only."""

    def __init__(self, codes: tuple[str, ...]) -> None:
        self.codes = codes

    def list_symbols(self, **kwargs: Any) -> list[Any]:
        return [SimpleNamespace(code=code, name=code, description="") for code in self.codes]

    def symbols(self) -> list[Any]:
        return self.list_symbols()


class _RecordingCalcAdapter:
    """Delegates to a live mock adapter; records calc symbols; optional margin fail."""

    def __init__(self, inner: MT5Adapter, catalogue: tuple[str, ...]) -> None:
        self._inner = inner
        self._catalogue = catalogue
        self.margin_symbols: list[str] = []
        self.profit_symbols: list[str] = []
        self.fail_margin: MT5MarginResult | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def list_symbols(self, **kwargs: Any) -> list[Any]:
        return [
            SimpleNamespace(code=code, name=code, description="", digits=5)
            for code in self._catalogue
        ]

    def symbols(self) -> list[Any]:
        return self.list_symbols()

    @staticmethod
    def _desk(symbol: str) -> str:
        from app.domain.institutional_trading.ai_scalping.universe_discovery import (
            scalp_desk_code,
        )

        return scalp_desk_code(symbol)

    def symbol_info(self, symbol: str) -> Any:
        return self._inner.symbol_info(self._desk(symbol))

    def latest_tick(self, symbol: str) -> Any:
        return self._inner.latest_tick(self._desk(symbol))

    def order_calc_margin(self, request: Any) -> Any:
        self.margin_symbols.append(str(request.symbol))
        if self.fail_margin is not None:
            return self.fail_margin
        desk = self._desk(request.symbol)
        if desk == request.symbol:
            return self._inner.order_calc_margin(request)
        return self._inner.order_calc_margin(replace(request, symbol=desk))

    def order_calc_profit(self, request: Any, *, close_price: Any = None) -> Any:
        self.profit_symbols.append(str(request.symbol))
        desk = self._desk(request.symbol)
        mapped = request if desk == request.symbol else replace(request, symbol=desk)
        return self._inner.order_calc_profit(mapped, close_price=close_price)


def _intent(symbol: str = "EURUSD") -> OrderIntent:
    return OrderIntent(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=LotSize.of("0.01"),
    )


@pytest.mark.unit
class TestCalculationErrorWrap:
    @pytest.mark.asyncio
    async def test_preserves_details_error_and_failure_class(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        factory, adapter, _validation, audit, _client = _wire()
        user_id = uuid4()
        await _connect(factory, adapter, audit, user_id)
        events: list[tuple[str, dict[str, Any]]] = []

        def _capture(event: str, **kwargs: Any) -> None:
            events.append((str(event), dict(kwargs)))

        monkeypatch.setattr(
            "app.application.use_cases.mt5_order.logger.error",
            _capture,
        )

        boom_adapter = adapter

        class _Boom:
            def __init__(self) -> None:
                self.adapter = boom_adapter

            def calculate(self, intent: OrderIntent) -> Any:
                raise RuntimeError("symbol_info unavailable for EURUSD")

        with pytest.raises(ValidationError) as exc_info:
            await CalculateMT5OrderUseCase(
                uow_factory=factory, validation_service=_Boom()  # type: ignore[arg-type]
            ).execute(
                MT5OrderValidateCommand(
                    user_id=user_id,
                    symbol="EURUSD",
                    side="buy",
                    order_type="market",
                    volume="0.01",
                    price="1.08520",
                    stop_loss="1.08000",
                    take_profit="1.09000",
                )
            )
        err = exc_info.value
        assert err.message == (
            "MT5 order calculation failed: symbol_info unavailable for EURUSD"
        )
        assert err.details["error"] == "symbol_info unavailable for EURUSD"
        assert err.details["failure_class"] == "A_CALCULATION"
        assert err.details["exception_type"] == "RuntimeError"
        assert (
            err.details["calculation_function"]
            == "MT5OrderValidationService.calculate"
        )
        assert len(events) == 1
        event, fields = events[0]
        assert event == "[QF][MT5_CALC_FAILED]"
        assert fields["failure_class"] == "A_CALCULATION"
        assert fields["exception_type"] == "RuntimeError"
        assert fields["exception"] == "symbol_info unavailable for EURUSD"
        assert fields["symbol"] == "EURUSD"
        assert fields["side"] == "buy"
        assert fields["volume"] == "0.01"
        assert fields["price"] == "1.08520"
        assert fields["sl"] == "1.08000"
        assert fields["tp"] == "1.09000"
        blob = str(fields).lower()
        assert "password" not in blob
        assert "secret" not in blob
        assert "token" not in blob
        assert "authorization" not in blob
        assert set(fields) <= {
            "failure_class",
            "exception_type",
            "exception",
            "calculation_function",
            "symbol",
            "side",
            "volume",
            "price",
            "sl",
            "tp",
        }


@pytest.mark.unit
class TestCanonicalBrokerSymbolForCalculation:
    @pytest.mark.parametrize(
        ("desk", "broker"),
        [
            ("EURUSD", "EURUSD_i"),
            ("XAUUSD", "XAUUSD_i"),
            ("GBPUSD", "GBPUSD_i"),
        ],
    )
    def test_desk_maps_to_catalogue_i_form(self, desk: str, broker: str) -> None:
        service = MT5OrderValidationService(adapter=_CatalogueProbe(WELTRADE_CATALOGUE))  # type: ignore[arg-type]
        resolved = service.resolve_canonical_broker_symbol(desk)
        assert resolved == broker
        assert resolved != desk

    def test_does_not_invent_missing_suffix(self) -> None:
        service = MT5OrderValidationService(
            adapter=_CatalogueProbe(("EURUSD", "GBPUSD"))  # type: ignore[arg-type]
        )
        assert service.resolve_canonical_broker_symbol("NZDCHF") == "NZDCHF"

    def test_calculate_uses_canonical_broker_symbol(self) -> None:
        inner = MT5Adapter(client=MockMT5Client())
        inner.initialize()
        inner.login(MT5LoginRequest(login=7, password="p", server="S"))
        recording = _RecordingCalcAdapter(inner, WELTRADE_CATALOGUE)
        service = MT5OrderValidationService(adapter=recording)  # type: ignore[arg-type]
        request, margin, profit = service.calculate(_intent("EURUSD"))
        assert request.symbol.upper() == "EURUSD_I"
        assert request.symbol.upper() != "EURUSD"
        assert recording.margin_symbols == [request.symbol]
        assert recording.profit_symbols == [request.symbol]
        assert margin.retcode == RETCODE_DONE
        assert profit.retcode == RETCODE_DONE

    def test_margin_failure_stops_before_profit(self) -> None:
        inner = MT5Adapter(client=MockMT5Client())
        inner.initialize()
        inner.login(MT5LoginRequest(login=7, password="p", server="S"))
        recording = _RecordingCalcAdapter(inner, WELTRADE_CATALOGUE)
        recording.fail_margin = MT5MarginResult(
            margin=Decimal("0"),
            retcode=RETCODE_INVALID,
            comment="order_calc_margin failed: (1, 'Invalid volume')",
        )
        service = MT5OrderValidationService(adapter=recording)  # type: ignore[arg-type]
        with pytest.raises(RuntimeError, match="order_calc_margin failed") as exc_info:
            service.calculate(_intent("XAUUSD"))
        assert "Invalid volume" in str(exc_info.value)
        assert recording.margin_symbols
        assert recording.profit_symbols == []


@pytest.mark.unit
class TestFailureClassesStayDistinct:
    def test_order_check_failure_is_class_b_not_calculation(self) -> None:
        adapter = MT5Adapter(client=MockMT5Client())
        adapter.initialize()
        adapter.login(MT5LoginRequest(login=7, password="p", server="S"))
        service = MT5OrderValidationService(adapter=adapter)

        def _fail_check(request: Any) -> MT5OrderCheckResult:
            return MT5OrderCheckResult(
                retcode=RETCODE_INVALID,
                comment="Invalid request",
                request=request,
            )

        adapter.order_check = _fail_check  # type: ignore[method-assign]
        result = service.validate_order(_intent("EURUSD"))
        assert result.valid is False
        joined = " ".join(result.messages)
        assert "order_check" in joined.lower()
        assert "MT5 order calculation failed" not in joined
        assert result.retcode == RETCODE_INVALID

    def test_order_send_failure_is_class_c_not_calculation(self) -> None:
        client = MockMT5Client()
        client.initialize()
        client.login(MT5LoginRequest(login=1, password="p", server="S"))
        client.force_send_retcode = 10004
        adapter = MT5Adapter(client=client, execution_enabled=True)
        validation = MT5OrderValidationService(adapter=adapter)
        gateway = ExecutionGateway(adapter=adapter, order_validation=validation)
        result = gateway.submit(
            _intent("XAUUSD"), user_id=uuid4(), request_id="c-send-1"
        )
        assert "MT5 order calculation failed" not in (result.message or "")
        assert result.retcode == 10004
        assert "forced retcode 10004" in (result.message or "")

    def test_order_send_is_not_retried_on_failure(self) -> None:
        class _CountSend(MockMT5Client):
            sends = 0

            def order_send(self, request: Any) -> Any:  # type: ignore[override]
                type(self).sends += 1
                self.force_send_retcode = 10031
                return super().order_send(request)

        _CountSend.sends = 0
        client = _CountSend()
        client.initialize()
        client.login(MT5LoginRequest(login=1, password="p", server="S"))
        adapter = MT5Adapter(client=client, execution_enabled=True)
        validation = MT5OrderValidationService(adapter=adapter)
        gateway = ExecutionGateway(adapter=adapter, order_validation=validation)
        gateway.submit(_intent("XAUUSD"), user_id=uuid4(), request_id="c-once")
        assert _CountSend.sends == 1

    def test_oms_live_path_does_not_call_calculate(self) -> None:
        engine_src = (
            REPO / "app/application/services/institutional_execution_engine.py"
        ).read_text(encoding="utf-8")
        gateway_src = (
            REPO / "app/application/services/execution_gateway.py"
        ).read_text(encoding="utf-8")
        calc_src = (
            REPO / "app/application/services/mt5_order_validation.py"
        ).read_text(encoding="utf-8")
        assert "self.gateway.submit" in engine_src
        assert ".order_check(" in engine_src
        assert "validation_service.calculate" not in engine_src
        assert "order_calc_margin" not in engine_src
        assert "adapter.order_send" in gateway_src
        assert "order_calc_margin" not in gateway_src
        assert "Never retry order_send" in (
            REPO / "app/infrastructure/brokers/mt5/gateway_client.py"
        ).read_text(encoding="utf-8")
        # calculate() still exists, but OMS does not use it.
        assert "def calculate(" in calc_src


@pytest.mark.unit
class TestValidateEndpointUnchangedWrap:
    @pytest.mark.asyncio
    async def test_validate_does_not_use_calculation_wrap(self) -> None:
        factory, adapter, validation, audit, _client = _wire()
        user_id = uuid4()
        await _connect(factory, adapter, audit, user_id)
        dto = await ValidateMT5OrderUseCase(
            uow_factory=factory, validation_service=validation, audit=audit
        ).execute(
            MT5OrderValidateCommand(
                user_id=user_id,
                symbol="EURUSD",
                side="buy",
                order_type="market",
                volume="0.01",
            )
        )
        assert dto.valid is True
        assert "MT5 order calculation failed" not in " ".join(dto.messages)
