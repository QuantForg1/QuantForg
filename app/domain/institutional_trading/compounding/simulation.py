"""Deterministic shadow policy comparison. Not a live promotion gate.

All modes keep live volume <= Risk-approved volume. Hypothetical utilization
only changes how much of that already-approved budget is used.
"""

from __future__ import annotations

import random
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.compounding.engine import (
    evaluate_compounding_shadow,
)
from app.domain.institutional_trading.compounding.models import CompoundingInputs


def _score_row(*, quality: int, confidence: int, rr: float) -> dict[str, Any]:
    return {
        "trade_quality": quality,
        "quality": quality,
        "ai_confidence": confidence,
        "confidence": confidence,
        "expected_rr": rr,
        "mtf_alignment": quality,
        "factors": {
            "bos": quality,
            "choch": quality,
            "fvg": quality,
            "order_block": quality,
            "momentum": quality,
            "liquidity_sweep": quality,
            "session": 80,
            "spread": 80,
            "volatility": 70,
        },
        "reject": False,
    }


def simulate_mode_comparison(
    *,
    n: int = 400,
    seed: int = 42,
    risk_approved: Decimal = Decimal("0.01"),
) -> dict[str, Any]:
    """Monte Carlo of *shadow utilization* inside a fixed Risk budget.

    Live execution is identical across modes in this layer (no OMS). Reported
    expectancy is hypothetical R * suggested_volume / min_lot, not live PnL.
    """
    rng = random.Random(seed)
    modes_seen: dict[str, list[float]] = {}
    live_r: list[float] = []
    for _ in range(max(1, int(n))):
        quality = rng.randint(55, 99)
        confidence = rng.randint(55, 99)
        rr = round(rng.uniform(0.8, 3.0), 2)
        won = rng.random() < (0.35 + (quality / 400.0))
        realized = rr if won else -1.0
        daily = Decimal(str(round(rng.uniform(-4.0, 2.0), 2)))
        equity = Decimal("208.86")
        daily_loss = Decimal("0") if daily >= 0 else (abs(daily) / equity * Decimal("100"))
        obs = evaluate_compounding_shadow(
            CompoundingInputs(
                symbol="XAUUSD_i",
                direction="BUY",
                trade_class="SCALP",
                score=_score_row(quality=quality, confidence=confidence, rr=rr),
                confidence=confidence,
                quality=quality,
                expected_rr=Decimal(str(rr)),
                equity=equity,
                daily_pnl=daily,
                daily_loss_pct=daily_loss.quantize(Decimal("0.01")),
                open_positions=0,
                remaining_capacity=10,
                configured_max_open=10,
                risk_approved_volume=risk_approved,
                candidate_allowed=True,
            )
        )
        live_r.append(realized)
        util = float(obs.sizing.suggested_volume / risk_approved) if risk_approved else 0.0
        modes_seen.setdefault(obs.mode, []).append(realized * util)

    def _pack(xs: list[float]) -> dict[str, float | int | None]:
        if not xs:
            return {"n": 0, "mean": None, "win_rate": None}
        wins = [x for x in xs if x > 0]
        return {
            "n": len(xs),
            "mean": round(sum(xs) / len(xs), 4),
            "win_rate": round(len(wins) / len(xs), 4),
        }

    return {
        "advisory_only": True,
        "live_activation": "SHADOW_ONLY",
        "promoted_to_live": False,
        "note": (
            "Hypothetical utilization of an already-approved Risk budget. "
            "Not a walk-forward on market bars. Do not promote on this alone."
        ),
        "samples": n,
        "seed": seed,
        "live_identical_r": _pack(live_r),
        "by_mode_hypothetical": {k: _pack(v) for k, v in sorted(modes_seen.items())},
        "historical_backtest": "NOT_RUN",
        "walk_forward": "NOT_RUN",
        "reason_not_promoted": (
            "No market-bar backtest/walk-forward. Shadow layer cannot change live Risk/OMS."
        ),
    }
