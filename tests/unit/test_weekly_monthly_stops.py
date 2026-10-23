"""Weekly / monthly P/L from MT5 deals; the limits are disabled by the owner.

Owner 2026-10-23 (final): only the 25% daily stop applies. Weekly and monthly
P/L are still computed from MT5 deals for reporting (summaries, journal) and
reach the Risk Engine, but a 0 limit means disabled. If a limit is ever
configured again it is measured against the period-start balance, the same
basis as the daily stop.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal as D

import pytest

from app.application.services.live_account_risk_tracker import LiveAccountRiskTracker
from app.application.services.risk_engine import RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.institutional_trading.decision_models import AccountRiskState

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

WEEK_START = datetime(2026, 10, 19, tzinfo=UTC)  # Monday


def _deal(
    ticket: int, when: str, profit: str, *, volume: str = "0.01", kind: str = "sell"
) -> dict:
    return {
        "ticket": ticket,
        "time": datetime.fromisoformat(when).replace(tzinfo=UTC),
        "deal_type": kind,
        "volume": volume,
        "profit": profit,
        "commission": "-0.05",
        "swap": "0",
    }


def _account(balance: str) -> AccountSnapshot:
    bal = D(balance)
    return AccountSnapshot(
        login=1,
        balance=bal,
        equity=bal,
        margin=D("0"),
        free_margin=bal,
        margin_level=D("0"),
        profit=D("0"),
        leverage=1000,
    )


def test_trade_pnl_since_counts_only_trades_in_period() -> None:
    deals = [
        _deal(1, "2026-10-16T10:00:00", "-3.00"),  # previous week
        _deal(2, "2026-10-20T10:00:00", "-2.00"),
        _deal(2, "2026-10-20T10:00:00", "-2.00"),  # duplicate ticket
        _deal(3, "2026-10-21T11:00:00", "1.50"),
        _deal(4, "2026-10-21T12:00:00", "20.00", volume="0", kind="balance"),  # deposit
    ]
    # (-2.00 - 0.05) + (1.50 - 0.05)
    assert LiveAccountRiskTracker.trade_pnl_since(deals, since=WEEK_START) == D("-0.60")


def test_account_state_carries_monthly_pnl() -> None:
    state = AccountRiskState(equity=D("50"), monthly_pnl=D("-4"))
    assert state.monthly_pnl == D("-4")
    assert state.to_dict()["monthly_pnl"] == "-4"


def test_owner_default_has_no_weekly_or_monthly_block() -> None:
    # 80% of the week/month lost: still no weekly/monthly reason (disabled).
    _s, reasons, _w = RiskEngine().evaluate_drawdown(
        _account("10"), weekly_pnl=D("-40"), monthly_pnl=D("-40")
    )
    assert not any("weekly" in r or "monthly" in r for r in reasons)
    state, _r, _w = RiskEngine().evaluate_drawdown(
        _account("10"), weekly_pnl=D("-40"), monthly_pnl=D("-40")
    )
    assert state.weekly_loss_pct == D("80.00")  # still reported


@pytest.mark.parametrize(
    ("weekly", "blocked"),
    [("-19.00", False), ("-19.01", True)],  # week started at $50: 38% = $19.00
)
def test_a_configured_weekly_limit_uses_week_start_basis(
    weekly: str, blocked: bool
) -> None:
    balance = D("50") + D(weekly)
    engine = RiskEngine(config=RiskEngineConfig(max_weekly_loss_pct=D("38")))
    _s, reasons, _w = engine.evaluate_drawdown(
        _account(str(balance)), weekly_pnl=D(weekly)
    )
    assert any("weekly loss" in r for r in reasons) is blocked


def test_profit_never_blocks() -> None:
    _s, reasons, _w = RiskEngine().evaluate_drawdown(
        _account("60"), weekly_pnl=D("10"), monthly_pnl=D("10")
    )
    assert not any("weekly" in r or "monthly" in r for r in reasons)
