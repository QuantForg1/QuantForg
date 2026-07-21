"""XAUUSD specs + exposure formula — never FX 100k inflation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.services.risk_engine import RiskEngine
from app.domain.entities.risk_engine import RiskEngineConfig, contract_size_for_symbol
from app.domain.trading.xauusd_specs import (
    CONTRACT_SIZE,
    MAX_LEVERAGE,
    MAX_SPREAD,
    coerce_max_spread,
    exposure_pct_of_equity,
    margin_required,
    notional_value,
)


@pytest.mark.unit
class TestXauusdSpecs:
    def test_contract_size_is_100(self) -> None:
        assert CONTRACT_SIZE == Decimal("100")
        assert contract_size_for_symbol("XAUUSD") == Decimal("100")
        assert contract_size_for_symbol("EURUSD") == Decimal("100")  # platform gold-only

    def test_fx_spread_ceiling_coerced(self) -> None:
        assert coerce_max_spread(Decimal("0.00050")) == MAX_SPREAD
        assert coerce_max_spread(Decimal("0.30")) == Decimal("0.30")
        assert coerce_max_spread(None) == MAX_SPREAD

    def test_margin_and_exposure_match_live_account_shape(self) -> None:
        """Reproduce the ~40,000% bug path and the corrected formula.

        Live account (verified): equity≈99.2, leverage=1000, price≈4017, vol=0.01

        Wrong FX path (cs=100000, lev=100):
          margin = 0.01 * 4017 * 100000 / 100 = 40170
          pct    = 40170 / 99.2 * 100 ≈ 40494%

        Correct XAUUSD path (cs=100, lev=1000):
          margin = 0.01 * 4017 * 100 / 1000 = 4.02
          pct    = 4.02 / 99.2 * 100 ≈ 4.05%
        """
        volume = Decimal("0.01")
        price = Decimal("4017")
        equity = Decimal("99.2")
        leverage = Decimal("1000")

        wrong_margin = (volume * price * Decimal("100000") / Decimal("100")).quantize(
            Decimal("0.01")
        )
        wrong_pct = (wrong_margin / equity * Decimal("100")).quantize(Decimal("0.01"))
        assert wrong_pct > Decimal("40000")

        margin = margin_required(volume=volume, price=price, leverage=leverage)
        pct = exposure_pct_of_equity(
            volume=volume, price=price, equity=equity, leverage=leverage
        )
        assert margin == Decimal("4.02")
        assert pct == Decimal("4.05")
        assert notional_value(volume=volume, price=price) == Decimal("4017.00")
        assert MAX_LEVERAGE == Decimal("1000")

    def test_risk_engine_exposure_uses_margin_not_fx_notional(self) -> None:
        engine = RiskEngine(config=RiskEngineConfig())
        exposure = engine.calculate_exposure(
            positions=[],
            equity=Decimal("99.2"),
            proposed_symbol="XAUUSD",
            proposed_side="buy",
            proposed_lots=Decimal("0.01"),
            entry_price=Decimal("4017"),
            leverage=Decimal("1000"),
        )
        ok, reasons, _, metrics = engine.exposure_limits_ok(
            exposure, equity=Decimal("99.2"), symbol="XAUUSD"
        )
        assert ok, reasons
        assert metrics["symbol_pct"] == Decimal("4.05")
        assert metrics["total_pct"] == Decimal("4.05")
