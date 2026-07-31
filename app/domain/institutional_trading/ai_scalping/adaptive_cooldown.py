"""Adaptive entry cooldown — shorter in good tape, longer in poor tape.

Never forces trades. Never zeros cooldown after rejects. Does not lower
quality thresholds — only spaces NEW entries after a fill / abort burst.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
    MarketRegimeLabel,
)


@dataclass(frozen=True, slots=True)
class AdaptiveCooldownDecision:
    seconds: int
    allow_new_entry: bool
    remaining_seconds: float
    reasons: tuple[str, ...]
    conditions: dict[str, object]

    def to_dict(self) -> dict[str, Any]:
        return {
            "seconds": self.seconds,
            "allow_new_entry": self.allow_new_entry,
            "remaining_seconds": round(self.remaining_seconds, 2),
            "reasons": list(self.reasons),
            "conditions": dict(self.conditions),
        }


def resolve_adaptive_cooldown_seconds(
    *,
    atr_pct: Decimal | None = None,
    spread_score: int = 70,
    liquidity_score: int = 70,
    execution_quality_ok: bool = True,
    recent_rejects: int = 0,
    regime: MarketRegimeLabel | str | None = None,
    config: AiScalpingConfig | None = None,
) -> AdaptiveCooldownDecision:
    """Compute cooldown length from live conditions (no quality floor change)."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    lo = int(cfg.cooldown_min_seconds)
    hi = int(cfg.cooldown_max_seconds)
    base = int(cfg.cooldown_base_seconds)
    reasons: list[str] = [f"Base cooldown={base}s"]
    seconds = base
    good = 0
    poor = 0

    # Volatility
    if atr_pct is not None:
        if atr_pct >= cfg.atr_high_pct:
            seconds = int(seconds * 1.25)
            poor += 1
            reasons.append("High ATR% → longer cooldown")
        elif atr_pct <= cfg.atr_low_pct:
            seconds = int(seconds * 1.35)
            poor += 1
            reasons.append("Compressed ATR% → longer cooldown")
        else:
            good += 1
            reasons.append("Normal ATR% → supportive")

    # Spread / liquidity
    if spread_score >= 80:
        good += 1
        seconds = int(seconds * 0.85)
        reasons.append("Tight spread → shorter cooldown")
    elif spread_score < 55:
        poor += 1
        seconds = int(seconds * 1.4)
        reasons.append("Weak spread → longer cooldown")

    if liquidity_score >= 75:
        good += 1
        seconds = int(seconds * 0.9)
        reasons.append("Strong liquidity → shorter cooldown")
    elif liquidity_score < 55:
        poor += 1
        seconds = int(seconds * 1.3)
        reasons.append("Thin liquidity → longer cooldown")

    # Execution health
    if not execution_quality_ok:
        poor += 2
        seconds = int(seconds * 1.5)
        reasons.append("Execution quality degraded → longer cooldown")
    else:
        good += 1

    if recent_rejects >= 3:
        poor += 2
        seconds = max(seconds, int(base * 1.8))
        reasons.append(f"Recent rejects={recent_rejects} → extended cooldown")
    elif recent_rejects >= 1:
        poor += 1
        seconds = int(seconds * 1.2)
        reasons.append(f"Recent rejects={recent_rejects} → modest extension")

    regime_s = str(regime or "")
    if regime_s in {"strong_trend", "breakout", "expansion"}:
        if poor == 0:
            seconds = int(seconds * 0.8)
            good += 1
            reasons.append(f"Regime {regime_s} + clean tape → shorter cooldown")
    elif regime_s in {"range", "compression"}:
        seconds = int(seconds * 1.25)
        poor += 1
        reasons.append(f"Regime {regime_s} → longer cooldown")
    elif regime_s == "weak_trend":
        seconds = int(seconds * 1.05)
        reasons.append("Weak trend → slightly longer cooldown")

    # Good-conditions floor: never below configured min
    if good >= 3 and poor == 0:
        seconds = min(seconds, max(lo, int(base * 0.7)))
        reasons.append("All conditions supportive → near-min cooldown")

    seconds = max(lo, min(hi, seconds))
    reasons.append(f"Resolved cooldown={seconds}s (clamp {lo}-{hi})")

    return AdaptiveCooldownDecision(
        seconds=seconds,
        allow_new_entry=True,  # computed against gate state separately
        remaining_seconds=0.0,
        reasons=tuple(reasons),
        conditions={
            "atr_pct": str(atr_pct) if atr_pct is not None else None,
            "spread_score": spread_score,
            "liquidity_score": liquidity_score,
            "execution_quality_ok": execution_quality_ok,
            "recent_rejects": recent_rejects,
            "regime": regime_s or None,
            "good_signals": good,
            "poor_signals": poor,
        },
    )


@dataclass
class AdaptiveCooldownGate:
    """Process-local gate: last entry / reject timestamps + resolved seconds."""

    _last_entry_mono: float | None = field(default=None, repr=False)
    _last_seconds: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def note_entry(self, *, seconds: int) -> None:
        with self._lock:
            self._last_entry_mono = time.monotonic()
            self._last_seconds = max(0, int(seconds))

    def note_reject_burst(self, *, seconds: int) -> None:
        """Extend spacing after reject bursts without forcing trades."""
        with self._lock:
            self._last_entry_mono = time.monotonic()
            self._last_seconds = max(self._last_seconds, int(seconds))

    def clear_for_post_close_rescan(self) -> None:
        """After a close — allow immediate scan for a NEW valid setup only."""
        with self._lock:
            self._last_entry_mono = None
            self._last_seconds = 0

    def evaluate(self, decision: AdaptiveCooldownDecision) -> AdaptiveCooldownDecision:
        with self._lock:
            if self._last_entry_mono is None:
                return AdaptiveCooldownDecision(
                    seconds=decision.seconds,
                    allow_new_entry=True,
                    remaining_seconds=0.0,
                    reasons=(*decision.reasons, "No prior entry — cooldown clear"),
                    conditions=decision.conditions,
                )
            elapsed = time.monotonic() - self._last_entry_mono
            need = float(self._last_seconds or decision.seconds)
            remaining = max(0.0, need - elapsed)
            allow = remaining <= 0.0
            extra = (
                "Cooldown clear — new entry permitted"
                if allow
                else f"Cooldown active — {remaining:.1f}s remaining"
            )
            return AdaptiveCooldownDecision(
                seconds=decision.seconds,
                allow_new_entry=allow,
                remaining_seconds=remaining,
                reasons=(*decision.reasons, extra),
                conditions={
                    **decision.conditions,
                    "evaluated_at": datetime.now(UTC).isoformat(),
                },
            )

    def reset(self) -> None:
        with self._lock:
            self._last_entry_mono = None
            self._last_seconds = 0


_GATE: AdaptiveCooldownGate | None = None
_GATE_LOCK = threading.Lock()


def get_adaptive_cooldown_gate() -> AdaptiveCooldownGate:
    global _GATE
    with _GATE_LOCK:
        if _GATE is None:
            _GATE = AdaptiveCooldownGate()
        return _GATE
