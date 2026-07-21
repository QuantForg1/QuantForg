"""Trade veto system — hard rejects from capital-preservation rules."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.decision_intelligence.config import DecisionIntelligenceConfig


@dataclass(frozen=True, slots=True)
class VetoInput:
    spread: Decimal | None = None
    daily_drawdown_pct: Decimal = Decimal("0")
    consecutive_losses: int = 0
    forbidden_technique: bool = False
    operator_veto: bool = False
    operator_veto_reason: str = ""


@dataclass(frozen=True, slots=True)
class VetoResult:
    clear: bool
    vetoes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "clear": self.clear,
            "vetoes": list(self.vetoes),
        }


def evaluate_vetoes(
    config: DecisionIntelligenceConfig, inp: VetoInput
) -> VetoResult:
    vetoes: list[str] = []
    if inp.forbidden_technique:
        vetoes.append("Forbidden technique (martingale/grid/average-down).")
    if inp.spread is None:
        vetoes.append("Spread unavailable — veto fail-closed.")
    elif inp.spread > config.max_spread:
        vetoes.append(
            f"Abnormal spread {inp.spread} exceeds {config.max_spread}."
        )
    if inp.daily_drawdown_pct >= config.max_daily_drawdown_pct:
        vetoes.append(
            f"Daily drawdown {inp.daily_drawdown_pct}% >= "
            f"{config.max_daily_drawdown_pct}%."
        )
    if inp.consecutive_losses >= config.max_consecutive_losses:
        vetoes.append(
            f"Consecutive losses {inp.consecutive_losses} >= "
            f"{config.max_consecutive_losses}."
        )
    if inp.operator_veto:
        vetoes.append(
            inp.operator_veto_reason or "Operator veto applied."
        )
    return VetoResult(clear=len(vetoes) == 0, vetoes=tuple(vetoes))
