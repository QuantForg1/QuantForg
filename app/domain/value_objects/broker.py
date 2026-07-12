"""Broker identity and server value objects."""

from __future__ import annotations

import re
from typing import Self
from uuid import UUID

from pydantic import field_validator

from app.domain.exceptions.base import ValidationError
from app.domain.value_objects.base import ValueObject

_SERVER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-: ]{0,127}$")
_REGION_PATTERN = re.compile(r"^[A-Z]{2}(-[A-Z0-9]{1,8})?$")


class BrokerId(ValueObject):
    """Typed identity for a broker catalogue entry."""

    value: UUID

    @classmethod
    def of(cls, value: UUID | str) -> Self:
        if isinstance(value, UUID):
            return cls(value=value)
        return cls(value=UUID(str(value)))

    def __str__(self) -> str:
        return str(self.value)


class AccountId(ValueObject):
    """Typed identity for a broker account (integration layer)."""

    value: UUID

    @classmethod
    def of(cls, value: UUID | str) -> Self:
        if isinstance(value, UUID):
            return cls(value=value)
        return cls(value=UUID(str(value)))

    def __str__(self) -> str:
        return str(self.value)


class ServerName(ValueObject):
    """Broker trade server hostname / label (e.g. ``Demo-Server``)."""

    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, raw: str) -> str:
        name = raw.strip()
        if not name:
            return ""
        if not _SERVER_PATTERN.match(name):
            raise ValidationError(
                "Server name must be 1-128 safe hostname characters",
                details={"field": "server_name", "value": raw},
            )
        return name

    @classmethod
    def of(cls, value: str) -> Self:
        return cls(value=value)

    def __str__(self) -> str:
        return self.value


class BrokerRegion(ValueObject):
    """Broker region code (ISO-like, e.g. ``EU``, ``US-EAST``)."""

    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, raw: str) -> str:
        region = raw.strip().upper()
        if not region:
            return ""
        if not _REGION_PATTERN.match(region):
            raise ValidationError(
                "Broker region must look like XX or XX-SUFFIX",
                details={"field": "broker_region", "value": raw},
            )
        return region

    @classmethod
    def of(cls, value: str) -> Self:
        return cls(value=value)

    def __str__(self) -> str:
        return self.value
