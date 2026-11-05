"""MT5 adapter → BrokerPositionReader for optional PME SL confirmation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.management.broker_confirm import (
    BrokerPositionSnapshot,
)


@dataclass
class Mt5BrokerPositionReader:
    """Read-only position snapshot via existing MT5 adapter. No orders."""

    mt5_adapter: Any
    invalidate_cache: bool = True

    def read_position(self, ticket: int, *, symbol: str) -> BrokerPositionSnapshot:
        adapter = self.mt5_adapter
        if adapter is None:
            return BrokerPositionSnapshot(
                ticket=ticket,
                available=False,
                reason="mt5_adapter missing",
            )
        try:
            if self.invalidate_cache and hasattr(adapter, "invalidate_positions_cache"):
                adapter.invalidate_positions_cache()
            rows = list(adapter.list_positions() or [])
        except Exception as exc:  # fail closed
            return BrokerPositionSnapshot(
                ticket=ticket,
                available=False,
                reason=f"list_positions failed: {type(exc).__name__}",
            )
        match = None
        for row in rows:
            try:
                if int(getattr(row, "ticket", 0) or 0) == int(ticket):
                    match = row
                    break
            except (TypeError, ValueError):
                continue
        if match is None:
            return BrokerPositionSnapshot(
                ticket=ticket,
                available=False,
                reason="ticket absent from broker book",
            )
        try:
            sl_raw = getattr(match, "stop_loss", None)
            if sl_raw is None:
                sl_raw = getattr(match, "sl", None)
            tp_raw = getattr(match, "take_profit", None)
            if tp_raw is None:
                tp_raw = getattr(match, "tp", None)
            vol_raw = getattr(match, "volume", None)
            sl = Decimal(str(sl_raw)) if sl_raw not in (None, "") else None
            tp = Decimal(str(tp_raw)) if tp_raw not in (None, "") else None
            vol = Decimal(str(vol_raw)) if vol_raw not in (None, "") else None
        except Exception:
            return BrokerPositionSnapshot(
                ticket=ticket,
                available=False,
                reason="broker row parse failed",
            )
        _ = symbol  # reserved for multi-symbol filters
        return BrokerPositionSnapshot(
            ticket=ticket,
            available=True,
            stop_loss=sl,
            take_profit=tp,
            volume=vol,
            reason="ok",
        )
