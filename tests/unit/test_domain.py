"""Unit tests for domain base types and exceptions."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.entities.base import Entity
from app.domain.exceptions.base import (
    ConflictError,
    DomainError,
    NotFoundError,
    ValidationError,
)
from app.domain.value_objects.market import Price


@pytest.mark.unit
class TestEntity:
    def test_identity_equality(self) -> None:
        shared_id = uuid4()
        a = Entity(id=shared_id)
        b = Entity(id=shared_id)
        assert a == b
        assert hash(a) == hash(b)

    def test_different_ids_not_equal(self) -> None:
        assert Entity() != Entity()

    def test_touch_updates_timestamp(self) -> None:
        entity = Entity()
        before = entity.updated_at
        entity.touch()
        assert entity.updated_at >= before

    def test_to_dict(self) -> None:
        entity = Entity()
        data = entity.to_dict()
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data


@pytest.mark.unit
class TestValueObject:
    def test_value_equality(self) -> None:
        assert Price.of("1.5") == Price.of("1.5")
        assert Price.of("1.5") != Price.of("2.0")

    def test_frozen(self) -> None:
        price = Price.of("1.0")
        with pytest.raises(Exception):
            price.value = Price.of("2").value  # type: ignore[misc]

    def test_to_dict(self) -> None:
        assert "value" in Price.of("5").to_dict()


@pytest.mark.unit
class TestDomainExceptions:
    def test_domain_error_defaults(self) -> None:
        err = DomainError("something broke")
        assert err.code == "domain_error"
        assert err.message == "something broke"
        assert err.details == {}

    def test_not_found(self) -> None:
        err = NotFoundError("missing", details={"id": "abc"})
        assert err.code == "not_found"
        assert err.details["id"] == "abc"

    def test_validation(self) -> None:
        err = ValidationError()
        assert err.code == "validation_error"

    def test_conflict(self) -> None:
        err = ConflictError()
        assert err.code == "conflict"
