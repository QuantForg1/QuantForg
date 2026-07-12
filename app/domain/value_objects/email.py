"""Email address value object."""

from __future__ import annotations

import re

from pydantic import field_validator

from app.domain.exceptions.base import ValidationError
from app.domain.value_objects.base import ValueObject

_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


class EmailAddress(ValueObject):
    """Canonical, lower-cased email address.

    Why it exists
    -------------
    Emails appear on User and AuditLog contexts. Centralising format and
    normalisation prevents invalid addresses from entering the domain.
    """

    value: str

    @field_validator("value")
    @classmethod
    def _validate_email(cls, raw: str) -> str:
        normalised = raw.strip().lower()
        if not normalised or len(normalised) > 254:
            raise ValidationError(
                "Email address must be between 1 and 254 characters",
                details={"field": "email"},
            )
        if not _EMAIL_PATTERN.match(normalised):
            raise ValidationError(
                "Email address format is invalid",
                details={"field": "email", "value": raw},
            )
        return normalised

    def __str__(self) -> str:
        return self.value
