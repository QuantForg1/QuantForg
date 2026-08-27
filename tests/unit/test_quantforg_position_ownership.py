"""QuantForg vs manual position ownership — capacity, duplicate, PME, scanner.

Never sends a live order_send.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.application.services.mt5_position_truth import (
    apply_mt5_position_truth,
    force_sync_positions,
)
from app.domain.entities.mt5_portfolio import MT5Position
from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    may_add_scalping_trade,
)
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import AccountRiskState
from app.domain.institutional_trading.management.class_policy import (
    TRADE_CLASS_UNKNOWN,
    encode_execution_comment,
    resolve_class_management,
)
from app.domain.institutional_trading.management.engine import PositionManagementEngine
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    OmsManageResult,
    PositionLifecycleState,
    PositionManageContext,
)
from app.domain.institutional_trading.operations.position_plan import (
    HOLD_MAX_OPEN_TRADES,
    SCALP_MAX_OPEN_TRADES,
    build_position_plan,
    remaining_quantforg_capacity,
)
from app.domain.institutional_trading.operations.quantforg_position_cap import (
    OWNER_MANUAL,
    OWNER_OTHER_EA,
    OWNER_QUANTFORG,
    OWNER_UNKNOWN,
    QUANTFORG_MAGIC,
    classify_position_owner,
    count_quantforg_positions,
    is_quantforg_owned_position,
    is_quantforg_same_symbol_open,
    ownership_observability,
    same_symbol_ownership_facts,
    snapshot_quantforg_positions,
)
from app.domain.institutional_trading.operations.trade_classifier import TradeClass
from app.domain.institutional_trading.production_hardening.position_recovery import (
    recover_positions_from_mt5,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

OPENED = datetime(2026, 8, 23, 16, 0, tzinfo=UTC)


def _mt5(
    ticket: int,
    *,
    symbol: str = "XAUUSD_i",
    magic: int = 0,
    comment: str = "",
    side: str = "buy",
) -> MT5Position:
    return MT5Position(
        ticket=ticket,
        symbol=symbol,
        side=side,
        volume=Decimal("0.02"),
        open_price=Decimal("3400"),
        current_price=Decimal("3401"),
        magic=magic,
        comment=comment,
    )


class _FakeAdapter:
    def __init__(self, rows: list[MT5Position]) -> None:
        self._rows = rows

    def list_positions(self) -> list[MT5Position]:
        return list(self._rows)


class _CapturingOms:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def modify_sltp(self, **kwargs: object) -> OmsManageResult:
        self.calls.append({"op": "modify_sltp", **kwargs})
        return OmsManageResult(outcome="success", message="modified", retcode=10009)

    def partial_close(self, **kwargs: object) -> OmsManageResult:
        self.calls.append({"op": "partial_close", **kwargs})
        return OmsManageResult(outcome="success", message="partial", retcode=10009)

    def close_position(self, **kwargs: object) -> OmsManageResult:
        self.calls.append({"op": "close_position", **kwargs})
        return OmsManageResult(outcome="success", message="closed", retcode=10009)


def _managed(
    ticket: int,
    *,
    magic: int = QUANTFORG_MAGIC,
    symbol: str = "XAUUSD_i",
    trade_class: str = "SCALP",
) -> ManagedPosition:
    return ManagedPosition(
        ticket=ticket,
        symbol=symbol,
        side="buy",
        entry_price=Decimal("3400"),
        initial_volume=Decimal("0.02"),
        remaining_volume=Decimal("0.02"),
        initial_stop=Decimal("3390"),
        risk_distance=Decimal("10"),
        opened_at=OPENED,
        state=PositionLifecycleState.OPEN,
        current_stop=Decimal("3390"),
        current_tp=Decimal("3420"),
        magic=magic,
        comment="ite:v1:S:abc" if magic == QUANTFORG_MAGIC else "manual",
        trade_class=trade_class if magic == QUANTFORG_MAGIC else "",
        management_profile=(
            resolve_class_management(trade_class).profile_name
            if magic == QUANTFORG_MAGIC
            else ""
        ),
    )


def _ctx(price: str = "3410") -> PositionManageContext:
    return PositionManageContext(
        now=OPENED + timedelta(minutes=5),
        current_price=Decimal(price),
        atr=Decimal("5"),
        mid_price=Decimal(price),
        position_still_open=True,
        user_id=uuid4(),
        request_id="own-test",
        connected=True,
    )


def test_magic_quantforg_gold_is_owned() -> None:
    row = _mt5(1, magic=QUANTFORG_MAGIC)
    assert is_quantforg_owned_position(row) is True
    assert classify_position_owner(row) == OWNER_QUANTFORG
    obs = ownership_observability(row)
    assert obs["consumes_quantforg_capacity"] is True
    assert obs["managed_by_pme"] is True
    assert obs["is_manual"] is False


def test_magic_zero_gold_is_manual() -> None:
    row = _mt5(562330473, magic=0)
    assert is_quantforg_owned_position(row) is False
    assert classify_position_owner(row) == OWNER_MANUAL
    obs = ownership_observability(row)
    assert obs["consumes_quantforg_capacity"] is False
    assert obs["managed_by_pme"] is False
    assert obs["is_manual"] is True


def test_other_ea_magic_is_not_owned() -> None:
    row = _mt5(3, magic=999001)
    assert is_quantforg_owned_position(row) is False
    assert classify_position_owner(row) == OWNER_OTHER_EA


def test_quantforg_magic_other_symbol_not_gold_owned() -> None:
    row = _mt5(4, symbol="EURUSD", magic=QUANTFORG_MAGIC)
    assert is_quantforg_owned_position(row) is False
    assert classify_position_owner(row) == OWNER_UNKNOWN


def test_comment_prefix_cannot_promote_manual() -> None:
    row = _mt5(5, magic=0, comment="ite:v1:S:deadbeef")
    assert is_quantforg_owned_position(row) is False
    assert classify_position_owner(row) == OWNER_MANUAL


def test_four_manual_zero_quantforg_count() -> None:
    rows = [_mt5(100 + i, magic=0) for i in range(4)]
    assert count_quantforg_positions(rows, symbol="XAUUSD_i") == 0
    snap = snapshot_quantforg_positions(rows, symbol="XAUUSD_i", configured_max=10)
    assert snap.account_count == 4
    assert snap.quantforg_count == 0
    assert snap.capacity_available is True


def test_manual_does_not_consume_quantforg_capacity() -> None:
    remaining = remaining_quantforg_capacity(
        current_count=count_quantforg_positions(
            [_mt5(1, magic=0)], symbol="XAUUSD_i"
        ),
        configured_max=10,
        class_cap=10,
    )
    assert remaining == 10


def test_quantforg_gold_consumes_capacity() -> None:
    rows = [_mt5(10, magic=QUANTFORG_MAGIC)]
    assert count_quantforg_positions(rows, symbol="XAUUSD_i") == 1
    remaining = remaining_quantforg_capacity(
        current_count=1, configured_max=10, class_cap=10
    )
    assert remaining == 9


def test_mixed_manual_and_quantforg_counts() -> None:
    rows = [
        _mt5(1, magic=0),
        _mt5(2, magic=0),
        _mt5(3, magic=QUANTFORG_MAGIC),
        _mt5(4, magic=888),
    ]
    assert count_quantforg_positions(rows, symbol="XAUUSD_i") == 1
    facts = same_symbol_ownership_facts(rows, candidate_symbol="XAUUSD_i")
    assert facts["quantforg_open_count"] == 1
    assert facts["account_open_count"] == 4
    assert facts["manual_same_symbol_count"] == 2
    assert facts["already_open"] is True
    assert facts["already_open_reason"] == "QUANTFORG_SAME_SYMBOL_OPEN"


def test_quantforg_close_releases_capacity() -> None:
    before = [_mt5(1, magic=QUANTFORG_MAGIC), _mt5(2, magic=0)]
    after = [_mt5(2, magic=0)]
    assert count_quantforg_positions(before) == 1
    assert count_quantforg_positions(after) == 0
    assert snapshot_quantforg_positions(after, configured_max=5).capacity_available


def test_manual_close_does_not_change_quantforg_capacity() -> None:
    before = [_mt5(1, magic=0), _mt5(2, magic=0), _mt5(3, magic=QUANTFORG_MAGIC)]
    after = [_mt5(2, magic=0), _mt5(3, magic=QUANTFORG_MAGIC)]
    assert count_quantforg_positions(before) == count_quantforg_positions(after) == 1


def test_manual_same_symbol_does_not_trigger_duplicate() -> None:
    facts = same_symbol_ownership_facts(
        [_mt5(562330473, magic=0)],
        candidate_symbol="XAUUSD_i",
    )
    assert facts["already_open"] is False
    assert facts["candidate_allowed"] is True
    assert facts["already_open_reason"] == "MANUAL_SAME_SYMBOL_PRESENT"
    assert is_quantforg_same_symbol_open("XAUUSD_i", set()) is False
    add = may_add_scalping_trade(
        open_positions=0,
        max_open=10,
        new_confidence=78,
        best_open_confidence=None,
        new_direction="BUY",
        open_directions=(),
    )
    assert add.allow is True


def test_quantforg_same_symbol_triggers_duplicate_set() -> None:
    facts = same_symbol_ownership_facts(
        [_mt5(9, magic=QUANTFORG_MAGIC)],
        candidate_symbol="XAUUSD_i",
    )
    assert facts["already_open"] is True
    assert facts["candidate_allowed"] is False
    assert facts["already_open_reason"] == "QUANTFORG_SAME_SYMBOL_OPEN"
    add = may_add_scalping_trade(
        open_positions=1,
        max_open=10,
        new_confidence=70,
        best_open_confidence=78,
        new_direction="BUY",
        open_directions=("BUY",),
        require_improvement=True,
    )
    assert add.allow is False


def test_opposite_direction_follows_existing_duplicate_guard() -> None:
    add = may_add_scalping_trade(
        open_positions=1,
        max_open=10,
        new_confidence=70,
        best_open_confidence=90,
        new_direction="SELL",
        open_directions=("BUY",),
        require_improvement=True,
    )
    assert add.allow is True
    assert "Opposite direction" in add.reason


def test_manual_is_not_addon_blocker() -> None:
    facts = same_symbol_ownership_facts(
        [_mt5(1, magic=0, side="sell")],
        candidate_symbol="XAUUSD_i",
    )
    assert facts["candidate_allowed"] is True
    add = may_add_scalping_trade(
        open_positions=facts["quantforg_open_count"],
        max_open=10,
        new_confidence=78,
        best_open_confidence=None,
        new_direction="BUY",
        open_directions=(),
    )
    assert add.allow is True


def test_quantforg_still_respects_same_symbol_duplicate() -> None:
    assert is_quantforg_same_symbol_open("XAUUSD_i", {"XAUUSD_I"}) is True
    assert is_quantforg_same_symbol_open("XAUUSD_i", {"XAUUSD"}) is True


def test_manual_not_recovered_into_pme(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUANTFORG_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.domain.institutional_trading.production_hardening.position_recovery._state_path",
        lambda: tmp_path / "pme.json",
    )
    engine = PositionManagementEngine(oms=_CapturingOms())  # type: ignore[arg-type]
    live = _mt5(562330473, magic=0)
    out = recover_positions_from_mt5(
        mt5_adapter=_FakeAdapter([live]),
        engine=engine,
        symbol="XAUUSD_i",
    )
    assert out["ok"] is True
    assert out["registered"] == 0
    assert out.get("skipped_non_owned") == 1
    assert engine.get(562330473) is None


def test_manual_gets_no_trade_class_or_profile(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUANTFORG_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.domain.institutional_trading.production_hardening.position_recovery._state_path",
        lambda: tmp_path / "pme.json",
    )
    engine = PositionManagementEngine(oms=_CapturingOms())  # type: ignore[arg-type]
    recover_positions_from_mt5(
        mt5_adapter=_FakeAdapter([_mt5(8, magic=0)]),
        engine=engine,
        symbol="XAUUSD_i",
    )
    assert engine._positions == {}


def test_manual_receives_no_sl_tp_mutation() -> None:
    oms = _CapturingOms()
    engine = PositionManagementEngine(oms=oms)  # type: ignore[arg-type]
    pos = _managed(562330473, magic=0)
    engine._positions[pos.ticket] = pos
    result = engine.evaluate(pos.ticket, _ctx("3410"))
    assert result.action is ManageActionKind.NOOP
    assert result.record.reason == "NOT_QUANTFORG_OWNED"
    assert oms.calls == []
    assert pos.current_stop == Decimal("3390")


def test_register_rejects_manual() -> None:
    engine = PositionManagementEngine(oms=_CapturingOms())  # type: ignore[arg-type]
    engine.register(_managed(11, magic=0))
    assert engine.get(11) is None


def test_quantforg_recovered_with_proven_class(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUANTFORG_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.domain.institutional_trading.production_hardening.position_recovery._state_path",
        lambda: tmp_path / "pme.json",
    )
    engine = PositionManagementEngine(oms=_CapturingOms())  # type: ignore[arg-type]
    comment = encode_execution_comment("ite:v1", "efe330dd625e", "SCALP")
    live = _mt5(20, magic=QUANTFORG_MAGIC, comment=comment)
    out = recover_positions_from_mt5(
        mt5_adapter=_FakeAdapter([live]),
        engine=engine,
        symbol="XAUUSD_i",
    )
    assert out["registered"] == 1
    pos = engine.get(20)
    assert pos is not None
    assert pos.trade_class == "SCALP"
    assert pos.management_profile
    assert pos.magic == QUANTFORG_MAGIC


def test_unknown_quantforg_class_stays_explicit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUANTFORG_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.domain.institutional_trading.production_hardening.position_recovery._state_path",
        lambda: tmp_path / "pme.json",
    )
    engine = PositionManagementEngine(oms=_CapturingOms())  # type: ignore[arg-type]
    live = _mt5(21, magic=QUANTFORG_MAGIC, comment="ite:v1:deadbeefcafe")
    recover_positions_from_mt5(
        mt5_adapter=_FakeAdapter([live]),
        engine=engine,
        symbol="XAUUSD_i",
    )
    pos = engine.get(21)
    assert pos is not None
    assert pos.trade_class == TRADE_CLASS_UNKNOWN


def test_force_sync_purges_manual_from_pme() -> None:
    engine = PositionManagementEngine(oms=_CapturingOms())  # type: ignore[arg-type]
    engine._positions[562330473] = _managed(562330473, magic=0)
    sync = force_sync_positions(
        _FakeAdapter([_mt5(562330473, magic=0)]),
        symbol="XAUUSD_i",
        internal_positions=1,
        position_engine=engine,
    )
    assert sync.quantforg_positions == 0
    assert engine.get(562330473) is None
    account = apply_mt5_position_truth(
        AccountRiskState(
            equity=Decimal("10000"),
            open_positions=4,
            already_in_trade=True,
        ),
        sync,
    )
    assert account.open_positions == 0
    assert account.already_in_trade is False
    assert account.account_open_positions == 1


@pytest.mark.asyncio
async def test_scanner_manual_same_symbol_keeps_buy_eligible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from app.application.services.institutional_multi_asset_scanner import (
        run_institutional_multi_asset_scan,
    )
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )

    async def _fake_score(_mt5: Any, symbol: str, **_k: Any) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "reject": False,
            "direction": "BUY",
            "ai_confidence": 91,
            "trade_quality": 92,
            "liquidity": 85,
            "expected_rr": "1.80",
            "spread_score": 90,
            "market_regime": "strong_trend",
            "setup_family": "trend_continuation",
            "execution_health_ok": True,
            "atr_pct": "0.90",
            "momentum": 72,
            "structure_score": 68,
            "factors": {
                "momentum": 72,
                "trend_strength": 70,
                "mtf": 80,
                "volume": 70,
                "bos": 60,
                "choch": 55,
            },
        }

    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.score_symbol_for_scan",
        _fake_score,
    )
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.resolve_scan_universe",
        lambda *_a, **_k: ("XAUUSD",),
    )
    engine = SimpleNamespace(
        _positions={1: _managed(1, magic=0, symbol="XAUUSD")}
    )
    cfg = replace(
        DEFAULT_AI_SCALPING_CONFIG,
        universe=("XAUUSD",),
        adaptive_cooldown_enabled=False,
        multi_strategy_enabled=True,
        dynamic_universe_enabled=False,
        parallel_scan_enabled=False,
        live_symbol_learning_enabled=False,
    )
    out = await run_institutional_multi_asset_scan(
        mt5_adapter=_FakeAdapter([_mt5(1, symbol="XAUUSD", magic=0)]),
        position_engine=engine,
        config=cfg,
        open_positions=0,
    )
    assert out.get("blocked_by_portfolio") is False
    assert int(out.get("quantforg_open_count") or 0) == 0
    assert int(out.get("manual_same_symbol_count") or 0) >= 1
    assert out.get("already_open_reason") == "MANUAL_SAME_SYMBOL_PRESENT"
    assert "XAUUSD" in {s.upper() for s in (out.get("eligible_symbols") or [])}
    assert out.get("best_symbol")


@pytest.mark.asyncio
async def test_scanner_manual_same_symbol_keeps_sell_eligible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from app.application.services.institutional_multi_asset_scanner import (
        run_institutional_multi_asset_scan,
    )
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )

    async def _fake_score(_mt5: Any, symbol: str, **_k: Any) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "reject": False,
            "direction": "SELL",
            "ai_confidence": 91,
            "trade_quality": 92,
            "liquidity": 85,
            "expected_rr": "1.80",
            "spread_score": 90,
            "market_regime": "strong_trend",
            "setup_family": "trend_continuation",
            "execution_health_ok": True,
            "atr_pct": "0.90",
            "momentum": 72,
            "structure_score": 68,
            "factors": {
                "momentum": 72,
                "trend_strength": 70,
                "mtf": 80,
                "volume": 70,
                "bos": 60,
                "choch": 55,
            },
        }

    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.score_symbol_for_scan",
        _fake_score,
    )
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.resolve_scan_universe",
        lambda *_a, **_k: ("XAUUSD",),
    )
    cfg = replace(
        DEFAULT_AI_SCALPING_CONFIG,
        universe=("XAUUSD",),
        adaptive_cooldown_enabled=False,
        multi_strategy_enabled=True,
        dynamic_universe_enabled=False,
        parallel_scan_enabled=False,
        live_symbol_learning_enabled=False,
    )
    out = await run_institutional_multi_asset_scan(
        mt5_adapter=_FakeAdapter([_mt5(1, symbol="XAUUSD", magic=0)]),
        config=cfg,
        open_positions=0,
    )
    assert out.get("best_symbol")
    assert int(out.get("quantforg_open_count") or 0) == 0


@pytest.mark.asyncio
async def test_scanner_quantforg_same_symbol_blocks_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from app.application.services.institutional_multi_asset_scanner import (
        run_institutional_multi_asset_scan,
    )
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )

    async def _fake_score(_mt5: Any, symbol: str, **_k: Any) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "reject": False,
            "direction": "BUY",
            "ai_confidence": 91,
            "trade_quality": 92,
            "liquidity": 85,
            "expected_rr": "1.80",
            "spread_score": 90,
            "market_regime": "strong_trend",
            "setup_family": "trend_continuation",
            "execution_health_ok": True,
            "atr_pct": "0.90",
            "momentum": 72,
            "structure_score": 68,
            "factors": {
                "momentum": 72,
                "trend_strength": 70,
                "mtf": 80,
                "volume": 70,
                "bos": 60,
                "choch": 55,
            },
        }

    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.score_symbol_for_scan",
        _fake_score,
    )
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.resolve_scan_universe",
        lambda *_a, **_k: ("XAUUSD",),
    )
    cfg = replace(
        DEFAULT_AI_SCALPING_CONFIG,
        universe=("XAUUSD",),
        adaptive_cooldown_enabled=False,
        multi_strategy_enabled=True,
        dynamic_universe_enabled=False,
        parallel_scan_enabled=False,
        live_symbol_learning_enabled=False,
    )
    out = await run_institutional_multi_asset_scan(
        mt5_adapter=_FakeAdapter([_mt5(9, symbol="XAUUSD", magic=QUANTFORG_MAGIC)]),
        config=cfg,
        open_positions=1,
    )
    assert out.get("already_open_reason") == "QUANTFORG_SAME_SYMBOL_OPEN"
    assert out.get("best_symbol") == "XAUUSD"
    assert "XAUUSD" in list(out.get("eligible_symbols") or [])


def test_manual_does_not_reduce_effective_count() -> None:
    plan = build_position_plan(
        cycle_id="c1",
        snapshot_id="s1",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=95,
        confidence=90,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10, trading_mode="scalping"),
        risk_allowed_count=10,
        portfolio_allowed_count=10,
        broker_allowed_count=10,
        min_lot=Decimal("0.01"),
    )
    assert plan.effective_count >= 2
    assert plan.effective_count <= SCALP_MAX_OPEN_TRADES


def test_quantforg_positions_reduce_remaining_capacity() -> None:
    plan = build_position_plan(
        cycle_id="c1",
        snapshot_id="s1",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=95,
        confidence=90,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=3,
        ite_config=ITEConfig(max_open_trades=10, trading_mode="scalping"),
        risk_allowed_count=10,
        portfolio_allowed_count=10,
        broker_allowed_count=10,
        min_lot=Decimal("0.01"),
    )
    empty = build_position_plan(
        cycle_id="c1",
        snapshot_id="s1",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=95,
        confidence=90,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10, trading_mode="scalping"),
        risk_allowed_count=10,
        portfolio_allowed_count=10,
        broker_allowed_count=10,
        min_lot=Decimal("0.01"),
    )
    assert plan.effective_count < empty.effective_count


def test_effective_count_follows_min_stack() -> None:
    plan = build_position_plan(
        cycle_id="c1",
        snapshot_id="s1",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=99,
        confidence=99,
        aggregate_lots=Decimal("1.00"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10, trading_mode="scalping"),
        risk_allowed_count=2,
        portfolio_allowed_count=8,
        broker_allowed_count=7,
        min_lot=Decimal("0.01"),
    )
    assert plan.effective_count == 2


def test_scalp_can_target_up_to_ten() -> None:
    plan = build_position_plan(
        cycle_id="c1",
        snapshot_id="s1",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=99,
        confidence=99,
        aggregate_lots=Decimal("1.00"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10, trading_mode="scalping"),
        risk_allowed_count=10,
        portfolio_allowed_count=10,
        broker_allowed_count=10,
        min_lot=Decimal("0.01"),
    )
    assert plan.effective_count == SCALP_MAX_OPEN_TRADES
    assert plan.effective_count != 1


def test_hold_can_target_up_to_five() -> None:
    plan = build_position_plan(
        cycle_id="c1",
        snapshot_id="s1",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.HOLD,
        opportunity_score=99,
        confidence=99,
        aggregate_lots=Decimal("1.00"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=5, trading_mode="swing"),
        risk_allowed_count=5,
        portfolio_allowed_count=5,
        broker_allowed_count=5,
        min_lot=Decimal("0.01"),
    )
    assert plan.effective_count == HOLD_MAX_OPEN_TRADES
    assert plan.effective_count != 1


def test_account_open_still_observable_for_global_risk() -> None:
    rows = [_mt5(i, magic=0) for i in range(1, 5)]
    sync = force_sync_positions(
        _FakeAdapter(rows), symbol="XAUUSD_i", internal_positions=0
    )
    account = apply_mt5_position_truth(
        AccountRiskState(
            equity=Decimal("2000"),
            open_positions=0,
            free_margin=Decimal("50"),
        ),
        sync,
    )
    assert account.account_open_positions == 4
    assert account.open_positions == 0
    assert account.free_margin == Decimal("50")
