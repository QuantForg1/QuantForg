"""IRL significance & stability — research sample diagnostics only."""

from __future__ import annotations

import math
import statistics
from typing import Any


def compute_significance(trades: list[dict[str, Any]], stats: dict[str, Any]) -> dict[str, Any]:
    n = len(trades)
    pnls = [float(t.get("pnl") or 0.0) for t in trades]
    variance = statistics.pvariance(pnls) if n >= 2 else 0.0
    # Rough Wilson-ish confidence proxy from sample size + win rate
    wr = (stats.get("win_rate") or 0.0) / 100.0
    se = math.sqrt(wr * (1.0 - wr) / n) if n > 0 else 1.0
    confidence = max(0.0, min(99.0, (1.0 - 1.96 * se) * 100.0)) if n >= 5 else max(0.0, n * 8.0)

    # Stability: inverse of return volatility scaled
    rets = []
    eq = 10_000.0
    for p in pnls:
        if eq > 0:
            rets.append(p / eq)
        eq += p
    stab = 50.0
    if len(rets) >= 3:
        vol = statistics.pstdev(rets)
        stab = max(0.0, min(100.0, 100.0 - vol * 2000.0))

    # Consistency: rolling win-rate variance
    consistency = 50.0
    if n >= 10:
        window = max(5, n // 5)
        rates: list[float] = []
        for i in range(window, n + 1):
            chunk = pnls[i - window : i]
            rates.append(sum(1 for x in chunk if x > 0) / window)
        if len(rates) >= 2:
            consistency = max(0.0, min(100.0, 100.0 - statistics.pstdev(rates) * 200.0))

    # Outliers: |pnl| > mean + 3*std
    outliers: list[int] = []
    if n >= 5:
        mu = statistics.mean(pnls)
        sd = statistics.pstdev(pnls) or 1.0
        for i, p in enumerate(pnls):
            if abs(p - mu) > 3.0 * sd:
                outliers.append(i)

    # Walk-forward score: split halves expectancy agreement
    walk_forward = 50.0
    if n >= 12:
        mid = n // 2
        a = pnls[:mid]
        b = pnls[mid:]
        ea = sum(a) / len(a)
        eb = sum(b) / len(b)
        if abs(ea) + abs(eb) > 1e-9:
            walk_forward = max(
                0.0,
                min(100.0, 100.0 - abs(ea - eb) / (abs(ea) + abs(eb)) * 100.0),
            )
        else:
            walk_forward = 70.0

    return {
        "sample_size": n,
        "confidence": round(confidence, 2),
        "variance": round(variance, 6),
        "stability_score": round(stab, 2),
        "consistency_score": round(consistency, 2),
        "outlier_indices": outliers[:20],
        "outlier_count": len(outliers),
        "walk_forward_score": round(walk_forward, 2),
    }
