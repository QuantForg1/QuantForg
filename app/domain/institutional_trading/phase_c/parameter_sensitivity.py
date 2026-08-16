"""Parameter sensitivity — detect fragile optima. Research only."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence


def evaluate_parameter_sensitivity(
    baseline_params: Mapping[str, float],
    evaluate_fn: Callable[[dict[str, float]], float],
    *,
    small: float = 0.05,
    medium: float = 0.15,
    min_evals: int = 3,
) -> dict[str, Any]:
    """Perturb each numeric param ±small/±medium; classify stability."""
    base = {str(k): float(v) for k, v in baseline_params.items()}
    if not base:
        return {"state": "INSUFFICIENT_DATA", "detail": "no parameters"}

    try:
        baseline_score = float(evaluate_fn(dict(base)))
    except Exception as exc:
        return {
            "state": "INSUFFICIENT_DATA",
            "detail": f"baseline_eval_failed:{exc}",
        }

    scores: list[float] = [baseline_score]
    for key, val in base.items():
        if val == 0:
            continue
        for scale in (small, -small, medium, -medium):
            trial = dict(base)
            trial[key] = val * (1.0 + scale)
            try:
                scores.append(float(evaluate_fn(trial)))
            except Exception:
                continue

    if len(scores) < min_evals:
        return {"state": "INSUFFICIENT_DATA", "scores_n": len(scores)}

    # Relative drop from baseline
    worst = min(scores)
    best = max(scores)
    drop = (baseline_score - worst) / abs(baseline_score) if baseline_score else 0.0
    spread = (best - worst) / (abs(baseline_score) + 1e-9)

    if drop >= 0.5 or spread >= 1.0:
        state = "FRAGILE"
    elif drop >= 0.25 or spread >= 0.5:
        state = "SENSITIVE"
    else:
        state = "ROBUST"

    return {
        "state": state,
        "baseline_score": round(baseline_score, 6),
        "worst_neighbor_score": round(worst, 6),
        "best_neighbor_score": round(best, 6),
        "relative_drop": round(drop, 6),
        "neighbor_spread": round(spread, 6),
        "perturbations": {"small": small, "medium": medium},
        "auto_select_peak": False,
    }


def classify_from_scores(
    baseline: float, neighbor_scores: Sequence[float]
) -> dict[str, Any]:
    """Convenience when scores are precomputed."""
    scores = [float(baseline), *[float(x) for x in neighbor_scores]]
    if len(scores) < 3:
        return {"state": "INSUFFICIENT_DATA"}
    worst = min(scores)
    best = max(scores)
    drop = (baseline - worst) / abs(baseline) if baseline else 0.0
    spread = (best - worst) / (abs(baseline) + 1e-9)
    if drop >= 0.5 or spread >= 1.0:
        state = "FRAGILE"
    elif drop >= 0.25 or spread >= 0.5:
        state = "SENSITIVE"
    else:
        state = "ROBUST"
    return {
        "state": state,
        "baseline_score": baseline,
        "worst_neighbor_score": worst,
        "relative_drop": round(drop, 6),
        "neighbor_spread": round(spread, 6),
    }
