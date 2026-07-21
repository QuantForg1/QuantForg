"""Alpha Engine scorers — supplied market facts only; never invent data."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.alpha_engine.config import AlphaEngineConfig
from app.domain.alpha_engine.score import EngineScore, empty, scored, unavailable


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def score_regime(
    config: AlphaEngineConfig, facts: dict[str, Any] | None
) -> EngineScore:
    title = "Market Regime Engine"
    if facts is None:
        return unavailable(
            "market_regime",
            title,
            "Regime facts not supplied",
            threshold=config.min_regime_score,
        )
    trend = str(facts.get("trend") or "").strip().lower()
    atr = _dec(facts.get("atr"))
    price = _dec(facts.get("price"))
    news = facts.get("news_driven")
    structure = str(facts.get("structure_label") or "").strip()
    if not trend and atr is None and not structure and news is None:
        return empty(
            "market_regime",
            title,
            "Insufficient regime inputs — no invented regime",
            threshold=config.min_regime_score,
        )
    reasons: list[str] = []
    score = Decimal("50")
    bullish = trend in {"up", "bullish", "trending_up"}
    bearish = trend in {"down", "bearish", "trending_down"}
    if bullish or bearish:
        score += Decimal("15")
        reasons.append(f"Trend={trend}")
    elif trend in {"ranging", "range", "sideways", "neutral"}:
        score += Decimal("5")
        reasons.append(f"Trend={trend}")
    elif trend:
        reasons.append(f"Unrecognized trend label={trend}")
    if structure:
        score += Decimal("10")
        reasons.append(f"Structure={structure}")
    atr_pct: Decimal | None = None
    if atr is not None and price is not None and price > 0:
        atr_pct = (atr / price * Decimal("100")).quantize(Decimal("0.01"))
        reasons.append(f"ATR%={atr_pct}")
        if atr_pct >= config.high_vol_atr_pct:
            score -= Decimal("10")
            reasons.append("High volatility penalty")
        elif atr_pct <= config.low_vol_atr_pct:
            score += Decimal("5")
            reasons.append("Low volatility")
    if news is True:
        score -= Decimal("15")
        reasons.append("News-driven session — quality reduced")
    elif news is False:
        score += Decimal("5")
        reasons.append("Not news-driven")
    return scored(
        "market_regime", title, score,
        threshold=config.min_regime_score,
        reasons=reasons or ["Regime scored from supplied facts"],
        factors={"trend": trend or None, "atr_pct": str(atr_pct) if atr_pct else None},
    )


def score_liquidity(
    config: AlphaEngineConfig, facts: dict[str, Any] | None
) -> EngineScore:
    title = "Liquidity Mapping"
    if facts is None:
        return unavailable(
            "liquidity", title, "Liquidity/spread facts not supplied",
            threshold=config.min_liquidity_score,
        )
    spread = _dec(facts.get("spread"))
    pools = facts.get("liquidity_pools")
    sweeps = facts.get("sweep_count")
    if spread is None and pools is None and sweeps is None:
        return empty(
            "liquidity", title, "No liquidity fields — never invents pools",
            threshold=config.min_liquidity_score,
        )
    reasons: list[str] = []
    score = Decimal("50")
    if spread is not None:
        reasons.append(f"Spread={spread}")
        if spread <= config.max_spread_for_high_liquidity:
            score += Decimal("25")
            reasons.append("Tight spread band")
        elif spread <= config.max_spread_acceptable:
            score += Decimal("10")
            reasons.append("Acceptable spread band")
        else:
            score -= Decimal("20")
            reasons.append("Spread above acceptable threshold")
    if isinstance(pools, list):
        score += min(Decimal("15"), Decimal(str(len(pools))) * Decimal("3"))
        reasons.append(f"Supplied pool count={len(pools)}")
    if sweeps is not None:
        try:
            n = int(sweeps)
            score += min(Decimal("10"), Decimal(str(max(0, n))) * Decimal("2"))
            reasons.append(f"Sweep count={n}")
        except (TypeError, ValueError):
            reasons.append("sweep_count unreadable")
    return scored(
        "liquidity", title, score,
        threshold=config.min_liquidity_score,
        reasons=reasons,
        factors={"spread": str(spread) if spread is not None else None},
    )


def score_structure(
    config: AlphaEngineConfig, facts: dict[str, Any] | None
) -> EngineScore:
    title = "Market Structure Engine"
    if facts is None:
        return unavailable(
            "market_structure", title, "Structure facts not supplied",
            threshold=config.min_structure_score,
        )
    bias = str(facts.get("bias") or facts.get("structure_bias") or "").lower()
    bos = facts.get("bos")
    choch = facts.get("choch")
    swings = facts.get("swing_count")
    if not bias and bos is None and choch is None and swings is None:
        return empty(
            "market_structure", title, "No structure fields — never invents BOS/CHoCH",
            threshold=config.min_structure_score,
        )
    reasons: list[str] = []
    score = Decimal("45")
    if bias in {"bullish", "up", "long"} or bias in {"bearish", "down", "short"}:
        score += Decimal("20")
        reasons.append(f"Bias={bias}")
    elif bias in {"neutral", "ranging"}:
        score += Decimal("5")
        reasons.append(f"Bias={bias}")
    if bos is True:
        score += Decimal("15")
        reasons.append("BOS present (supplied)")
    elif bos is False:
        reasons.append("BOS absent (supplied)")
    if choch is True:
        score += Decimal("10")
        reasons.append("CHoCH present (supplied)")
    elif choch is False:
        reasons.append("CHoCH absent (supplied)")
    if swings is not None:
        try:
            n = int(swings)
            score += min(Decimal("10"), Decimal(str(max(0, n))))
            reasons.append(f"Swing count={n}")
        except (TypeError, ValueError):
            reasons.append("swing_count unreadable")
    return scored(
        "market_structure", title, score,
        threshold=config.min_structure_score,
        reasons=reasons or ["Structure scored from supplied facts"],
        factors={"bias": bias or None, "bos": bos, "choch": choch},
    )


def score_order_flow(
    config: AlphaEngineConfig, facts: dict[str, Any] | None
) -> EngineScore:
    title = "Order Flow Analysis"
    if facts is None:
        return unavailable(
            "order_flow", title, "Order-flow / tick facts not supplied",
            threshold=config.min_order_flow_score,
        )
    imbalance = _dec(facts.get("imbalance") or facts.get("bid_ask_imbalance"))
    delta = _dec(facts.get("delta") or facts.get("tick_delta"))
    volume_burst = facts.get("volume_burst")
    if imbalance is None and delta is None and volume_burst is None:
        return empty(
            "order_flow", title, "No tick imbalance/delta — never invents flow",
            threshold=config.min_order_flow_score,
        )
    reasons: list[str] = []
    score = Decimal("50")
    if imbalance is not None:
        abs_imb = abs(imbalance)
        score += min(Decimal("25"), abs_imb * Decimal("25"))
        reasons.append(f"Imbalance={imbalance}")
    if delta is not None:
        score += min(Decimal("15"), abs(delta) * Decimal("5"))
        reasons.append(f"Delta={delta}")
    if volume_burst is True:
        score += Decimal("10")
        reasons.append("Volume burst flagged")
    elif volume_burst is False:
        reasons.append("No volume burst")
    return scored(
        "order_flow", title, score,
        threshold=config.min_order_flow_score,
        reasons=reasons,
        factors={
            "imbalance": str(imbalance) if imbalance is not None else None,
            "delta": str(delta) if delta is not None else None,
        },
    )


def score_confluence(
    config: AlphaEngineConfig, engines: dict[str, EngineScore]
) -> EngineScore:
    title = "Confluence Engine"
    usable = [
        e for e in engines.values()
        if e.status == "available" and e.score is not None
    ]
    if not usable:
        return unavailable(
            "confluence", title, "No available engine scores to confluence",
            threshold=config.min_confluence_score,
        )
    total = sum((e.score for e in usable), Decimal("0"))
    avg = (total / Decimal(str(len(usable)))).quantize(Decimal("0.01"))
    reasons = [
        f"{e.engine_id}={e.score} (pass={e.passed})" for e in usable
    ]
    reasons.append(f"Average of {len(usable)} available engines")
    return scored(
        "confluence", title, avg,
        threshold=config.min_confluence_score,
        reasons=reasons,
        factors={"engine_count": len(usable)},
    )


def score_opportunity(
    config: AlphaEngineConfig, candidates: list[dict[str, Any]] | None
) -> EngineScore:
    title = "Opportunity Ranking"
    if candidates is None:
        return unavailable(
            "opportunity", title, "Opportunity candidates not supplied",
            threshold=config.min_opportunity_score,
        )
    if not candidates:
        return empty(
            "opportunity", title, "Empty candidate list",
            threshold=config.min_opportunity_score,
        )
    ranked: list[dict[str, Any]] = []
    for row in candidates[: config.max_ranked_opportunities]:
        if not isinstance(row, dict):
            continue
        s = _dec(row.get("score") or row.get("opportunity_score"))
        if s is None:
            continue
        ranked.append(
            {
                "id": str(row.get("id") or row.get("setup_id") or ""),
                "score": str(s),
                "eligible": s >= config.min_opportunity_score,
                "label": str(row.get("label") or row.get("name") or ""),
            }
        )
    if not ranked:
        return empty(
            "opportunity",
            title,
            "Candidates missing score fields — never invents scores",
            threshold=config.min_opportunity_score,
        )
    ranked.sort(key=lambda r: Decimal(r["score"]), reverse=True)
    top = Decimal(ranked[0]["score"])
    eligible = sum(1 for r in ranked if r["eligible"])
    return scored(
        "opportunity", title, top,
        threshold=config.min_opportunity_score,
        reasons=[
            f"Ranked {len(ranked)} candidates with supplied scores",
            f"Eligible vs threshold: {eligible}",
            f"Top score={top}",
        ],
        factors={"ranked": ranked, "eligible_count": eligible},
    )


def score_execution_optimizer(
    config: AlphaEngineConfig, facts: dict[str, Any] | None
) -> EngineScore:
    title = "Execution Optimizer"
    if facts is None:
        return unavailable(
            "execution_optimizer", title, "Execution timing/spread facts not supplied",
            threshold=config.min_execution_score,
        )
    spread = _dec(facts.get("spread"))
    session = str(facts.get("session") or "").lower()
    timing = _dec(facts.get("timing_score"))
    slippage = _dec(facts.get("expected_slippage") or facts.get("slippage"))
    if spread is None and not session and timing is None and slippage is None:
        return empty(
            "execution_optimizer", title, "No execution fields — advisory only",
            threshold=config.min_execution_score,
        )
    reasons: list[str] = ["Advisory only — never places orders"]
    score = Decimal("50")
    if spread is not None:
        if spread <= config.max_spread_for_high_liquidity:
            score += Decimal("20")
            reasons.append(f"Spread favorable ({spread})")
        elif spread <= config.max_spread_acceptable:
            score += Decimal("5")
            reasons.append(f"Spread acceptable ({spread})")
        else:
            score -= Decimal("25")
            reasons.append(f"Spread unfavorable ({spread})")
    if session in {"london", "new_york", "ny", "london_ny_overlap"}:
        score += Decimal("10")
        reasons.append(f"Session={session}")
    elif session in {"asia", "off"}:
        score -= Decimal("5")
        reasons.append(f"Session={session}")
    if timing is not None:
        score = (score + timing) / Decimal("2")
        reasons.append(f"Timing score supplied={timing}")
    if slippage is not None:
        if slippage > Decimal("1"):
            score -= Decimal("15")
        reasons.append(f"Expected slippage={slippage}")
    return scored(
        "execution_optimizer", title, score,
        threshold=config.min_execution_score,
        reasons=reasons,
        factors={"session": session or None, "spread": str(spread) if spread else None},
    )


def score_exit(
    config: AlphaEngineConfig, facts: dict[str, Any] | None
) -> EngineScore:
    title = "Exit Intelligence"
    if facts is None:
        return unavailable(
            "exit_intelligence", title, "Open-trade exit facts not supplied",
            threshold=config.min_exit_score,
        )
    mfe = _dec(facts.get("mfe"))
    mae = _dec(facts.get("mae"))
    invalidation = facts.get("structure_invalidated")
    time_in_trade = facts.get("time_in_trade_minutes")
    if mfe is None and mae is None and invalidation is None and time_in_trade is None:
        return empty(
            "exit_intelligence", title, "No exit metrics — never invents MFE/MAE",
            threshold=config.min_exit_score,
        )
    reasons: list[str] = ["Advisory hold/exit quality — not a profit promise"]
    score = Decimal("50")
    if mfe is not None:
        score += min(Decimal("20"), max(Decimal("0"), mfe) * Decimal("2"))
        reasons.append(f"MFE={mfe}")
    if mae is not None:
        score -= min(Decimal("20"), max(Decimal("0"), mae) * Decimal("2"))
        reasons.append(f"MAE={mae}")
    if invalidation is True:
        score -= Decimal("30")
        reasons.append("Structure invalidated — exit pressure")
    elif invalidation is False:
        score += Decimal("10")
        reasons.append("Structure intact")
    if time_in_trade is not None:
        try:
            mins = int(time_in_trade)
            reasons.append(f"Time in trade={mins}m")
            if mins > 240:
                score -= Decimal("5")
        except (TypeError, ValueError):
            reasons.append("time_in_trade unreadable")
    return scored(
        "exit_intelligence", title, score,
        threshold=config.min_exit_score,
        reasons=reasons,
        factors={"mfe": str(mfe) if mfe is not None else None},
    )


def score_trade(
    config: AlphaEngineConfig, facts: dict[str, Any] | None
) -> EngineScore:
    title = "Institutional Trade Scoring"
    if facts is None:
        return unavailable(
            "trade_scoring", title, "Trade scoring factors not supplied",
            threshold=config.min_trade_score,
        )
    keys = (
        "setup_quality",
        "risk_reward",
        "location_quality",
        "timing_quality",
        "management_quality",
    )
    present = {k: _dec(facts.get(k)) for k in keys}
    available = {k: v for k, v in present.items() if v is not None}
    if not available:
        return empty(
            "trade_scoring", title, "No factor scores — never invents trade quality",
            threshold=config.min_trade_score,
        )
    avg = (
        sum(available.values(), Decimal("0")) / Decimal(str(len(available)))
    ).quantize(Decimal("0.01"))
    reasons = [f"{k}={v}" for k, v in available.items()]
    reasons.append("Weighted equal average of supplied factors only")
    return scored(
        "trade_scoring", title, avg,
        threshold=config.min_trade_score,
        reasons=reasons,
        factors={k: str(v) for k, v in available.items()},
    )


def score_continuous(
    config: AlphaEngineConfig, trades: list[dict[str, Any]] | None
) -> EngineScore:
    title = "Continuous Trade Evaluation"
    if trades is None:
        return unavailable(
            "continuous_evaluation", title, "Closed-trade rows not supplied",
            threshold=config.min_continuous_score,
        )
    if not trades:
        return empty(
            "continuous_evaluation", title, "No recorded trades to evaluate",
            threshold=config.min_continuous_score,
        )
    qualities: list[Decimal] = []
    reasons: list[str] = []
    for row in trades[:50]:
        if not isinstance(row, dict):
            continue
        q = _dec(row.get("execution_quality") or row.get("quality") or row.get("score"))
        slip = _dec(row.get("slippage"))
        if q is not None:
            # Accept 0-1 or 0-100
            qualities.append(q * Decimal("100") if q <= 1 else q)
        elif slip is not None:
            qualities.append(
                max(Decimal("0"), Decimal("100") - abs(slip) * Decimal("50"))
            )
    if not qualities:
        return empty(
            "continuous_evaluation",
            title,
            "Trades missing quality/slippage fields — never invents metrics",
            threshold=config.min_continuous_score,
        )
    avg = (
        sum(qualities, Decimal("0")) / Decimal(str(len(qualities)))
    ).quantize(Decimal("0.01"))
    reasons.append(f"Evaluated {len(qualities)} recorded trades")
    reasons.append(f"Average observed quality={avg}")
    reasons.append("No profitability promise")
    return scored(
        "continuous_evaluation", title, avg,
        threshold=config.min_continuous_score,
        reasons=reasons,
        factors={"sample_size": len(qualities)},
    )
