"""Unit tests — Micro Account Analyzer (Institutional Mode frozen)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.services.micro_account_analyzer import (
    report_to_markdown,
    run_micro_account_analyzer,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.micro_account_analyzer import (
    RISK_LADDER_PCT,
    analyze_micro_account,
    calculate_lots,
    desk_fallback_specs,
    evaluate_eligibility,
    institutional_profile_dict,
    min_safe_balances_table,
)
from app.domain.institutional_trading.micro_account_mode import stop_distance_from_atr


@pytest.mark.unit
def test_institutional_profile_frozen() -> None:
    p = institutional_profile_dict()
    assert p["frozen"] is True
    assert p["quality"] == 80
    assert p["confluence"] == 80
    assert p["risk_pct"] == "1.0"
    assert p["modified_by_micro_mode"] is False
    assert DEFAULT_ITE_CONFIG.min_trade_quality_score == 80
    assert DEFAULT_ITE_CONFIG.min_confluence_score == 80
    assert DEFAULT_ITE_CONFIG.risk_per_trade_pct == Decimal("1.0")


@pytest.mark.unit
def test_fifty_not_eligible_at_2pct() -> None:
    specs = desk_fallback_specs()
    assert specs.volume_min == Decimal("0.01")
    result = evaluate_eligibility(
        balance=Decimal("50"),
        risk_pct=Decimal("2.00"),
        atr=Decimal("12"),
        specs=specs,
    )
    assert result.eligible is False
    assert result.status == "NOT ELIGIBLE"
    assert "NOT ELIGIBLE" in result.reason
    assert result.estimated_lot_size is None


@pytest.mark.unit
def test_never_forces_min_lot() -> None:
    specs = desk_fallback_specs()
    lots = calculate_lots(
        equity=Decimal("50"),
        risk_pct=Decimal("1.00"),
        stop_distance=Decimal("18"),
        specs=specs,
    )
    assert lots == Decimal("0")
    assert lots < specs.volume_min


@pytest.mark.unit
def test_min_safe_balance_ladder() -> None:
    specs = desk_fallback_specs()
    stop = stop_distance_from_atr(Decimal("12"))
    rows = min_safe_balances_table(stop_distance=stop, specs=specs)
    assert len(rows) == len(RISK_LADDER_PCT)
    # $18 loss at 0.01 → 1% floor = $1800
    one = next(r for r in rows if r["risk_pct"] == "1.00")
    assert one["min_safe_balance"] == "1800.00"
    two = next(r for r in rows if r["risk_pct"] == "2.00")
    assert two["min_safe_balance"] == "900.00"


@pytest.mark.unit
def test_analyze_report_fifty_clear() -> None:
    report = analyze_micro_account(
        balance=Decimal("50"),
        risk_pct=Decimal("2.00"),
        atr=Decimal("12"),
        specs=desk_fallback_specs(),
    )
    assert report["institutional_mode_modified"] is False
    assert report["eligible"] is False
    assert report["eligible_label"] == "NO"
    assert report["fifty_dollar_clear_statement"]
    assert "$50 is NOT tradable" in report["fifty_dollar_clear_statement"]
    assert len(report["flow"]) >= 6


@pytest.mark.unit
def test_run_analyzer_offline_fallback() -> None:
    report = run_micro_account_analyzer(
        balance=Decimal("50"),
        risk_pct=Decimal("2.00"),
        atr=Decimal("12"),
        use_live_broker=False,
        use_live_atr=False,
    )
    assert report["broker_specs"]["source"] == "desk_fallback"
    md = report_to_markdown(report)
    assert "Micro Account Analyzer" in md
    assert "NOT ELIGIBLE" in md or "NOT tradable" in md


@pytest.mark.unit
def test_eligible_when_equity_covers_min_lot() -> None:
    specs = desk_fallback_specs()
    # At ATR=12 stop=18, need $900 for 2% → $2000 is eligible
    result = evaluate_eligibility(
        balance=Decimal("2000"),
        risk_pct=Decimal("2.00"),
        atr=Decimal("12"),
        specs=specs,
    )
    assert result.eligible is True
    assert result.status == "Eligible"
    assert result.estimated_lot_size is not None
    assert result.estimated_lot_size >= specs.volume_min
