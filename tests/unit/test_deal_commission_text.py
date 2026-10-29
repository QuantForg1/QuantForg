"""Missing deal commission must not be rewritten as a zero tariff."""

from __future__ import annotations

from types import SimpleNamespace

from services.mt5_gateway.deals import deal_commission_text


def test_missing_commission_is_not_zero() -> None:
    assert deal_commission_text(SimpleNamespace(ticket=1)) is None
    assert deal_commission_text(SimpleNamespace(commission=None)) is None


def test_numeric_zero_commission_is_preserved() -> None:
    assert deal_commission_text(SimpleNamespace(commission=0)) == "0"
    assert deal_commission_text(SimpleNamespace(commission=0.0)) == "0.0"


def test_nonzero_commission_is_preserved() -> None:
    assert deal_commission_text(SimpleNamespace(commission=-1.5)) == "-1.5"
