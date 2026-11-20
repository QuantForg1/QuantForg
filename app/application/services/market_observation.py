"""Build an observation report from a public quote. Read-only."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.market_observation import ObservationInput, build_market_observation


def observation_from_tick_bundle(
    bundle: Any | None,
    *,
    symbol: str,
    read_at: datetime | None = None,
) -> dict[str, Any]:
    """Map a public tick bundle. A missing bundle stays unavailable."""
    clock = read_at or datetime.now(UTC)
    tick = getattr(bundle, "tick", None) if bundle is not None else None
    return build_market_observation(
        ObservationInput(
            symbol=str(getattr(bundle, "symbol", None) or symbol),
            read_at=clock,
            quote_time=getattr(tick, "timestamp", None) if tick is not None else None,
            bid=getattr(tick, "bid", None) if tick is not None else None,
            ask=getattr(tick, "ask", None) if tick is not None else None,
            spread=getattr(tick, "spread", None) if tick is not None else None,
            source=str(getattr(bundle, "source", "") or "none"),
            quote_status=str(getattr(bundle, "status", "") or "unavailable"),
        )
    )
