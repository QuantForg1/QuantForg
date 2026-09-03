"""FX TAKE must not be halved by gold 1:100 exposure, then fail $6.

Does not send orders. Does not lower P>70, sniper, RR, ATR, or $6/$20/$30.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.institutional_decision_pipeline import (
    _account_snapshot,
    risk_config_from_ite,
)
from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.institutional_trading.config import (
    DEFAULT_ITE_CONFIG,
    MAX_PLANNED_SL_RISK_USD,
    MAX_TOTAL_PLANNED_RISK_USD,
    MIN_PLANNED_RISK_USD,
)
from app.domain.institutional_trading.operations.min_lot_feasibility import (
    CODE_MIN_PLANNED_RISK_NOT_REACHED,
    lot_dollar_risk,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_USDCAD_ENTRY = Decimal("1.379975")
_USDCAD_SL = Decimal("0.00042792899999995")
_USDCAD_CS = Decimal("100000")
_EQUITY = Decimal("83.84")
_LIVE_LEVERAGE = 2000


def _ite_engine() -> RiskEngine:
    return RiskEngine(
        config=risk_config_from_ite(
            DEFAULT_ITE_CONFIG,
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            max_lot=Decimal("1000"),
            contract_size=_USDCAD_CS,
        )
    )


def _check() -> RiskCheckInput:
    return RiskCheckInput(
        user_id=uuid4(),
        request_id="fx-exposure-usdcad",
        symbol="USDCAD",
        side="sell",
        requested_lots=None,
        stop_loss_distance=_USDCAD_SL,
        atr=Decimal("0.00075286"),
        sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
        entry_price=_USDCAD_ENTRY,
        contract_size=_USDCAD_CS,
        session_allowed=True,
        spread=Decimal("0.00029"),
    )


def _acct(*, leverage: int) -> AccountSnapshot:
    return AccountSnapshot(
        login=1,
        balance=_EQUITY,
        equity=_EQUITY,
        margin=Decimal("0"),
        free_margin=_EQUITY,
        margin_level=Decimal("0"),
        profit=Decimal("0"),
        leverage=leverage,
    )


def test_floors_unchanged() -> None:
    assert MIN_PLANNED_RISK_USD == Decimal("6.00")
    assert MAX_PLANNED_SL_RISK_USD == Decimal("20.00")
    assert MAX_TOTAL_PLANNED_RISK_USD == Decimal("30.00")


def test_hardcoded_100_leverage_halves_then_misses_six_dollar_floor() -> None:
    """Reproduction: ITE snapshot leverage=100 → 263% exposure → 0.16→0.08 → $3.42."""
    result = _ite_engine().evaluate(
        _check(),
        account=_acct(leverage=100),
        positions=[],
        daily_pnl=Decimal("0"),
    )
    assert result.decision is RiskDecision.REJECT
    hay = " ".join(result.reasons)
    assert "symbol exposure" in hay
    assert "size reduced from" in hay
    assert CODE_MIN_PLANNED_RISK_NOT_REACHED in hay
    assert result.approved_lots == Decimal("0")


def test_live_fx_leverage_keeps_planned_risk_in_six_to_twenty_band() -> None:
    result = _ite_engine().evaluate(
        _check(),
        account=_acct(leverage=_LIVE_LEVERAGE),
        positions=[],
        daily_pnl=Decimal("0"),
    )
    assert result.decision is not RiskDecision.REJECT
    assert result.approved_lots > 0
    hay = " ".join(result.reasons)
    assert CODE_MIN_PLANNED_RISK_NOT_REACHED not in hay
    assert "symbol exposure" not in hay
    planned = lot_dollar_risk(
        result.approved_lots,
        stop_distance=_USDCAD_SL,
        contract_size=_USDCAD_CS,
    )
    assert planned > MIN_PLANNED_RISK_USD
    assert planned <= MAX_PLANNED_SL_RISK_USD


def test_six_dollar_floor_still_rejects_halved_fx_size() -> None:
    planned = lot_dollar_risk(
        Decimal("0.08"),
        stop_distance=_USDCAD_SL,
        contract_size=_USDCAD_CS,
    )
    assert planned < MIN_PLANNED_RISK_USD
    assert planned.quantize(Decimal("0.01")) == Decimal("3.42")


def test_ite_snapshot_uses_live_account_leverage_not_gold_100() -> None:
    snap = _account_snapshot(
        equity=_EQUITY,
        free_margin=_EQUITY,
        leverage=Decimal("2000"),
    )
    assert snap.leverage == 2000
    missing = _account_snapshot(equity=_EQUITY, free_margin=_EQUITY, leverage=None)
    assert missing.leverage == 1000
    assert missing.leverage != 100


def test_max_open_positions_does_not_fire_on_empty_book() -> None:
    result = _ite_engine().evaluate(
        _check(),
        account=_acct(leverage=_LIVE_LEVERAGE),
        positions=[],
        daily_pnl=Decimal("0"),
    )
    assert result.checks.get("open_positions") is True
    hay = " ".join(result.reasons)
    assert "open positions" not in hay


def test_nzdusd_uses_fx_contract_size_not_gold() -> None:
    engine = _ite_engine()
    assert engine._contract_size("NZDUSD") == Decimal("100000")
    assert engine._contract_size("USDCAD") == Decimal("100000")
    assert engine._contract_size("XAUUSD") == Decimal("100")
    assert engine._asset_class("NZDUSD") == "fx"
    assert engine._asset_class("USDCAD") == "fx"
    assert engine._asset_class("USDCHF") == "fx"
    assert engine._asset_class("XAUUSD") == "metal"
