"""Pure technical indicators over OHLC closes — no market invention."""

from __future__ import annotations

from collections.abc import Sequence


def closes(values: Sequence[float]) -> list[float]:
    return [float(v) for v in values]


def sma(series: Sequence[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(series)
    if period <= 0:
        return out
    for i in range(period - 1, len(series)):
        window = series[i - period + 1 : i + 1]
        out[i] = sum(window) / period
    return out


def ema(series: Sequence[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(series)
    if period <= 0 or not series:
        return out
    k = 2 / (period + 1)
    # Seed with SMA
    if len(series) < period:
        return out
    seed = sum(series[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(series)):
        prev = series[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(series: Sequence[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(series)
    if period <= 0 or len(series) <= period:
        return out
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(series)):
        delta = series[i] - series[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def _rsi(g: float, loss: float) -> float:
        if loss == 0:
            return 100.0
        rs = g / loss
        return 100.0 - (100.0 / (1.0 + rs))

    out[period] = _rsi(avg_gain, avg_loss)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i + 1] = _rsi(avg_gain, avg_loss)
    return out


def macd(
    series: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    fast_line = ema(series, fast)
    slow_line = ema(series, slow)
    macd_line: list[float | None] = [None] * len(series)
    for i in range(len(series)):
        f = fast_line[i]
        s = slow_line[i]
        if f is not None and s is not None:
            macd_line[i] = float(f) - float(s)
    # Signal EMA over macd values (skip Nones)
    compact = [v for v in macd_line if v is not None]
    signal_compact = ema(compact, signal)
    signal_line: list[float | None] = [None] * len(series)
    hist: list[float | None] = [None] * len(series)
    j = 0
    for i, v in enumerate(macd_line):
        if v is None:
            continue
        sig = signal_compact[j] if j < len(signal_compact) else None
        signal_line[i] = sig
        if sig is not None:
            hist[i] = v - sig
        j += 1
    return macd_line, signal_line, hist


def bollinger(
    series: Sequence[float],
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    mid = sma(series, period)
    upper: list[float | None] = [None] * len(series)
    lower: list[float | None] = [None] * len(series)
    for i in range(period - 1, len(series)):
        window = series[i - period + 1 : i + 1]
        mean = mid[i]
        if mean is None:
            continue
        var = sum((x - mean) ** 2 for x in window) / period
        std = var**0.5
        upper[i] = mean + num_std * std
        lower[i] = mean - num_std * std
    return upper, mid, lower


def momentum(series: Sequence[float], lookback: int = 10) -> list[float | None]:
    out: list[float | None] = [None] * len(series)
    for i in range(lookback, len(series)):
        prev = series[i - lookback]
        if prev == 0:
            out[i] = 0.0
        else:
            out[i] = (series[i] / prev - 1.0) * 100.0
    return out


def highest(series: Sequence[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(series)
    for i in range(period - 1, len(series)):
        out[i] = max(series[i - period + 1 : i + 1])
    return out


def lowest(series: Sequence[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(series)
    for i in range(period - 1, len(series)):
        out[i] = min(series[i - period + 1 : i + 1])
    return out
