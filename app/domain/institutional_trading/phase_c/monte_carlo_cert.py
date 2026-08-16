"""Monte Carlo certification wrapper — records assumptions; reuses research MC."""

from __future__ import annotations

import random
from typing import Any, Sequence


def run_monte_carlo_certification(
    trade_returns: Sequence[float],
    *,
    iterations: int = 500,
    seed: int = 42,
    slippage_noise: float = 0.05,
    spread_noise: float = 0.02,
    miss_trade_prob: float = 0.02,
    delay_noise: float = 0.01,
) -> dict[str, Any]:
    """Controlled perturbations. Does not call OMS/Gateway/MT5."""
    base = [float(x) for x in trade_returns]
    if len(base) < 5:
        return {
            "state": "INSUFFICIENT_DATA",
            "assumptions": {
                "iterations": iterations,
                "seed": seed,
                "slippage_noise": slippage_noise,
                "spread_noise": spread_noise,
                "miss_trade_prob": miss_trade_prob,
                "delay_noise": delay_noise,
            },
            "distributions": None,
        }
    rng = random.Random(seed)  # noqa: S311
    finals: list[float] = []
    drawdowns: list[float] = []
    max_losses: list[float] = []
    expectancies: list[float] = []

    for _ in range(max(10, int(iterations))):
        order = list(base)
        rng.shuffle(order)
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        worst = 0.0
        realized: list[float] = []
        for r in order:
            if rng.random() < miss_trade_prob:
                continue
            noise = 1.0 - abs(rng.gauss(0, slippage_noise)) - abs(
                rng.gauss(0, spread_noise)
            )
            delay = 1.0 - abs(rng.gauss(0, delay_noise))
            adj = r * max(0.0, noise) * max(0.0, delay)
            realized.append(adj)
            equity += adj
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)
            worst = min(worst, adj)
        finals.append(equity)
        drawdowns.append(max_dd)
        max_losses.append(worst)
        expectancies.append(sum(realized) / len(realized) if realized else 0.0)

    def _pct(xs: list[float], p: float) -> float:
        s = sorted(xs)
        if not s:
            return 0.0
        i = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
        return s[i]

    wins = [x for x in base if x > 0]
    losses = [abs(x) for x in base if x < 0]
    pf = (sum(wins) / sum(losses)) if losses and sum(losses) > 0 else None

    return {
        "state": "COMPUTED",
        "assumptions": {
            "iterations": iterations,
            "seed": seed,
            "slippage_noise": slippage_noise,
            "spread_noise": spread_noise,
            "miss_trade_prob": miss_trade_prob,
            "delay_noise": delay_noise,
            "sequence_shuffle": True,
            "parameter_perturbation": False,
        },
        "distributions": {
            "returns_final_p05": round(_pct(finals, 5), 6),
            "returns_final_p50": round(_pct(finals, 50), 6),
            "returns_final_p95": round(_pct(finals, 95), 6),
            "drawdown_p50": round(_pct(drawdowns, 50), 6),
            "drawdown_p95": round(_pct(drawdowns, 95), 6),
            "max_loss_p05": round(_pct(max_losses, 5), 6),
            "expectancy_p50": round(_pct(expectancies, 50), 6),
            "baseline_profit_factor": None if pf is None else round(pf, 6),
            "risk_of_ruin_proxy": round(
                sum(1 for f in finals if f < 0) / len(finals), 4
            ),
        },
        "live_action": "NONE",
    }
