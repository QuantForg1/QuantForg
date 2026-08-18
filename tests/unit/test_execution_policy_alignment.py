"""Execution-policy alignment: canonical desks vs Gateway whitelist.

Does not raise max_leverage, weaken min-lot, Safety, Risk, or OMS.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.domain.entities.execution_safety import ExecutionPolicy
from app.domain.entities.mt5_order import OrderIntent
from app.domain.enums.order import OrderSide, OrderType
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_SCALPING_UNIVERSE,
    MICRO_SAFE_USD_MAJOR_DESKS,
)
from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    discover_from_broker_rows,
    resolve_seed_to_broker_symbol,
)
from app.domain.trading.execution_universe import (
    canonical_execution_desks,
    canonical_execution_universe,
    execution_symbol_allowed,
)
from app.domain.trading.xauusd_specs import MAX_LEVERAGE
from app.domain.value_objects.mt5_order import LotSize
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter


@pytest.fixture
def multi_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: False,
    )


@pytest.mark.unit
def test_canonical_universe_is_scalping_desks_not_alpha_indices(
    multi_symbol: None,
) -> None:
    desks = canonical_execution_desks()
    assert desks == frozenset(DEFAULT_SCALPING_UNIVERSE)
    assert "USDCHF" in desks
    assert "AUDUSD" in desks
    for desk in MICRO_SAFE_USD_MAJOR_DESKS:
        assert desk in desks
    # Do not blindly execute scanner crosses / dead index aliases.
    assert "EURJPY" not in desks
    assert "GBPCAD" not in desks
    assert "GBPAUD" not in desks
    assert "CADCHF" not in desks
    assert "NAS100" not in desks
    assert "GER40" not in desks


@pytest.mark.unit
@pytest.mark.parametrize(
    ("desk", "broker"),
    [
        ("USDCHF", "USDCHF_I"),
        ("AUDUSD", "AUDUSD_I"),
        ("EURUSD", "EURUSD_I"),
        ("GBPUSD", "GBPUSD_I"),
        ("USDCAD", "USDCAD_I"),
        ("NZDUSD", "NZDUSD_I"),
    ],
)
def test_approved_broker_form_reaches_gateway_policy(
    multi_symbol: None,
    desk: str,
    broker: str,
) -> None:
    rows = [{"code": broker, "trade_mode": 4, "digits": 5}]
    discovered = discover_from_broker_rows(rows)
    assert resolve_seed_to_broker_symbol(desk, discovered=discovered) == broker
    policy = ExecutionPolicy()
    assert policy.allows_symbol(desk)
    assert policy.allows_symbol(broker)
    assert execution_symbol_allowed(broker, canonical_execution_universe())


@pytest.mark.unit
def test_unapproved_cross_remains_blocked(multi_symbol: None) -> None:
    policy = ExecutionPolicy()
    for sym in (
        "EURJPY",
        "EURJPY_I",
        "GBPCAD",
        "GBPCAD_I",
        "GBPAUD_I",
        "CADCHF_I",
        "AEXEUR",
    ):
        assert policy.allows_symbol(sym) is False
        assert execution_symbol_allowed(sym, canonical_execution_universe()) is False


@pytest.mark.unit
def test_leverage_2000_vs_max_1000_remains_blocked(multi_symbol: None) -> None:
    assert MAX_LEVERAGE == Decimal("1000")
    policy = ExecutionPolicy()
    assert policy.max_leverage == Decimal("1000")
    adapter = MT5Adapter(client=MockMT5Client())
    safety = ExecutionSafetyService(
        adapter=adapter,
        order_validation=MT5OrderValidationService(adapter=adapter),
        policy=policy,
    )
    intent = OrderIntent(
        symbol="USDCHF_I",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        volume=LotSize.of("0.01"),
    )
    ok, reasons, _warnings, checks = safety.evaluate_policy(
        intent,
        login=1,
        spread=Decimal("0.00007"),
        leverage=Decimal("2000"),
    )
    assert ok is False
    assert checks["symbol_whitelist"] is True
    assert checks["leverage_limit"] is False
    assert any("leverage 2000 exceeds max_leverage 1000" in r for r in reasons)


@pytest.mark.unit
def test_min_lot_and_safety_remain_authoritative(multi_symbol: None) -> None:
    policy = ExecutionPolicy()
    assert policy.min_lot == Decimal("0.01")
    adapter = MT5Adapter(client=MockMT5Client())
    adapter.initialize()
    from app.domain.interfaces.mt5_client import MT5LoginRequest

    adapter.login(MT5LoginRequest(login=7, password="p", server="S"))
    safety = ExecutionSafetyService(
        adapter=adapter,
        order_validation=MT5OrderValidationService(adapter=adapter),
        policy=policy,
    )
    intent = OrderIntent(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=LotSize.of("0.015"),
    )
    record = safety.decide(
        user_id=uuid4(),
        request_id="align-min-lot",
        intent=intent,
        connected=True,
        login=7,
        recent=[],
    )
    from app.domain.enums.execution import ExecutionDecision

    assert record.decision is ExecutionDecision.REJECT
    assert record.checks.get("volume_limits") is False


@pytest.mark.unit
def test_gold_only_safety_still_blocks_fx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )
    policy = ExecutionPolicy()
    assert policy.allows_symbol("XAUUSD")
    assert policy.allows_symbol("XAUUSD_I")
    assert not policy.allows_symbol("USDCHF_I")
    assert not policy.allows_symbol("AUDUSD")


@pytest.mark.unit
def test_optimizer_execute_now_intact(multi_symbol: None) -> None:
    from app.domain.institutional_trading.ai_scalping.execution_optimizer import (
        clear_optimizer_defers,
        evaluate_execution_moment,
        should_defer_submit,
    )

    clear_optimizer_defers()
    out = evaluate_execution_moment(
        symbol="USDCHF_I",
        decision=SimpleNamespace(
            action=SimpleNamespace(value="SELL"),
            symbol="USDCHF_I",
        ),
        snapshot=SimpleNamespace(entry_closes=(0.80, 0.801, 0.8005)),
        account=SimpleNamespace(atr=0.0012, mid_price=0.80),
        decision_key="align-opt",
    )
    assert out["final_state"] in {"EXECUTE_NOW", "WAIT_BOUNDED", "BLOCK"}
    assert out["forced_trades"] is False
    if out["final_state"] == "EXECUTE_NOW":
        assert should_defer_submit(out) is False
    clear_optimizer_defers()
