"""Probability of Backtest Overfitting (PBO) — research validation only.

CSCV-style estimate following Bailey / López de Prado motivation.
Never used as an automatic LIVE block in Phase C.
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any, Sequence


def _rank_best(rows: Sequence[Sequence[float]]) -> int:
    """Index of configuration with highest mean performance."""
    means = [sum(r) / len(r) if r else float("-inf") for r in rows]
    return max(range(len(means)), key=lambda i: means[i])


def estimate_pbo(
    performance_matrix: Sequence[Sequence[float]],
    *,
    min_trials: int = 8,
) -> dict[str, Any]:
    """Estimate PBO via Combinatorially Symmetric Cross-Validation.

    performance_matrix: shape (n_configs, n_splits) of IS-like scores per fold.
    For each partition of splits into two equal halves S*/S~, pick best config
    on S*, evaluate relative rank on S~. PBO ≈ P(rank underperform on S~).
    """
    n_cfg = len(performance_matrix)
    if n_cfg < 2:
        return {
            "state": "INSUFFICIENT_DATA",
            "PBO": None,
            "number_of_trials": n_cfg,
            "number_of_configurations": n_cfg,
            "selection_method": "CSCV",
            "detail": "need >= 2 configurations",
        }
    n_splits = min(len(row) for row in performance_matrix) if performance_matrix else 0
    if n_splits < 4 or n_splits % 2 != 0:
        return {
            "state": "INSUFFICIENT_DATA",
            "PBO": None,
            "number_of_trials": n_cfg,
            "number_of_configurations": n_cfg,
            "number_of_splits": n_splits,
            "selection_method": "CSCV",
            "detail": "need even n_splits >= 4",
        }
    if n_cfg < min_trials:
        # Still compute if possible, but mark insufficient for decisioning
        pass

    matrix = [list(row[:n_splits]) for row in performance_matrix]
    half = n_splits // 2
    idxs = list(range(n_splits))
    overfit_flags: list[int] = []
    is_scores: list[float] = []
    oos_scores: list[float] = []

    # Cap combinations for tractability
    combos = list(combinations(idxs, half))
    if len(combos) > 200:
        step = max(1, len(combos) // 200)
        combos = combos[::step][:200]

    for s_star in combos:
        s_star_set = set(s_star)
        s_tilde = [i for i in idxs if i not in s_star_set]
        is_rows = [[row[i] for i in s_star] for row in matrix]
        oos_rows = [[row[i] for i in s_tilde] for row in matrix]
        best = _rank_best(is_rows)
        is_mean = sum(is_rows[best]) / half
        oos_means = [sum(r) / half for r in oos_rows]
        # Relative rank of best-IS config among OOS means (0=worst, 1=best)
        sorted_oos = sorted(oos_means)
        # Rank fraction: how often OOS of selected is below median of peers
        selected_oos = oos_means[best]
        # Overfit if selected config's OOS is worse than median of all configs
        median_oos = sorted_oos[len(sorted_oos) // 2]
        overfit_flags.append(1 if selected_oos < median_oos else 0)
        is_scores.append(is_mean)
        oos_scores.append(selected_oos)

    if not overfit_flags:
        return {
            "state": "INSUFFICIENT_DATA",
            "PBO": None,
            "number_of_trials": n_cfg,
            "number_of_configurations": n_cfg,
            "selection_method": "CSCV",
        }

    pbo = sum(overfit_flags) / len(overfit_flags)
    if n_cfg < min_trials:
        state = "INSUFFICIENT_DATA"
    elif pbo >= 0.5:
        state = "HIGH_PBO_RISK"
    elif pbo >= 0.3:
        state = "MODERATE_PBO_RISK"
    else:
        state = "LOW_PBO_RISK"

    return {
        "state": state,
        "PBO": round(pbo, 4),
        "number_of_trials": n_cfg,
        "number_of_configurations": n_cfg,
        "number_of_splits": n_splits,
        "selection_method": "CSCV",
        "IS_performance_mean": round(sum(is_scores) / len(is_scores), 6),
        "OOS_performance_mean": round(sum(oos_scores) / len(oos_scores), 6),
        "rank_instability": round(pbo, 4),
        "live_block": False,
        "auto_action": "NONE",
    }
