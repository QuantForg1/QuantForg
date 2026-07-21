"""Environment Intelligence — regime/session/spread from supplied facts."""

from __future__ import annotations

from decimal import Decimal

from app.domain.trading_brain_v3.config import TradingBrainConfig
from app.domain.trading_brain_v3.types import BrainInput, ModuleResult


def evaluate_environment(
    inp: BrainInput, config: TradingBrainConfig
) -> ModuleResult:
    reasons: list[str] = []
    score = Decimal("0")
    parts = 0

    has_any = any(
        v is not None
        for v in (inp.spread, inp.atr, inp.regime, inp.session, inp.news_blackout)
    )
    if not has_any:
        return ModuleResult(
            module="environment_intelligence",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="No Trade",
            reasons=(
                "No environment facts supplied — never invents market data",
            ),
            details={},
        )

    if inp.spread is not None:
        parts += 1
        if inp.spread > config.max_spread:
            score += Decimal("20")
            reasons.append(
                f"Spread {inp.spread} exceeds max {config.max_spread}"
            )
        elif inp.spread > config.max_spread / 2:
            score += Decimal("55")
            reasons.append(f"Spread {inp.spread} elevated but usable")
        else:
            score += Decimal("80")
            reasons.append(f"Spread {inp.spread} within comfort")
    if inp.regime is not None:
        parts += 1
        if inp.regime.lower() in {"news", "volatile", "chaotic"}:
            score += Decimal("35")
            reasons.append(f"Regime {inp.regime} hostile to entries")
        else:
            score += Decimal("75")
            reasons.append(f"Regime {inp.regime} observed")
    if inp.session is not None:
        parts += 1
        sess = inp.session.lower()
        if sess in {"london", "ny", "overlap"}:
            score += Decimal("80")
            reasons.append(f"Session {inp.session} supportive")
        else:
            score += Decimal("50")
            reasons.append(f"Session {inp.session} observed")
    if inp.atr is not None:
        parts += 1
        score += Decimal("60")
        reasons.append(f"ATR {inp.atr} supplied (not invented)")
    if inp.news_blackout is True:
        reasons.append("News blackout active — environment veto")
        avg = Decimal("20")
    elif parts:
        avg = (score / Decimal(str(parts))).quantize(Decimal("0.01"))
    else:
        avg = Decimal("0")

    passed = avg >= config.min_environment_score and inp.news_blackout is not True
    rec = "Proceed" if passed else "No Trade"
    if not passed:
        reasons.append("Environment below threshold — recommend No Trade")
    reasons.append("Losses remain possible; no profitability promise")
    return ModuleResult(
        module="environment_intelligence",
        status="available",
        score=avg,
        passed=passed,
        recommendation=rec,
        reasons=tuple(reasons),
        details={
            "min_environment_score": str(config.min_environment_score),
            "spread": str(inp.spread) if inp.spread is not None else None,
            "regime": inp.regime,
            "session": inp.session,
        },
    )
