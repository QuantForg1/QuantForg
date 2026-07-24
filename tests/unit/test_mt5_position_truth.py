"""MT5 position truth — force sync before max-open blocks."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.application.services.mt5_position_truth import (
    apply_mt5_position_truth,
    force_sync_positions,
)
from app.domain.entities.mt5_portfolio import MT5Position
from app.domain.institutional_trading.decision_models import AccountRiskState
from app.domain.institutional_trading.management.engine import PositionManagementEngine
from app.domain.institutional_trading.management.models import (
    ManagedPosition,
    PositionLifecycleState,
)


class _FakeClient:
    def __init__(self, rows: list[MT5Position]) -> None:
        self._rows = rows
        self._positions_cache: list[MT5Position] | None = list(rows)
        self._positions_cache_at = 1.0
        self.invalidated = False

    def invalidate_positions_cache(self) -> None:
        self.invalidated = True
        self._positions_cache = None
        self._positions_cache_at = 0.0

    def list_positions(self) -> list[MT5Position]:
        return list(self._rows)


class _FakeAdapter:
    def __init__(self, rows: list[MT5Position]) -> None:
        self._client = _FakeClient(rows)

    def list_positions(self) -> list[MT5Position]:
        return self._client.list_positions()


def _pos(ticket: int, symbol: str = "XAUUSD") -> MT5Position:
    return MT5Position(
        ticket=ticket,
        symbol=symbol,
        side="buy",
        volume=Decimal("0.01"),
        open_price=Decimal("4000"),
        current_price=Decimal("4001"),
    )


@pytest.mark.unit
def test_force_sync_clears_cache_and_logs_mt5_as_truth() -> None:
    adapter = _FakeAdapter([])
    engine = PositionManagementEngine(oms=SimpleNamespace())  # type: ignore[arg-type]
    engine.register(
        ManagedPosition(
            ticket=99,
            symbol="XAUUSD",
            side="buy",
            entry_price=Decimal("4000"),
            initial_volume=Decimal("0.01"),
            remaining_volume=Decimal("0.01"),
            initial_stop=Decimal("3990"),
            risk_distance=Decimal("10"),
            opened_at=datetime.now(UTC),
            state=PositionLifecycleState.OPEN,
            current_stop=Decimal("3990"),
            current_tp=Decimal("4020"),
        )
    )
    assert len(engine._positions) == 1

    sync = force_sync_positions(
        adapter,
        symbol="XAUUSD",
        internal_positions=1,
        position_engine=engine,
    )
    assert adapter._client.invalidated is True
    assert sync.mt5_positions == 0
    assert sync.internal_positions == 1
    assert sync.repaired is True
    assert len(engine._positions) == 0


@pytest.mark.unit
def test_force_sync_keeps_live_mt5_positions() -> None:
    adapter = _FakeAdapter([_pos(7)])
    sync = force_sync_positions(
        adapter,
        symbol="XAUUSD",
        internal_positions=0,
        position_engine=None,
    )
    assert sync.mt5_positions == 1
    assert sync.tickets == (7,)
    assert sync.repaired is True  # differed from internal 0


@pytest.mark.unit
def test_apply_mt5_truth_rewrites_account() -> None:
    account = AccountRiskState(
        equity=Decimal("1000"),
        open_positions=1,
        already_in_trade=True,
    )
    sync = force_sync_positions(
        _FakeAdapter([]),
        symbol="XAUUSD",
        internal_positions=1,
    )
    fixed = apply_mt5_position_truth(account, sync)
    assert fixed.open_positions == 0
    assert fixed.already_in_trade is False
