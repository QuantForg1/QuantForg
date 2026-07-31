"""ULTRA_AGGRESSIVE institutional risk profile — unit contracts."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_scalping.config import AiScalpingConfig
from app.domain.institutional_trading.ai_scalping.dynamic_sizing_v2 import (
    calculate_dynamic_lots_v2,
)
from app.domain.institutional_trading.ai_scalping.risk_profiles import (
    ai_scalping_config_for_profile,
    apply_risk_profile,
    get_active_ai_scalping_config,
    max_risk_ceiling_for_profile,
    normalize_risk_profile_id,
    profile_summary,
    set_active_ai_scalping_config,
    ultra_aggressive_ai_scalping_config,
)


@pytest.fixture(autouse=True)
def _reset_active_profile() -> None:
    set_active_ai_scalping_config(AiScalpingConfig())
    yield
    set_active_ai_scalping_config(AiScalpingConfig())


@pytest.mark.unit
class TestUltraAggressiveProfileConfig:
    def test_normalize_aliases(self) -> None:
        assert normalize_risk_profile_id("ultra") == "ULTRA_AGGRESSIVE"
        assert normalize_risk_profile_id("ULTRA-AGGRESSIVE") == "ULTRA_AGGRESSIVE"
        assert normalize_risk_profile_id(None) == "STANDARD"

    def test_ceilings(self) -> None:
        assert max_risk_ceiling_for_profile("STANDARD") == Decimal("0.75")
        assert max_risk_ceiling_for_profile("ULTRA_AGGRESSIVE") == Decimal("8.00")

    def test_ultra_knobs(self) -> None:
        cfg = ultra_aggressive_ai_scalping_config()
        assert cfg.risk_profile_id == "ULTRA_AGGRESSIVE"
        assert cfg.risk_per_trade_pct == Decimal("8.00")
        assert cfg.max_daily_exposure_pct == Decimal("20.00")
        assert cfg.max_symbol_exposure_pct == Decimal("8.00")
        assert cfg.max_open_trades == 10
        assert cfg.pyramid_winners_only is True
        assert cfg.dynamic_sizing_v2_enabled is True
        assert cfg.portfolio_risk_engine_v2_enabled is True
        # Quality floors unchanged from STANDARD baseline
        std = AiScalpingConfig()
        assert cfg.normal_vol.quality == std.normal_vol.quality
        assert cfg.normal_vol.confidence == std.normal_vol.confidence

    def test_standard_still_hard_caps_at_0_75(self) -> None:
        cfg = AiScalpingConfig(risk_per_trade_pct=Decimal("5.00"))
        assert cfg.risk_profile_id == "STANDARD"
        assert cfg.risk_per_trade_pct == Decimal("0.75")

    def test_ultra_allows_8_pct(self) -> None:
        cfg = AiScalpingConfig(
            risk_profile_id="ULTRA_AGGRESSIVE",
            risk_per_trade_pct=Decimal("8.00"),
        )
        assert cfg.risk_per_trade_pct == Decimal("8.00")

    def test_active_profile_store(self) -> None:
        apply_risk_profile("ULTRA_AGGRESSIVE")
        active = get_active_ai_scalping_config()
        assert active.risk_profile_id == "ULTRA_AGGRESSIVE"
        assert active.risk_per_trade_pct == Decimal("8.00")
        summary = profile_summary("ULTRA_AGGRESSIVE")
        assert summary["risk_per_trade_pct"] == "8.00"
        assert summary["quality_floors_unchanged"] is True


@pytest.mark.unit
class TestUltraAggressiveSizing:
    def _common(self, *, config: AiScalpingConfig) -> dict:
        return {
            "equity": Decimal("5000"),
            "balance": Decimal("5000"),
            "free_margin": Decimal("4000"),
            "stop_distance": Decimal("2.0"),
            "atr": Decimal("2.5"),
            "mid_price": Decimal("2400"),
            "leverage": Decimal("1000"),
            "contract_size": Decimal("100"),
            "min_lot": Decimal("0.01"),
            "lot_step": Decimal("0.01"),
            "max_lot": Decimal("50"),
            "config": config,
            "log": False,
        }

    def test_weak_still_rejected(self) -> None:
        cfg = ai_scalping_config_for_profile("ULTRA_AGGRESSIVE")
        d = calculate_dynamic_lots_v2(
            quality_score=50,
            confidence=50,
            quality_reject=False,
            **self._common(config=cfg),
        )
        assert d.valid is False
        assert d.quality_band == "weak"
        assert d.final_lot == Decimal("0")

    def test_exceptional_full_8_when_all_conditions_met(self) -> None:
        cfg = ai_scalping_config_for_profile("ULTRA_AGGRESSIVE")
        d = calculate_dynamic_lots_v2(
            quality_score=95,
            confidence=92,
            liquidity_score=85,
            spread_score=85,
            trend_confidence=90,
            mtf_score=90,
            news_risk_multiplier=Decimal("1"),
            session_risk_multiplier=Decimal("1"),
            **self._common(config=cfg),
        )
        assert d.valid is True
        assert d.risk_profile_id == "ULTRA_AGGRESSIVE"
        assert d.configured_max_risk_pct == Decimal("8.00")
        assert d.risk_pct == Decimal("8.0000")
        assert d.risk_reduction_reason is None
        assert d.quality_band == "exceptional"
        # Preferred equity tier for $5k is 0.50-1.00; risk-based should land in range
        assert d.final_lot >= Decimal("0.50")
        assert d.final_lot <= Decimal("1.00")
        payload = d.to_dict()
        assert Decimal(str(payload["configured_max_risk_pct"])) == Decimal("8.00")
        assert Decimal(str(payload["effective_risk_pct"])) == Decimal("8.00")
        assert payload["target_lot"] is not None

    def test_lower_quality_reduces_below_8(self) -> None:
        cfg = ai_scalping_config_for_profile("ULTRA_AGGRESSIVE")
        d = calculate_dynamic_lots_v2(
            quality_score=90,
            confidence=88,
            liquidity_score=85,
            spread_score=85,
            trend_confidence=88,
            mtf_score=90,
            news_risk_multiplier=Decimal("1"),
            **self._common(config=cfg),
        )
        assert d.valid is True
        assert d.quality_band == "high"
        assert d.risk_pct < Decimal("8.00")
        assert d.risk_reduction_reason is not None
        assert "quality_band=high" in (d.risk_reduction_reason or "")

    def test_mtf_incomplete_reduces(self) -> None:
        cfg = ai_scalping_config_for_profile("ULTRA_AGGRESSIVE")
        d = calculate_dynamic_lots_v2(
            quality_score=95,
            confidence=92,
            liquidity_score=85,
            spread_score=85,
            trend_confidence=90,
            mtf_score=60,
            news_risk_multiplier=Decimal("1"),
            **self._common(config=cfg),
        )
        assert d.valid is True
        assert d.risk_pct < Decimal("8.00")
        assert "mtf_incomplete" in (d.risk_reduction_reason or "")

    def test_never_exceeds_configured_max(self) -> None:
        cfg = ai_scalping_config_for_profile("ULTRA_AGGRESSIVE")
        d = calculate_dynamic_lots_v2(
            quality_score=99,
            confidence=99,
            liquidity_score=99,
            spread_score=99,
            trend_confidence=99,
            mtf_score=99,
            news_risk_multiplier=Decimal("1"),
            risk_pct=Decimal("12.00"),  # attempt above ceiling
            **self._common(config=cfg),
        )
        assert d.configured_max_risk_pct == Decimal("8.00")
        assert d.risk_pct <= Decimal("8.00")

    def test_standard_profile_unchanged_ceiling(self) -> None:
        cfg = ai_scalping_config_for_profile("STANDARD")
        d = calculate_dynamic_lots_v2(
            quality_score=95,
            confidence=92,
            liquidity_score=85,
            spread_score=85,
            mtf_score=90,
            news_risk_multiplier=Decimal("1"),
            **self._common(config=cfg),
        )
        assert d.configured_max_risk_pct <= Decimal("0.75")
        assert d.risk_pct <= Decimal("0.75")

    def test_pre_allows_empty_book_at_symbol_cap(self) -> None:
        """ULTRA max_symbol == risk/trade (8%); landing on cap must not reject."""
        from app.domain.institutional_trading.ai_scalping import (
            portfolio_risk_engine_v2 as pre,
        )
        from app.domain.institutional_trading.decision_models import AccountRiskState

        cfg = ai_scalping_config_for_profile("ULTRA_AGGRESSIVE")
        account = AccountRiskState(
            balance=Decimal("5000"),
            equity=Decimal("5000"),
            free_margin=Decimal("4500"),
            used_margin=Decimal("0"),
            floating_pnl=Decimal("0"),
            leverage=Decimal("1000"),
            open_positions=0,
            daily_pnl=Decimal("0"),
            atr=Decimal("2.5"),
            mid_price=Decimal("2400"),
        )
        alloc = pre.evaluate_portfolio_allocation(
            account=account,
            symbol="XAUUSD",
            stop_distance=Decimal("2.0"),
            positions=[],
            new_direction="buy",
            new_confidence=92,
            entry=Decimal("2400"),
            atr=Decimal("2.5"),
            mid_price=Decimal("2400"),
            leverage=Decimal("1000"),
            risk_pct=cfg.risk_per_trade_pct,
            session_risk_multiplier=Decimal("1"),
            quality_score=95,
            confidence=92,
            liquidity_score=85,
            spread_score=85,
            trend_confidence=92,
            mtf_score=90,
            news_risk_multiplier=Decimal("1"),
            quality_reject=False,
            broker=pre.BrokerComplianceSpec(
                min_lot=Decimal("0.01"),
                lot_step=Decimal("0.01"),
                max_lot=Decimal("50"),
                contract_size=Decimal("100"),
            ),
            balance=Decimal("5000"),
            used_margin=Decimal("0"),
            floating_pnl=Decimal("0"),
            config=cfg,
            log=False,
        )
        assert alloc.allow is True
        assert alloc.approved_lots > 0
        assert alloc.sizing is not None
        assert alloc.sizing.risk_pct == Decimal("8.0000")
