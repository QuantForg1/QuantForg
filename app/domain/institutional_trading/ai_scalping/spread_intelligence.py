"""Spread intelligence — soft confidence penalty; hard reject at ceiling / abnormal.

Historical ring buffer rejects only when current spread is abnormal vs recent
distribution AND still respects absolute / ATR caps. Never forces trades.
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)

_HISTORY: dict[str, deque[Decimal]] = defaultdict(lambda: deque(maxlen=64))
_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class SpreadAssessment:
    score: int  # 0-100
    confidence_penalty: int
    reject: bool
    reason: str
    historical_median: str | None = None
    abnormal_vs_history: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "confidence_penalty": self.confidence_penalty,
            "reject": self.reject,
            "reason": self.reason,
            "historical_median": self.historical_median,
            "abnormal_vs_history": self.abnormal_vs_history,
        }


def _record_spread(symbol: str | None, spread: Decimal) -> deque[Decimal]:
    key = (symbol or "GLOBAL").strip().upper() or "GLOBAL"
    with _LOCK:
        hist = _HISTORY[key]
        hist.append(spread)
        return deque(hist)


def _median(values: deque[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal("2")


def assess_spread(
    spread: Decimal | None,
    *,
    atr: Decimal | None = None,
    config: AiScalpingConfig | None = None,
    symbol: str | None = None,
) -> SpreadAssessment:
    """Reject when spread exceeds absolute max, ATR%, or abnormal vs history."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    if spread is None:
        return SpreadAssessment(
            score=50,
            confidence_penalty=0,
            reject=False,
            reason="Spread unavailable - neutral",
        )
    hist = _record_spread(symbol, spread)
    med = _median(hist)
    med_s = str(med) if med is not None else None
    abnormal = False
    if med is not None and len(hist) >= 8 and med > 0:
        # Abnormal: > 2.5× recent median (flash / liquidity vacuum)
        if spread > med * Decimal("2.5"):
            abnormal = True

    if spread > cfg.max_spread_reject:
        return SpreadAssessment(
            score=0,
            confidence_penalty=cfg.spread_soft_penalty_max,
            reject=True,
            reason=(
                f"Spread {spread} exceeds configured reject {cfg.max_spread_reject}"
            ),
            historical_median=med_s,
            abnormal_vs_history=abnormal,
        )
    if atr is not None and atr > 0 and cfg.max_spread_atr_pct > 0:
        atr_cap = (atr * cfg.max_spread_atr_pct / Decimal("100")).quantize(
            Decimal("0.0001")
        )
        if spread > atr_cap:
            return SpreadAssessment(
                score=0,
                confidence_penalty=cfg.spread_soft_penalty_max,
                reject=True,
                reason=(
                    f"Spread {spread} exceeds {cfg.max_spread_atr_pct}% of ATR "
                    f"({atr_cap})"
                ),
                historical_median=med_s,
                abnormal_vs_history=abnormal,
            )
    if abnormal:
        return SpreadAssessment(
            score=0,
            confidence_penalty=cfg.spread_soft_penalty_max,
            reject=True,
            reason=(
                f"Abnormal spread {spread} vs historical median {med} "
                f"(>{Decimal('2.5')}×)"
            ),
            historical_median=med_s,
            abnormal_vs_history=True,
        )
    if spread <= cfg.max_spread_for_full_score:
        return SpreadAssessment(
            score=100,
            confidence_penalty=0,
            reject=False,
            reason=f"Spread {spread} tight",
            historical_median=med_s,
            abnormal_vs_history=False,
        )
    span = cfg.max_spread_reject - cfg.max_spread_for_full_score
    if span <= 0:
        ratio = Decimal("1")
    else:
        ratio = (spread - cfg.max_spread_for_full_score) / span
    ratio = max(Decimal("0"), min(Decimal("1"), ratio))
    score = int(max(0, float(100 * (1 - ratio))))
    penalty = round(float(ratio) * cfg.spread_soft_penalty_max)
    return SpreadAssessment(
        score=score,
        confidence_penalty=penalty,
        reject=False,
        reason=f"Spread {spread} elevated - soft penalty {penalty}",
        historical_median=med_s,
        abnormal_vs_history=False,
    )


def spread_history_values(symbol: str | None) -> list[Decimal]:
    """Observe-only copy of recent spreads for a symbol (never fabricates)."""
    key = (symbol or "GLOBAL").strip().upper() or "GLOBAL"
    with _LOCK:
        return list(_HISTORY.get(key, ()))
