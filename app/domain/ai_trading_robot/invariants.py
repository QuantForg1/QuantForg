"""Hard invariants — capital preservation over aggression."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

FORBIDDEN_TECHNIQUES: frozenset[str] = frozenset(
    {
        "martingale",
        "grid",
        "average_down",
        "average_losing",
        "pyramid_into_loss",
        "double_after_loss",
        "recovery_lot",
    }
)


@dataclass(frozen=True, slots=True)
class InvariantCheck:
    ok: bool
    reasons: tuple[str, ...]
    techniques_blocked: tuple[str, ...]


def assert_no_forbidden_technique(name: str | None) -> InvariantCheck:
    raw = (name or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not raw:
        return InvariantCheck(ok=True, reasons=(), techniques_blocked=())
    hits = tuple(sorted(t for t in FORBIDDEN_TECHNIQUES if t in raw))
    if hits:
        return InvariantCheck(
            ok=False,
            reasons=(
                f"Forbidden technique blocked: {', '.join(hits)}. "
                "Robot V1 never uses martingale, grid, or averaging losers.",
            ),
            techniques_blocked=hits,
        )
    return InvariantCheck(ok=True, reasons=(), techniques_blocked=())


def risk_must_decrease_after_drawdown(
    *,
    base_risk_pct: Decimal,
    current_drawdown_pct: Decimal,
    consecutive_losses: int,
    reduction_per_loss: Decimal = Decimal("0.25"),
    reduction_per_dd_pct: Decimal = Decimal("0.10"),
    floor_pct: Decimal = Decimal("0.25"),
) -> Decimal:
    """Shrink risk after losses / drawdown — never increase.

    Example: base 1.0%, 2 losses → 0.50%; +2% DD → further cut.
    """
    risk = base_risk_pct
    if consecutive_losses > 0:
        risk = risk - (Decimal(consecutive_losses) * reduction_per_loss)
    if current_drawdown_pct > 0:
        risk = risk - (current_drawdown_pct * reduction_per_dd_pct)
    if risk < floor_pct:
        risk = floor_pct
    if risk > base_risk_pct:
        risk = base_risk_pct  # never allow increase vs base
    return risk.quantize(Decimal("0.01"))


def reject_averaging_into_loss(
    *,
    open_side: str | None,
    proposed_side: str,
    open_unrealized_pnl: Decimal | None,
) -> InvariantCheck:
    """Block adding to a losing position in the same direction."""
    if not open_side or open_unrealized_pnl is None:
        return InvariantCheck(ok=True, reasons=(), techniques_blocked=())
    same = open_side.strip().lower() == proposed_side.strip().lower()
    if same and open_unrealized_pnl < 0:
        return InvariantCheck(
            ok=False,
            reasons=(
                "Averaging into a losing position is forbidden "
                "(no add-to-loser / grid recovery).",
            ),
            techniques_blocked=("average_losing",),
        )
    return InvariantCheck(ok=True, reasons=(), techniques_blocked=())
