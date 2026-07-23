"""Unit tests — Micro Account Mode (Institutional Mode untouched)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.services.micro_account_feasibility import (
    report_to_markdown,
    run_micro_account_feasibility,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.micro_account_mode import (
    DEFAULT_MICRO_ACCOUNT_PROFILE,
    MicroTradability,
    consecutive_losses_to_drawdown,
    dollar_risk_at_lots,
    equity_floor_for_risk,
    evaluate_balance,
    min_usable_risk_pct,
    size_micro_lots,
    stop_distance_from_atr,
)
from app.domain.trading.xauusd_specs import VOLUME_MIN


@pytest.mark.unit
def test_institutional_defaults_unchanged() -> None:
    assert DEFAULT_ITE_CONFIG.min_trade_quality_score == 80
    assert DEFAULT_ITE_CONFIG.min_confluence_score == 80
    assert DEFAULT_ITE_CONFIG.risk_per_trade_pct == Decimal("1.0")
    assert DEFAULT_MICRO_ACCOUNT_PROFILE.mode_id == "MICRO_ACCOUNT_MODE"


@pytest.mark.unit
def test_dollar_risk_at_min_lot_is_stop_distance() -> None:
    """0.01 lot × stop × 100 contract = stop dollars."""
    stop = Decimal("18.00")
    loss = dollar_risk_at_lots(
        lots=VOLUME_MIN, stop_distance=stop, contract_size=Decimal("100")
    )
    assert loss == Decimal("18.00")


@pytest.mark.unit
def test_fifty_not_tradable_at_reference_atr() -> None:
    result = evaluate_balance(Decimal("50"), atr=Decimal("12"))
    assert result.tradability is MicroTradability.NOT_TRADABLE
    assert result.smallest_executable_lot is None
    assert result.min_usable_risk_pct > DEFAULT_MICRO_ACCOUNT_PROFILE.hard_max_risk_pct
    assert any("$50 cannot safely trade" in r for r in result.reasons)


@pytest.mark.unit
def test_never_fakes_lots_below_min() -> None:
    # 1% of $50 with $18 stop → tiny lots → reject to 0
    lots = size_micro_lots(
        equity=Decimal("50"),
        stop_distance=Decimal("18"),
        risk_pct=Decimal("1.0"),
    )
    assert lots == Decimal("0")


@pytest.mark.unit
def test_rejects_risk_above_hard_max() -> None:
    lots = size_micro_lots(
        equity=Decimal("500"),
        stop_distance=Decimal("18"),
        risk_pct=Decimal("10.0"),  # above hard max 5%
    )
    assert lots == Decimal("0")


@pytest.mark.unit
def test_consecutive_losses_math() -> None:
    # $500, $18 loss → 20% DD budget $100 → 5 losses
    n = consecutive_losses_to_drawdown(
        equity=Decimal("500"),
        loss_per_trade=Decimal("18"),
        drawdown_pct=Decimal("20"),
    )
    assert n == 5


@pytest.mark.unit
def test_equity_floor_for_2pct() -> None:
    floor = equity_floor_for_risk(
        dollar_risk_at_min_lot=Decimal("18"),
        risk_pct=Decimal("2.0"),
    )
    assert floor == Decimal("900.00")


@pytest.mark.unit
def test_stop_distance_matches_institutional_multiplier() -> None:
    assert stop_distance_from_atr(Decimal("12")) == Decimal("18.0000")


@pytest.mark.unit
def test_min_usable_risk_pct() -> None:
    pct = min_usable_risk_pct(equity=Decimal("100"), dollar_risk=Decimal("18"))
    assert pct == Decimal("18.00")


@pytest.mark.unit
def test_feasibility_report_preserves_institutional() -> None:
    report = run_micro_account_feasibility(atr=Decimal("12"))
    assert report["institutional_mode_modified"] is False
    assert report["institutional_unchanged"]["quality"] == 80
    assert report["institutional_unchanged"]["confluence"] == 80
    assert report["institutional_unchanged"]["risk_per_trade_pct"] == "1.0"
    assert report["summary"]["fifty_dollar_explicit"]
    assert Decimal("50") == Decimal(report["balances"][0]["equity"])
    md = report_to_markdown(report)
    assert "Micro Account Mode" in md
    assert "$50 cannot safely trade" in md
