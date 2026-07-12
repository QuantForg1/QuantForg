"""MarketSnapshot — point-in-time aggregate view for one or more symbols.

Why it exists
-------------
A MarketSnapshot bundles the latest known tick, quote, spread, and optional
candle for a symbol (or a set of per-symbol views) at a UTC capture time.
It is a read-model-friendly immutable record — not a trading decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Self
from uuid import UUID, uuid4

from app.domain.entities._guards import require
from app.domain.market_data._validation import ensure_utc
from app.domain.market_data.candle import Candle
from app.domain.market_data.quote import Quote
from app.domain.market_data.spread import Spread
from app.domain.market_data.tick import Tick
from app.domain.value_objects.identity import SymbolCode


@dataclass(frozen=True, kw_only=True, slots=True)
class SymbolMarketView:
    """Immutable per-symbol slice inside a :class:`MarketSnapshot`."""

    symbol_code: SymbolCode
    tick: Tick | None = None
    quote: Quote | None = None
    spread: Spread | None = None
    candle: Candle | None = None

    def __post_init__(self) -> None:
        require(
            isinstance(self.symbol_code, SymbolCode),
            "symbol_code must be a SymbolCode",
        )
        for label, observation in (
            ("tick", self.tick),
            ("quote", self.quote),
            ("spread", self.spread),
            ("candle", self.candle),
        ):
            if observation is not None:
                require(
                    observation.symbol_code == self.symbol_code,
                    f"{label} symbol_code must match view symbol_code",
                    view=str(self.symbol_code),
                    observation=str(observation.symbol_code),
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol_code": str(self.symbol_code),
            "tick": self.tick.to_dict() if self.tick else None,
            "quote": self.quote.to_dict() if self.quote else None,
            "spread": self.spread.to_dict() if self.spread else None,
            "candle": self.candle.to_dict() if self.candle else None,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class MarketSnapshot:
    """Immutable multi-symbol market snapshot.

    Supports one or many symbols via ``views``. A single-symbol snapshot is
    simply a snapshot with exactly one view.
    """

    views: tuple[SymbolMarketView, ...]
    captured_at: datetime
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "captured_at",
            ensure_utc(self.captured_at, field="captured_at"),
        )
        require(len(self.views) >= 1, "snapshot must contain at least one symbol view")
        codes = [view.symbol_code.value for view in self.views]
        require(
            len(codes) == len(set(codes)),
            "snapshot must not contain duplicate symbol codes",
            symbols=codes,
        )

    @classmethod
    def create(
        cls,
        *,
        views: list[SymbolMarketView] | tuple[SymbolMarketView, ...],
        captured_at: datetime | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: build a snapshot from one or more symbol views."""
        kwargs: dict[str, object] = {
            "views": tuple(views),
            "captured_at": captured_at or datetime.now(UTC),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    @classmethod
    def for_symbol(
        cls,
        *,
        symbol_code: str | SymbolCode,
        tick: Tick | None = None,
        quote: Quote | None = None,
        spread: Spread | None = None,
        candle: Candle | None = None,
        captured_at: datetime | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: convenience builder for a single-symbol snapshot."""
        code = (
            symbol_code
            if isinstance(symbol_code, SymbolCode)
            else SymbolCode(value=symbol_code)
        )
        view = SymbolMarketView(
            symbol_code=code,
            tick=tick,
            quote=quote,
            spread=spread,
            candle=candle,
        )
        return cls.create(views=(view,), captured_at=captured_at, entity_id=entity_id)

    @property
    def symbol_codes(self) -> tuple[str, ...]:
        """Return all symbol codes covered by this snapshot."""
        return tuple(view.symbol_code.value for view in self.views)

    def view_for(self, symbol_code: str | SymbolCode) -> SymbolMarketView | None:
        """Look up the view for a symbol code, if present."""
        code = (
            symbol_code
            if isinstance(symbol_code, SymbolCode)
            else SymbolCode(value=symbol_code)
        )
        for view in self.views:
            if view.symbol_code == code:
                return view
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "captured_at": self.captured_at.isoformat(),
            "symbol_codes": list(self.symbol_codes),
            "views": [view.to_dict() for view in self.views],
        }
