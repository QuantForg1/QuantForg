"""Core intelligence engines — supplied facts only, prefer No Trade."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.scalping_ai_v2.config import ScalpingAiV2Config
from app.domain.scalping_ai_v2.types import ModuleResult, ScalpCycleInput


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def evaluate_market_quality(
    inp: ScalpCycleInput, config: ScalpingAiV2Config
) -> ModuleResult:
    reasons: list[str] = []
    has_any = any(
        v is not None
        for v in (
            inp.spread,
            inp.atr,
            inp.regime,
            inp.session,
            inp.trend,
            inp.volatility,
            inp.liquidity_state,
            inp.market_health,
            inp.confidence,
        )
    )
    if not has_any:
        return ModuleResult(
            module="market_quality_engine",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="No Trade",
            reasons=(
                "No market quality facts — never invents market data",
                "Prefer No Trade over poor-quality trades",
            ),
        )

    score = Decimal("0")
    parts = 0
    spread = inp.spread
    if spread is None and inp.bid is not None and inp.ask is not None:
        spread = abs(inp.ask - inp.bid)

    if spread is not None:
        parts += 1
        if spread > config.max_spread:
            score += Decimal("15")
            reasons.append(f"Spread {spread} exceeds max {config.max_spread}")
        else:
            score += Decimal("80")
            reasons.append(f"Spread {spread} acceptable")
    if inp.regime is not None:
        parts += 1
        if str(inp.regime).lower() in {"news", "chaotic", "volatile"}:
            score += Decimal("25")
            reasons.append(f"Regime {inp.regime} hostile to scalping")
        else:
            score += Decimal("75")
            reasons.append(f"Regime {inp.regime} observed")
    if inp.session is not None:
        parts += 1
        sess = str(inp.session).lower()
        if sess in {s.lower() for s in config.allowed_sessions}:
            score += Decimal("80")
            reasons.append(f"Session {inp.session} allowed")
        else:
            score += Decimal("20")
            reasons.append(f"Session {inp.session} outside allowed set")
    if inp.trend is not None:
        parts += 1
        score += Decimal("70")
        reasons.append(f"Trend {inp.trend} supplied")
    if inp.volatility is not None:
        parts += 1
        score += Decimal("65")
        reasons.append(f"Volatility {inp.volatility} supplied")
    if inp.liquidity_state is not None:
        parts += 1
        score += Decimal("70")
        reasons.append(f"Liquidity {inp.liquidity_state} supplied")
    if inp.market_health is not None:
        parts += 1
        if str(inp.market_health).lower() in {"poor", "degraded", "offline"}:
            score += Decimal("15")
            reasons.append(f"Market health {inp.market_health} — No Trade bias")
        else:
            score += Decimal("80")
            reasons.append(f"Market health {inp.market_health}")
    if inp.atr is not None and inp.price is not None and inp.price > 0:
        parts += 1
        atr_pct = (inp.atr / inp.price) * Decimal("100")
        if atr_pct < config.min_atr_pct or atr_pct > config.max_atr_pct:
            score += Decimal("25")
            reasons.append(f"ATR% {atr_pct:.4f} outside band")
        else:
            score += Decimal("75")
            reasons.append(f"ATR% {atr_pct:.4f} within band")
    if inp.confidence is not None:
        parts += 1
        if inp.confidence >= config.min_confidence:
            score += Decimal("80")
            reasons.append(f"Confidence {inp.confidence} meets min")
        else:
            score += Decimal("30")
            reasons.append(f"Confidence {inp.confidence} below min")

    avg = (score / Decimal(parts)).quantize(Decimal("0.01")) if parts else Decimal("0")
    passed = avg >= config.min_market_quality
    reasons.append(f"Market quality {avg} vs min {config.min_market_quality}")
    reasons.append("Never promises profitability")
    return ModuleResult(
        module="market_quality_engine",
        status="available",
        score=avg,
        passed=passed,
        recommendation="Proceed" if passed else "No Trade",
        reasons=tuple(reasons),
        details={"confidence_score": str(inp.confidence) if inp.confidence else None},
    )


def evaluate_multi_timeframe(
    inp: ScalpCycleInput, config: ScalpingAiV2Config
) -> ModuleResult:
    _ = config
    if all(
        v is None
        for v in (
            inp.htf_bias,
            inp.ltf_confirmation,
            inp.trend_strength,
            inp.trend_consistency,
        )
    ):
        return ModuleResult(
            module="multi_timeframe_trend_engine",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="No Trade",
            reasons=("No multi-timeframe facts supplied",),
        )
    reasons: list[str] = []
    score = Decimal("50")
    if inp.htf_bias:
        reasons.append(f"HTF bias {inp.htf_bias}")
        score += Decimal("10")
    if inp.ltf_confirmation:
        reasons.append(f"LTF confirmation {inp.ltf_confirmation}")
        if inp.htf_bias and str(inp.htf_bias).lower() == str(
            inp.ltf_confirmation
        ).lower():
            score += Decimal("20")
            reasons.append("HTF/LTF aligned")
        else:
            score -= Decimal("15")
            reasons.append("HTF/LTF misaligned — prefer No Trade")
    if inp.trend_strength is not None:
        reasons.append(f"Trend strength {inp.trend_strength}")
        score += min(inp.trend_strength / Decimal("5"), Decimal("15"))
    if inp.trend_consistency is not None:
        reasons.append(f"Trend consistency {inp.trend_consistency}")
        score += min(inp.trend_consistency / Decimal("5"), Decimal("15"))
    score = min(max(score, Decimal("0")), Decimal("100")).quantize(Decimal("0.01"))
    passed = score >= Decimal("55") and not (
        inp.htf_bias
        and inp.ltf_confirmation
        and str(inp.htf_bias).lower() != str(inp.ltf_confirmation).lower()
    )
    return ModuleResult(
        module="multi_timeframe_trend_engine",
        status="available",
        score=score,
        passed=passed,
        recommendation="Proceed" if passed else "No Trade",
        reasons=tuple(reasons),
    )


def evaluate_liquidity(
    inp: ScalpCycleInput, config: ScalpingAiV2Config
) -> ModuleResult:
    _ = config
    if all(
        v is None
        for v in (
            inp.sweep_detected,
            inp.equal_highs_lows,
            inp.session_liquidity,
            inp.liquidity_side,
            inp.stop_hunt,
        )
    ):
        return ModuleResult(
            module="liquidity_intelligence",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="No Trade",
            reasons=("No liquidity facts supplied — never invents sweeps",),
        )
    reasons: list[str] = []
    score = Decimal("55")
    if inp.sweep_detected is True:
        score += Decimal("15")
        reasons.append("Liquidity sweep detected (supplied)")
    if inp.equal_highs_lows is True:
        score += Decimal("10")
        reasons.append("Equal highs/lows observed")
    if inp.session_liquidity:
        reasons.append(f"Session liquidity {inp.session_liquidity}")
        score += Decimal("5")
    if inp.liquidity_side:
        reasons.append(f"Liquidity side {inp.liquidity_side}")
    if inp.stop_hunt is True:
        score -= Decimal("20")
        reasons.append("Stop hunt risk — caution / No Trade bias")
    score = min(max(score, Decimal("0")), Decimal("100")).quantize(Decimal("0.01"))
    passed = score >= Decimal("50") and inp.stop_hunt is not True
    return ModuleResult(
        module="liquidity_intelligence",
        status="available",
        score=score,
        passed=passed,
        recommendation="Proceed" if passed else "No Trade",
        reasons=tuple(reasons) or ("Liquidity snapshot evaluated",),
    )


def evaluate_market_structure(
    inp: ScalpCycleInput, config: ScalpingAiV2Config
) -> ModuleResult:
    _ = config
    if all(
        v is None
        for v in (inp.bos, inp.choch, inp.mss, inp.swing_bias, inp.structure_phase)
    ):
        return ModuleResult(
            module="market_structure_engine",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="No Trade",
            reasons=("No structure facts supplied",),
        )
    reasons: list[str] = []
    score = Decimal("50")
    if inp.bos is True:
        score += Decimal("15")
        reasons.append("BOS true")
    if inp.choch is True:
        score += Decimal("10")
        reasons.append("CHOCH true")
    if inp.mss is True:
        score += Decimal("10")
        reasons.append("MSS true")
    if inp.swing_bias:
        reasons.append(f"Swing bias {inp.swing_bias}")
        score += Decimal("5")
    if inp.structure_phase:
        reasons.append(f"Phase {inp.structure_phase}")
        if str(inp.structure_phase).lower() == "reversal" and not inp.choch:
            score -= Decimal("10")
            reasons.append("Reversal without CHOCH — caution")
    score = min(max(score, Decimal("0")), Decimal("100")).quantize(Decimal("0.01"))
    passed = score >= Decimal("55")
    return ModuleResult(
        module="market_structure_engine",
        status="available",
        score=score,
        passed=passed,
        recommendation="Proceed" if passed else "No Trade",
        reasons=tuple(reasons) or ("Structure evaluated",),
    )


def rank_opportunities(
    inp: ScalpCycleInput, config: ScalpingAiV2Config
) -> ModuleResult:
    opps = inp.opportunities
    if opps is None:
        return ModuleResult(
            module="opportunity_ranking_engine",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="No Trade",
            reasons=("No opportunities supplied — never invents setups",),
        )
    if len(opps) == 0:
        return ModuleResult(
            module="opportunity_ranking_engine",
            status="empty",
            score=Decimal("0"),
            passed=False,
            recommendation="No Trade",
            reasons=("Empty opportunity list — prefer No Trade",),
            details={"ranked": []},
        )

    ranked: list[dict[str, Any]] = []
    for i, raw in enumerate(opps):
        if not isinstance(raw, dict):
            continue
        q = _dec(raw.get("quality_score"))
        c = _dec(raw.get("confidence_score"))
        r = _dec(raw.get("risk_score"))
        e = _dec(raw.get("execution_score"))
        if all(x is None for x in (q, c, r, e)):
            ranked.append(
                {
                    "id": str(raw.get("id") or f"opp_{i}"),
                    "status": "unavailable",
                    "reason": "Scores missing — not invented",
                }
            )
            continue
        # Lower risk_score is better; invert for composite.
        risk_component = (
            (Decimal("100") - r) if r is not None else Decimal("50")
        )
        parts = [
            x
            for x in (q, c, risk_component, e)
            if x is not None
        ]
        composite = (sum(parts) / Decimal(len(parts))).quantize(Decimal("0.01"))
        ok = (
            (q is None or q >= config.min_quality_score)
            and (c is None or c >= config.min_confidence)
            and (e is None or e >= config.min_execution_score)
            and (r is None or r <= config.max_risk_score)
        )
        ranked.append(
            {
                "id": str(raw.get("id") or f"opp_{i}"),
                "status": "available",
                "quality_score": str(q) if q is not None else None,
                "confidence_score": str(c) if c is not None else None,
                "risk_score": str(r) if r is not None else None,
                "execution_score": str(e) if e is not None else None,
                "composite": str(composite),
                "eligible": ok,
            }
        )

    eligible = [
        r
        for r in ranked
        if r.get("status") == "available" and r.get("eligible") is True
    ]
    eligible.sort(key=lambda x: Decimal(str(x["composite"])), reverse=True)
    if not eligible:
        return ModuleResult(
            module="opportunity_ranking_engine",
            status="available",
            score=Decimal("0"),
            passed=False,
            recommendation="No Trade",
            reasons=(
                "No opportunity met quality/confidence/risk/execution gates",
                "Only highest quality may proceed",
            ),
            details={"ranked": ranked},
        )
    top = eligible[0]
    return ModuleResult(
        module="opportunity_ranking_engine",
        status="available",
        score=Decimal(str(top["composite"])),
        passed=True,
        recommendation="Proceed",
        reasons=(
            f"Top opportunity {top['id']} composite {top['composite']}",
            "Lower-ranked setups held",
        ),
        details={"ranked": ranked, "selected": top},
    )
