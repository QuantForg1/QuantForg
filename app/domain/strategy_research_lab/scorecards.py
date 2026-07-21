"""Strategy Scorecards — from supplied validation metrics only."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.strategy_research_lab.config import StrategyLabConfig


@dataclass(frozen=True, slots=True)
class ScorecardInput:
    strategy_key: str
    profit_factor: Decimal | None = None
    sharpe: Decimal | None = None
    max_drawdown_pct: Decimal | None = None
    trade_count: int | None = None
    win_rate: Decimal | None = None
    stability: Decimal | None = None


@dataclass(frozen=True, slots=True)
class StrategyScorecard:
    strategy_key: str
    score: Decimal
    passed: bool
    grades: dict[str, str]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_key": self.strategy_key,
            "score": str(self.score),
            "passed": self.passed,
            "grades": dict(self.grades),
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "status": self.status,
            "lab_only": True,
        }


def build_strategy_scorecard(
    config: StrategyLabConfig, inp: ScorecardInput
) -> StrategyScorecard:
    strengths: list[str] = []
    weaknesses: list[str] = []
    grades: dict[str, str] = {}
    score = Decimal("40")
    present = 0

    if inp.profit_factor is not None:
        present += 1
        if inp.profit_factor >= config.min_profit_factor:
            score += Decimal("15")
            grades["profit_factor"] = "pass"
            strengths.append(f"Profit factor {inp.profit_factor}")
        else:
            grades["profit_factor"] = "fail"
            weaknesses.append(
                f"Profit factor {inp.profit_factor} < {config.min_profit_factor}"
            )
    else:
        grades["profit_factor"] = "unavailable"

    if inp.sharpe is not None:
        present += 1
        if inp.sharpe >= config.min_sharpe:
            score += Decimal("15")
            grades["sharpe"] = "pass"
            strengths.append(f"Sharpe {inp.sharpe}")
        else:
            grades["sharpe"] = "fail"
            weaknesses.append(f"Sharpe {inp.sharpe} < {config.min_sharpe}")
    else:
        grades["sharpe"] = "unavailable"

    if inp.max_drawdown_pct is not None:
        present += 1
        if inp.max_drawdown_pct <= config.max_drawdown_pct:
            score += Decimal("10")
            grades["drawdown"] = "pass"
            strengths.append(f"Drawdown {inp.max_drawdown_pct}% within cap")
        else:
            grades["drawdown"] = "fail"
            weaknesses.append(
                f"Drawdown {inp.max_drawdown_pct}% > {config.max_drawdown_pct}%"
            )
    else:
        grades["drawdown"] = "unavailable"

    if inp.trade_count is not None:
        present += 1
        if inp.trade_count >= config.min_trades:
            score += Decimal("10")
            grades["sample_size"] = "pass"
            strengths.append(f"Trade count {inp.trade_count}")
        else:
            grades["sample_size"] = "fail"
            weaknesses.append(
                f"Trade count {inp.trade_count} < {config.min_trades}"
            )
    else:
        grades["sample_size"] = "unavailable"

    if inp.stability is not None:
        present += 1
        if inp.stability >= Decimal("0.5"):
            score += Decimal("10")
            grades["stability"] = "pass"
            strengths.append(f"Stability {inp.stability}")
        else:
            grades["stability"] = "fail"
            weaknesses.append(f"Stability {inp.stability} weak")
    else:
        grades["stability"] = "unavailable"

    if present == 0:
        return StrategyScorecard(
            strategy_key=inp.strategy_key,
            score=Decimal("0"),
            passed=False,
            grades=grades,
            strengths=(),
            weaknesses=("No metrics supplied — scorecard unavailable.",),
            status="unavailable",
        )

    score = max(Decimal("0"), min(Decimal("100"), score)).quantize(Decimal("0.01"))
    passed = score >= config.min_scorecard and not any(
        g == "fail" for g in grades.values()
    )
    return StrategyScorecard(
        strategy_key=inp.strategy_key,
        score=score,
        passed=passed,
        grades=grades,
        strengths=tuple(strengths),
        weaknesses=tuple(weaknesses)
        or ("No critical weaknesses in supplied metrics.",),
        status="available",
    )
