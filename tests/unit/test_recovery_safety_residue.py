"""Safe residue from the local checkout. Published caps stay in place."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.services.institutional_oms_adapter import RecordingOmsPort
from app.domain.institutional_trading.compounding.models import HARD_MAX_RISK_PCT
from app.domain.institutional_trading.execution.bridge import BridgeAbortReason
from app.domain.institutional_trading.execution.models import ExecutionMode
from app.domain.institutional_trading.micro_account_mode import MicroAccountProfile
from services.mt5_gateway.schemas import TradeRequestBody
from tests.unit.test_institutional_trading_phase_c import (
    _bridge,
    _buy_decision,
    _ctx,
)


class _ArmOnLaterRead:
    """First kill-switch read is clear. Every later read is armed."""

    def __init__(self) -> None:
        self.reads = 0

    @property
    def enabled(self) -> bool:
        self.reads += 1
        return self.reads >= 2

    def bind(self, plane: object) -> _ArmOnLaterRead:
        _ = plane
        return self


@pytest.mark.unit
def test_omitted_volume_is_zero_not_the_cap() -> None:
    body = TradeRequestBody(symbol="XAUUSD", action="buy")
    assert body.volume == 0
    assert body.volume != 0.01


@pytest.mark.unit
def test_published_hard_risk_cap_is_fourteen_percent() -> None:
    assert MicroAccountProfile().hard_max_risk_pct == Decimal("14.0")
    assert Decimal("14.0") == HARD_MAX_RISK_PCT


@pytest.mark.unit
def test_kill_switch_armed_before_submit_reaches_oms_nothing() -> None:
    decision, snap, acct = _buy_decision()
    oms = RecordingOmsPort()
    integ = _bridge(oms, mode=ExecutionMode.LIVE)
    switch = _ArmOnLaterRead()
    integ.bridge.kill_switch = switch
    result = integ.execute(decision, _ctx(decision, snap, acct))
    assert result.aborted is True
    assert result.abort_reason is BridgeAbortReason.KILL_SWITCH
    assert oms.calls == []
    assert switch.reads == 2
    assert result.decision_hash in integ.bridge._executed_hashes
