"""Quant AI — pairwise correlation from real close series (no invented quotes)."""

from __future__ import annotations

from typing import Any


def _returns(closes: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(closes)):
        if closes[i - 1] == 0:
            continue
        out.append((closes[i] - closes[i - 1]) / closes[i - 1])
    return out


def _pearson(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 5:
        return None
    x = a[-n:]
    y = b[-n:]
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y, strict=True))
    den_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
    den_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5
    if den_x == 0 or den_y == 0:
        return None
    return float(num / (den_x * den_y))


def correlation_from_closes(
    series: dict[str, list[float]],
) -> dict[str, Any]:
    """Build labels + matrix from real close prices per symbol."""
    labels = sorted(k for k, v in series.items() if len(v) >= 10)
    if len(labels) < 2:
        return {
            "status": "unavailable",
            "reason": "Need at least two symbols with sufficient real OHLC",
            "labels": labels,
            "matrix": [],
            "data_source": "mt5_candles",
        }
    rets = {lab: _returns(series[lab]) for lab in labels}
    matrix: list[list[float | None]] = []
    for a in labels:
        row: list[float | None] = []
        for b in labels:
            if a == b:
                row.append(1.0)
            else:
                c = _pearson(rets[a], rets[b])
                row.append(round(c, 4) if c is not None else None)
        matrix.append(row)
    return {
        "status": "available",
        "labels": labels,
        "matrix": matrix,
        "data_source": "mt5_candles",
        "why": {
            "summary": f"Pearson correlation on returns across {len(labels)} symbols",
            "supporting_factors": [
                "Computed from observed closes only",
                "Pairs with insufficient bars show null cells",
            ],
        },
    }
