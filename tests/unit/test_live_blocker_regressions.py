"""Regressions for the three live blockers after 6ddb1f9a.

WAIT_NO_VALID_TP_ROOM stays a real net-floor reject. Account trading
disabled is only the account flag. The gold symbol is the catalogue
spelling, and the strategy symbol stays XAUUSD. No order is sent.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.domain.institutional_trading.ai_scalping.config import AiScalpingConfig
from app.domain.institutional_trading.ai_scalping.structure_targets import (
    compute_structure_targets,
)
from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    resolve_canonical_market_data_symbol,
)
from app.domain.institutional_trading.auto_trading import (
    AutoTradePolicy,
    evaluate_auto_trade_safety,
)
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.owner_live_limits import (
    OWNER_DAILY_LOSS_PCT,
    OWNER_MAX_AGGREGATE_OPEN_RISK_PCT,
    OWNER_MAX_LOT,
    OWNER_MAX_OPEN_POSITIONS,
    OWNER_MAX_PLANNED_RISK_PCT,
    OWNER_MAX_SPREAD,
    OWNER_MIN_REWARD_RISK,
    OWNER_MIN_TRADE_QUALITY,
    OWNER_SL_ATR_MULTIPLIER,
    evaluate_owner_entry,
)
from app.domain.institutional_trading.runtime_policy import (
    approved_baseline,
    reset_runtime_policy,
    use_runtime_policy,
)
from app.domain.trading.gold_only import (
    GOLD_SYMBOL,
    autonomous_execution_symbols,
    canonical_gold_execution_symbol,
)
from services.mt5_gateway.order_guard import (
    RETCODE_ORDER_GUARD_REJECTED,
    ClientOrderIdRegistry,
    OrderGuardRejected,
    enforce_order_guard,
)
from services.mt5_gateway.symbol_resolve import resolve_catalogue_symbol
from tests.unit.test_auto_trading_safety import _all_pass_facts
from tests.unit.test_owner_sl15_tp2 import _snapshot

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ENTRY = Decimal("4133.00")
ATR = Decimal("2.00")


def test_owner_policy_floors_stay_at_the_authorized_values() -> None:
    assert Decimal("20.0") == OWNER_MAX_PLANNED_RISK_PCT
    assert Decimal("30.0") == OWNER_MAX_AGGREGATE_OPEN_RISK_PCT
    assert Decimal("48.0") == OWNER_DAILY_LOSS_PCT
    assert Decimal("0.50") == OWNER_MIN_REWARD_RISK
    assert OWNER_MIN_TRADE_QUALITY == 70
    assert Decimal("0.01") == OWNER_MAX_LOT
    assert Decimal("1.00") == OWNER_MAX_SPREAD
    assert OWNER_MAX_OPEN_POSITIONS == 5
    assert Decimal("1.00") == OWNER_SL_ATR_MULTIPLIER
    assert GOLD_SYMBOL == "XAUUSD"


@pytest.fixture
def gold_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )


def test_catalogue_only_xauusd_stays_xauusd(gold_only: None) -> None:
    rows = ({"code": "XAUUSD", "trade_mode": 4},)
    assert (
        resolve_canonical_market_data_symbol("XAUUSD", broker_symbol_rows=rows)
        == "XAUUSD"
    )
    assert autonomous_execution_symbols(broker_symbol_rows=rows) == ("XAUUSD",)
    assert resolve_catalogue_symbol("XAUUSD", {"XAUUSD": "XAUUSD"}) == "XAUUSD"
    assert resolve_catalogue_symbol("XAUUSD_I", {"XAUUSD": "XAUUSD"}) == "XAUUSD"


def test_catalogue_only_suffix_uses_that_exact_spelling(gold_only: None) -> None:
    rows = ({"code": "XAUUSD_i", "trade_mode": 4},)
    assert (
        resolve_canonical_market_data_symbol("XAUUSD", broker_symbol_rows=rows)
        == "XAUUSD_i"
    )
    assert autonomous_execution_symbols(broker_symbol_rows=rows) == ("XAUUSD_i",)
    assert resolve_catalogue_symbol("XAUUSD", {"XAUUSD_I": "XAUUSD_i"}) == "XAUUSD_i"


def test_both_spellings_prefer_the_exact_seed(gold_only: None) -> None:
    rows = (
        {"code": "XAUUSD", "trade_mode": 4},
        {"code": "XAUUSD_i", "trade_mode": 4},
    )
    assert (
        resolve_canonical_market_data_symbol("XAUUSD", broker_symbol_rows=rows)
        == "XAUUSD"
    )
    assert (
        resolve_canonical_market_data_symbol("XAUUSD_i", broker_symbol_rows=rows)
        == "XAUUSD_i"
    )


def test_no_catalogue_does_not_invent_a_suffix(gold_only: None) -> None:
    assert autonomous_execution_symbols() == ("XAUUSD",)
    assert autonomous_execution_symbols(broker_symbol_rows=()) == ("XAUUSD",)
    assert (
        autonomous_execution_symbols(
            broker_symbol_rows=({"code": "EURUSD", "trade_mode": 4},)
        )
        == ()
    )
    assert canonical_gold_execution_symbol("XAUUSD") == "XAUUSD"
    assert resolve_canonical_market_data_symbol("XAUUSD", broker_symbol_rows=()) == ""


def test_invalid_structure_is_not_stretched_to_clear_0_50() -> None:
    targets = compute_structure_targets(
        _snapshot(highs=("4133.40", "4134.00", "4140.00")),  # type: ignore[arg-type]
        direction=TradeDirection.BUY,
        entry=ENTRY,
        atr=ATR,
        config=AiScalpingConfig(),
    )
    assert targets.take_profit is None
    assert targets.expected_net_rr is not None
    assert targets.expected_net_rr < Decimal("0.50")
    assert targets.expected_rr is not None
    assert "4140.00" not in targets.reason
    assert "TP not stretched" in targets.reason


def test_valid_structure_clears_the_net_floor() -> None:
    targets = compute_structure_targets(
        _snapshot(highs=("4138.00",)),  # type: ignore[arg-type]
        direction=TradeDirection.BUY,
        entry=ENTRY,
        atr=ATR,
        config=AiScalpingConfig(),
    )
    assert targets.take_profit == Decimal("4138.00")
    assert targets.expected_net_rr is not None
    assert targets.expected_net_rr >= Decimal("0.50")


def _entry(**overrides: object) -> list[str]:
    args: dict[str, object] = {
        "symbol": "XAUUSD",
        "side": "sell",
        "volume": Decimal("0.01"),
        "entry": Decimal("4116.43"),
        "stop_loss": Decimal("4118.03"),
        "take_profit": Decimal("4112.93"),
        "spread": Decimal("0.38"),
        "contract_size": Decimal("100"),
        "equity": Decimal("50.84"),
        "commission": Decimal("0"),
    }
    args.update(overrides)
    return evaluate_owner_entry(**args)  # type: ignore[arg-type]


def test_spread_minimum_lot_and_stop_distance_constraints() -> None:
    assert _entry(spread=Decimal("1.00")) == []
    assert any(r.startswith("OWNER_MAX_SPREAD") for r in _entry(spread=Decimal("1.01")))
    assert any(
        r.startswith("OWNER_STOPS_LEVEL")
        for r in _entry(min_stop_distance=Decimal("2.00"))
    )
    assert _entry(min_stop_distance=Decimal("1.00")) == []
    token = use_runtime_policy({**approved_baseline(), "min_lot": "0.01"})
    try:
        assert any(
            r.startswith("OWNER_MIN_LOT") for r in _entry(volume=Decimal("0.001"))
        )
        assert _entry(volume=Decimal("0.01")) == []
    finally:
        reset_runtime_policy(token)


def test_account_flag_terminal_flag_and_symbol_flag_stay_distinct() -> None:
    policy = AutoTradePolicy(enabled=True)
    account = evaluate_auto_trade_safety(
        policy,
        _all_pass_facts(
            account_trading_enabled=False,
            no_broker_restrictions=False,
            mt5_autotrading_enabled=True,
        ),
    )
    assert account.failed_reasons[0] == "Account trading is disabled"
    terminal = evaluate_auto_trade_safety(
        policy,
        _all_pass_facts(
            account_trading_enabled=True,
            mt5_autotrading_enabled=False,
            mt5_autotrading_known=True,
        ),
    )
    assert "Account trading is disabled" not in terminal.failed_reasons
    assert any("AutoTrading is disabled" in r for r in terminal.failed_reasons)
    symbol = evaluate_auto_trade_safety(
        policy, _all_pass_facts(symbol="XAUUSD", symbol_tradable=False)
    )
    assert "Account trading is disabled" not in symbol.failed_reasons
    assert any("not tradable" in r for r in symbol.failed_reasons)
    enabled = evaluate_auto_trade_safety(policy, _all_pass_facts())
    assert enabled.allowed is True


def test_duplicate_submission_and_missing_stops_never_fill() -> None:
    quote = {
        "bid": "3877.656",
        "ask": "3878.000",
        "specs": {
            "contract_size": "100",
            "tick_size": "0.001",
            "tick_value": "0.1",
            "point": "0.001",
        },
    }
    body = {
        "symbol": "XAUUSD",
        "action": "sell",
        "volume": 0.01,
        "sl": 3881.306,
        "tp": 3874.000,
        "position": 0,
        "client_order_id": "same-id",
        "commission": 0,
        "slippage": 10,
    }
    registry = ClientOrderIdRegistry()
    assert (
        enforce_order_guard(
            body,
            equity=Decimal("33.52"),
            quote=quote,
            positions_lookup=lambda: [],
            registry=registry,
        )
        == "entry"
    )
    with pytest.raises(OrderGuardRejected) as dup:
        enforce_order_guard(
            dict(body),
            equity=Decimal("33.52"),
            quote=quote,
            positions_lookup=lambda: [],
            registry=registry,
        )
    assert dup.value.code == "GUARD_DUPLICATE_CLIENT_ORDER_ID"
    assert dup.value.as_detail()["deal_ticket"] == 0
    naked = dict(body)
    naked["sl"] = 0
    naked["client_order_id"] = "naked"
    with pytest.raises(OrderGuardRejected) as missing:
        enforce_order_guard(
            naked,
            equity=Decimal("33.52"),
            quote=quote,
            positions_lookup=lambda: [],
            registry=ClientOrderIdRegistry(),
        )
    assert missing.value.code == "GUARD_SL_REQUIRED"
    assert missing.value.as_detail()["retcode"] == RETCODE_ORDER_GUARD_REJECTED
    assert missing.value.as_detail()["order_ticket"] == 0


def test_mock_gateway_fill_requires_a_deal_and_keeps_stops() -> None:
    import app.infrastructure.brokers.mt5.gateway_client as mod
    from app.domain.entities.mt5_order import TradeRequest

    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if body["client_order_id"] == "guarded":
            return httpx.Response(
                403,
                json={
                    "detail": {
                        "ok": False,
                        "retcode": 90002,
                        "code": "GUARD_MAX_RISK",
                        "comment": "planned loss exceeds 20% of equity",
                        "order_ticket": 0,
                        "deal_ticket": 0,
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "ok": True,
                "retcode": 10009,
                "order_ticket": 11,
                "deal_ticket": 22,
                "volume": 0.01,
                "price": 3878.0,
                "comment": "Request executed",
            },
        )

    transport = httpx.MockTransport(handler)
    original = mod.httpx.Client

    class PatchedClient(original):  # type: ignore[valid-type,misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    client = mod.GatewayMT5Client(base_url="https://gw.example", token="tok")
    request = TradeRequest(
        symbol="XAUUSD",
        action="sell",
        volume=Decimal("0.01"),
        price=Decimal("3877.656"),
        stop_loss=Decimal("3881.306"),
        take_profit=Decimal("3874.000"),
        deviation=10,
        magic=260720,
        client_order_id="paper-fill",
    )
    guarded = TradeRequest(
        symbol="XAUUSD",
        action="sell",
        volume=Decimal("0.01"),
        price=Decimal("3877.656"),
        stop_loss=Decimal("3884.006"),
        take_profit=Decimal("3870.000"),
        deviation=10,
        magic=260720,
        client_order_id="guarded",
    )
    mod.httpx.Client = PatchedClient  # type: ignore[misc]
    try:
        object.__setattr__(client, "_connected", True)
        with pytest.raises(RuntimeError, match="90002"):
            client.order_send(guarded)
        filled = client.order_send(request)
    finally:
        mod.httpx.Client = original  # type: ignore[misc]

    assert seen[0]["symbol"] == "XAUUSD"
    assert seen[0]["sl"] > 0
    assert seen[0]["tp"] > 0
    assert filled.retcode == 10009
    assert filled.order_ticket == 11
    assert filled.deal_ticket == 22
    assert filled.request is not None
    assert filled.request.stop_loss == Decimal("3881.306")
    assert filled.request.take_profit == Decimal("3874.000")


class _TradeMode:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.info_calls: list[str] = []

    def symbol_info(self, symbol: str) -> Any:
        self.info_calls.append(symbol)
        return type("Spec", (), {"trade_mode": self.mode})()


async def _call_sync(fn: Any, /, *args: Any, **kwargs: Any) -> Any:
    return fn(*args, **kwargs)


def _pick_runtime(mode: str) -> Any:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.application.services.institutional_ite_runtime import (
        InstitutionalIteRuntime,
    )

    runtime = InstitutionalIteRuntime(
        plane=MagicMock(),
        reliability=MagicMock(),
        probes=MagicMock(),
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=SimpleNamespace(engine=SimpleNamespace(_positions={})),
        mt5_adapter=_TradeMode(mode),
    )
    runtime._offload_blocking_io = _call_sync  # type: ignore[method-assign]

    async def _preferred() -> str:
        return "XAUUSD"

    runtime._multi_asset_preferred_symbol = _preferred  # type: ignore[method-assign]
    runtime._last_multi_asset_scan = {
        "as_of": "2026-10-30T20:45:00Z",
        "enabled": True,
        "eligible_symbols": ["XAUUSD"],
        "eligible_count": 1,
        "note": "scan_complete",
    }
    return runtime


@pytest.fixture
def gold_only_pick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )
    from app.application.services.market_closed_cooldown import clear_market_closed

    clear_market_closed("XAUUSD")


@pytest.mark.asyncio
async def test_full_mode_bare_xauusd_stays_executable(
    gold_only_pick: None,
) -> None:
    runtime = _pick_runtime("full")
    chosen = await runtime._pick_executable_symbol_async()
    assert chosen == "XAUUSD"
    assert runtime._last_pick_abort is None
    runtime.guarded_submit.assert_not_called()


@pytest.mark.asyncio
async def test_close_only_xauusd_blocks_without_a_generic_abort(
    gold_only_pick: None,
) -> None:
    from app.application.services.closeonly_symbol_router import (
        CLOSE_ONLY_ENTRY_BLOCK,
        SYMBOL_CLOSE_ONLY,
        waiting_cycle_detail,
    )

    runtime = _pick_runtime("closeonly")
    chosen = await runtime._pick_executable_symbol_async()
    assert chosen is None
    assert runtime._last_pick_abort == SYMBOL_CLOSE_ONLY
    assert CLOSE_ONLY_ENTRY_BLOCK in waiting_cycle_detail(SYMBOL_CLOSE_ONLY)
    runtime.guarded_submit.assert_not_called()


def test_close_only_does_not_hide_a_stricter_blocker() -> None:
    from app.application.services.closeonly_symbol_router import (
        CLOSE_ONLY_ENTRY_BLOCK,
        close_only_primary,
    )

    assert close_only_primary(None, None, "closeonly") == (
        CLOSE_ONLY_ENTRY_BLOCK,
        "broker",
    )
    assert close_only_primary("Kill switch armed", "operator", "closeonly") == (
        "Kill switch armed",
        "operator",
    )
    assert close_only_primary(None, None, "full") == (None, None)
