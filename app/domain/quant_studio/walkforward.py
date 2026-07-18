"""Quant Studio — walk-forward stability summary from fold metrics."""

from __future__ import annotations

from typing import Any


def summarize_walkforward_stability(folds: list[dict[str, Any]]) -> dict[str, Any]:
    if not folds:
        return {
            "status": "unavailable",
            "reason": "No walk-forward folds available",
            "autonomous_trading": False,
        }

    is_pfs: list[float] = []
    oos_pfs: list[float] = []
    for f in folds:
        try:
            if f.get("is_profit_factor") is not None:
                is_pfs.append(float(f["is_profit_factor"]))
            if f.get("oos_profit_factor") is not None:
                oos_pfs.append(float(f["oos_profit_factor"]))
        except (TypeError, ValueError):
            continue

    def _mean(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    def _std(xs: list[float]) -> float | None:
        if len(xs) < 2:
            return None
        m = sum(xs) / len(xs)
        return float((sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5)

    mean_is = _mean(is_pfs)
    mean_oos = _mean(oos_pfs)
    std_oos = _std(oos_pfs)

    stability = None
    if mean_is and mean_is > 0 and mean_oos is not None:
        # Closer OOS to IS and lower OOS variance → higher stability
        ratio = min(1.5, max(0.0, mean_oos / mean_is))
        var_pen = 0.0
        if std_oos is not None and mean_oos != 0:
            var_pen = min(0.5, abs(std_oos / mean_oos) * 0.5)
        stability = round(max(0.0, min(1.0, ratio * (1.0 - var_pen))), 4)

    return {
        "status": "available",
        "fold_count": len(folds),
        "mean_is_profit_factor": round(mean_is, 4) if mean_is is not None else None,
        "mean_oos_profit_factor": round(mean_oos, 4) if mean_oos is not None else None,
        "oos_profit_factor_std": round(std_oos, 4) if std_oos is not None else None,
        "stability_score": stability,
        "train_validation_oos": {
            "train": "in-sample windows",
            "validation": "parameter selection on IS",
            "out_of_sample": "held-out OOS windows",
        },
        "why": {
            "summary": (
                f"Stability {stability}"
                if stability is not None
                else "Stability not scorable"
            ),
            "supporting_factors": [
                f"Folds={len(folds)}",
                f"Mean IS PF={mean_is}",
                f"Mean OOS PF={mean_oos}",
            ],
        },
        "autonomous_trading": False,
        "advisory_only": True,
    }
