"""Resolve the single executable BUY/SELL for institutional decisions.

Never prefers BUY. Never invents a side. Weak / conflicting → NONE (NO_TRADE).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.institutional_trading.decision_models import (
    ConfluenceResult,
    TradeDirection,
)


@dataclass(frozen=True, slots=True)
class ExecutableDirection:
    direction: TradeDirection
    reason: str
    source: str  # ai | confluence | none


def _parse_ai_direction(raw: str | None) -> TradeDirection:
    u = (raw or "").strip().upper()
    if u == "BUY":
        return TradeDirection.BUY
    if u == "SELL":
        return TradeDirection.SELL
    return TradeDirection.NONE


def resolve_executable_direction(
    *,
    confluence: ConfluenceResult,
    ai_direction: str | None = None,
    ai_reject: bool | None = None,
    scalping: bool = False,
) -> ExecutableDirection:
    """Pick the final validated side for OMS — or NONE.

    Scalping: when AI quality gates pass with BUY/SELL, that side is authoritative.
    If confluence has the opposite side → NONE (never flip AI into a BUY OMS fill).
    Swing / no AI: confluence only; never default NONE → BUY.
    """
    ai_dir = _parse_ai_direction(ai_direction)

    if (
        scalping
        and ai_reject is False
        and ai_dir
        in {
            TradeDirection.BUY,
            TradeDirection.SELL,
        }
    ):
        if (
            confluence.direction in {TradeDirection.BUY, TradeDirection.SELL}
            and confluence.direction != ai_dir
        ):
            return ExecutableDirection(
                direction=TradeDirection.NONE,
                reason=(
                    f"Validated AI {ai_dir.value} disagrees with confluence "
                    f"{confluence.direction.value} — NO_TRADE"
                ),
                source="none",
            )
        return ExecutableDirection(
            direction=ai_dir,
            reason=f"Validated AI signal {ai_dir.value} (authoritative)",
            source="ai",
        )

    if scalping and ai_reject is True:
        return ExecutableDirection(
            direction=TradeDirection.NONE,
            reason="AI quality gates rejected — NO_TRADE",
            source="none",
        )

    if confluence.direction in {TradeDirection.BUY, TradeDirection.SELL}:
        return ExecutableDirection(
            direction=confluence.direction,
            reason=f"Confluence direction {confluence.direction.value}",
            source="confluence",
        )

    return ExecutableDirection(
        direction=TradeDirection.NONE,
        reason="No validated BUY/SELL edge — NO_TRADE",
        source="none",
    )
