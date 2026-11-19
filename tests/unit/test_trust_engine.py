"""Trust Engine — verified figures, no invented money, no order path."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.application.dto.auth import AuthUserDTO
from app.application.services.trust_engine import load_trust_performance
from app.domain.exceptions.base import NotFoundError, ServiceUnavailableError
from app.domain.trust_engine import TrustBuildInput, build_trust_report

pytestmark = [pytest.mark.unit]

_READ_AT = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
_ROOT = Path(__file__).resolve().parents[2]


def _deal(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ticket": 1,
        "position_id": 10,
        "symbol": "XAUUSD",
        "side": "buy",
        "volume": "0.10",
        "price": "2400.00",
        "profit": "0",
        "commission": "0",
        "swap": "0",
        "deal_type": "entry_in",
        "time": "2026-11-18T10:00:00+00:00",
    }
    base.update(overrides)
    return base


def _round_trip(
    *,
    position_id: int,
    entry_ticket: int,
    exit_ticket: int,
    profit: str,
    commission: str | None = "0",
    swap: str = "0",
    symbol: str = "XAUUSD",
    side: str = "buy",
    entry: str = "2400.00",
    exit_price: str = "2410.00",
    entry_time: str = "2026-11-18T10:00:00+00:00",
    exit_time: str = "2026-11-18T12:00:00+00:00",
) -> list[dict[str, object]]:
    return [
        _deal(
            ticket=entry_ticket,
            position_id=position_id,
            symbol=symbol,
            side=side,
            price=entry,
            profit="0",
            commission="0" if commission is not None else None,
            swap="0",
            deal_type="entry_in",
            time=entry_time,
        ),
        _deal(
            ticket=exit_ticket,
            position_id=position_id,
            symbol=symbol,
            side="sell" if side == "buy" else "buy",
            price=exit_price,
            profit=profit,
            commission=commission,
            swap=swap,
            deal_type="entry_out",
            time=exit_time,
        ),
    ]


def _report(deals: list[dict[str, object]], **kwargs: object) -> dict:
    spec = TrustBuildInput(
        deals=tuple(deals),
        history_available=True,
        read_at=_READ_AT,
        account_scope="live",
        source="broker_history_deals",
        **kwargs,  # type: ignore[arg-type]
    )
    return build_trust_report(spec)


def test_complete_round_trip_uses_broker_profit_commission_and_swap() -> None:
    report = _report(
        _round_trip(
            position_id=10,
            entry_ticket=1,
            exit_ticket=2,
            profit="10",
            commission="-1",
            swap="-0.5",
        ),
        account_login=12345678,
        floating_pnl="4.25",
    )
    trade = report["trades"][0]
    assert trade["symbol"] == "XAUUSD"
    assert trade["direction"]["value"] == "buy"
    assert trade["entry_price"]["value"] == "2400.00"
    assert trade["exit_price"]["value"] == "2410.00"
    assert trade["gross_pnl"]["value"] == "10"
    assert trade["net_pnl"]["value"] == "8.5"
    assert trade["net_pnl"]["status"] == "verified"
    assert trade["net_pnl"]["source"] == "broker_history_deals"
    assert trade["net_pnl"]["live_performance"] is True
    assert trade["spread"]["value"] is None
    assert trade["spread"]["status"] == "unavailable"
    assert trade["slippage"]["status"] == "unavailable"
    assert trade["stop_loss"]["status"] == "unavailable"
    assert trade["take_profit"]["status"] == "unavailable"
    assert trade["strategy_id"]["status"] == "unavailable"
    assert trade["account_id_masked"] == "••••5678"
    assert "12345678" not in json.dumps(report)
    performance = report["performance"]
    assert performance["total_trades"]["value"] == 1
    assert performance["winning_trades"]["value"] == 1
    assert performance["net_realized_pnl"]["value"] == "8.5"
    assert performance["floating_pnl"]["value"] == "4.25"
    assert (
        performance["floating_pnl"]["value"] != performance["net_realized_pnl"]["value"]
    )
    assert performance["trading_costs"]["value"] == "-1.5"
    assert performance["average_holding_time_seconds"]["value"] == "7200.000"
    assert report["places_orders"] is False
    assert report["authoritative_for_execution"] is False


def test_missing_commission_does_not_become_zero() -> None:
    deals = _round_trip(
        position_id=10,
        entry_ticket=1,
        exit_ticket=2,
        profit="10",
        commission=None,
        swap="0",
    )
    report = _report(deals)
    trade = report["trades"][0]
    assert trade["commission"]["value"] is None
    assert trade["commission"]["status"] == "unavailable"
    assert trade["net_pnl"]["value"] is None
    assert report["performance"]["net_realized_pnl"]["value"] is None
    assert report["performance"]["net_realized_pnl"]["status"] == "unavailable"
    assert report["performance"]["trading_costs"]["value"] is None


def test_deposits_are_not_trades() -> None:
    deals = [
        _deal(
            ticket=9,
            position_id=0,
            symbol="BALANCE",
            side="buy",
            volume="0",
            price="0",
            profit="1000",
            deal_type="balance",
            time="2026-11-18T09:00:00+00:00",
        ),
        *_round_trip(
            position_id=10,
            entry_ticket=1,
            exit_ticket=2,
            profit="5",
            commission="0",
            swap="0",
        ),
    ]
    report = _report(deals)
    assert report["performance"]["total_trades"]["value"] == 1
    assert report["performance"]["net_realized_pnl"]["value"] == "5"
    assert report["performance"]["excluded_non_trade_deals"]["value"] == 1


def test_untyped_deals_are_not_paired_by_guessing() -> None:
    deals = [
        _deal(ticket=1, position_id=10, deal_type="deal", price="2400", profit="0"),
        _deal(
            ticket=2,
            position_id=10,
            deal_type="deal",
            price="2410",
            profit="12",
            time="2026-11-18T12:00:00+00:00",
        ),
    ]
    report = _report(deals)
    assert report["trades"] == []
    assert report["performance"]["total_trades"]["value"] == 0
    assert report["performance"]["net_realized_pnl"]["value"] == "0"
    assert report["performance"]["unpaired_deals"]["value"] == 2


def test_backtest_results_are_not_verified_live_performance() -> None:
    report = build_trust_report(
        TrustBuildInput(
            deals=tuple(
                _round_trip(
                    position_id=3,
                    entry_ticket=1,
                    exit_ticket=2,
                    profit="20",
                )
            ),
            history_available=True,
            account_scope="backtest",
            source="backtest_metrics",
            read_at=_READ_AT,
        )
    )
    net = report["performance"]["net_realized_pnl"]
    assert net["value"] == "20"
    assert net["status"] == "partially_verified"
    assert net["account_scope"] == "backtest"
    assert net["live_performance"] is False
    assert report["live_performance"] is False


def test_unknown_scope_keeps_broker_facts_and_withholds_the_live_label() -> None:
    report = build_trust_report(
        TrustBuildInput(
            deals=tuple(
                _round_trip(
                    position_id=3,
                    entry_ticket=1,
                    exit_ticket=2,
                    profit="20",
                )
            ),
            history_available=True,
            account_scope="unknown",
            read_at=_READ_AT,
        )
    )
    net = report["performance"]["net_realized_pnl"]
    assert net["status"] == "verified"
    assert net["live_performance"] is False
    assert report["live_performance"] is False


def test_drawdown_win_rate_and_profit_factor_from_closed_nets() -> None:
    deals: list[dict[str, object]] = []
    deals += _round_trip(
        position_id=1,
        entry_ticket=1,
        exit_ticket=2,
        profit="10",
        exit_time="2026-11-18T11:00:00+00:00",
    )
    deals += _round_trip(
        position_id=2,
        entry_ticket=3,
        exit_ticket=4,
        profit="-30",
        entry_time="2026-11-18T12:00:00+00:00",
        exit_time="2026-11-18T13:00:00+00:00",
    )
    deals += _round_trip(
        position_id=3,
        entry_ticket=5,
        exit_ticket=6,
        profit="5",
        symbol="EURUSD",
        entry_time="2026-11-18T14:00:00+00:00",
        exit_time="2026-11-18T15:00:00+00:00",
    )
    report = _report(deals, strategy_by_position={1: "gold-scalp"})
    performance = report["performance"]
    assert performance["total_trades"]["value"] == 3
    assert performance["winning_trades"]["value"] == 2
    assert performance["losing_trades"]["value"] == 1
    assert performance["win_rate"]["value"] == "0.666667"
    assert performance["profit_factor"]["value"] == "0.500000"
    assert performance["average_win"]["value"] == "7.500000"
    assert performance["average_loss"]["value"] == "-30.000000"
    assert performance["maximum_drawdown"]["value"] == "30"
    assert performance["net_realized_pnl"]["value"] == "-15"
    symbols = {trade["symbol"] for trade in report["trades"]}
    assert symbols == {"XAUUSD", "EURUSD"}
    by_strategy = {row["strategy_id"]: row for row in report["strategy_performance"]}
    assert by_strategy["gold-scalp"]["net_realized_pnl"]["value"] == "10"
    assert by_strategy[None]["trade_count"]["value"] == 2


def test_profit_factor_is_unavailable_when_there_are_no_losses() -> None:
    report = _report(
        _round_trip(position_id=1, entry_ticket=1, exit_ticket=2, profit="10")
    )
    assert report["performance"]["profit_factor"]["value"] is None
    assert report["performance"]["profit_factor"]["status"] == "unavailable"
    assert report["performance"]["win_rate"]["value"] == "1.000000"


def test_empty_history_does_not_invent_a_win_rate() -> None:
    report = _report([])
    assert report["performance"]["total_trades"]["value"] == 0
    assert report["performance"]["total_trades"]["status"] == "verified"
    assert report["performance"]["net_realized_pnl"]["value"] == "0"
    assert report["performance"]["win_rate"]["value"] is None
    assert report["performance"]["win_rate"]["status"] == "unavailable"
    assert report["performance"]["maximum_drawdown"]["value"] == "0"
    assert report["performance"]["maximum_drawdown"]["method"] == "no_closed_trades"


def test_missing_history_withholds_zero_fills() -> None:
    report = build_trust_report(
        TrustBuildInput(deals=None, history_available=False, read_at=_READ_AT)
    )
    assert report["trades"] == []
    assert report["performance"]["total_trades"]["value"] is None
    assert report["performance"]["total_trades"]["status"] == "pending_synchronization"
    assert report["performance"]["net_realized_pnl"]["value"] is None
    assert report["live_performance"] is False


def test_float_prices_are_rejected() -> None:
    deals = _round_trip(position_id=1, entry_ticket=1, exit_ticket=2, profit="10")
    deals[1]["profit"] = 10.1  # type: ignore[assignment]
    report = _report(deals)
    assert report["trades"][0]["gross_pnl"]["value"] is None
    assert report["performance"]["net_realized_pnl"]["value"] is None


def test_modules_do_not_reference_order_send() -> None:
    for relative in (
        "app/domain/trust_engine/report.py",
        "app/domain/trust_engine/__init__.py",
        "app/application/services/trust_engine.py",
        "app/presentation/routers/trust_engine.py",
    ):
        text = (_ROOT / relative).read_text(encoding="utf-8")
        assert "order_send" not in text
        assert "execution_gateway" not in text


def test_router_is_registered_for_customers_and_flag_defaults_off() -> None:
    from app.main import _OPERATOR_ONLY_ROUTER_MODULES, _ROUTER_SPECS
    from core.config.settings import Settings

    spec = dict(_ROUTER_SPECS)
    assert spec["trust_engine"] == "app.presentation.routers.trust_engine"
    assert "trust_engine" not in _OPERATOR_ONLY_ROUTER_MODULES
    assert Settings.model_fields["trust_engine_enabled"].default is False


class _History:
    def __init__(
        self, deals: list[dict[str, object]] | None, error: Exception | None = None
    ) -> None:
        self.deals = deals
        self.error = error
        self.user_ids: list[UUID] = []

    async def execute(
        self, *, user_id: UUID, date_from: object = None, date_to: object = None
    ) -> object:
        self.user_ids.append(user_id)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(deals=self.deals or [])


class _Account:
    def __init__(
        self, *, profit: str, login: int, server: str, error: Exception | None = None
    ) -> None:
        self.profit = profit
        self.login = login
        self.server = server
        self.error = error
        self.user_ids: list[UUID] = []

    async def execute(self, *, user_id: UUID) -> object:
        self.user_ids.append(user_id)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(profit=self.profit, login=self.login, server=self.server)


@pytest.mark.asyncio
async def test_loader_reads_only_the_requested_user() -> None:
    owner = uuid4()
    other = uuid4()
    history = _History(
        _round_trip(position_id=4, entry_ticket=1, exit_ticket=2, profit="3")
    )
    account = _Account(profit="1.5", login=5550001111, server="Broker-Demo")
    report = await load_trust_performance(
        user_id=owner,
        history=history,
        account=account,
        read_at=_READ_AT,
    )
    assert history.user_ids == [owner]
    assert account.user_ids == [owner]
    assert other not in history.user_ids
    encoded = json.dumps(report)
    assert str(owner) not in encoded
    assert str(other) not in encoded
    assert "5550001111" not in encoded
    assert report["account_id_masked"] == "••••••1111"
    assert report["account_scope"] == "unknown"
    assert report["performance"]["net_realized_pnl"]["live_performance"] is False
    assert report["performance"]["floating_pnl"]["value"] == "1.5"
    assert report["broker_server"] == "Broker-Demo"


@pytest.mark.asyncio
async def test_loader_pending_when_the_user_has_no_connection() -> None:
    account = _Account(profit="9", login=1, server="X")
    report = await load_trust_performance(
        user_id=uuid4(),
        history=_History([], error=NotFoundError("No active MT5 connection")),
        account=account,
        read_at=_READ_AT,
    )
    assert report["performance"]["total_trades"]["status"] == "pending_synchronization"
    assert report["performance"]["net_realized_pnl"]["value"] is None
    assert account.user_ids == []


@pytest.mark.asyncio
async def test_loader_keeps_realized_pnl_when_the_snapshot_fails() -> None:
    report = await load_trust_performance(
        user_id=uuid4(),
        history=_History(
            _round_trip(position_id=8, entry_ticket=1, exit_ticket=2, profit="6")
        ),
        account=_Account(
            profit="9",
            login=1,
            server="X",
            error=ServiceUnavailableError("snapshot down"),
        ),
        read_at=_READ_AT,
    )
    assert report["performance"]["net_realized_pnl"]["value"] == "6"
    assert report["performance"]["floating_pnl"]["status"] == "unavailable"
    assert report["performance"]["floating_pnl"]["value"] is None


@pytest.mark.asyncio
async def test_route_stays_hidden_until_the_flag_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.presentation.routers import trust_engine as router_module

    def _forbidden() -> tuple[object, object]:
        raise AssertionError("broker reader was called while the flag is off")

    monkeypatch.setattr(router_module, "_reader", _forbidden)
    monkeypatch.setattr(
        router_module,
        "get_settings",
        lambda: SimpleNamespace(trust_engine_enabled=False),
    )
    user = AuthUserDTO(
        id=uuid4(),
        email="a@example.invalid",
        display_name="A",
        role="trader",
        status="active",
        auth_user_id=None,
    )
    with pytest.raises(HTTPException) as caught:
        await router_module.trust_performance(user)
    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_route_passes_only_the_authenticated_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.presentation.routers import trust_engine as router_module

    seen: list[UUID] = []

    class _HistoryOk:
        async def execute(
            self, *, user_id: UUID, date_from: object = None, date_to: object = None
        ) -> object:
            seen.append(user_id)
            return SimpleNamespace(deals=[])

    class _AccountOk:
        async def execute(self, *, user_id: UUID) -> object:
            seen.append(user_id)
            return SimpleNamespace(profit="0", login=99887766, server="Srv")

    monkeypatch.setattr(
        router_module,
        "get_settings",
        lambda: SimpleNamespace(trust_engine_enabled=True),
    )
    monkeypatch.setattr(router_module, "_reader", lambda: (_HistoryOk(), _AccountOk()))
    user = AuthUserDTO(
        id=uuid4(),
        email="a@example.invalid",
        display_name="A",
        role="trader",
        status="active",
        auth_user_id=None,
    )
    report = await router_module.trust_performance(user)
    assert seen == [user.id, user.id]
    assert report["places_orders"] is False
    assert "99887766" not in json.dumps(report)
