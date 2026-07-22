"""Types for Integration Sprint V1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class FeedHealth:
    feed: str
    status: str  # healthy | degraded | missing | error
    latency_ms: float | None
    freshness_seconds: float | None
    synchronized: bool | None
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feed": self.feed,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "freshness_seconds": self.freshness_seconds,
            "synchronized": self.synchronized,
            "message": self.message,
            "details": dict(self.details),
            "read_only": True,
            "never_places_trades": True,
        }


@dataclass(frozen=True, slots=True)
class FeedSnapshot:
    feed: str
    available: bool
    payload: dict[str, Any] | list[Any] | None
    health: FeedHealth
    missing_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "feed": self.feed,
            "available": self.available,
            "payload": self.payload,
            "health": self.health.to_dict(),
            "missing_reason": self.missing_reason,
            "read_only": True,
            "invented": False,
        }
