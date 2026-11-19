"""Extended strategy pack (62 plugins) - intentions only, no execution.

Every rule is a well-known, documented technique implemented on the supplied
OHLC bars. Rules fire on the *event* bar (cross, flip, pattern completion),
not on every bar of a state, so they can be scored as discrete trades.
Missing data (volume, bar time) returns HOLD - never a guessed value.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, ClassVar

from app.domain.interfaces.strategy_engine import (
    EngineSignalAction,
    StrategyIntention,
    StrategySnapshot,
)
from app.strategies.library import _go, _hold

NAN = float("nan")
BUY = EngineSignalAction.BUY
SELL = EngineSignalAction.SELL
Out = tuple[EngineSignalAction, float, str, str] | None


# ----------------------------------------------------------------- indicators


def _ok(*xs: float) -> bool:
    return all(not math.isnan(x) for x in xs)


def sma(xs: list[float], n: int) -> list[float]:
    out = [NAN] * len(xs)
    acc = 0.0
    cnt = 0
    start = 0
    for i, x in enumerate(xs):
        if math.isnan(x):
            acc, cnt, start = 0.0, 0, i + 1
            continue
        acc += x
        cnt += 1
        if cnt > n:
            acc -= xs[i - n]
            cnt = n
        if cnt == n and i - start + 1 >= n:
            out[i] = acc / n
    return out


def ema(xs: list[float], n: int) -> list[float]:
    out = [NAN] * len(xs)
    k = 2.0 / (n + 1)
    prev = NAN
    for i, x in enumerate(xs):
        if math.isnan(x):
            continue
        prev = x if math.isnan(prev) else prev + k * (x - prev)
        out[i] = prev
    # discard warm-up
    first = next((i for i, x in enumerate(xs) if not math.isnan(x)), len(xs))
    for i in range(first, min(len(xs), first + n - 1)):
        out[i] = NAN
    return out


def wilder(xs: list[float], n: int) -> list[float]:
    out = [NAN] * len(xs)
    prev = NAN
    seed: list[float] = []
    for i, x in enumerate(xs):
        if math.isnan(x):
            continue
        if math.isnan(prev):
            seed.append(x)
            if len(seed) == n:
                prev = sum(seed) / n
                out[i] = prev
            continue
        prev = (prev * (n - 1) + x) / n
        out[i] = prev
    return out


def wma(xs: list[float], n: int) -> list[float]:
    out = [NAN] * len(xs)
    den = n * (n + 1) / 2
    for i in range(n - 1, len(xs)):
        win = xs[i - n + 1 : i + 1]
        if any(math.isnan(v) for v in win):
            continue
        out[i] = sum(v * (j + 1) for j, v in enumerate(win)) / den
    return out


def stdev(xs: list[float], n: int) -> list[float]:
    out = [NAN] * len(xs)
    for i in range(n - 1, len(xs)):
        win = xs[i - n + 1 : i + 1]
        m = sum(win) / n
        out[i] = math.sqrt(sum((v - m) ** 2 for v in win) / n)
    return out


def highest(xs: list[float], n: int) -> list[float]:
    return [NAN if i < n - 1 else max(xs[i - n + 1 : i + 1]) for i in range(len(xs))]


def lowest(xs: list[float], n: int) -> list[float]:
    return [NAN if i < n - 1 else min(xs[i - n + 1 : i + 1]) for i in range(len(xs))]


def rsi(xs: list[float], n: int = 14) -> list[float]:
    ups = [NAN] + [max(xs[i] - xs[i - 1], 0.0) for i in range(1, len(xs))]
    dns = [NAN] + [max(xs[i - 1] - xs[i], 0.0) for i in range(1, len(xs))]
    au, ad = wilder(ups, n), wilder(dns, n)
    out = []
    for u, d in zip(au, ad, strict=True):
        if not _ok(u, d):
            out.append(NAN)
        elif d == 0:
            out.append(100.0)
        else:
            out.append(100 - 100 / (1 + u / d))
    return out


def roc(xs: list[float], n: int) -> list[float]:
    return [
        NAN if i < n or xs[i - n] == 0 else (xs[i] / xs[i - n] - 1) * 100
        for i in range(len(xs))
    ]


def stoch(xs: list[float], n: int) -> list[float]:
    hi, lo = highest(xs, n), lowest(xs, n)
    return [
        NAN if not _ok(h, l_, x) else (50.0 if h == l_ else (x - l_) / (h - l_) * 100)
        for x, h, l_ in zip(xs, hi, lo, strict=True)
    ]


def cross_up(a: list[float], b: list[float] | float) -> bool:
    b1 = b if isinstance(b, float | int) else b[-1]
    b2 = b if isinstance(b, float | int) else b[-2]
    return _ok(a[-1], a[-2], b1, b2) and a[-2] <= b2 and a[-1] > b1


def cross_dn(a: list[float], b: list[float] | float) -> bool:
    b1 = b if isinstance(b, float | int) else b[-1]
    b2 = b if isinstance(b, float | int) else b[-2]
    return _ok(a[-1], a[-2], b1, b2) and a[-2] >= b2 and a[-1] < b1


class S:
    """Bar arrays with cached common indicators."""

    def __init__(self, snapshot: StrategySnapshot) -> None:
        b = snapshot.bars
        self.o = [x.open for x in b]
        self.h = [x.high for x in b]
        self.l = [x.low for x in b]
        self.c = [x.close for x in b]
        self.v = [x.volume for x in b]
        self.t = [x.time for x in b]
        self._cache: dict[tuple[Any, ...], list[float]] = {}

    def __len__(self) -> int:
        return len(self.c)

    def memo(self, key: tuple[Any, ...], fn: Any) -> list[float]:
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def ema(self, n: int) -> list[float]:
        return self.memo(("ema", n), lambda: ema(self.c, n))

    def sma(self, n: int) -> list[float]:
        return self.memo(("sma", n), lambda: sma(self.c, n))

    def rsi(self, n: int = 14) -> list[float]:
        return self.memo(("rsi", n), lambda: rsi(self.c, n))

    def tr(self) -> list[float]:
        def calc() -> list[float]:
            out = [self.h[0] - self.l[0]]
            for i in range(1, len(self.c)):
                pc = self.c[i - 1]
                out.append(
                    max(self.h[i] - self.l[i], abs(self.h[i] - pc), abs(self.l[i] - pc))
                )
            return out

        return self.memo(("tr",), calc)

    def atr(self, n: int = 14) -> list[float]:
        return self.memo(("atr", n), lambda: wilder(self.tr(), n))

    def macd(
        self, f: int = 12, s: int = 26, g: int = 9
    ) -> tuple[list[float], list[float]]:
        line = self.memo(
            ("macd", f, s),
            lambda: [
                NAN if not _ok(a, b) else a - b
                for a, b in zip(self.ema(f), self.ema(s), strict=True)
            ],
        )
        sig = self.memo(("macds", f, s, g), lambda: ema(line, g))
        return line, sig

    def body(self, i: int = -1) -> float:
        return abs(self.c[i] - self.o[i])

    def bull(self, i: int = -1) -> bool:
        return self.c[i] > self.o[i]

    def bear(self, i: int = -1) -> bool:
        return self.c[i] < self.o[i]

    def hour(self, i: int = -1) -> tuple[int, int] | None:
        raw = (self.t[i] or "").strip()
        if not raw:
            return None
        try:
            d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        return d.hour, d.minute

    def day(self, i: int) -> str:
        return (self.t[i] or "")[:10]


def pivots(xs: list[float], k: int, *, high: bool) -> list[int]:
    """Indices of confirmed swing pivots (k bars each side)."""
    out = []
    for i in range(k, len(xs) - k):
        win = xs[i - k : i + k + 1]
        if (high and xs[i] == max(win)) or (not high and xs[i] == min(win)):
            out.append(i)
    return out


def _conf(x: float) -> float:
    return round(max(0.5, min(0.85, x)), 3)


# ------------------------------------------------------------------- base


class RuleStrategy:
    key: ClassVar[str] = ""
    name: ClassVar[str] = ""
    category: ClassVar[str] = "custom"
    description: ClassVar[str] = ""
    default_params: ClassVar[dict[str, Any]] = {}
    warmup: ClassVar[int] = 60
    indicator: ClassVar[str] = ""

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        for k, v in params.items():
            if k in self.default_params and isinstance(
                self.default_params[k], int | float
            ):
                try:
                    if float(v) <= 0:
                        return False, (f"{k} must be > 0",)
                except (TypeError, ValueError):
                    return False, (f"{k} must be numeric",)
        return True, ()

    def rule(self, s: S, p: dict[str, Any]) -> Out:  # pragma: no cover - abstract
        raise NotImplementedError

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        ind = self.indicator or self.name
        if len(snapshot.bars) < self.warmup:
            return _hold(
                self.key,
                snapshot,
                "Not enough bars",
                ind,
                f"need>={self.warmup}",
                str(len(snapshot.bars)),
            )
        params = {**self.default_params, **(snapshot.params or {})}
        try:
            out = self.rule(S(snapshot), params)
        except (ValueError, ZeroDivisionError, IndexError, OverflowError):
            out = None
        if out is None:
            return _hold(self.key, snapshot, f"No {self.name} setup", ind, "rule")
        action, conf, reason, value = out
        return _go(self.key, snapshot, action, _conf(conf), reason, ind, "rule", value)


def _f(x: float) -> str:
    return f"{x:.2f}"


# ---------------------------------------------------------- momentum / osc


class MacdZeroCross(RuleStrategy):
    key = "macd_zero_cross"
    name = "MACD Zero Cross"
    category = "trend"
    description = "MACD line crosses the zero line (12/26 EMA trend change)."
    indicator = "MACD"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        m, _ = s.macd()
        if cross_up(m, 0.0):
            return BUY, 0.6, "MACD crossed above zero", _f(m[-1])
        if cross_dn(m, 0.0):
            return SELL, 0.6, "MACD crossed below zero", _f(m[-1])
        return None


class MacdHistogramReversal(RuleStrategy):
    key = "macd_histogram_reversal"
    name = "MACD Histogram Reversal"
    category = "momentum"
    description = "Histogram turns up below zero / down above zero (momentum shift)."
    indicator = "MACD_HIST"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        m, g = s.macd()
        h = [NAN if not _ok(a, b) else a - b for a, b in zip(m, g, strict=True)]
        if not _ok(h[-1], h[-2], h[-3]):
            return None
        if h[-1] < 0 and h[-3] > h[-2] < h[-1]:
            return BUY, 0.57, "MACD histogram turned up below zero", _f(h[-1])
        if h[-1] > 0 and h[-3] < h[-2] > h[-1]:
            return SELL, 0.57, "MACD histogram turned down above zero", _f(h[-1])
        return None


class PpoSignalCross(RuleStrategy):
    key = "ppo_signal_cross"
    name = "PPO Signal Cross"
    category = "momentum"
    description = (
        "Percentage Price Oscillator crosses its signal line with trend filter."
    )
    indicator = "PPO"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        e12, e26 = s.ema(12), s.ema(26)
        ppo = [
            NAN if not _ok(a, b) else (a - b) / b * 100
            for a, b in zip(e12, e26, strict=True)
        ]
        sig = ema(ppo, 9)
        e100 = s.ema(100)
        if cross_up(ppo, sig) and s.c[-1] > e100[-1]:
            return BUY, 0.6, "PPO crossed above signal in uptrend", _f(ppo[-1])
        if cross_dn(ppo, sig) and s.c[-1] < e100[-1]:
            return SELL, 0.6, "PPO crossed below signal in downtrend", _f(ppo[-1])
        return None


class TrixSignalCross(RuleStrategy):
    key = "trix_signal_cross"
    name = "TRIX Signal Cross"
    category = "trend"
    description = "Triple-smoothed EMA rate of change crosses its signal line."
    indicator = "TRIX"
    warmup = 80

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        e3 = ema(ema(ema(s.c, 15), 15), 15)
        trix = [NAN] + [
            NAN if not _ok(e3[i], e3[i - 1]) else (e3[i] / e3[i - 1] - 1) * 10000
            for i in range(1, len(e3))
        ]
        sig = ema(trix, 9)
        if cross_up(trix, sig) and trix[-1] < 0:
            return BUY, 0.6, "TRIX crossed up from below zero", _f(trix[-1])
        if cross_dn(trix, sig) and trix[-1] > 0:
            return SELL, 0.6, "TRIX crossed down from above zero", _f(trix[-1])
        return None


class KstSignalCross(RuleStrategy):
    key = "kst_signal_cross"
    name = "Know Sure Thing"
    category = "momentum"
    description = "Pring's KST (weighted multi-period ROC) crosses its signal."
    indicator = "KST"
    warmup = 70

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        parts = [
            (sma(roc(s.c, 10), 10), 1),
            (sma(roc(s.c, 15), 10), 2),
            (sma(roc(s.c, 20), 10), 3),
            (sma(roc(s.c, 30), 15), 4),
        ]
        kst = [
            (
                NAN
                if not _ok(*(pp[0][i] for pp in parts))
                else sum(pp[0][i] * pp[1] for pp in parts)
            )
            for i in range(len(s))
        ]
        sig = sma(kst, 9)
        if cross_up(kst, sig):
            return BUY, 0.58, "KST crossed above signal", _f(kst[-1])
        if cross_dn(kst, sig):
            return SELL, 0.58, "KST crossed below signal", _f(kst[-1])
        return None


class RocZeroCross(RuleStrategy):
    key = "roc_zero_cross"
    name = "Rate of Change"
    category = "momentum"
    description = "12-bar ROC crosses zero in the direction of the 50 EMA."
    indicator = "ROC"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        r = roc(s.c, 12)
        e = s.ema(50)
        if cross_up(r, 0.0) and s.c[-1] > e[-1]:
            return BUY, 0.56, "ROC turned positive above EMA50", _f(r[-1])
        if cross_dn(r, 0.0) and s.c[-1] < e[-1]:
            return SELL, 0.56, "ROC turned negative below EMA50", _f(r[-1])
        return None


class ChandeMomentum(RuleStrategy):
    key = "chande_momentum"
    name = "Chande Momentum Oscillator"
    category = "mean_reversion"
    description = "CMO leaves oversold (-50) / overbought (+50) territory."
    indicator = "CMO"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        n = 14
        cmo = [NAN] * len(s)
        for i in range(n, len(s)):
            d = [s.c[j] - s.c[j - 1] for j in range(i - n + 1, i + 1)]
            up = sum(x for x in d if x > 0)
            dn = -sum(x for x in d if x < 0)
            cmo[i] = 0.0 if up + dn == 0 else (up - dn) / (up + dn) * 100
        if cross_up(cmo, -50.0):
            return BUY, 0.57, "CMO left oversold", _f(cmo[-1])
        if cross_dn(cmo, 50.0):
            return SELL, 0.57, "CMO left overbought", _f(cmo[-1])
        return None


class UltimateOscillator(RuleStrategy):
    key = "ultimate_oscillator"
    name = "Ultimate Oscillator"
    category = "mean_reversion"
    description = "Williams' 7/14/28 Ultimate Oscillator leaves 30/70 zones."
    indicator = "UO"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        bp, tr = [NAN], [NAN]
        for i in range(1, len(s)):
            lo = min(s.l[i], s.c[i - 1])
            bp.append(s.c[i] - lo)
            tr.append(max(s.h[i], s.c[i - 1]) - lo)

        def avg(n: int, i: int) -> float:
            t = sum(tr[i - n + 1 : i + 1])
            return NAN if t == 0 else sum(bp[i - n + 1 : i + 1]) / t

        uo = [NAN] * len(s)
        for i in range(29, len(s)):
            a7, a14, a28 = avg(7, i), avg(14, i), avg(28, i)
            if _ok(a7, a14, a28):
                uo[i] = 100 * (4 * a7 + 2 * a14 + a28) / 7
        if cross_up(uo, 30.0):
            return BUY, 0.58, "Ultimate Oscillator left oversold", _f(uo[-1])
        if cross_dn(uo, 70.0):
            return SELL, 0.58, "Ultimate Oscillator left overbought", _f(uo[-1])
        return None


class StochRsiCross(RuleStrategy):
    key = "stoch_rsi_cross"
    name = "Stochastic RSI"
    category = "mean_reversion"
    description = "StochRSI %K crosses %D inside the 20/80 extremes."
    indicator = "STOCHRSI"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        k = sma(stoch(s.rsi(14), 14), 3)
        d = sma(k, 3)
        if cross_up(k, d) and k[-2] < 20:
            return BUY, 0.57, "StochRSI bullish cross below 20", _f(k[-1])
        if cross_dn(k, d) and k[-2] > 80:
            return SELL, 0.57, "StochRSI bearish cross above 80", _f(k[-1])
        return None


class ConnorsRsi2(RuleStrategy):
    key = "connors_rsi2"
    name = "Connors RSI(2)"
    category = "mean_reversion"
    description = "RSI(2) extreme against the 200 SMA trend (buy dips in uptrends)."
    indicator = "RSI2"
    warmup = 205

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        r = s.rsi(2)
        m = s.sma(200)
        if cross_dn(r, 5.0) and s.c[-1] > m[-1]:
            return BUY, 0.62, "RSI(2) below 5 in a 200-SMA uptrend", _f(r[-1])
        if cross_up(r, 95.0) and s.c[-1] < m[-1]:
            return SELL, 0.62, "RSI(2) above 95 in a 200-SMA downtrend", _f(r[-1])
        return None


def _divergence(s: S, osc: list[float], k: int = 3, look: int = 40) -> Out:
    """Regular divergence confirmed on the bar the second pivot is confirmed."""
    n = len(s)
    lows = [i for i in pivots(s.l, k, high=False) if i >= n - look]
    highs = [i for i in pivots(s.h, k, high=True) if i >= n - look]
    if len(lows) >= 2 and lows[-1] == n - 1 - k:
        a, b = lows[-2], lows[-1]
        if b - a >= 5 and s.l[b] < s.l[a] and _ok(osc[a], osc[b]) and osc[b] > osc[a]:
            return (
                BUY,
                0.62,
                "Bullish divergence (lower low, higher oscillator low)",
                _f(osc[b]),
            )
    if len(highs) >= 2 and highs[-1] == n - 1 - k:
        a, b = highs[-2], highs[-1]
        if b - a >= 5 and s.h[b] > s.h[a] and _ok(osc[a], osc[b]) and osc[b] < osc[a]:
            return (
                SELL,
                0.62,
                "Bearish divergence (higher high, lower oscillator high)",
                _f(osc[b]),
            )
    return None


class RsiDivergence(RuleStrategy):
    key = "rsi_divergence"
    name = "RSI Divergence"
    category = "reversal"
    description = "Regular RSI(14) divergence at confirmed swing points."
    indicator = "RSI"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        return _divergence(s, s.rsi(14))


class MacdDivergence(RuleStrategy):
    key = "macd_divergence"
    name = "MACD Divergence"
    category = "reversal"
    description = "Regular MACD-line divergence at confirmed swing points."
    indicator = "MACD"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        return _divergence(s, s.macd()[0])


class MoneyFlowIndex(RuleStrategy):
    key = "money_flow_index"
    name = "Money Flow Index"
    category = "mean_reversion"
    description = "Volume-weighted RSI (tick volume) leaves 20/80 extremes."
    indicator = "MFI"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        if not any(x > 0 for x in s.v[-30:]):
            return None
        tp = [(h + l_ + c) / 3 for h, l_, c in zip(s.h, s.l, s.c, strict=True)]
        n = 14
        mfi = [NAN] * len(s)
        for i in range(n, len(s)):
            pos = sum(
                tp[j] * s.v[j] for j in range(i - n + 1, i + 1) if tp[j] > tp[j - 1]
            )
            neg = sum(
                tp[j] * s.v[j] for j in range(i - n + 1, i + 1) if tp[j] < tp[j - 1]
            )
            mfi[i] = 100.0 if neg == 0 else 100 - 100 / (1 + pos / neg)
        if cross_up(mfi, 20.0):
            return BUY, 0.57, "MFI left oversold", _f(mfi[-1])
        if cross_dn(mfi, 80.0):
            return SELL, 0.57, "MFI left overbought", _f(mfi[-1])
        return None


class ChaikinMoneyFlow(RuleStrategy):
    key = "chaikin_money_flow"
    name = "Chaikin Money Flow"
    category = "volume"
    description = "CMF(20) crosses zero in the direction of the 50 EMA."
    indicator = "CMF"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        if not any(x > 0 for x in s.v[-30:]):
            return None
        mfv = [
            0.0 if h == l_ else ((c - l_) - (h - c)) / (h - l_) * v
            for h, l_, c, v in zip(s.h, s.l, s.c, s.v, strict=True)
        ]
        n = 20
        cmf = [NAN] * len(s)
        for i in range(n - 1, len(s)):
            vol = sum(s.v[i - n + 1 : i + 1])
            cmf[i] = NAN if vol == 0 else sum(mfv[i - n + 1 : i + 1]) / vol
        e = s.ema(50)
        if cross_up(cmf, 0.0) and s.c[-1] > e[-1]:
            return BUY, 0.56, "CMF turned positive in uptrend", f"{cmf[-1]:.3f}"
        if cross_dn(cmf, 0.0) and s.c[-1] < e[-1]:
            return SELL, 0.56, "CMF turned negative in downtrend", f"{cmf[-1]:.3f}"
        return None


class ElderForceIndex(RuleStrategy):
    key = "elder_force_index"
    name = "Elder Force Index"
    category = "trend"
    description = "2-EMA Force Index dips below zero in an EMA13 uptrend (and mirror)."
    indicator = "FI"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        if not any(x > 0 for x in s.v[-30:]):
            return None
        fi = [NAN] + [(s.c[i] - s.c[i - 1]) * s.v[i] for i in range(1, len(s))]
        f2 = ema(fi, 2)
        e = s.ema(13)
        up = _ok(e[-1], e[-3]) and e[-1] > e[-3] and s.c[-1] > s.ema(50)[-1]
        dn = _ok(e[-1], e[-3]) and e[-1] < e[-3] and s.c[-1] < s.ema(50)[-1]
        if up and cross_dn(f2, 0.0):
            return BUY, 0.58, "Force Index pullback in uptrend", _f(f2[-1])
        if dn and cross_up(f2, 0.0):
            return SELL, 0.58, "Force Index rally in downtrend", _f(f2[-1])
        return None


class ElderImpulse(RuleStrategy):
    key = "elder_impulse"
    name = "Elder Impulse System"
    category = "trend"
    description = "EMA13 slope and MACD histogram slope turn green/red together."
    indicator = "IMPULSE"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        e = s.ema(13)
        m, g = s.macd()
        h = [NAN if not _ok(a, b) else a - b for a, b in zip(m, g, strict=True)]

        def color(i: int) -> int:
            if not _ok(e[i], e[i - 1], h[i], h[i - 1]):
                return 0
            if e[i] > e[i - 1] and h[i] > h[i - 1]:
                return 1
            if e[i] < e[i - 1] and h[i] < h[i - 1]:
                return -1
            return 0

        now, prev = color(-1), color(-2)
        if now == 1 and prev != 1:
            return BUY, 0.57, "Impulse turned green", _f(h[-1])
        if now == -1 and prev != -1:
            return SELL, 0.57, "Impulse turned red", _f(h[-1])
        return None


class ElderRay(RuleStrategy):
    key = "elder_ray"
    name = "Elder Ray"
    category = "trend"
    description = "Bear power turns up below zero in an uptrend (bull power mirror)."
    indicator = "BULL_BEAR_POWER"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        e = s.ema(13)
        if not _ok(e[-1], e[-3]):
            return None
        bear = [l_ - x for l_, x in zip(s.l, e, strict=True)]
        bull = [h - x for h, x in zip(s.h, e, strict=True)]
        if e[-1] > e[-3] and bear[-1] < 0 and bear[-3] > bear[-2] < bear[-1]:
            return BUY, 0.57, "Bear power hooked up in uptrend", _f(bear[-1])
        if e[-1] < e[-3] and bull[-1] > 0 and bull[-3] < bull[-2] > bull[-1]:
            return SELL, 0.57, "Bull power hooked down in downtrend", _f(bull[-1])
        return None


class VortexCross(RuleStrategy):
    key = "vortex_cross"
    name = "Vortex Indicator"
    category = "trend"
    description = "VI+ / VI- (14) crossover."
    indicator = "VORTEX"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        n = 14
        tr = s.tr()
        vp = [NAN] * len(s)
        vm = [NAN] * len(s)
        for i in range(n, len(s)):
            t = sum(tr[i - n + 1 : i + 1])
            if t == 0:
                continue
            vp[i] = sum(abs(s.h[j] - s.l[j - 1]) for j in range(i - n + 1, i + 1)) / t
            vm[i] = sum(abs(s.l[j] - s.h[j - 1]) for j in range(i - n + 1, i + 1)) / t
        if cross_up(vp, vm):
            return BUY, 0.57, "VI+ crossed above VI-", f"{vp[-1]:.3f}"
        if cross_dn(vp, vm):
            return SELL, 0.57, "VI+ crossed below VI-", f"{vp[-1]:.3f}"
        return None


class ParabolicSarFlip(RuleStrategy):
    key = "parabolic_sar"
    name = "Parabolic SAR"
    category = "trend"
    description = "Wilder's Parabolic SAR (0.02/0.2) flips direction."
    indicator = "PSAR"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        up = s.c[1] > s.c[0]
        sar = s.l[0] if up else s.h[0]
        ep = s.h[0] if up else s.l[0]
        af = 0.02
        flips: list[int] = []
        for i in range(1, len(s)):
            sar = sar + af * (ep - sar)
            if up:
                sar = min(sar, s.l[i - 1], s.l[i - 2] if i > 1 else s.l[i - 1])
                if s.l[i] < sar:
                    up, sar, ep, af = False, ep, s.l[i], 0.02
                    flips.append(i)
                elif s.h[i] > ep:
                    ep, af = s.h[i], min(0.2, af + 0.02)
            else:
                sar = max(sar, s.h[i - 1], s.h[i - 2] if i > 1 else s.h[i - 1])
                if s.h[i] > sar:
                    up, sar, ep, af = True, ep, s.h[i], 0.02
                    flips.append(i)
                elif s.l[i] < ep:
                    ep, af = s.l[i], min(0.2, af + 0.02)
        if flips and flips[-1] == len(s) - 1:
            if up:
                return BUY, 0.56, "Parabolic SAR flipped bullish", _f(sar)
            return SELL, 0.56, "Parabolic SAR flipped bearish", _f(sar)
        return None


class ChandelierExitFlip(RuleStrategy):
    key = "chandelier_exit"
    name = "Chandelier Exit"
    category = "trend"
    description = "Close crosses the 22-bar / 3xATR chandelier stop (direction flip)."
    indicator = "CHANDELIER"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        a = s.atr(22)
        hh, ll = highest(s.h, 22), lowest(s.l, 22)
        direction = 0
        flip_at = -1
        for i in range(23, len(s)):
            if not _ok(a[i - 1], hh[i - 1], ll[i - 1]):
                continue
            long_stop = hh[i - 1] - 3 * a[i - 1]
            short_stop = ll[i - 1] + 3 * a[i - 1]
            new = direction
            if s.c[i] > short_stop:
                new = 1
            elif s.c[i] < long_stop:
                new = -1
            if new != direction and direction != 0:
                flip_at = i
            direction = new
        if flip_at == len(s) - 1:
            return (
                (BUY if direction == 1 else SELL),
                0.58,
                "Chandelier stop flipped",
                _f(s.c[-1]),
            )
        return None


def _dmi(s: S, n: int = 14) -> tuple[list[float], list[float], list[float]]:
    pdm = [NAN] + [
        (
            max(s.h[i] - s.h[i - 1], 0.0)
            if s.h[i] - s.h[i - 1] > s.l[i - 1] - s.l[i]
            else 0.0
        )
        for i in range(1, len(s))
    ]
    mdm = [NAN] + [
        (
            max(s.l[i - 1] - s.l[i], 0.0)
            if s.l[i - 1] - s.l[i] > s.h[i] - s.h[i - 1]
            else 0.0
        )
        for i in range(1, len(s))
    ]
    atr = wilder([NAN, *s.tr()[1:]], n)
    sp, sm = wilder(pdm, n), wilder(mdm, n)
    pdi = [
        NAN if not _ok(a, b) or a == 0 else 100 * b / a
        for a, b in zip(atr, sp, strict=True)
    ]
    mdi = [
        NAN if not _ok(a, b) or a == 0 else 100 * b / a
        for a, b in zip(atr, sm, strict=True)
    ]
    dx = [
        NAN if not _ok(a, b) or a + b == 0 else 100 * abs(a - b) / (a + b)
        for a, b in zip(pdi, mdi, strict=True)
    ]
    return pdi, mdi, wilder(dx, n)


class DmiCross(RuleStrategy):
    key = "dmi_cross"
    name = "DMI Crossover"
    category = "trend"
    description = "+DI / -DI crossover confirmed by ADX above 20."
    indicator = "DMI"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        pdi, mdi, adx = _dmi(s)
        if not _ok(adx[-1]) or adx[-1] < 20:
            return None
        if cross_up(pdi, mdi):
            return BUY, 0.58, "+DI crossed above -DI (ADX>20)", _f(adx[-1])
        if cross_dn(pdi, mdi):
            return SELL, 0.58, "+DI crossed below -DI (ADX>20)", _f(adx[-1])
        return None


# --------------------------------------------------------- moving averages


class KamaCross(RuleStrategy):
    key = "kama_cross"
    name = "Kaufman Adaptive MA"
    category = "trend"
    description = "Close crosses KAMA(10,2,30) while KAMA slopes the same way."
    indicator = "KAMA"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        n, fast, slow = 10, 2 / 3, 2 / 31
        k = [NAN] * len(s)
        k[n] = s.c[n]
        for i in range(n + 1, len(s)):
            change = abs(s.c[i] - s.c[i - n])
            vol = sum(abs(s.c[j] - s.c[j - 1]) for j in range(i - n + 1, i + 1))
            er = 0.0 if vol == 0 else change / vol
            sc = (er * (fast - slow) + slow) ** 2
            k[i] = k[i - 1] + sc * (s.c[i] - k[i - 1])
        if cross_up(s.c, k) and k[-1] > k[-3]:
            return BUY, 0.57, "Close crossed above rising KAMA", _f(k[-1])
        if cross_dn(s.c, k) and k[-1] < k[-3]:
            return SELL, 0.57, "Close crossed below falling KAMA", _f(k[-1])
        return None


def _dema(xs: list[float], n: int) -> list[float]:
    e = ema(xs, n)
    ee = ema(e, n)
    return [NAN if not _ok(a, b) else 2 * a - b for a, b in zip(e, ee, strict=True)]


class DemaCross(RuleStrategy):
    key = "dema_cross"
    name = "DEMA Crossover"
    category = "trend"
    description = "Double-EMA 20 crosses double-EMA 50 (lower lag than plain EMA)."
    indicator = "DEMA"
    warmup = 110

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        a, b = _dema(s.c, 20), _dema(s.c, 50)
        if cross_up(a, b):
            return BUY, 0.58, "DEMA20 crossed above DEMA50", _f(a[-1])
        if cross_dn(a, b):
            return SELL, 0.58, "DEMA20 crossed below DEMA50", _f(a[-1])
        return None


class TemaTurn(RuleStrategy):
    key = "tema_turn"
    name = "TEMA Turn"
    category = "trend"
    description = "Triple-EMA(30) slope turns with price on the same side."
    indicator = "TEMA"
    warmup = 100

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        e1 = ema(s.c, 30)
        e2 = ema(e1, 30)
        e3 = ema(e2, 30)
        t = [
            NAN if not _ok(a, b, c) else 3 * a - 3 * b + c
            for a, b, c in zip(e1, e2, e3, strict=True)
        ]
        if not _ok(t[-1], t[-2], t[-3]):
            return None
        if t[-3] > t[-2] < t[-1] and s.c[-1] > t[-1]:
            return BUY, 0.56, "TEMA turned up", _f(t[-1])
        if t[-3] < t[-2] > t[-1] and s.c[-1] < t[-1]:
            return SELL, 0.56, "TEMA turned down", _f(t[-1])
        return None


class ZlemaCross(RuleStrategy):
    key = "zlema_cross"
    name = "Zero-Lag EMA"
    category = "trend"
    description = "Close crosses ZLEMA(21) in the direction of the 100 EMA."
    indicator = "ZLEMA"
    warmup = 110

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        lag = 10
        adj = [NAN if i < lag else 2 * s.c[i] - s.c[i - lag] for i in range(len(s))]
        z = ema(adj, 21)
        e = s.ema(100)
        if cross_up(s.c, z) and s.c[-1] > e[-1]:
            return BUY, 0.57, "Close crossed above ZLEMA in uptrend", _f(z[-1])
        if cross_dn(s.c, z) and s.c[-1] < e[-1]:
            return SELL, 0.57, "Close crossed below ZLEMA in downtrend", _f(z[-1])
        return None


class McGinleyDynamic(RuleStrategy):
    key = "mcginley_dynamic"
    name = "McGinley Dynamic"
    category = "trend"
    description = "Close crosses the McGinley Dynamic(14) line."
    indicator = "MCGINLEY"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        n = 14
        md = [NAN] * len(s)
        md[0] = s.c[0]
        for i in range(1, len(s)):
            prev = md[i - 1]
            ratio = s.c[i] / prev if prev else 1.0
            md[i] = prev + (s.c[i] - prev) / (n * ratio**4)
        md[: n * 2] = [NAN] * (n * 2)
        if cross_up(s.c, md) and md[-1] > md[-4]:
            return BUY, 0.56, "Close crossed above rising McGinley", _f(md[-1])
        if cross_dn(s.c, md) and md[-1] < md[-4]:
            return SELL, 0.56, "Close crossed below falling McGinley", _f(md[-1])
        return None


class EmaRibbon(RuleStrategy):
    key = "ema_ribbon"
    name = "EMA Ribbon Alignment"
    category = "trend"
    description = "8/13/21/34/55 EMAs become fully stacked (fresh alignment bar)."
    indicator = "RIBBON"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        es = [s.ema(n) for n in (8, 13, 21, 34, 55)]

        def stacked(i: int, up: bool) -> bool:
            v = [e[i] for e in es]
            if not _ok(*v):
                return False
            return (
                all(v[j] > v[j + 1] for j in range(4))
                if up
                else all(v[j] < v[j + 1] for j in range(4))
            )

        if stacked(-1, True) and not stacked(-2, True):
            return BUY, 0.6, "EMA ribbon stacked bullish", _f(es[0][-1])
        if stacked(-1, False) and not stacked(-2, False):
            return SELL, 0.6, "EMA ribbon stacked bearish", _f(es[0][-1])
        return None


class GoldenDeathCross(RuleStrategy):
    key = "golden_death_cross"
    name = "Golden / Death Cross"
    category = "trend"
    description = "SMA50 crosses SMA200."
    indicator = "SMA50/200"
    warmup = 205

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        a, b = s.sma(50), s.sma(200)
        if cross_up(a, b):
            return BUY, 0.6, "Golden cross (SMA50 > SMA200)", _f(a[-1])
        if cross_dn(a, b):
            return SELL, 0.6, "Death cross (SMA50 < SMA200)", _f(a[-1])
        return None


class EmaPullback(RuleStrategy):
    key = "ema_pullback"
    name = "EMA20 Pullback"
    category = "trend"
    description = (
        "Price tags EMA20 in an EMA20>EMA50 trend and closes back with the trend."
    )
    indicator = "EMA20/50"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        e20, e50 = s.ema(20), s.ema(50)
        if not _ok(e20[-1], e50[-1], e20[-5]):
            return None
        up = e20[-1] > e50[-1] and e20[-1] > e20[-5]
        dn = e20[-1] < e50[-1] and e20[-1] < e20[-5]
        if up and s.l[-1] <= e20[-1] < s.c[-1] and s.bull() and s.l[-2] > e20[-2]:
            return BUY, 0.61, "Bullish rejection of EMA20 in uptrend", _f(e20[-1])
        if dn and s.h[-1] >= e20[-1] > s.c[-1] and s.bear() and s.h[-2] < e20[-2]:
            return SELL, 0.61, "Bearish rejection of EMA20 in downtrend", _f(e20[-1])
        return None


class VwmaCross(RuleStrategy):
    key = "vwma_cross"
    name = "Volume-Weighted MA"
    category = "volume"
    description = "Close crosses VWMA(20) on above-average tick volume."
    indicator = "VWMA"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        if not any(x > 0 for x in s.v[-30:]):
            return None
        n = 20
        vw = [NAN] * len(s)
        for i in range(n - 1, len(s)):
            vol = sum(s.v[i - n + 1 : i + 1])
            if vol:
                vw[i] = sum(s.c[j] * s.v[j] for j in range(i - n + 1, i + 1)) / vol
        vavg = sum(s.v[-21:-1]) / 20
        if s.v[-1] <= vavg:
            return None
        if cross_up(s.c, vw):
            return BUY, 0.56, "Close crossed above VWMA on volume", _f(vw[-1])
        if cross_dn(s.c, vw):
            return SELL, 0.56, "Close crossed below VWMA on volume", _f(vw[-1])
        return None


# -------------------------------------------------------------- channels


class AtrEnvelopeReversion(RuleStrategy):
    key = "atr_envelope_reversion"
    name = "ATR Envelope Reversion"
    category = "mean_reversion"
    description = "Close re-enters the SMA20 +/- 2.5xATR envelope after an excursion."
    indicator = "ENVELOPE"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        m, a = s.sma(20), s.atr(14)
        if not _ok(m[-1], m[-2], a[-1], a[-2]):
            return None
        up1, lo1 = m[-1] + 2.5 * a[-1], m[-1] - 2.5 * a[-1]
        up2, lo2 = m[-2] + 2.5 * a[-2], m[-2] - 2.5 * a[-2]
        if s.c[-2] < lo2 and s.c[-1] > lo1:
            return BUY, 0.58, "Re-entered envelope from below", _f(lo1)
        if s.c[-2] > up2 and s.c[-1] < up1:
            return SELL, 0.58, "Re-entered envelope from above", _f(up1)
        return None


class AtrChannelBreakout(RuleStrategy):
    key = "atr_channel_breakout"
    name = "ATR Channel Breakout"
    category = "breakout"
    description = "Close breaks SMA20 +/- 2xATR (volatility expansion)."
    indicator = "ATR_CHANNEL"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        m, a = s.sma(20), s.atr(14)
        up = [NAN if not _ok(x, y) else x + 2 * y for x, y in zip(m, a, strict=True)]
        lo = [NAN if not _ok(x, y) else x - 2 * y for x, y in zip(m, a, strict=True)]
        if cross_up(s.c, up):
            return BUY, 0.57, "Close broke the upper ATR channel", _f(up[-1])
        if cross_dn(s.c, lo):
            return SELL, 0.57, "Close broke the lower ATR channel", _f(lo[-1])
        return None


class Turtle55(RuleStrategy):
    key = "turtle_55"
    name = "Turtle System 2"
    category = "breakout"
    description = "Close breaks the prior 55-bar high / low (Turtle System 2 entry)."
    indicator = "DONCHIAN55"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        hh = max(s.h[-56:-1])
        ll = min(s.l[-56:-1])
        if s.c[-1] > hh and s.c[-2] <= max(s.h[-57:-2]):
            return BUY, 0.58, "55-bar breakout", _f(hh)
        if s.c[-1] < ll and s.c[-2] >= min(s.l[-57:-2]):
            return SELL, 0.58, "55-bar breakdown", _f(ll)
        return None


class DonchianMidline(RuleStrategy):
    key = "donchian_midline"
    name = "Donchian Midline"
    category = "trend"
    description = "Close crosses the 20-bar Donchian midline with the 50 EMA."
    indicator = "DONCHIAN_MID"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        hh, ll = highest(s.h, 20), lowest(s.l, 20)
        mid = [
            NAN if not _ok(a, b) else (a + b) / 2 for a, b in zip(hh, ll, strict=True)
        ]
        e = s.ema(50)
        if cross_up(s.c, mid) and s.c[-1] > e[-1]:
            return BUY, 0.55, "Close crossed above Donchian midline", _f(mid[-1])
        if cross_dn(s.c, mid) and s.c[-1] < e[-1]:
            return SELL, 0.55, "Close crossed below Donchian midline", _f(mid[-1])
        return None


def _bb(
    s: S, n: int = 20, k: float = 2.0
) -> tuple[list[float], list[float], list[float]]:
    m, sd = s.sma(n), stdev(s.c, n)
    up = [NAN if not _ok(a, b) else a + k * b for a, b in zip(m, sd, strict=True)]
    lo = [NAN if not _ok(a, b) else a - k * b for a, b in zip(m, sd, strict=True)]
    return m, up, lo


class PercentBReversal(RuleStrategy):
    key = "percent_b_reversal"
    name = "Bollinger %B Reversal"
    category = "mean_reversion"
    description = (
        "%B returns inside the bands after closing outside (with RSI confirm)."
    )
    indicator = "%B"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        _, up, lo = _bb(s)
        pb = [
            NAN if not _ok(u, l_) or u == l_ else (c - l_) / (u - l_)
            for c, u, l_ in zip(s.c, up, lo, strict=True)
        ]
        r = s.rsi(14)
        if cross_up(pb, 0.0) and r[-1] < 45:
            return BUY, 0.58, "%B back above 0", _f(pb[-1])
        if cross_dn(pb, 1.0) and r[-1] > 55:
            return SELL, 0.58, "%B back below 1", _f(pb[-1])
        return None


class BollingerBandWalk(RuleStrategy):
    key = "bollinger_band_walk"
    name = "Bollinger Band Walk"
    category = "trend"
    description = "Second consecutive close outside the band in trend direction."
    indicator = "BB"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        _, up, lo = _bb(s)
        e20, e50 = s.ema(20), s.ema(50)
        if not _ok(up[-3], e50[-1]):
            return None
        if (
            s.c[-1] > up[-1]
            and s.c[-2] > up[-2]
            and s.c[-3] <= up[-3]
            and e20[-1] > e50[-1]
        ):
            return BUY, 0.56, "Walking the upper band", _f(up[-1])
        if (
            s.c[-1] < lo[-1]
            and s.c[-2] < lo[-2]
            and s.c[-3] >= lo[-3]
            and e20[-1] < e50[-1]
        ):
            return SELL, 0.56, "Walking the lower band", _f(lo[-1])
        return None


class TtmSqueeze(RuleStrategy):
    key = "ttm_squeeze"
    name = "TTM Squeeze"
    category = "breakout"
    description = "Bollinger Bands leave the Keltner Channel; trade momentum direction."
    indicator = "SQUEEZE"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        m, up, lo = _bb(s)
        e, a = s.ema(20), s.atr(20)

        def on(i: int) -> bool:
            if not _ok(up[i], e[i], a[i]):
                return False
            return up[i] < e[i] + 1.5 * a[i] and lo[i] > e[i] - 1.5 * a[i]

        if not (on(-2) and on(-3) and not on(-1)):
            return None
        hh, ll = max(s.h[-20:]), min(s.l[-20:])
        mom = s.c[-1] - ((hh + ll) / 2 + m[-1]) / 2
        if mom > 0:
            return BUY, 0.6, "Squeeze fired with positive momentum", _f(mom)
        if mom < 0:
            return SELL, 0.6, "Squeeze fired with negative momentum", _f(mom)
        return None


class LinRegChannelReversion(RuleStrategy):
    key = "linreg_channel_reversion"
    name = "Regression Channel Reversion"
    category = "mean_reversion"
    description = "Close returns inside a 50-bar +/-2 sigma linear-regression channel."
    indicator = "LINREG"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        def channel(end: int) -> tuple[float, float]:
            ys = s.c[end - 50 : end]
            n = len(ys)
            xm = (n - 1) / 2
            ym = sum(ys) / n
            sxx = sum((i - xm) ** 2 for i in range(n))
            slope = sum((i - xm) * (y - ym) for i, y in enumerate(ys)) / sxx
            fit = [ym + slope * (i - xm) for i in range(n)]
            sd = math.sqrt(sum((y - f) ** 2 for y, f in zip(ys, fit, strict=True)) / n)
            return fit[-1], sd

        f1, sd1 = channel(len(s))
        f2, sd2 = channel(len(s) - 1)
        if s.c[-2] < f2 - 2 * sd2 and s.c[-1] > f1 - 2 * sd1:
            return BUY, 0.57, "Back inside regression channel from below", _f(f1)
        if s.c[-2] > f2 + 2 * sd2 and s.c[-1] < f1 + 2 * sd1:
            return SELL, 0.57, "Back inside regression channel from above", _f(f1)
        return None


# ------------------------------------------------------ cyclic / advanced


class RelativeVigorIndex(RuleStrategy):
    key = "relative_vigor_index"
    name = "Relative Vigor Index"
    category = "momentum"
    description = "RVI(10) crosses its signal line on the side of the 50 EMA."
    indicator = "RVI"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        def sym(xs: list[float], i: int) -> float:
            return (xs[i] + 2 * xs[i - 1] + 2 * xs[i - 2] + xs[i - 3]) / 6

        co = [c - o for c, o in zip(s.c, s.o, strict=True)]
        hl = [h - l_ for h, l_ in zip(s.h, s.l, strict=True)]
        num = [NAN] * 3 + [sym(co, i) for i in range(3, len(s))]
        den = [NAN] * 3 + [sym(hl, i) for i in range(3, len(s))]
        sn, sd = sma(num, 10), sma(den, 10)
        rvi = [
            NAN if not _ok(a, b) or b == 0 else a / b
            for a, b in zip(sn, sd, strict=True)
        ]
        sig = [NAN] * 3 + [
            NAN if not _ok(*rvi[i - 3 : i + 1]) else sym(rvi, i)
            for i in range(3, len(s))
        ]
        e = s.ema(50)
        if cross_up(rvi, sig) and s.c[-1] > e[-1]:
            return BUY, 0.55, "RVI crossed above signal", f"{rvi[-1]:.3f}"
        if cross_dn(rvi, sig) and s.c[-1] < e[-1]:
            return SELL, 0.55, "RVI crossed below signal", f"{rvi[-1]:.3f}"
        return None


class CoppockCurve(RuleStrategy):
    key = "coppock_curve"
    name = "Coppock Curve"
    category = "momentum"
    description = "WMA10(ROC14+ROC11) turns up below zero / down above zero."
    indicator = "COPPOCK"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        a, b = roc(s.c, 14), roc(s.c, 11)
        cc = wma(
            [NAN if not _ok(x, y) else x + y for x, y in zip(a, b, strict=True)], 10
        )
        if not _ok(cc[-1], cc[-2], cc[-3]):
            return None
        if cc[-1] < 0 and cc[-3] > cc[-2] < cc[-1]:
            return BUY, 0.56, "Coppock turned up below zero", _f(cc[-1])
        if cc[-1] > 0 and cc[-3] < cc[-2] > cc[-1]:
            return SELL, 0.56, "Coppock turned down above zero", _f(cc[-1])
        return None


class FisherTransform(RuleStrategy):
    key = "fisher_transform"
    name = "Fisher Transform"
    category = "reversal"
    description = "Ehlers Fisher(10) crosses its trigger at the +/-1.5 extremes."
    indicator = "FISHER"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        mid = [(h + l_) / 2 for h, l_ in zip(s.h, s.l, strict=True)]
        hh, ll = highest(mid, 10), lowest(mid, 10)
        val = 0.0
        fish = [NAN] * len(s)
        prev = 0.0
        for i in range(9, len(s)):
            rng = hh[i] - ll[i]
            x = 0.0 if rng == 0 else (mid[i] - ll[i]) / rng - 0.5
            val = max(-0.999, min(0.999, 0.66 * x + 0.67 * val))
            prev = 0.5 * math.log((1 + val) / (1 - val)) + 0.5 * prev
            fish[i] = prev
        trig = [NAN, *fish[:-1]]
        if cross_up(fish, trig) and fish[-2] < -1.5:
            return BUY, 0.58, "Fisher turned up from below -1.5", _f(fish[-1])
        if cross_dn(fish, trig) and fish[-2] > 1.5:
            return SELL, 0.58, "Fisher turned down from above 1.5", _f(fish[-1])
        return None


class SchaffTrendCycle(RuleStrategy):
    key = "schaff_trend_cycle"
    name = "Schaff Trend Cycle"
    category = "trend"
    description = "STC (MACD 23/50, cycle 10) leaves the 25/75 zones."
    indicator = "STC"
    warmup = 120

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        m, _ = s.macd(23, 50, 9)

        def smooth_stoch(xs: list[float]) -> list[float]:
            st = stoch(xs, 10)
            out = [NAN] * len(xs)
            prev = NAN
            for i, x in enumerate(st):
                if math.isnan(x):
                    continue
                prev = x if math.isnan(prev) else prev + 0.5 * (x - prev)
                out[i] = prev
            return out

        stc = smooth_stoch(smooth_stoch(m))
        if cross_up(stc, 25.0):
            return BUY, 0.57, "STC rose through 25", _f(stc[-1])
        if cross_dn(stc, 75.0):
            return SELL, 0.57, "STC fell through 75", _f(stc[-1])
        return None


class MassIndexReversal(RuleStrategy):
    key = "mass_index_reversal"
    name = "Mass Index Reversal Bulge"
    category = "reversal"
    description = (
        "Mass Index rises above 27 then falls below 26.5 - fade the prior trend."
    )
    indicator = "MASS"
    warmup = 70

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        rng = [h - l_ for h, l_ in zip(s.h, s.l, strict=True)]
        e1 = ema(rng, 9)
        e2 = ema(e1, 9)
        ratio = [
            NAN if not _ok(a, b) or b == 0 else a / b
            for a, b in zip(e1, e2, strict=True)
        ]
        mi = [NAN] * len(s)
        for i in range(24, len(s)):
            win = ratio[i - 24 : i + 1]
            if _ok(*win):
                mi[i] = sum(win)
        if not cross_dn(mi, 26.5) or max(x for x in mi[-15:] if _ok(x)) < 27:
            return None
        e = s.ema(9)
        if s.c[-1] < e[-10]:
            return BUY, 0.55, "Reversal bulge after a decline", _f(mi[-1])
        return SELL, 0.55, "Reversal bulge after a rally", _f(mi[-1])


class WilliamsVixFix(RuleStrategy):
    key = "williams_vix_fix"
    name = "Williams VIX Fix"
    category = "reversal"
    description = "Synthetic VIX spike ends with a bullish bar (capitulation buy)."
    indicator = "WVF"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        hc = highest(s.c, 22)
        wvf = [
            NAN if not _ok(h) or h == 0 else (h - l_) / h * 100
            for h, l_ in zip(hc, s.l, strict=True)
        ]
        m = sma(wvf, 20)
        sd = stdev([0.0 if math.isnan(x) else x for x in wvf], 20)
        band = [NAN if not _ok(a, b) else a + 2 * b for a, b in zip(m, sd, strict=True)]
        if (
            _ok(band[-2], band[-1])
            and wvf[-2] > band[-2]
            and wvf[-1] <= band[-1]
            and s.bull()
        ):
            return BUY, 0.58, "Volatility spike faded with a bullish bar", _f(wvf[-1])
        return None


class ChoppinessBreakout(RuleStrategy):
    key = "choppiness_breakout"
    name = "Choppiness Breakout"
    category = "breakout"
    description = "Choppiness Index drops below 50 after a choppy phase (>61.8)."
    indicator = "CHOP"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        n = 14
        tr = s.tr()
        chop = [NAN] * len(s)
        for i in range(n, len(s)):
            hh, ll = max(s.h[i - n + 1 : i + 1]), min(s.l[i - n + 1 : i + 1])
            if hh > ll:
                chop[i] = (
                    100
                    * math.log10(sum(tr[i - n + 1 : i + 1]) / (hh - ll))
                    / math.log10(n)
                )
        recent = [x for x in chop[-20:-1] if _ok(x)]
        if not recent or max(recent) < 61.8 or not cross_dn(chop, 50.0):
            return None
        mid = (max(s.h[-20:]) + min(s.l[-20:])) / 2
        if s.c[-1] > mid:
            return BUY, 0.56, "Trend emerging from chop (upside)", _f(chop[-1])
        return SELL, 0.56, "Trend emerging from chop (downside)", _f(chop[-1])


# ------------------------------------------------------- session / levels


def _hm(s: S, i: int) -> int | None:
    t = s.hour(i)
    return None if t is None else t[0] * 60 + t[1]


class LondonOpeningRange(RuleStrategy):
    key = "london_opening_range"
    name = "London Opening Range Breakout"
    category = "session"
    description = "Break of the 07:00-08:00 UTC range between 08:00 and 12:00 UTC."
    indicator = "ORB"
    warmup = 100

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        now = _hm(s, -1)
        if now is None or not (8 * 60 <= now < 12 * 60):
            return None
        today = s.day(-1)
        idx = [
            i
            for i in range(len(s) - 30, len(s))
            if s.day(i) == today and (_hm(s, i) or 0) // 60 == 7
        ]
        if len(idx) < 2:
            return None
        hi = max(s.h[i] for i in idx)
        lo = min(s.l[i] for i in idx)
        if s.c[-1] > hi >= s.c[-2]:
            return BUY, 0.58, "Broke above London opening range", _f(hi)
        if s.c[-1] < lo <= s.c[-2]:
            return SELL, 0.58, "Broke below London opening range", _f(lo)
        return None


class AsianRangeFade(RuleStrategy):
    key = "asian_range_fade"
    name = "Asian Range Fake-out Fade"
    category = "session"
    description = (
        "London probes beyond the Asian range then closes back inside - fade it."
    )
    indicator = "ASIA_RANGE"
    warmup = 100

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        now = _hm(s, -1)
        if now is None or not (7 * 60 <= now < 11 * 60):
            return None
        today = s.day(-1)
        idx = [
            i
            for i in range(len(s) - 60, len(s))
            if s.day(i) == today and (_hm(s, i) or 0) < 7 * 60
        ]
        if len(idx) < 8:
            return None
        hi = max(s.h[i] for i in idx)
        lo = min(s.l[i] for i in idx)
        if s.h[-1] > hi and s.c[-1] < hi and s.bear():
            return SELL, 0.58, "False break above Asian high", _f(hi)
        if s.l[-1] < lo and s.c[-1] > lo and s.bull():
            return BUY, 0.58, "False break below Asian low", _f(lo)
        return None


class NewYorkOpenMomentum(RuleStrategy):
    key = "ny_open_momentum"
    name = "New York Open Momentum"
    category = "session"
    description = "Strong 13:30 UTC bar in the direction of the 50 EMA."
    indicator = "NY_OPEN"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        now = _hm(s, -1)
        if now is None or not (13 * 60 + 30 <= now < 13 * 60 + 45):
            return None
        a, e = s.atr(14), s.ema(50)
        if not _ok(a[-1], e[-1]) or s.body() < 0.6 * a[-1]:
            return None
        if s.bull() and s.c[-1] > e[-1]:
            return BUY, 0.57, "Strong bullish New York open bar", _f(s.body())
        if s.bear() and s.c[-1] < e[-1]:
            return SELL, 0.57, "Strong bearish New York open bar", _f(s.body())
        return None


def _prev_day_hlc(s: S) -> tuple[float, float, float] | None:
    today = s.day(-1)
    if not today:
        return None
    prev = [i for i in range(len(s)) if s.day(i) and s.day(i) < today]
    if not prev:
        return None
    day = s.day(prev[-1])
    idx = [i for i in prev if s.day(i) == day]
    if len(idx) < 20:
        return None
    return max(s.h[i] for i in idx), min(s.l[i] for i in idx), s.c[idx[-1]]


class PivotPointBounce(RuleStrategy):
    key = "pivot_point_bounce"
    name = "Daily Pivot Bounce"
    category = "levels"
    description = "Rejection candle at the classic daily S1 / R1 pivot."
    indicator = "PIVOT"
    warmup = 120

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        hlc = _prev_day_hlc(s)
        if hlc is None:
            return None
        h, l_, c = hlc
        pp = (h + l_ + c) / 3
        s1, r1 = 2 * pp - h, 2 * pp - l_
        if s.l[-1] <= s1 < s.c[-1] and s.bull() and s.l[-2] > s1:
            return BUY, 0.58, "Bounce off daily S1", _f(s1)
        if s.h[-1] >= r1 > s.c[-1] and s.bear() and s.h[-2] < r1:
            return SELL, 0.58, "Rejection at daily R1", _f(r1)
        return None


class CamarillaBreakout(RuleStrategy):
    key = "camarilla_breakout"
    name = "Camarilla H4/L4 Breakout"
    category = "levels"
    description = "Close breaks the Camarilla H4 / L4 level."
    indicator = "CAMARILLA"
    warmup = 120

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        hlc = _prev_day_hlc(s)
        if hlc is None:
            return None
        h, l_, c = hlc
        h4 = c + 1.1 * (h - l_) / 2
        l4 = c - 1.1 * (h - l_) / 2
        if s.c[-1] > h4 >= s.c[-2]:
            return BUY, 0.57, "Broke Camarilla H4", _f(h4)
        if s.c[-1] < l4 <= s.c[-2]:
            return SELL, 0.57, "Broke Camarilla L4", _f(l4)
        return None


class FibonacciPullback(RuleStrategy):
    key = "fibonacci_pullback"
    name = "Fibonacci 61.8% Pullback"
    category = "levels"
    description = "Rejection at the 61.8% retracement of the last 60-bar swing."
    indicator = "FIB"
    warmup = 80

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        win_h, win_l = s.h[-61:-1], s.l[-61:-1]
        hi, lo = max(win_h), min(win_l)
        hi_i, lo_i = win_h.index(hi), win_l.index(lo)
        a = s.atr(14)[-1]
        if not _ok(a) or hi - lo < 4 * a:
            return None
        if lo_i < hi_i:  # up-swing
            fib = hi - 0.618 * (hi - lo)
            if s.l[-1] <= fib < s.c[-1] and s.bull() and s.l[-2] > fib:
                return BUY, 0.6, "Bullish rejection at 61.8% retracement", _f(fib)
        else:
            fib = lo + 0.618 * (hi - lo)
            if s.h[-1] >= fib > s.c[-1] and s.bear() and s.h[-2] < fib:
                return SELL, 0.6, "Bearish rejection at 61.8% retracement", _f(fib)
        return None


# -------------------------------------------------------------- patterns


class DoubleTopBottom(RuleStrategy):
    key = "double_top_bottom"
    name = "Double Top / Bottom"
    category = "pattern"
    description = "Two equal swing extremes; close breaks the neckline."
    indicator = "DOUBLE"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        a = s.atr(14)[-1]
        if not _ok(a):
            return None
        n = len(s)
        lows = [i for i in pivots(s.l, 3, high=False) if i >= n - 50]
        highs = [i for i in pivots(s.h, 3, high=True) if i >= n - 50]
        if len(lows) >= 2:
            i, j = lows[-2], lows[-1]
            if j - i >= 5 and abs(s.l[i] - s.l[j]) <= 0.3 * a:
                neck = max(s.h[i : j + 1])
                if s.c[-1] > neck >= s.c[-2]:
                    return BUY, 0.62, "Double bottom neckline break", _f(neck)
        if len(highs) >= 2:
            i, j = highs[-2], highs[-1]
            if j - i >= 5 and abs(s.h[i] - s.h[j]) <= 0.3 * a:
                neck = min(s.l[i : j + 1])
                if s.c[-1] < neck <= s.c[-2]:
                    return SELL, 0.62, "Double top neckline break", _f(neck)
        return None


class MorningEveningStar(RuleStrategy):
    key = "morning_evening_star"
    name = "Morning / Evening Star"
    category = "pattern"
    description = "Three-candle star reversal at a 10-bar extreme."
    indicator = "STAR"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        a = s.atr(14)[-1]
        if not _ok(a):
            return None
        big, small = 0.6 * a, 0.3 * a
        mid3 = (s.o[-3] + s.c[-3]) / 2
        if (
            s.bear(-3)
            and s.body(-3) > big
            and s.body(-2) < small
            and s.bull()
            and s.c[-1] > mid3
            and min(s.l[-3:]) <= min(s.l[-12:])
        ):
            return BUY, 0.6, "Morning star at a swing low", _f(s.c[-1])
        if (
            s.bull(-3)
            and s.body(-3) > big
            and s.body(-2) < small
            and s.bear()
            and s.c[-1] < mid3
            and max(s.h[-3:]) >= max(s.h[-12:])
        ):
            return SELL, 0.6, "Evening star at a swing high", _f(s.c[-1])
        return None


class ThreeSoldiersCrows(RuleStrategy):
    key = "three_soldiers_crows"
    name = "Three White Soldiers / Black Crows"
    category = "pattern"
    description = "Three strong same-colour candles after an opposite move."
    indicator = "SOLDIERS"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        a = s.atr(14)[-1]
        m = s.sma(20)
        if not _ok(a, m[-4]):
            return None
        idx = (-3, -2, -1)
        if (
            all(s.bull(i) and s.body(i) > 0.5 * a for i in idx)
            and s.c[-1] > s.c[-2] > s.c[-3]
            and s.c[-4] < m[-4]
        ):
            return BUY, 0.58, "Three white soldiers", _f(s.c[-1])
        if (
            all(s.bear(i) and s.body(i) > 0.5 * a for i in idx)
            and s.c[-1] < s.c[-2] < s.c[-3]
            and s.c[-4] > m[-4]
        ):
            return SELL, 0.58, "Three black crows", _f(s.c[-1])
        return None


class HaramiReversal(RuleStrategy):
    key = "harami_reversal"
    name = "Harami Reversal"
    category = "pattern"
    description = "Inside-body candle of opposite colour at an RSI extreme."
    indicator = "HARAMI"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        a = s.atr(14)[-1]
        r = s.rsi(14)
        if not _ok(a, r[-2]) or s.body(-2) < 0.6 * a:
            return None
        lo2, hi2 = min(s.o[-2], s.c[-2]), max(s.o[-2], s.c[-2])
        inside = lo2 < min(s.o[-1], s.c[-1]) and max(s.o[-1], s.c[-1]) < hi2
        if inside and s.bear(-2) and s.bull() and r[-2] < 35:
            return BUY, 0.56, "Bullish harami at oversold", _f(r[-2])
        if inside and s.bull(-2) and s.bear() and r[-2] > 65:
            return SELL, 0.56, "Bearish harami at overbought", _f(r[-2])
        return None


class TweezerReversal(RuleStrategy):
    key = "tweezer_reversal"
    name = "Tweezer Top / Bottom"
    category = "pattern"
    description = "Matching extremes on two opposite candles at a 15-bar extreme."
    indicator = "TWEEZER"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        a = s.atr(14)[-1]
        if not _ok(a):
            return None
        tol = 0.1 * a
        if (
            s.bear(-2)
            and s.bull()
            and abs(s.l[-1] - s.l[-2]) <= tol
            and min(s.l[-2:]) <= min(s.l[-15:])
        ):
            return BUY, 0.57, "Tweezer bottom", _f(s.l[-1])
        if (
            s.bull(-2)
            and s.bear()
            and abs(s.h[-1] - s.h[-2]) <= tol
            and max(s.h[-2:]) >= max(s.h[-15:])
        ):
            return SELL, 0.57, "Tweezer top", _f(s.h[-1])
        return None


class MarubozuMomentum(RuleStrategy):
    key = "marubozu_momentum"
    name = "Marubozu Momentum"
    category = "momentum"
    description = "Full-body candle (>1.2xATR, tiny wicks) with the 50 EMA trend."
    indicator = "MARUBOZU"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        a, e = s.atr(14)[-1], s.ema(50)[-1]
        rng = s.h[-1] - s.l[-1]
        if not _ok(a, e) or rng == 0 or s.body() < 1.2 * a or s.body() / rng < 0.85:
            return None
        if s.bull() and s.c[-1] > e:
            return BUY, 0.57, "Bullish marubozu with trend", _f(s.body())
        if s.bear() and s.c[-1] < e:
            return SELL, 0.57, "Bearish marubozu with trend", _f(s.body())
        return None


class DojiBandReversal(RuleStrategy):
    key = "doji_band_reversal"
    name = "Doji at Band Reversal"
    category = "reversal"
    description = "Doji outside the Bollinger Band, confirmed by the next candle."
    indicator = "DOJI_BB"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        _, up, lo = _bb(s)
        rng = s.h[-2] - s.l[-2]
        if not _ok(up[-2], lo[-2]) or rng == 0 or s.body(-2) / rng > 0.15:
            return None
        if s.l[-2] < lo[-2] and s.bull() and s.c[-1] > s.h[-2]:
            return BUY, 0.58, "Doji below lower band confirmed", _f(lo[-2])
        if s.h[-2] > up[-2] and s.bear() and s.c[-1] < s.l[-2]:
            return SELL, 0.58, "Doji above upper band confirmed", _f(up[-2])
        return None


class OutsideBarReversal(RuleStrategy):
    key = "outside_bar_reversal"
    name = "Outside Bar Reversal"
    category = "pattern"
    description = (
        "Engulfing range bar closing beyond the prior extreme after a 5-bar move."
    )
    indicator = "OUTSIDE_BAR"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        outside = s.h[-1] > s.h[-2] and s.l[-1] < s.l[-2]
        if not outside:
            return None
        if s.c[-1] > s.h[-2] and s.c[-2] < s.c[-6]:
            return BUY, 0.58, "Bullish outside reversal", _f(s.c[-1])
        if s.c[-1] < s.l[-2] and s.c[-2] > s.c[-6]:
            return SELL, 0.58, "Bearish outside reversal", _f(s.c[-1])
        return None


class WideRangeBar(RuleStrategy):
    key = "wide_range_bar"
    name = "Wide Range Bar Continuation"
    category = "momentum"
    description = "Range > 2xATR closing in its top/bottom 20% with the 50 EMA."
    indicator = "WRB"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        a, e = s.atr(14)[-2], s.ema(50)[-1]
        rng = s.h[-1] - s.l[-1]
        if not _ok(a, e) or rng < 2 * a:
            return None
        pos = (s.c[-1] - s.l[-1]) / rng
        if pos > 0.8 and s.c[-1] > e:
            return BUY, 0.57, "Wide range bar closing at its high", _f(rng)
        if pos < 0.2 and s.c[-1] < e:
            return SELL, 0.57, "Wide range bar closing at its low", _f(rng)
        return None


class MarketStructureBos(RuleStrategy):
    key = "market_structure_bos"
    name = "Market Structure Break"
    category = "structure"
    description = "Higher low then close above the last swing high (BOS) - and mirror."
    indicator = "BOS"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        hs = pivots(s.h, 3, high=True)
        ls = pivots(s.l, 3, high=False)
        if len(hs) < 2 or len(ls) < 2:
            return None
        last_h, last_l = s.h[hs[-1]], s.l[ls[-1]]
        if s.l[ls[-1]] > s.l[ls[-2]] and s.c[-1] > last_h >= s.c[-2]:
            return BUY, 0.6, "Bullish break of structure after higher low", _f(last_h)
        if s.h[hs[-1]] < s.h[hs[-2]] and s.c[-1] < last_l <= s.c[-2]:
            return SELL, 0.6, "Bearish break of structure after lower high", _f(last_l)
        return None


class BollingerRsiReversion(RuleStrategy):
    key = "bollinger_rsi_reversion"
    name = "Bollinger + RSI Reversion"
    category = "mean_reversion"
    description = "Close outside the band with RSI extreme, then a confirming candle."
    indicator = "BB_RSI"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        _, up, lo = _bb(s)
        r = s.rsi(14)
        if not _ok(lo[-2], r[-2]):
            return None
        if s.c[-2] < lo[-2] and r[-2] < 30 and s.bull() and s.c[-1] > s.h[-2]:
            return BUY, 0.6, "Oversold band close confirmed", _f(r[-2])
        if s.c[-2] > up[-2] and r[-2] > 70 and s.bear() and s.c[-1] < s.l[-2]:
            return SELL, 0.6, "Overbought band close confirmed", _f(r[-2])
        return None


class HigherTimeframeTrendPullback(RuleStrategy):
    key = "htf_trend_pullback"
    name = "Trend Pullback (RSI 40/60)"
    category = "trend"
    description = (
        "EMA50>EMA200 trend; RSI dips under 40 and recovers (mirror for sells)."
    )
    indicator = "EMA200_RSI"
    warmup = 210

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        e50, e200, r = s.ema(50), s.ema(200), s.rsi(14)
        if not _ok(e50[-1], e200[-1]):
            return None
        recent = r[-6:-1]
        if e50[-1] > e200[-1] and min(recent) < 40 and cross_up(r, 45.0):
            return BUY, 0.6, "Uptrend pullback recovering", _f(r[-1])
        if e50[-1] < e200[-1] and max(recent) > 60 and cross_dn(r, 55.0):
            return SELL, 0.6, "Downtrend rally failing", _f(r[-1])
        return None


class MomentumIgnition(RuleStrategy):
    key = "momentum_ignition"
    name = "Momentum Ignition"
    category = "momentum"
    description = "Three expanding candles in one direction breaking a 20-bar extreme."
    indicator = "IGNITION"

    def rule(self, s: S, _p: dict[str, Any]) -> Out:
        bodies = [s.body(i) for i in (-3, -2, -1)]
        if not (bodies[0] < bodies[1] < bodies[2]):
            return None
        if all(s.bull(i) for i in (-3, -2, -1)) and s.c[-1] > max(s.h[-23:-3]):
            return (
                BUY,
                0.56,
                "Expanding bullish candles broke the 20-bar high",
                _f(s.c[-1]),
            )
        if all(s.bear(i) for i in (-3, -2, -1)) and s.c[-1] < min(s.l[-23:-3]):
            return (
                SELL,
                0.56,
                "Expanding bearish candles broke the 20-bar low",
                _f(s.c[-1]),
            )
        return None


EXTENDED_PLUGINS: tuple[type[RuleStrategy], ...] = (
    MacdZeroCross,
    MacdHistogramReversal,
    PpoSignalCross,
    TrixSignalCross,
    KstSignalCross,
    RocZeroCross,
    ChandeMomentum,
    UltimateOscillator,
    StochRsiCross,
    ConnorsRsi2,
    RsiDivergence,
    MacdDivergence,
    MoneyFlowIndex,
    ChaikinMoneyFlow,
    ElderForceIndex,
    ElderImpulse,
    ElderRay,
    VortexCross,
    ParabolicSarFlip,
    ChandelierExitFlip,
    DmiCross,
    KamaCross,
    DemaCross,
    TemaTurn,
    ZlemaCross,
    McGinleyDynamic,
    EmaRibbon,
    GoldenDeathCross,
    EmaPullback,
    VwmaCross,
    AtrEnvelopeReversion,
    AtrChannelBreakout,
    Turtle55,
    DonchianMidline,
    PercentBReversal,
    BollingerBandWalk,
    TtmSqueeze,
    LinRegChannelReversion,
    RelativeVigorIndex,
    CoppockCurve,
    FisherTransform,
    SchaffTrendCycle,
    MassIndexReversal,
    WilliamsVixFix,
    ChoppinessBreakout,
    LondonOpeningRange,
    AsianRangeFade,
    NewYorkOpenMomentum,
    PivotPointBounce,
    CamarillaBreakout,
    FibonacciPullback,
    DoubleTopBottom,
    MorningEveningStar,
    ThreeSoldiersCrows,
    HaramiReversal,
    TweezerReversal,
    MarubozuMomentum,
    DojiBandReversal,
    OutsideBarReversal,
    WideRangeBar,
    MarketStructureBos,
    BollingerRsiReversion,
    HigherTimeframeTrendPullback,
    MomentumIgnition,
)


def extended_plugins() -> list[RuleStrategy]:
    return [cls() for cls in EXTENDED_PLUGINS]
