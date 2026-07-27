"""Slippage protection — measure requested vs filled; journal & gate."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class SlippageAssessment:
    requested_price: Decimal | None
    filled_price: Decimal | None
    slippage: Decimal | None
    latency_ms: float | None
    exceeded: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_price": (
                str(self.requested_price) if self.requested_price is not None else None
            ),
            "filled_price": (
                str(self.filled_price) if self.filled_price is not None else None
            ),
            "slippage": str(self.slippage) if self.slippage is not None else None,
            "latency_ms": (
                round(self.latency_ms, 3) if self.latency_ms is not None else None
            ),
            "exceeded": self.exceeded,
            "reason": self.reason,
        }


def measure_slippage(
    *,
    side: str,
    requested_price: Decimal | None,
    filled_price: Decimal | None,
    max_slippage: Decimal,
    latency_ms: float | None = None,
) -> SlippageAssessment:
    """Adverse slippage vs requested. Never invents fills."""
    if requested_price is None or filled_price is None:
        return SlippageAssessment(
            requested_price=requested_price,
            filled_price=filled_price,
            slippage=None,
            latency_ms=latency_ms,
            exceeded=False,
            reason="Slippage not measurable — missing requested or fill price",
        )
    side_l = (side or "").lower()
    if side_l in {"buy", "long"}:
        slip = filled_price - requested_price  # adverse if fill higher
    else:
        slip = requested_price - filled_price  # adverse if fill lower
    exceeded = slip > max_slippage
    return SlippageAssessment(
        requested_price=requested_price,
        filled_price=filled_price,
        slippage=slip,
        latency_ms=latency_ms,
        exceeded=exceeded,
        reason=(
            f"Slippage {slip} exceeds tolerance {max_slippage}"
            if exceeded
            else f"Slippage {slip} within tolerance {max_slippage}"
        ),
    )


def extract_fill_price(raw: dict[str, Any] | None) -> Decimal | None:
    if not raw:
        return None
    for key in (
        "fill_price",
        "filled_price",
        "price",
        "avg_price",
        "deal_price",
        "execution_price",
    ):
        val = raw.get(key)
        if val is None and isinstance(raw.get("result"), dict):
            val = raw["result"].get(key)
        if val is None:
            continue
        try:
            d = Decimal(str(val))
            if d > 0:
                return d
        except Exception:
            continue
    return None
