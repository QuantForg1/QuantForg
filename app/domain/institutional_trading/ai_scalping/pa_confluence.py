"""Price-action + EMA/RSI confluence helpers for scalping execution quality.

Additive to the existing AI strategy — never replaces decide_scalping_direction /
score_scalping_setup core logic. Does not lower institutional safety floors.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.domain.indicators import ema, rsi
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.models import MarketAnalysisSnapshot


@dataclass(frozen=True, slots=True)
class PaConfluenceResult:
    """Composite EMA / RSI / candle PA confluence for one setup."""

    score: int
    ema_score: int
    rsi_score: int
    candle_score: int
    smc_score: int
    passed: bool
    reasons: tuple[str, ...]
    indicators: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "ema_score": self.ema_score,
            "rsi_score": self.rsi_score,
            "candle_score": self.candle_score,
            "smc_score": self.smc_score,
            "passed": self.passed,
            "reasons": list(self.reasons),
            "indicators": dict(self.indicators),
        }


def _last(series: Sequence[float | None]) -> float | None:
    for v in reversed(series):
        if v is not None:
            return float(v)
    return None


def assess_ema_stack(
    closes: Sequence[float],
    *,
    direction: TradeDirection,
) -> tuple[int, dict[str, Any], str]:
    """EMA 20 / 50 / 200 stack alignment vs intended direction."""
    if len(closes) < 200:
        return 50, {"ema_ready": False}, "EMA stack insufficient history"
    e20 = _last(ema(list(closes), 20))
    e50 = _last(ema(list(closes), 50))
    e200 = _last(ema(list(closes), 200))
    px = float(closes[-1])
    indicators = {
        "ema_ready": True,
        "ema20": e20,
        "ema50": e50,
        "ema200": e200,
        "close": px,
    }
    if e20 is None or e50 is None or e200 is None:
        return 50, indicators, "EMA values unavailable"
    bullish = e20 > e50 > e200 and px >= e20
    bearish = e20 < e50 < e200 and px <= e20
    soft_bull = e20 > e50 and px > e50
    soft_bear = e20 < e50 and px < e50
    if direction is TradeDirection.BUY:
        if bullish:
            return 95, indicators, "EMA 20>50>200 bullish stack"
        if soft_bull:
            return 72, indicators, "EMA soft bullish (20>50)"
        if bearish:
            return 15, indicators, "EMA stack opposing BUY"
        return 40, indicators, "EMA neutral for BUY"
    if direction is TradeDirection.SELL:
        if bearish:
            return 95, indicators, "EMA 20<50<200 bearish stack"
        if soft_bear:
            return 72, indicators, "EMA soft bearish (20<50)"
        if bullish:
            return 15, indicators, "EMA stack opposing SELL"
        return 40, indicators, "EMA neutral for SELL"
    return 35, indicators, "EMA no clear direction"


def assess_rsi_confirm(
    closes: Sequence[float],
    *,
    direction: TradeDirection,
    period: int = 14,
) -> tuple[int, dict[str, Any], str]:
    """RSI trend + momentum confirmation (not oversold/overbought fade alone)."""
    if len(closes) < period + 5:
        return 50, {"rsi_ready": False}, "RSI insufficient history"
    series = rsi(list(closes), period)
    cur = _last(series)
    prev = None
    vals = [v for v in series if v is not None]
    if len(vals) >= 2:
        prev = vals[-2]
    indicators: dict[str, Any] = {"rsi_ready": True, "rsi": cur, "rsi_prev": prev}
    if cur is None:
        return 50, indicators, "RSI unavailable"
    rising = prev is not None and cur > prev
    falling = prev is not None and cur < prev
    if direction is TradeDirection.BUY:
        if 45 <= cur <= 70 and rising:
            return 90, indicators, f"RSI momentum bullish ({cur:.1f})"
        if 50 <= cur <= 65:
            return 75, indicators, f"RSI trend support ({cur:.1f})"
        if cur > 78:
            return 25, indicators, f"RSI overbought fade risk ({cur:.1f})"
        if cur < 40:
            return 30, indicators, f"RSI weak for BUY ({cur:.1f})"
        return 55, indicators, f"RSI neutral BUY ({cur:.1f})"
    if direction is TradeDirection.SELL:
        if 30 <= cur <= 55 and falling:
            return 90, indicators, f"RSI momentum bearish ({cur:.1f})"
        if 35 <= cur <= 50:
            return 75, indicators, f"RSI trend support ({cur:.1f})"
        if cur < 22:
            return 25, indicators, f"RSI oversold fade risk ({cur:.1f})"
        if cur > 60:
            return 30, indicators, f"RSI weak for SELL ({cur:.1f})"
        return 55, indicators, f"RSI neutral SELL ({cur:.1f})"
    return 40, indicators, "RSI no direction"


def assess_candle_pa(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    direction: TradeDirection,
) -> tuple[int, dict[str, Any], str]:
    """Rejection candle + strong engulfing confirmation on the latest bars."""
    n = min(len(opens), len(highs), len(lows), len(closes))
    if n < 3:
        return 50, {"candle_ready": False}, "Candle PA insufficient history"
    o1, h1, l1, c1 = opens[-1], highs[-1], lows[-1], closes[-1]
    o0, _h0, _l0, c0 = opens[-2], highs[-2], lows[-2], closes[-2]
    body1 = abs(c1 - o1)
    range1 = max(h1 - l1, 1e-12)
    upper_wick = h1 - max(o1, c1)
    lower_wick = min(o1, c1) - l1
    bullish_engulf = (
        c1 > o1 and c0 < o0 and c1 >= o0 and o1 <= c0 and body1 > abs(c0 - o0)
    )
    bearish_engulf = (
        c1 < o1 and c0 > o0 and c1 <= o0 and o1 >= c0 and body1 > abs(c0 - o0)
    )
    bull_reject = lower_wick >= body1 * 1.5 and lower_wick >= upper_wick and c1 >= o1
    bear_reject = upper_wick >= body1 * 1.5 and upper_wick >= lower_wick and c1 <= o1
    strong_body = body1 / range1 >= 0.55
    indicators = {
        "candle_ready": True,
        "bullish_engulf": bullish_engulf,
        "bearish_engulf": bearish_engulf,
        "bull_reject": bull_reject,
        "bear_reject": bear_reject,
        "strong_body": strong_body,
    }
    if direction is TradeDirection.BUY:
        if bullish_engulf and strong_body:
            return 95, indicators, "Strong bullish engulfing"
        if bull_reject:
            return 85, indicators, "Bullish rejection candle"
        if c1 > o1 and strong_body:
            return 70, indicators, "Bullish impulse candle"
        if bearish_engulf or bear_reject:
            return 20, indicators, "Bearish PA opposing BUY"
        return 45, indicators, "No strong bullish candle PA"
    if direction is TradeDirection.SELL:
        if bearish_engulf and strong_body:
            return 95, indicators, "Strong bearish engulfing"
        if bear_reject:
            return 85, indicators, "Bearish rejection candle"
        if c1 < o1 and strong_body:
            return 70, indicators, "Bearish impulse candle"
        if bullish_engulf or bull_reject:
            return 20, indicators, "Bullish PA opposing SELL"
        return 45, indicators, "No strong bearish candle PA"
    return 40, indicators, "Candle PA no direction"


def assess_smc_pa(snapshot: MarketAnalysisSnapshot) -> tuple[int, dict[str, Any], str]:
    """BOS / CHoCH / liquidity sweep / FVG already present on the snapshot."""
    structure = snapshot.primary_structure
    bos = len(structure.breaks_of_structure) if structure else 0
    choch = len(structure.changes_of_character) if structure else 0
    liq = snapshot.liquidity
    sweeps = len(liq.sweeps) if liq else 0
    fvg = snapshot.fair_value_gaps
    gaps = len(getattr(fvg, "active_gaps", ()) or ()) if fvg else 0
    score = 20
    parts: list[str] = []
    if bos:
        score += 20
        parts.append(f"BOS={bos}")
    if choch:
        score += 20
        parts.append(f"CHoCH={choch}")
    if sweeps:
        score += 20
        parts.append(f"sweep={sweeps}")
    if gaps:
        score += 15
        parts.append(f"FVG={gaps}")
    score = min(100, score)
    indicators = {"bos": bos, "choch": choch, "sweeps": sweeps, "fvg": gaps}
    reason = "SMC PA: " + (", ".join(parts) if parts else "thin structure context")
    return score, indicators, reason


def evaluate_pa_confluence(
    snapshot: MarketAnalysisSnapshot,
    *,
    direction: TradeDirection,
    closes: Sequence[float] | None = None,
    opens: Sequence[float] | None = None,
    highs: Sequence[float] | None = None,
    lows: Sequence[float] | None = None,
    config: AiScalpingConfig | None = None,
) -> PaConfluenceResult:
    """Combine EMA + RSI + candle + SMC into a minimum-confluence gate score."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    reasons: list[str] = []
    indicators: dict[str, Any] = {}

    smc_score, smc_ind, smc_reason = assess_smc_pa(snapshot)
    reasons.append(smc_reason)
    indicators.update(smc_ind)

    close_list = list(closes) if closes is not None else []
    if close_list:
        ema_score, ema_ind, ema_reason = assess_ema_stack(
            close_list, direction=direction
        )
        rsi_score, rsi_ind, rsi_reason = assess_rsi_confirm(
            close_list, direction=direction
        )
        reasons.extend([ema_reason, rsi_reason])
        indicators.update(ema_ind)
        indicators.update(rsi_ind)
    else:
        # Soft proxies when OHLC not wired — never invent bars
        ema_score = max(40, min(85, int(snapshot.trend.alignment_score)))
        rsi_score = int(
            (getattr(snapshot.trade_quality, "components", {}) or {}).get(
                "momentum", 55
            )
            or 55
        )
        reasons.append("EMA/RSI soft proxy (no entry OHLC series)")
        indicators["ema_ready"] = False
        indicators["rsi_ready"] = False

    if (
        opens is not None
        and highs is not None
        and lows is not None
        and closes is not None
        and len(closes) >= 3
    ):
        candle_score, candle_ind, candle_reason = assess_candle_pa(
            list(opens),
            list(highs),
            list(lows),
            list(closes),
            direction=direction,
        )
        reasons.append(candle_reason)
        indicators.update(candle_ind)
    else:
        candle_score = smc_score
        reasons.append("Candle PA deferred to SMC events (no OHLC)")
        indicators["candle_ready"] = False

    # Weighted composite — SMC + EMA + RSI + candle
    score = round(
        smc_score * 0.35 + ema_score * 0.25 + rsi_score * 0.20 + candle_score * 0.20
    )
    score = max(0, min(100, score))
    data_ready = bool(indicators.get("ema_ready") or indicators.get("candle_ready"))
    has_smc = bool(
        indicators.get("bos")
        or indicators.get("choch")
        or indicators.get("sweeps")
        or indicators.get("fvg")
    )
    if data_ready:
        passed = score >= cfg.min_pa_confluence_score
    else:
        # Soft path without OHLC — never invent bars; require SMC evidence
        soft_floor = max(40, cfg.min_pa_confluence_score - 15)
        passed = has_smc and score >= soft_floor
    if not passed:
        reasons.append(
            f"PA confluence {score} < minimum {cfg.min_pa_confluence_score}"
            + (
                ""
                if data_ready
                else f" (soft floor {max(40, cfg.min_pa_confluence_score - 15)})"
            )
        )
    else:
        reasons.append(f"PA confluence {score} ≥ gate (ready={data_ready})")

    return PaConfluenceResult(
        score=score,
        ema_score=ema_score,
        rsi_score=rsi_score,
        candle_score=candle_score,
        smc_score=smc_score,
        passed=passed,
        reasons=tuple(reasons),
        indicators=indicators,
    )
