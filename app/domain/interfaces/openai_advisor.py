"""OpenAI advisor port — advice only; never places orders (ADR-0015)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

ALLOWED_STANCES = frozenset(
    {"HOLD", "LEAN_LONG", "LEAN_SHORT", "NO_TRADE", "UNKNOWN"}
)


@dataclass(frozen=True, slots=True)
class OpenAIAdvice:
    """Validated advisory payload. ``authorizes_trade`` is always False."""

    advisory_only: bool
    stance: str
    confidence: float
    summary: str
    risks: tuple[str, ...] = ()
    model: str = ""
    authorizes_trade: bool = False
    provider_status: str = "ok"
    detail: str = ""
    raw_keys: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "advisory_only": True,
            "stance": self.stance,
            "confidence": self.confidence,
            "summary": self.summary,
            "risks": list(self.risks),
            "model": self.model,
            "authorizes_trade": False,
            "provider_status": self.provider_status,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class OpenAIProviderStatus:
    """Safe provider diagnostics — never includes the API key."""

    configured: bool
    enabled: bool
    model: str
    status: str
    detail: str
    base_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": "openai",
            "configured": self.configured,
            "enabled": self.enabled,
            "model": self.model,
            "status": self.status,
            "detail": self.detail,
            "base_url": self.base_url,
            "authorizes_trade": False,
            "gemini": False,
        }


class OpenAIAdvisorPort(Protocol):
    """Produce non-authoritative trading advice via OpenAI Responses API."""

    def provider_status(self) -> OpenAIProviderStatus:
        """Return configuration status without calling the network."""
        ...

    async def advise(
        self,
        *,
        symbol: str,
        market_snapshot: dict[str, Any],
        instructions: str | None = None,
    ) -> OpenAIAdvice:
        """Return structured advice. Never calls MT5 or OMS."""
        ...
