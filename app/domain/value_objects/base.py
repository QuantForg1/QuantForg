"""Pydantic-backed immutable value object base.

Value objects in QuantForg are frozen Pydantic models. They validate on
construction, compare by value, and never mutate after creation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ValueObject(BaseModel):
    """Immutable validated value object.

    Subclasses declare fields with Pydantic validators. The model is frozen
    so attribute assignment after construction raises an error.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=False,
        str_strip_whitespace=True,
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary suitable for logging or transport."""
        return self.model_dump(mode="json")
