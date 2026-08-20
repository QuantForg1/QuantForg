"""AI Scalping score v6.3 — adaptive regime, multi-setup, quality-first."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace as dc_replace
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.adaptive_cooldown import (
    resolve_adaptive_cooldown_seconds,
)
from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
    ResolvedThresholds,
    resolve_adaptive_thresholds,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.ai_scalping.direction import (
    decide_scalping_direction,
)
from app.domain.institutional_trading.ai_scalping.pa_confluence import (
    evaluate_pa_confluence,
)
from app.domain.institutional_trading.ai_scalping.quality_gates import (
    evaluate_quality_gates,
)
from app.domain.institutional_trading.ai_scalping.regime import (
    classify_scalping_regime,
)
from app.domain.institutional_trading.ai_scalping.regime_execution import (
    build_regime_execution_profile,
)
from app.domain.institutional_trading.ai_scalping.session_intelligence import (
    assess_session,
)
from app.domain.institutional_trading.ai_scalping.setup_scanner import (
    scan_setup_families,
)
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    assess_spread,
)
from app.domain.institutional_trading.ai_scalping.structure_targets import (
    compute_structure_targets,
)
from app.domain.institutional_trading.ai_scalping.symbol_state import (
    get_symbol_state_book,
)
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.models import MarketAnalysisSnapshot


@dataclass(frozen=True, slots=True)
class AiScalpingScore:
    confidence: int
    trade_quality: int
    confluence: int
    expected_rr: Decimal | None
    expected_hold_time: str
    market_regime: str
    momentum: int
    liquidity: int
    spread_score: int
    atr_pct: Decimal | None
    direction: str
    factors: dict[str, int]
    thresholds: dict[str, object]
    reasons: tuple[str, ...]
    reject: bool
    reject_reason: str | None = None
    buy_score: int = 0
    sell_score: int = 0
    structure_score: int = 0
    entry: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    quality_checks: dict[str, bool] | None = None
    reject_reasons: tuple[str, ...] = ()
    indicators: dict[str, object] | None = None
    entry_reason: str | None = None
    regime_execution: dict[str, object] | None = None
    setup_family: str | None = None
    setup_scan: dict[str, object] | None = None
    adaptive_cooldown: dict[str, object] | None = None
    volatility_decision: dict[str, object] | None = None
    opportunity_score: int = 0
    opportunity_threshold: int = 70
    score_band: str = "SETUP_NOT_READY"
    score_breakdown: dict[str, int] | None = None
    opportunity_eligible: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ai_confidence": self.confidence,
            "trade_quality": self.trade_quality,
            "confluence": self.confluence,
            "expected_rr": (
                str(self.expected_rr) if self.expected_rr is not None else None
            ),
            "expected_hold_time": self.expected_hold_time,
            "market_regime": self.market_regime,
            "momentum": self.momentum,
            "liquidity": self.liquidity,
            "spread_score": self.spread_score,
            "atr_pct": str(self.atr_pct) if self.atr_pct is not None else None,
            "direction": self.direction,
            "buy_score": self.buy_score,
            "sell_score": self.sell_score,
            "structure_score": self.structure_score,
            "entry": self.entry,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "factors": dict(self.factors),
            "thresholds": dict(self.thresholds),
            "reasons": list(self.reasons),
            "reject": self.reject,
            "reject_reason": self.reject_reason,
            "reject_reasons": list(self.reject_reasons),
            "quality_checks": dict(self.quality_checks or {}),
            "indicators": dict(self.indicators or {}),
            "entry_reason": self.entry_reason,
            "regime_execution": dict(self.regime_execution or {}),
            "setup_family": self.setup_family,
            "setup_scan": dict(self.setup_scan or {}),
            "adaptive_cooldown": dict(self.adaptive_cooldown or {}),
            "volatility_decision": dict(self.volatility_decision or {}),
            "opportunity_score": self.opportunity_score,
            "opportunity_threshold": self.opportunity_threshold,
            "score_band": self.score_band,
            "score_breakdown": dict(self.score_breakdown or {}),
            "opportunity_eligible": self.opportunity_eligible,
            "never_prefer_buy_only": True,
        }


def _hold_time(
    cfg: AiScalpingConfig,
    confidence: int,
    regime: str,
    *,
    hold_lo: int | None = None,
    hold_hi: int | None = None,
) -> str:
    lo = hold_lo if hold_lo is not None else cfg.typical_hold_min_minutes
    hi = hold_hi if hold_hi is not None else cfg.typical_hold_max_minutes
    if confidence >= cfg.high_confidence_for_extend and regime in {
        "strong_trend",
        "breakout",
    }:
        hi = min(cfg.max_hold_minutes_if_confident, cfg.typical_hold_max_minutes)
    lo = max(cfg.typical_hold_min_minutes, lo)
    hi = min(hi, cfg.typical_hold_max_minutes, cfg.absolute_max_hold_minutes)
    if hi < lo:
        hi = lo
    return f"{lo}-{hi}m"


def score_scalping_setup(
    snapshot: MarketAnalysisSnapshot,
    *,
    atr: Decimal | None,
    mid: Decimal | None,
    historical_similarity: int | None = None,
    config: AiScalpingConfig | None = None,
    closes: Sequence[float] | None = None,
    opens: Sequence[float] | None = None,
    highs: Sequence[float] | None = None,
    lows: Sequence[float] | None = None,
    recent_rejects: int = 0,
    execution_quality_ok: bool = True,
    enforce_adaptive_cooldown: bool = False,
    symbol: str | None = None,
) -> AiScalpingScore:
    """Compute AI Confidence / Quality for institutional adaptive scalping."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    reasons: list[str] = []
    factors: dict[str, int] = {}

    trend = snapshot.trend
    quality = snapshot.trade_quality
    structure = snapshot.primary_structure

    direction_dec = decide_scalping_direction(snapshot, config=cfg)
    reasons.extend(direction_dec.reasons)
    factors.update(direction_dec.factors)
    direction = direction_dec.direction

    bos = len(structure.breaks_of_structure) if structure else 0
    choch = len(structure.changes_of_character) if structure else 0
    if bos or choch:
        reasons.append(f"Structure bos={bos} choch={choch}")

    from app.domain.institutional_trading.quality_components import (
        quality_components,
    )

    liq = snapshot.liquidity
    sweeps = len(liq.sweeps) if liq else 0
    q_components = quality_components(quality)
    liquidity_score = (
        88 if sweeps else max(20, int(q_components.get("liquidity", 40) or 40))
    )
    factors["liquidity_sweep"] = liquidity_score
    if sweeps:
        reasons.append(f"Liquidity sweeps={sweeps}")

    ob = snapshot.order_blocks
    active_ob = 0
    if ob:
        active_ob = sum(
            1
            for b in ob.order_blocks
            if str(getattr(getattr(b, "state", None), "value", b.state)).lower()
            in {"active", "validated"}
        )
    factors["order_block"] = 85 if active_ob else 20

    fvg = snapshot.fair_value_gaps
    open_fvg = len(getattr(fvg, "active_gaps", ()) or ()) if fvg else 0
    factors["fvg"] = 80 if open_fvg else 25

    resolved: ResolvedThresholds = resolve_adaptive_thresholds(
        atr, mid, config=cfg, symbol=str(symbol or getattr(snapshot, "symbol", "") or "")
    )
    factors["atr_expansion"] = (
        85 if resolved.band == "high" else (70 if resolved.band == "normal" else 50)
    )

    # Momentum tracks real trend alignment — never a silent 55 default that
    # fails min_momentum_score=65 even when trend is strong.
    mom_score = int(
        q_components.get("momentum")
        or q_components.get("trend_strength")
        or trend.alignment_score
        or 0
    )
    vol_score = int(
        q_components.get("volume")
        or q_components.get("vol")
        or q_components.get("liquidity")
        or 40
    )
    factors["volume"] = max(0, min(100, vol_score))
    factors["momentum"] = max(0, min(100, mom_score))
    factors["trend_strength"] = int(trend.alignment_score)
    factors["volatility"] = factors["atr_expansion"]
    factors["mtf"] = factors.get("h1_bias", 0) + factors.get("m15_structure", 0)
    factors["bos"] = 85 if bos else 20
    factors["choch"] = 80 if choch else 20

    session = assess_session(
        str(getattr(snapshot.session.session, "value", snapshot.session.session)),
        config=cfg,
    )
    factors["session"] = session.quality_score
    reasons.append(session.reason)

    spread_a = assess_spread(
        snapshot.spread,
        atr=atr,
        config=cfg,
        symbol=str(symbol or getattr(snapshot, "symbol", "") or ""),
    )
    factors["spread"] = spread_a.score
    reasons.append(spread_a.reason)
    if spread_a.reject and getattr(spread_a, "abnormal_vs_history", False):
        try:
            from app.domain.institutional_trading.ai_scalping.live_health import (
                get_live_health_monitor,
            )

            get_live_health_monitor().record_abnormal_spread(spread_a.reason)
        except Exception:
            pass

    hist = int(historical_similarity) if historical_similarity is not None else 50
    factors["historical_similar"] = max(0, min(100, hist))

    pa = evaluate_pa_confluence(
        snapshot,
        direction=direction,
        closes=closes,
        opens=opens,
        highs=highs,
        lows=lows,
        config=cfg,
    )
    factors["ema"] = pa.ema_score
    factors["rsi"] = pa.rsi_score
    factors["candle_pa"] = pa.candle_score
    factors["pa_confluence"] = pa.score
    reasons.extend(pa.reasons)

    setup_scan = None
    setup_family: str | None = None
    if cfg.multi_setup_scan_enabled:
        setup_scan = scan_setup_families(
            alignment=int(trend.alignment_score),
            bos=bos,
            choch=choch,
            sweeps=sweeps,
            open_fvg=open_fvg,
            momentum=factors["momentum"],
            volume=factors["volume"],
            liquidity=liquidity_score,
            ema=pa.ema_score,
            buy_score=direction_dec.buy_score,
            sell_score=direction_dec.sell_score,
            atr_band=resolved.band,
            config=cfg,
        )
        reasons.extend(setup_scan.reasons)
        if setup_scan.best is not None:
            setup_family = setup_scan.best.family
            factors["setup_family_score"] = setup_scan.best.score
            best_dir = setup_scan.best.direction
            if best_dir in {TradeDirection.BUY.value, TradeDirection.SELL.value}:
                if direction_dec.direction is TradeDirection.NONE:
                    reasons.append(
                        f"Setup {setup_family} suggests {best_dir} "
                        "but AI direction NONE"
                    )
                elif best_dir != direction_dec.direction.value:
                    reasons.append(
                        f"Setup {setup_family}={best_dir} vs AI="
                        f"{direction_dec.direction.value} — keep AI direction; "
                        "global gates decide"
                    )
                else:
                    reasons.append(f"Setup {setup_family} agrees with AI {best_dir}")

    weights = {
        "mtf": 14,
        "bos": 7,
        "choch": 7,
        "liquidity_sweep": 10,
        "order_block": 8,
        "fvg": 7,
        "atr_expansion": 5,
        "volume": 4,
        "momentum": 8,
        "trend_strength": 4,
        "volatility": 3,
        "session": 5,
        "spread": 4,
        "historical_similar": 2,
        "ema": 5,
        "rsi": 4,
        "candle_pa": 3,
    }
    weighted = sum(factors.get(k, 0) * w for k, w in weights.items())
    total_w = sum(weights.values())
    confidence = round(weighted / total_w) if total_w else 0
    # Session / spread already enter the weighted composite via factors.
    # Subtracting confidence_penalty again double-counts soft weights and
    # permanently suppressed LIVE adaptive confidence floors (verified:
    # quality≈84–89 with confidence stuck ≈54 after -10 session penalty).
    if (
        setup_scan
        and setup_scan.best
        and setup_scan.best.passed
        and setup_scan.best.direction == direction_dec.direction.value
    ):
        confidence = min(100, confidence + min(4, setup_scan.best.score // 30))
    confidence = max(0, min(100, confidence))

    trade_quality = int(quality.total)
    confluence = confidence

    regime = classify_scalping_regime(
        alignment_score=int(trend.alignment_score),
        atr_pct=resolved.atr_pct,
        bos=bos,
        choch=choch,
        sweep_count=sweeps,
        range_like=trend.alignment_score < 55,
        volume_expanding=factors["volume"] >= 70,
    )
    reasons.extend(regime.reasons)
    exec_profile = build_regime_execution_profile(
        regime, atr_pct=resolved.atr_pct, config=cfg
    )
    reasons.extend(exec_profile.reasons)

    cd_decision = resolve_adaptive_cooldown_seconds(
        atr_pct=resolved.atr_pct,
        spread_score=spread_a.score,
        liquidity_score=liquidity_score,
        execution_quality_ok=execution_quality_ok,
        recent_rejects=recent_rejects,
        regime=regime.regime,
        config=cfg,
    )
    scaled_seconds = int(Decimal(cd_decision.seconds) * exec_profile.cooldown_scale)
    scaled_seconds = max(
        cfg.cooldown_min_seconds,
        min(cfg.cooldown_max_seconds, scaled_seconds),
    )
    cd_decision = dc_replace(cd_decision, seconds=scaled_seconds)
    # Per-symbol cooldown only — never share a global gate across the universe.
    sym_key = (symbol or str(getattr(snapshot, "symbol", "") or "")).upper()
    if cfg.adaptive_cooldown_enabled and sym_key:
        cooldown_eval = get_symbol_state_book().evaluate_cooldown(sym_key, cd_decision)
    else:
        cooldown_eval = dc_replace(
            cd_decision, allow_new_entry=True, remaining_seconds=0.0
        )
    reasons.extend(cd_decision.reasons)
    if not cooldown_eval.allow_new_entry:
        reasons.append(
            f"Adaptive cooldown active "
            f"({cooldown_eval.remaining_seconds:.0f}s remaining)"
            + (f" symbol={sym_key}" if sym_key else "")
        )

    targets = compute_structure_targets(
        snapshot,
        direction=direction,
        entry=mid,
        atr=atr,
        config=cfg,
    )
    # Profile-aware RR fallback — never hardcode institutional 1.4.
    _rr_fallback = cfg.fixed_tp_r if cfg.fixed_tp_r is not None else cfg.min_expected_rr
    expected_rr = targets.expected_rr if targets.expected_rr is not None else _rr_fallback
    if targets.reason:
        reasons.append(targets.reason)

    effective_min_rr = max(cfg.min_expected_rr, exec_profile.min_expected_rr)
    # Consistency: regime bumps must not exceed fixed TP target.
    if cfg.fixed_tp_r is not None and cfg.fixed_tp_r > 0:
        effective_min_rr = min(effective_min_rr, cfg.fixed_tp_r)

    gates = evaluate_quality_gates(
        direction=direction_dec,
        momentum=factors["momentum"],
        liquidity=liquidity_score,
        structure_score=direction_dec.structure_score,
        session=session,
        spread=spread_a,
        thresholds=resolved,
        confidence=confidence,
        trade_quality=trade_quality,
        expected_rr=expected_rr,
        atr_pct=resolved.atr_pct,
        config=cfg,
        pa_confluence=pa,
        min_expected_rr_override=effective_min_rr,
        mtf_alignment=int(trend.alignment_score),
        market_regime=regime.regime,
        symbol=sym_key or None,
    )
    if gates.volatility_decision:
        vol_reason = str(gates.volatility_decision.get("reason") or "").strip()
        if vol_reason:
            reasons.append(vol_reason)

    from app.domain.institutional_trading.operations.probability_selector import (
        evaluate_from_score_dict,
    )

    reject_list: list[str] = list(gates.rejects)
    for soft in gates.soft_rejects:
        reasons.append(f"EVIDENCE: {soft}")
    # Setup scan ranks opportunities — absence does not poison global quality gates.
    if cfg.multi_setup_scan_enabled and (setup_scan is None or setup_scan.best is None):
        reasons.append(
            "No setup family cleared local evidence — Probability Center is selector"
        )

    # Live cooldown gate blocks NEW entries only (quality floors unchanged).
    if (
        cfg.adaptive_cooldown_enabled
        and enforce_adaptive_cooldown
        and not cooldown_eval.allow_new_entry
    ):
        reject_list.append(
            f"Adaptive cooldown active "
            f"({cooldown_eval.remaining_seconds:.0f}s remaining)"
        )

    verdict = evaluate_from_score_dict(
        {
            "direction": direction_dec.direction.value,
            "trade_quality": trade_quality,
            "ai_confidence": confidence,
            "structure_score": direction_dec.structure_score,
            "momentum": factors["momentum"],
            "liquidity": liquidity_score,
            "spread_score": spread_a.score,
            "expected_rr": expected_rr,
            "market_regime": regime.regime,
            "mtf_alignment": int(trend.alignment_score),
            "pa_confluence": pa.score,
            "factors": factors,
            "volatility_decision": gates.volatility_decision,
        }
    )
    reasons.append(
        f"opportunity_score={verdict.opportunity_score} "
        f"threshold={verdict.threshold} band={verdict.score_band}"
    )

    reject_list = list(dict.fromkeys(reject_list))
    reject = bool(reject_list)
    reject_reason = "; ".join(reject_list) if reject_list else None
    # Keep BUY/SELL for observability. Probability wait is not a direction wipe.
    if not reject and not verdict.eligible:
        reject = True
        reject_reason = verdict.fault_reason or "SETUP_NOT_READY"
        reject_list.append(reject_reason)
        reasons.append(f"WAIT: {reject_reason}")
        fam = f" setup={setup_family}" if setup_family else ""
        entry_reason = (
            f"WAIT {direction_dec.direction.value}: "
            f"opportunity_score={verdict.opportunity_score}{fam}"
        )
    elif reject:
        for r in reject_list:
            reasons.append(f"REJECT: {r}")
        entry_reason = reject_reason
    else:
        fam = f" setup={setup_family}" if setup_family else ""
        entry_reason = (
            f"TAKE {direction_dec.direction.value}: "
            f"opportunity_score={verdict.opportunity_score} "
            f"PA={pa.score} conf={confidence} regime={regime.regime}{fam}"
        )
        reasons.append(
            f"TAKE {direction_dec.direction.value}: Probability Center candidate "
            f"(score={verdict.opportunity_score} >= {verdict.threshold})"
        )

    hold = _hold_time(
        cfg,
        confidence,
        regime.regime,
        hold_lo=exec_profile.target_hold_min_minutes,
        hold_hi=exec_profile.target_hold_max_minutes,
    )

    return AiScalpingScore(
        confidence=confidence,
        trade_quality=trade_quality,
        confluence=confluence,
        expected_rr=expected_rr,
        expected_hold_time=hold,
        market_regime=regime.regime,
        momentum=factors["momentum"],
        liquidity=liquidity_score,
        spread_score=spread_a.score,
        atr_pct=resolved.atr_pct,
        direction=direction_dec.direction.value,
        factors=factors,
        thresholds=resolved.to_dict(),
        reasons=tuple(reasons),
        reject=reject,
        reject_reason=reject_reason,
        buy_score=direction_dec.buy_score,
        sell_score=direction_dec.sell_score,
        structure_score=direction_dec.structure_score,
        entry=str(targets.entry) if targets.entry is not None else None,
        stop_loss=str(targets.stop_loss) if targets.stop_loss is not None else None,
        take_profit=(
            str(targets.take_profit) if targets.take_profit is not None else None
        ),
        quality_checks=gates.checks,
        reject_reasons=tuple(reject_list),
        indicators=pa.indicators,
        entry_reason=entry_reason,
        regime_execution=exec_profile.to_dict(),
        setup_family=setup_family,
        setup_scan=setup_scan.to_dict() if setup_scan else None,
        adaptive_cooldown=cooldown_eval.to_dict(),
        volatility_decision=gates.volatility_decision,
        opportunity_score=verdict.opportunity_score,
        opportunity_threshold=verdict.threshold,
        score_band=verdict.score_band,
        score_breakdown=dict(verdict.score_breakdown),
        opportunity_eligible=verdict.eligible,
    )
