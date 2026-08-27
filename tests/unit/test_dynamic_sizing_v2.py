"""Institutional Dynamic Position Sizing Engine v2 — unit contracts."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_scalping.config import AiScalpingConfig
from app.domain.institutional_trading.ai_scalping.dynamic_sizing_v2 import (
    calculate_dynamic_lots_v2,
    check_portfolio_sizing_limits,
    classify_quality_band,
    interpolate_equity_tier,
)


@pytest.mark.unit
class TestEquityTierInterpolation:
    def test_anchor_points(self) -> None:
        t50 = interpolate_equity_tier(Decimal("50"))
        assert t50.preferred_lot_lo == Decimal("0.01")
        assert t50.preferred_lot_hi == Decimal("0.01")

        t100 = interpolate_equity_tier(Decimal("100"))
        assert t100.preferred_lot_lo == Decimal("0.02")
        assert t100.preferred_lot_hi == Decimal("0.03")

        t400 = interpolate_equity_tier(Decimal("400"))
        assert t400.preferred_lot_lo == Decimal("0.05")
        assert t400.preferred_lot_hi == Decimal("0.10")

        t1k = interpolate_equity_tier(Decimal("1000"))
        assert t1k.preferred_lot_lo == Decimal("0.20")
        assert t1k.preferred_lot_hi == Decimal("0.50")

        t5k = interpolate_equity_tier(Decimal("5000"))
        assert t5k.preferred_lot_lo == Decimal("0.50")
        assert t5k.preferred_lot_hi == Decimal("1.00")

    def test_smooth_between_anchors_no_jump(self) -> None:
        low = interpolate_equity_tier(Decimal("100"))
        mid = interpolate_equity_tier(Decimal("250"))
        high = interpolate_equity_tier(Decimal("400"))
        assert low.preferred_lot_lo < mid.preferred_lot_lo < high.preferred_lot_lo
        assert low.preferred_lot_hi < mid.preferred_lot_hi < high.preferred_lot_hi


@pytest.mark.unit
class TestQualityBands:
    def test_weak_reject(self) -> None:
        assert (
            classify_quality_band(
                reject=True,
                quality_score=95,
                confidence=95,
                min_quality=80,
                min_confidence=80,
            )
            == "weak"
        )

    def test_average_high_exceptional(self) -> None:
        assert (
            classify_quality_band(
                reject=False,
                quality_score=82,
                confidence=82,
                min_quality=80,
                min_confidence=80,
            )
            == "average"
        )
        assert (
            classify_quality_band(
                reject=False,
                quality_score=90,
                confidence=88,
                min_quality=80,
                min_confidence=80,
            )
            == "high"
        )
        assert (
            classify_quality_band(
                reject=False,
                quality_score=95,
                confidence=92,
                min_quality=80,
                min_confidence=80,
            )
            == "exceptional"
        )


@pytest.mark.unit
class TestDynamicSizingSafety:
    def test_never_force_broker_min_lot(self) -> None:
        """Wide stop where min_lot risk exceeds hard_max → reject (no upsize)."""
        # min_loss = 0.01 * 100 * 12 = 12 → ~6.6% of $181.53 > hard_max 5%
        d = calculate_dynamic_lots_v2(
            equity=Decimal("181.53"),
            balance=Decimal("181.53"),
            free_margin=Decimal("181.53"),
            stop_distance=Decimal("12.00"),
            risk_pct=Decimal("0.50"),
            contract_size=Decimal("100"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            quality_score=88,
            confidence=88,
            quality_reject=False,
            log=False,
        )
        assert d.valid is False
        assert d.final_lot == Decimal("0")
        assert d.method == "below_min_lot"
        assert "below_min_lot" in (d.rejection_reason or "")
        assert d.calculated_lot < d.broker_min_lot

    def test_micro_conditional_approves_when_min_lot_within_hard_max(self) -> None:
        """~$181 equity / moderate stop → micro_conditional keeps broker min_lot."""
        # min_loss = 0.01 * 100 * 7.26 = 7.26 → ~4.0% <= hard_max 5%
        d = calculate_dynamic_lots_v2(
            equity=Decimal("181.53"),
            balance=Decimal("181.53"),
            free_margin=Decimal("181.53"),
            stop_distance=Decimal("7.26"),
            risk_pct=Decimal("0.50"),
            contract_size=Decimal("100"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            quality_score=88,
            confidence=88,
            quality_reject=False,
            log=False,
        )
        assert d.valid is True
        assert d.final_lot == Decimal("0.01")
        assert "micro_conditional" in d.method
        assert d.calculated_lot < d.broker_min_lot

    def test_weak_setup_rejects(self) -> None:
        d = calculate_dynamic_lots_v2(
            equity=Decimal("5000"),
            stop_distance=Decimal("1.50"),
            risk_pct=Decimal("0.50"),
            quality_reject=True,
            quality_score=40,
            confidence=40,
            log=False,
        )
        assert d.valid is False
        assert d.quality_band == "weak"
        assert d.final_lot == Decimal("0")

    def test_opportunity_pass_does_not_quality_weak_reject(self) -> None:
        """Live stall: quality 66 / conf 57 after Opportunity 73 + sniper TAKE."""
        d = calculate_dynamic_lots_v2(
            equity=Decimal("5000"),
            stop_distance=Decimal("1.50"),
            risk_pct=Decimal("0.50"),
            contract_size=Decimal("100"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            quality_score=66,
            confidence=57,
            quality_reject=False,
            opportunity_score=73,
            sniper_passed=True,
            log=False,
        )
        assert d.valid is True
        assert d.final_lot > 0
        assert d.quality_band == "average"
        assert "Weak setup" not in (d.rejection_reason or "")

    def test_opportunity_pass_still_min_lot_infeasible(self) -> None:
        d = calculate_dynamic_lots_v2(
            equity=Decimal("139.90"),
            stop_distance=Decimal("9.1724"),
            risk_pct=Decimal("1.0"),
            contract_size=Decimal("100"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            quality_score=66,
            confidence=57,
            quality_reject=False,
            opportunity_score=73,
            sniper_passed=True,
            log=False,
        )
        assert d.valid is False
        assert d.method == "below_min_lot"
        assert d.final_lot == Decimal("0")

    def test_never_exceed_configured_max_risk(self) -> None:
        d = calculate_dynamic_lots_v2(
            equity=Decimal("10000"),
            stop_distance=Decimal("1.00"),
            risk_pct=Decimal("0.50"),
            contract_size=Decimal("100"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            max_lot=Decimal("50"),
            quality_score=99,
            confidence=99,
            quality_reject=False,
            log=False,
        )
        assert d.valid is True
        assert d.risk_pct <= Decimal("0.50")
        assert d.configured_max_risk_pct == Decimal("0.50")

    def test_average_reduces_risk_vs_high(self) -> None:
        common = {
            "equity": Decimal("8000"),
            "stop_distance": Decimal("1.20"),
            "risk_pct": Decimal("0.50"),
            "contract_size": Decimal("100"),
            "min_lot": Decimal("0.01"),
            "lot_step": Decimal("0.01"),
            "max_lot": Decimal("50"),
            "quality_reject": False,
            "log": False,
        }
        avg = calculate_dynamic_lots_v2(quality_score=82, confidence=82, **common)
        high = calculate_dynamic_lots_v2(quality_score=90, confidence=88, **common)
        assert avg.valid and high.valid
        assert avg.risk_pct < high.risk_pct
        assert avg.final_lot <= high.final_lot

    def test_smooth_growth_dampens_abrupt_jump(self) -> None:
        d = calculate_dynamic_lots_v2(
            equity=Decimal("10000"),
            stop_distance=Decimal("1.00"),
            risk_pct=Decimal("0.50"),
            contract_size=Decimal("100"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            max_lot=Decimal("50"),
            quality_score=95,
            confidence=92,
            previous_final_lot=Decimal("0.05"),
            lot_growth_max_step_pct=Decimal("0.35"),
            log=False,
        )
        assert d.valid is True
        # Cap growth to 0.05 * 1.35 = 0.0675 → quantize 0.06
        assert d.final_lot <= Decimal("0.07")
        assert d.final_lot < d.calculated_lot or d.final_lot <= Decimal("0.07")

    def test_audit_log_fields(self) -> None:
        d = calculate_dynamic_lots_v2(
            equity=Decimal("1000"),
            balance=Decimal("980"),
            free_margin=Decimal("900"),
            stop_distance=Decimal("2.00"),
            risk_pct=Decimal("0.50"),
            contract_size=Decimal("100"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            quality_score=90,
            confidence=88,
            liquidity_score=80,
            spread_score=75,
            log=False,
        )
        payload = d.to_dict()
        for key in (
            "balance",
            "equity",
            "free_margin",
            "suggested_lot",
            "calculated_lot",
            "final_lot",
            "stop_loss_distance",
            "risk_pct",
            "quality_score",
            "equity_tier",
            "broker_min_lot",
            "broker_lot_step",
            "broker_max_lot",
        ):
            assert key in payload
        assert payload["engine"] == "dynamic_sizing_v2"

    def test_preferred_hi_caps_never_forces_preferred_lo(self) -> None:
        """Risk-based raw below preferred_lo must not be forced up."""
        d = calculate_dynamic_lots_v2(
            equity=Decimal("1000"),
            stop_distance=Decimal("5.00"),
            risk_pct=Decimal("0.50"),
            contract_size=Decimal("100"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            quality_score=95,
            confidence=92,
            log=False,
        )
        tier = interpolate_equity_tier(Decimal("1000"))
        # raw ≈ 0.01; preferred_lo = 0.20 — must not upsize to 0.20
        if d.valid:
            assert d.final_lot < tier.preferred_lot_lo
        else:
            assert d.method == "below_min_lot"
            assert d.calculated_lot < tier.preferred_lot_lo

    def test_lot_result_compat(self) -> None:
        d = calculate_dynamic_lots_v2(
            equity=Decimal("5000"),
            stop_distance=Decimal("1.50"),
            risk_pct=Decimal("0.50"),
            contract_size=Decimal("100"),
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            quality_score=90,
            confidence=88,
            log=False,
        )
        lr = d.to_lot_result()
        assert lr.valid is d.valid
        assert lr.lots == d.final_lot
        assert lr.account_balance == d.balance


@pytest.mark.unit
class TestPortfolioSizingLimits:
    def test_correlation_and_symbol_caps(self) -> None:
        blocked, why = check_portfolio_sizing_limits(
            open_positions=2,
            max_open_positions=5,
            daily_loss_pct=Decimal("0"),
            max_daily_loss_pct=Decimal("3"),
            exposure_pct=Decimal("1.0"),
            max_exposure_pct=Decimal("2.0"),
            symbol_exposure_pct=Decimal("1.0"),
            max_symbol_exposure_pct=Decimal("1.0"),
        )
        assert blocked is True
        assert why is not None
        assert "Symbol exposure" in why

        blocked2, why2 = check_portfolio_sizing_limits(
            open_positions=2,
            max_open_positions=5,
            daily_loss_pct=Decimal("0"),
            max_daily_loss_pct=Decimal("3"),
            exposure_pct=Decimal("1.0"),
            max_exposure_pct=Decimal("2.0"),
            correlated_exposure_pct=Decimal("1.60"),
            max_correlated_exposure_pct=Decimal("1.50"),
        )
        assert blocked2 is True
        assert "Correlation" in (why2 or "")

    def test_config_flag_default_on(self) -> None:
        cfg = AiScalpingConfig()
        assert cfg.dynamic_sizing_v2_enabled is True
        assert cfg.max_margin_usage_pct == Decimal("30")
