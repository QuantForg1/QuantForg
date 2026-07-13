"""Pure portfolio risk statistics — operate only on caller-supplied series."""

from __future__ import annotations

import math
from collections.abc import Sequence


def _finite(values: Sequence[float]) -> list[float]:
    return [float(v) for v in values if math.isfinite(float(v))]


def historical_var(pnls: Sequence[float], confidence: float = 0.95) -> float | None:
    """Historical VaR as positive loss amount at confidence (e.g. 0.95)."""
    series = sorted(_finite(pnls))
    if len(series) < 5:
        return None
    if not (0.5 < confidence < 1.0):
        return None
    idx = math.floor((1.0 - confidence) * len(series))
    idx = max(0, min(idx, len(series) - 1))
    # VaR is the loss magnitude of the lower-tail outcome
    return abs(min(series[idx], 0.0))


def expected_shortfall(pnls: Sequence[float], confidence: float = 0.95) -> float | None:
    """CVaR / Expected Shortfall: mean loss beyond VaR threshold."""
    series = sorted(_finite(pnls))
    if len(series) < 5:
        return None
    if not (0.5 < confidence < 1.0):
        return None
    cut = math.floor((1.0 - confidence) * len(series))
    cut = max(1, min(cut + 1, len(series)))
    tail = series[:cut]
    losses = [abs(min(x, 0.0)) for x in tail]
    if not losses:
        return 0.0
    return sum(losses) / len(losses)


def herfindahl(weights: Sequence[float]) -> float:
    total = sum(abs(w) for w in weights)
    if total <= 0:
        return 0.0
    return sum((abs(w) / total) ** 2 for w in weights)


def diversification_score(
    corr_matrix: Sequence[Sequence[float | None]],
) -> float | None:
    """1 - average |corr| off-diagonal; None if matrix incomplete."""
    n = len(corr_matrix)
    if n < 2:
        return None
    vals: list[float] = []
    for i in range(n):
        row = corr_matrix[i]
        if len(row) != n:
            return None
        for j in range(i + 1, n):
            v = row[j]
            if v is None or not math.isfinite(v):
                return None
            vals.append(abs(v))
    if not vals:
        return None
    avg = sum(vals) / len(vals)
    return round(max(0.0, min(1.0, 1.0 - avg)), 4)


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 5:
        return None
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return max(-1.0, min(1.0, num / (dx * dy)))


def correlation_matrix(
    series_by_key: dict[str, list[float]],
) -> tuple[list[str], list[list[float | None]], list[list[str]]]:
    """Pairwise Pearson on aligned equal-length tails (last N overlapping points).

    Returns labels, matrix, and per-cell status notes.
    """
    keys = sorted(series_by_key.keys())
    n = len(keys)
    matrix: list[list[float | None]] = [[None] * n for _ in range(n)]
    notes: list[list[str]] = [[""] * n for _ in range(n)]
    for i, a in enumerate(keys):
        for j, b in enumerate(keys):
            if i == j:
                matrix[i][j] = 1.0
                notes[i][j] = "identity"
                continue
            sa = series_by_key[a]
            sb = series_by_key[b]
            m = min(len(sa), len(sb))
            if m < 5:
                notes[i][j] = f"insufficient_overlap ({m}<5)"
                continue
            corr = pearson(sa[-m:], sb[-m:])
            matrix[i][j] = corr
            notes[i][j] = "computed" if corr is not None else "undefined_zero_variance"
    return keys, matrix, notes


def cluster_labels(
    keys: Sequence[str],
    matrix: Sequence[Sequence[float | None]],
    threshold: float = 0.7,
) -> list[dict[str, object]]:
    """Greedy clusters where |corr| >= threshold (deterministic, sorted keys)."""
    assigned: dict[str, int] = {}
    clusters: list[list[str]] = []
    for i, key in enumerate(keys):
        if key in assigned:
            continue
        cluster = [key]
        assigned[key] = len(clusters)
        for j, other in enumerate(keys):
            if other in assigned or i == j:
                continue
            v = matrix[i][j]
            if v is not None and abs(v) >= threshold:
                cluster.append(other)
                assigned[other] = len(clusters)
        clusters.append(sorted(cluster))
    return [
        {"id": idx, "members": members, "size": len(members)}
        for idx, members in enumerate(clusters)
    ]
