"""Shared types for household portfolio honesty."""

from __future__ import annotations

from typing import Literal

DataStatus = Literal[
    "live",
    "cached",
    "stale",
    "disconnected",
    "unavailable",
    "unverified",
]

ConversionStatus = Literal["ok", "unavailable", "native_only"]
