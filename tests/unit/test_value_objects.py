"""Unit tests for domain value objects."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.exceptions.base import ValidationError
from app.domain.value_objects.confidence import Confidence
from app.domain.value_objects.email import EmailAddress
from app.domain.value_objects.identity import (
    AccountNumber,
    EntitySlug,
    Leverage,
    PersonName,
    PipSize,
    SymbolCode,
    VersionLabel,
)
from app.domain.value_objects.market import Percentage, Price, Quantity
from app.domain.value_objects.money import Money


@pytest.mark.unit
class TestEmailAddress:
    def test_normalises(self) -> None:
        assert EmailAddress(value="  Foo@Bar.COM ").value == "foo@bar.com"

    def test_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError):
            EmailAddress(value="not-an-email")


@pytest.mark.unit
class TestMoney:
    def test_add_same_currency(self) -> None:
        a = Money.of("10.50", "USD")
        b = Money.of("1.25", "USD")
        assert a.add(b).amount == Decimal("11.75")

    def test_rejects_float(self) -> None:
        with pytest.raises(ValidationError):
            Money.of(1.5, "USD")  # type: ignore[arg-type]

    def test_currency_mismatch(self) -> None:
        with pytest.raises(ValidationError):
            Money.of("1", "USD").add(Money.of("1", "EUR"))


@pytest.mark.unit
class TestMarketVOs:
    def test_price_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            Price.of("-1")

    def test_quantity_positive(self) -> None:
        assert Quantity.of("0.1").value == Decimal("0.1")
        with pytest.raises(ValidationError):
            Quantity.of("0")

    def test_percentage_bounds(self) -> None:
        assert Percentage.of("50").as_ratio() == Decimal("0.5")
        with pytest.raises(ValidationError):
            Percentage.of("101")


@pytest.mark.unit
class TestIdentityVOs:
    def test_symbol_code(self) -> None:
        assert SymbolCode.of("eurusd").value == "EURUSD"

    def test_account_number(self) -> None:
        assert str(AccountNumber.of("ACC-12345")) == "ACC-12345"

    def test_slug(self) -> None:
        assert EntitySlug.of("My-Broker").value == "my-broker"
        with pytest.raises(ValidationError):
            EntitySlug.of("Bad Slug!")

    def test_leverage(self) -> None:
        assert str(Leverage.of(100)) == "1:100"

    def test_version(self) -> None:
        assert VersionLabel.of("1.2.3").value == "1.2.3"

    def test_pip_size(self) -> None:
        assert PipSize.of("0.0001").value == Decimal("0.0001")

    def test_person_name(self) -> None:
        assert PersonName.of("  Alice  ").value == "Alice"


@pytest.mark.unit
class TestConfidence:
    def test_bounds(self) -> None:
        assert Confidence.of("0.85").value == Decimal("0.85")
        with pytest.raises(ValidationError):
            Confidence.of("1.5")
