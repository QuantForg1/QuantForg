"""Combined planned risk stays inside one 14% equity budget."""

from __future__ import annotations

from decimal import Decimal as D
from uuid import uuid4

import pytest

from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot, MT5Position
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.institutional_trading.operations.quantforg_position_cap import (
    QUANTFORG_MAGIC,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _position(*, stop: str | None) -> MT5Position:
    stop_value = D(stop) if stop is not None else D("0")
    return MT5Position(
        ticket=7,
        symbol="XAUUSD",
        side="buy",
        volume=D("0.01"),
        open_price=D("4000"),
        current_price=D("4000"),
        stop_loss=stop_value,
        initial_stop=stop_value,
        magic=QUANTFORG_MAGIC,
    )


def _evaluate(
    *,
    equity: str,
    stop: str,
    positions: list[object],
    max_open_positions: int = 2,
    max_total: str | None = None,
) -> object:
    config_kwargs: dict[str, object] = {
        "min_lot": D("0.01"),
        "lot_step": D("0.01"),
        "max_lot": D("0.01"),
        "contract_size": D("100"),
        "max_open_positions": max_open_positions,
    }
    if max_total is not None:
        config_kwargs["max_total_planned_risk_usd"] = D(max_total)
    engine = RiskEngine(config=RiskEngineConfig(**config_kwargs))  # type: ignore[arg-type]
    eq = D(equity)
    return engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id=f"agg-{equity}-{stop}",
            symbol="XAUUSD",
            side="sell",
            requested_lots=D("0.01"),
            stop_loss_distance=D(stop),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=D("4000"),
            contract_size=D("100"),
        ),
        account=AccountSnapshot(
            login=1,
            balance=eq,
            equity=eq,
            margin=D("0"),
            free_margin=eq,
            margin_level=D("0"),
            profit=D("0"),
            leverage=2000,
        ),
        positions=positions,  # type: ignore[arg-type]
    )


def test_open_risk_plus_new_entry_cannot_exceed_the_cap() -> None:
    # 0.01 lot and contract 100: dollar risk equals the stop distance.
    # Open $8 + new $7 = $15, above 14% of $100.
    assessment = _evaluate(
        equity="100",
        stop="7.00",
        positions=[_position(stop="3992")],
    )
    assert assessment.decision is RiskDecision.REJECT
    assert any(
        "aggregate planned SL risk" in reason
        or "REMAINING_PORTFOLIO_RISK_EXCEEDED" in reason
        for reason in assessment.reasons
    )


def test_exact_combined_cap_is_allowed() -> None:
    assessment = _evaluate(
        equity="100",
        stop="7.00",
        positions=[_position(stop="3993")],
    )
    assert not any(
        "aggregate planned SL risk" in reason and "exceeds" in reason
        for reason in assessment.reasons
    )


def test_unmeasured_open_quantforg_risk_blocks_the_new_entry() -> None:
    assessment = _evaluate(
        equity="100",
        stop="2.00",
        positions=[_position(stop=None)],
    )
    assert assessment.decision is RiskDecision.REJECT
    assert any("unmeasured" in reason for reason in assessment.reasons)


def test_a_zero_aggregate_cap_does_not_disable_the_check() -> None:
    assessment = _evaluate(
        equity="100",
        stop="2.00",
        positions=[],
        max_total="0",
    )
    assert assessment.decision is RiskDecision.REJECT
    assert any("unavailable" in reason for reason in assessment.reasons)


def test_unmeasured_manual_position_blocks_a_new_entry() -> None:
    manual = _position(stop=None)
    manual = manual.__class__(
        ticket=manual.ticket,
        symbol=manual.symbol,
        side=manual.side,
        volume=manual.volume,
        open_price=manual.open_price,
        current_price=manual.current_price,
        stop_loss=manual.stop_loss,
        initial_stop=manual.initial_stop,
        magic=0,
    )
    assessment = _evaluate(equity="100", stop="2.00", positions=[manual])
    assert assessment.decision is RiskDecision.REJECT
    assert any(
        "unmeasured" in reason and "MANUAL:7:" in reason
        for reason in assessment.reasons
    )


def test_measured_manual_exposure_counts_toward_the_cap() -> None:
    manual = _position(stop="3992")
    manual = manual.__class__(
        ticket=manual.ticket,
        symbol=manual.symbol,
        side=manual.side,
        volume=manual.volume,
        open_price=manual.open_price,
        current_price=manual.current_price,
        stop_loss=manual.stop_loss,
        initial_stop=manual.initial_stop,
        magic=0,
    )
    # Open $8 + new $7 = $15, above 14% of $100.
    assessment = _evaluate(equity="100", stop="7.00", positions=[manual])
    assert assessment.decision is RiskDecision.REJECT
    assert any(
        "exceeds" in reason or "REMAINING_PORTFOLIO_RISK_EXCEEDED" in reason
        for reason in assessment.reasons
    )


def test_a_looser_dollar_cap_cannot_raise_the_percent_budget() -> None:
    assessment = _evaluate(
        equity="100",
        stop="7.00",
        positions=[_position(stop="3992")],
        max_total="30",
    )
    assert assessment.decision is RiskDecision.REJECT
    assert any(
        "exceeds" in reason or "REMAINING_PORTFOLIO_RISK_EXCEEDED" in reason
        for reason in assessment.reasons
    )
