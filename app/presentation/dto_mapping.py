"""Helpers for mapping application DTOs to presentation responses."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def dto_to_dict(dto: Any) -> dict[str, Any]:
    """Convert a (possibly slotted) dataclass DTO into a plain dict.

    Slotted dataclasses do not expose ``__dict__``; routers must use this
    helper instead of ``dto.__dict__`` to avoid AttributeError → HTTP 500.
    """
    if is_dataclass(dto) and not isinstance(dto, type):
        return asdict(dto)
    raw = getattr(dto, "__dict__", None)
    if isinstance(raw, dict):
        return dict(raw)
    msg = f"Unsupported DTO type for response mapping: {type(dto)!r}"
    raise TypeError(msg)
