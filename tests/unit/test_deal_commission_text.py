"""Missing deal commission must not be rewritten as a zero tariff."""

from __future__ import annotations

from types import SimpleNamespace

from decimal import Decimal

from app.application.dto.portfolio import DealDTO
from app.domain.entities.mt5_portfolio import MT5Deal
from services.mt5_gateway.deals import (
    deal_commission_text,
    parse_reported_commission,
)


def test_missing_commission_is_not_zero() -> None:
    assert deal_commission_text(SimpleNamespace(ticket=1)) is None
    assert deal_commission_text(SimpleNamespace(commission=None)) is None


def test_numeric_zero_commission_is_preserved() -> None:
    assert deal_commission_text(SimpleNamespace(commission=0)) == "0"
    assert deal_commission_text(SimpleNamespace(commission=0.0)) == "0.0"


def test_nonzero_commission_is_preserved() -> None:
    assert deal_commission_text(SimpleNamespace(commission=-1.5)) == "-1.5"


def test_reported_null_commission_is_not_decimal_zero() -> None:
    assert parse_reported_commission(None) is None
    assert parse_reported_commission("") is None
    assert parse_reported_commission(0) == Decimal("0")
    assert parse_reported_commission("0.0") == Decimal("0.0")
    assert parse_reported_commission("-1.5") == Decimal("-1.5")


def test_missing_deal_commission_serializes_as_null() -> None:
    deal = MT5Deal(
        ticket=1,
        order_ticket=1,
        symbol="XAUUSD",
        side="buy",
        volume=Decimal("0.01"),
        price=Decimal("1"),
        commission=None,
    )
    assert deal.to_dict()["commission"] is None
    assert DealDTO.from_entity(deal).commission is None
