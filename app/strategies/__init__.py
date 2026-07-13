"""Deterministic strategy plugins — intentions only, no execution."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from app.domain.indicators import (
    bollinger,
    ema,
    highest,
    lowest,
    macd,
    momentum,
    rsi,
    sma,
)
from app.domain.interfaces.strategy_engine import (
    EngineSignalAction,
    SignalExplanation,
    StrategyIntention,
    StrategyPort,
    StrategySnapshot,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _closes(snapshot: StrategySnapshot) -> list[float]:
    return [b.close for b in snapshot.bars]


def _param(params: dict[str, Any], key: str, default: Any) -> Any:
    return params.get(key, default)


def _ctx(snapshot: StrategySnapshot) -> str:
    return f"session={snapshot.session}; state={snapshot.market_state}"


def _hold(
    key: str,
    snapshot: StrategySnapshot,
    reason: str,
    indicator: str,
    threshold: str,
    value: str = "",
) -> StrategyIntention:
    return StrategyIntention(
        action=EngineSignalAction.HOLD,
        confidence=0.0,
        explanations=(
            SignalExplanation(
                reason=reason,
                indicator=indicator,
                threshold=threshold,
                market_context=_ctx(snapshot),
                value=value,
            ),
        ),
        strategy_key=key,
        symbol=snapshot.symbol,
        timeframe=snapshot.timeframe,
        timestamp=_now(),
    )


class TrendFollowingStrategy:
    key: ClassVar[str] = "trend_following"
    name: ClassVar[str] = "Trend Following"
    category: ClassVar[str] = "trend"
    description: ClassVar[str] = "Follow EMA slope direction using close prices only."
    default_params: ClassVar[dict[str, Any]] = {"ema_period": 50}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        period = int(_param(params, "ema_period", 50))
        if period < 2:
            return False, ("ema_period must be >= 2",)
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "ema_period", 50))
        series = _closes(snapshot)
        if len(series) < period + 2:
            return _hold(
                self.key,
                snapshot,
                "Insufficient bars for EMA trend",
                "EMA",
                f"need>={period + 2}",
                value=str(len(series)),
            )
        line = ema(series, period)
        a, b = line[-2], line[-1]
        if a is None or b is None:
            return _hold(self.key, snapshot, "EMA not ready", "EMA", str(period))
        if b > a and series[-1] > b:
            action = EngineSignalAction.BUY
            reason = "Close above rising EMA"
            conf = min(0.85, 0.55 + (b - a) / max(abs(a), 1e-9) * 10)
        elif b < a and series[-1] < b:
            action = EngineSignalAction.SELL
            reason = "Close below falling EMA"
            conf = min(0.85, 0.55 + (a - b) / max(abs(a), 1e-9) * 10)
        else:
            return _hold(
                self.key,
                snapshot,
                "Price not aligned with EMA slope",
                "EMA",
                str(period),
                value=f"ema={b:.5f}; close={series[-1]:.5f}",
            )
        return StrategyIntention(
            action=action,
            confidence=round(conf, 3),
            explanations=(
                SignalExplanation(
                    reason=reason,
                    indicator="EMA",
                    threshold=str(period),
                    market_context=_ctx(snapshot),
                    value=f"ema={b:.5f}; prev={a:.5f}; close={series[-1]:.5f}",
                ),
            ),
            strategy_key=self.key,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            timestamp=_now(),
        )


class MovingAverageCrossStrategy:
    key: ClassVar[str] = "ma_cross"
    name: ClassVar[str] = "Moving Average Cross"
    category: ClassVar[str] = "trend"
    description: ClassVar[str] = "SMA fast/slow crossover."
    default_params: ClassVar[dict[str, Any]] = {"fast": 10, "slow": 30}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        fast = int(_param(params, "fast", 10))
        slow = int(_param(params, "slow", 30))
        errs = []
        if fast < 2:
            errs.append("fast must be >= 2")
        if slow <= fast:
            errs.append("slow must be > fast")
        return (len(errs) == 0, tuple(errs))

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        fast_p = int(_param(snapshot.params, "fast", 10))
        slow_p = int(_param(snapshot.params, "slow", 30))
        series = _closes(snapshot)
        if len(series) < slow_p + 2:
            return _hold(
                self.key,
                snapshot,
                "Insufficient bars for MA cross",
                "SMA",
                f"need>={slow_p + 2}",
                value=str(len(series)),
            )
        fast = sma(series, fast_p)
        slow = sma(series, slow_p)
        f0, f1 = fast[-2], fast[-1]
        s0, s1 = slow[-2], slow[-1]
        if f0 is None or f1 is None or s0 is None or s1 is None:
            return _hold(
                self.key, snapshot, "SMA not ready", "SMA", f"{fast_p}/{slow_p}"
            )
        if f0 <= s0 and f1 > s1:
            action, reason = EngineSignalAction.BUY, "Fast SMA crossed above slow SMA"
            conf = 0.7
        elif f0 >= s0 and f1 < s1:
            action, reason = EngineSignalAction.SELL, "Fast SMA crossed below slow SMA"
            conf = 0.7
        else:
            return _hold(
                self.key,
                snapshot,
                "No SMA cross on latest bar",
                "SMA",
                f"{fast_p}/{slow_p}",
                value=f"fast={f1:.5f}; slow={s1:.5f}",
            )
        return StrategyIntention(
            action=action,
            confidence=conf,
            explanations=(
                SignalExplanation(
                    reason=reason,
                    indicator="SMA_CROSS",
                    threshold=f"fast={fast_p}; slow={slow_p}",
                    market_context=_ctx(snapshot),
                    value=f"fast={f1:.5f}; slow={s1:.5f}",
                ),
            ),
            strategy_key=self.key,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            timestamp=_now(),
        )


class RsiStrategy:
    key: ClassVar[str] = "rsi"
    name: ClassVar[str] = "RSI"
    category: ClassVar[str] = "momentum"
    description: ClassVar[str] = "RSI overbought/oversold thresholds."
    default_params: ClassVar[dict[str, Any]] = {
        "period": 14,
        "oversold": 30,
        "overbought": 70,
    }

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        period = int(_param(params, "period", 14))
        lo = float(_param(params, "oversold", 30))
        hi = float(_param(params, "overbought", 70))
        errs = []
        if period < 2:
            errs.append("period must be >= 2")
        if not (0 < lo < hi < 100):
            errs.append("require 0 < oversold < overbought < 100")
        return (not errs, tuple(errs))

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 14))
        lo = float(_param(snapshot.params, "oversold", 30))
        hi = float(_param(snapshot.params, "overbought", 70))
        series = _closes(snapshot)
        line = rsi(series, period)
        val = line[-1]
        if val is None:
            return _hold(
                self.key,
                snapshot,
                "RSI not ready",
                "RSI",
                f"period={period}",
                value=str(len(series)),
            )
        if val <= lo:
            action, reason, conf = EngineSignalAction.BUY, "RSI at/below oversold", 0.65
        elif val >= hi:
            action, reason, conf = (
                EngineSignalAction.SELL,
                "RSI at/above overbought",
                0.65,
            )
        else:
            return _hold(
                self.key,
                snapshot,
                "RSI between thresholds",
                "RSI",
                f"oversold={lo}; overbought={hi}",
                value=f"{val:.2f}",
            )
        return StrategyIntention(
            action=action,
            confidence=conf,
            explanations=(
                SignalExplanation(
                    reason=reason,
                    indicator="RSI",
                    threshold=f"oversold={lo}; overbought={hi}",
                    market_context=_ctx(snapshot),
                    value=f"{val:.2f}",
                ),
            ),
            strategy_key=self.key,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            timestamp=_now(),
        )


class MacdStrategy:
    key: ClassVar[str] = "macd"
    name: ClassVar[str] = "MACD"
    category: ClassVar[str] = "momentum"
    description: ClassVar[str] = "MACD line cross of signal line."
    default_params: ClassVar[dict[str, Any]] = {"fast": 12, "slow": 26, "signal": 9}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        fast = int(_param(params, "fast", 12))
        slow = int(_param(params, "slow", 26))
        sig = int(_param(params, "signal", 9))
        errs = []
        if not (2 <= fast < slow):
            errs.append("require 2 <= fast < slow")
        if sig < 2:
            errs.append("signal must be >= 2")
        return (not errs, tuple(errs))

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        fast = int(_param(snapshot.params, "fast", 12))
        slow = int(_param(snapshot.params, "slow", 26))
        sig = int(_param(snapshot.params, "signal", 9))
        series = _closes(snapshot)
        macd_line, signal_line, _hist = macd(series, fast, slow, sig)
        m0, m1 = macd_line[-2], macd_line[-1]
        s0, s1 = signal_line[-2], signal_line[-1]
        if m0 is None or m1 is None or s0 is None or s1 is None:
            return _hold(
                self.key,
                snapshot,
                "MACD not ready",
                "MACD",
                f"{fast}/{slow}/{sig}",
                value=str(len(series)),
            )
        if m0 <= s0 and m1 > s1:
            action, reason = EngineSignalAction.BUY, "MACD crossed above signal"
            conf = 0.68
        elif m0 >= s0 and m1 < s1:
            action, reason = EngineSignalAction.SELL, "MACD crossed below signal"
            conf = 0.68
        else:
            return _hold(
                self.key,
                snapshot,
                "No MACD/signal cross",
                "MACD",
                f"{fast}/{slow}/{sig}",
                value=f"macd={m1:.5f}; signal={s1:.5f}",
            )
        return StrategyIntention(
            action=action,
            confidence=conf,
            explanations=(
                SignalExplanation(
                    reason=reason,
                    indicator="MACD",
                    threshold=f"fast={fast}; slow={slow}; signal={sig}",
                    market_context=_ctx(snapshot),
                    value=f"macd={m1:.5f}; signal={s1:.5f}",
                ),
            ),
            strategy_key=self.key,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            timestamp=_now(),
        )


class BollingerStrategy:
    key: ClassVar[str] = "bollinger"
    name: ClassVar[str] = "Bollinger"
    category: ClassVar[str] = "mean_reversion"
    description: ClassVar[str] = "Mean reversion at Bollinger band extremes."
    default_params: ClassVar[dict[str, Any]] = {"period": 20, "num_std": 2.0}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        period = int(_param(params, "period", 20))
        num_std = float(_param(params, "num_std", 2.0))
        errs = []
        if period < 5:
            errs.append("period must be >= 5")
        if num_std <= 0:
            errs.append("num_std must be > 0")
        return (not errs, tuple(errs))

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 20))
        num_std = float(_param(snapshot.params, "num_std", 2.0))
        series = _closes(snapshot)
        upper, mid, lower = bollinger(series, period, num_std)
        u, m, lo, c = upper[-1], mid[-1], lower[-1], series[-1]
        if u is None or m is None or lo is None:
            return _hold(
                self.key,
                snapshot,
                "Bollinger not ready",
                "BOLLINGER",
                f"period={period}; std={num_std}",
                value=str(len(series)),
            )
        if c <= float(lo):
            action, reason = EngineSignalAction.BUY, "Close at/below lower band"
            conf = 0.62
        elif c >= float(u):
            action, reason = EngineSignalAction.SELL, "Close at/above upper band"
            conf = 0.62
        else:
            return _hold(
                self.key,
                snapshot,
                "Close inside Bollinger bands",
                "BOLLINGER",
                f"period={period}; std={num_std}",
                value=f"close={c:.5f}; mid={float(m):.5f}",
            )
        return StrategyIntention(
            action=action,
            confidence=conf,
            explanations=(
                SignalExplanation(
                    reason=reason,
                    indicator="BOLLINGER",
                    threshold=f"period={period}; std={num_std}",
                    market_context=_ctx(snapshot),
                    value=f"close={c:.5f}; upper={float(u):.5f}; lower={float(lo):.5f}",
                ),
            ),
            strategy_key=self.key,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            timestamp=_now(),
        )


class BreakoutStrategy:
    key: ClassVar[str] = "breakout"
    name: ClassVar[str] = "Breakout"
    category: ClassVar[str] = "breakout"
    description: ClassVar[str] = "Close breaks N-bar high/low."
    default_params: ClassVar[dict[str, Any]] = {"lookback": 20}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        lookback = int(_param(params, "lookback", 20))
        if lookback < 2:
            return False, ("lookback must be >= 2",)
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        lookback = int(_param(snapshot.params, "lookback", 20))
        highs = [b.high for b in snapshot.bars]
        lows = [b.low for b in snapshot.bars]
        closes = _closes(snapshot)
        if len(closes) < lookback + 1:
            return _hold(
                self.key,
                snapshot,
                "Insufficient bars for breakout",
                "DONCHIAN",
                f"lookback={lookback}",
                value=str(len(closes)),
            )
        # Exclude current bar from range
        hh = highest(highs[:-1], lookback)[-1]
        ll = lowest(lows[:-1], lookback)[-1]
        c = closes[-1]
        if hh is None or ll is None:
            return _hold(
                self.key, snapshot, "Range not ready", "DONCHIAN", str(lookback)
            )
        if c > hh:
            action, reason = EngineSignalAction.BUY, "Close broke N-bar high"
            conf = 0.72
            thr = f"high={hh:.5f}"
        elif c < ll:
            action, reason = EngineSignalAction.SELL, "Close broke N-bar low"
            conf = 0.72
            thr = f"low={ll:.5f}"
        else:
            return _hold(
                self.key,
                snapshot,
                "No breakout vs prior range",
                "DONCHIAN",
                f"lookback={lookback}",
                value=f"close={c:.5f}; high={hh:.5f}; low={ll:.5f}",
            )
        return StrategyIntention(
            action=action,
            confidence=conf,
            explanations=(
                SignalExplanation(
                    reason=reason,
                    indicator="DONCHIAN",
                    threshold=f"lookback={lookback}; {thr}",
                    market_context=_ctx(snapshot),
                    value=f"close={c:.5f}",
                ),
            ),
            strategy_key=self.key,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            timestamp=_now(),
        )


class MomentumStrategy:
    key: ClassVar[str] = "momentum"
    name: ClassVar[str] = "Momentum"
    category: ClassVar[str] = "momentum"
    description: ClassVar[str] = "Rate-of-change momentum threshold."
    default_params: ClassVar[dict[str, Any]] = {"lookback": 10, "threshold_pct": 0.5}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        lookback = int(_param(params, "lookback", 10))
        if lookback < 1:
            return False, ("lookback must be >= 1",)
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        lookback = int(_param(snapshot.params, "lookback", 10))
        thr = float(_param(snapshot.params, "threshold_pct", 0.5))
        series = _closes(snapshot)
        mom = momentum(series, lookback)
        val = mom[-1]
        if val is None:
            return _hold(
                self.key,
                snapshot,
                "Momentum not ready",
                "ROC",
                f"lookback={lookback}",
                value=str(len(series)),
            )
        if val >= thr:
            action, reason = EngineSignalAction.BUY, "Momentum above threshold"
            conf = min(0.8, 0.5 + abs(val) / 100)
        elif val <= -thr:
            action, reason = EngineSignalAction.SELL, "Momentum below -threshold"
            conf = min(0.8, 0.5 + abs(val) / 100)
        else:
            return _hold(
                self.key,
                snapshot,
                "Momentum inside deadband",
                "ROC",
                f"±{thr}%",
                value=f"{val:.3f}%",
            )
        return StrategyIntention(
            action=action,
            confidence=round(conf, 3),
            explanations=(
                SignalExplanation(
                    reason=reason,
                    indicator="ROC",
                    threshold=f"lookback={lookback}; threshold_pct={thr}",
                    market_context=_ctx(snapshot),
                    value=f"{val:.3f}%",
                ),
            ),
            strategy_key=self.key,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            timestamp=_now(),
        )


class MeanReversionStrategy:
    key: ClassVar[str] = "mean_reversion"
    name: ClassVar[str] = "Mean Reversion"
    category: ClassVar[str] = "mean_reversion"
    description: ClassVar[str] = "Revert toward SMA when deviation exceeds threshold."
    default_params: ClassVar[dict[str, Any]] = {"period": 20, "deviation_pct": 1.0}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        period = int(_param(params, "period", 20))
        if period < 2:
            return False, ("period must be >= 2",)
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 20))
        deviation = float(_param(snapshot.params, "deviation_pct", 1.0))
        series = _closes(snapshot)
        line = sma(series, period)
        m = line[-1]
        c = series[-1]
        if m is None or m == 0:
            return _hold(
                self.key,
                snapshot,
                "SMA not ready",
                "SMA",
                f"period={period}",
                value=str(len(series)),
            )
        pct = (c / m - 1.0) * 100.0
        if pct <= -deviation:
            action, reason = EngineSignalAction.BUY, "Close below SMA by threshold"
            conf = 0.6
        elif pct >= deviation:
            action, reason = EngineSignalAction.SELL, "Close above SMA by threshold"
            conf = 0.6
        else:
            return _hold(
                self.key,
                snapshot,
                "Close near SMA",
                "SMA",
                f"deviation_pct=±{deviation}",
                value=f"pct={pct:.3f}; sma={m:.5f}",
            )
        return StrategyIntention(
            action=action,
            confidence=conf,
            explanations=(
                SignalExplanation(
                    reason=reason,
                    indicator="SMA_DEV",
                    threshold=f"period={period}; deviation_pct={deviation}",
                    market_context=_ctx(snapshot),
                    value=f"pct={pct:.3f}; close={c:.5f}; sma={m:.5f}",
                ),
            ),
            strategy_key=self.key,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            timestamp=_now(),
        )


class CustomRulesStrategy:
    """Evaluate a simple rule tree from params — no invented market facts."""

    key: ClassVar[str] = "custom_rules"
    name: ClassVar[str] = "Custom Rules"
    category: ClassVar[str] = "custom"
    description: ClassVar[str] = (
        "Rule tree over closes/SMA/RSI with explicit conditions."
    )
    default_params: ClassVar[dict[str, Any]] = {
        "rules": [
            {
                "when": {"indicator": "rsi", "op": "<=", "value": 30},
                "action": "BUY",
                "reason": "Custom RSI oversold rule",
            },
            {
                "when": {"indicator": "rsi", "op": ">=", "value": 70},
                "action": "SELL",
                "reason": "Custom RSI overbought rule",
            },
        ],
        "rsi_period": 14,
        "sma_period": 20,
    }

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        rules = _param(params, "rules", [])
        if not isinstance(rules, list) or not rules:
            return False, ("rules must be a non-empty list",)
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict) or "when" not in rule or "action" not in rule:
                return False, (f"rules[{i}] requires when/action",)
            action = str(rule.get("action", "")).upper()
            if action not in {"BUY", "SELL", "EXIT", "HOLD"}:
                return False, (f"rules[{i}].action invalid",)
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        rules = list(_param(snapshot.params, "rules", self.default_params["rules"]))
        series = _closes(snapshot)
        rsi_p = int(_param(snapshot.params, "rsi_period", 14))
        sma_p = int(_param(snapshot.params, "sma_period", 20))
        rsi_line = rsi(series, rsi_p)
        sma_line = sma(series, sma_p)
        ctx = {
            "close": series[-1] if series else None,
            "rsi": rsi_line[-1] if rsi_line else None,
            "sma": sma_line[-1] if sma_line else None,
        }
        for rule in rules:
            when = rule.get("when") or {}
            indicator = str(when.get("indicator", "")).lower()
            op = str(when.get("op", ""))
            target = float(when.get("value", 0))
            left = ctx.get(indicator)
            if left is None:
                continue
            ok = (
                (op == "<=" and float(left) <= target)
                or (op == ">=" and float(left) >= target)
                or (op == "<" and float(left) < target)
                or (op == ">" and float(left) > target)
                or (op == "==" and float(left) == target)
            )
            if not ok:
                continue
            action = EngineSignalAction(str(rule.get("action", "HOLD")).upper())
            reason = str(rule.get("reason") or f"Custom rule matched on {indicator}")
            return StrategyIntention(
                action=action,
                confidence=0.55,
                explanations=(
                    SignalExplanation(
                        reason=reason,
                        indicator=indicator.upper(),
                        threshold=f"{op}{target}",
                        market_context=_ctx(snapshot),
                        value=str(left),
                    ),
                ),
                strategy_key=self.key,
                symbol=snapshot.symbol,
                timeframe=snapshot.timeframe,
                timestamp=_now(),
                metadata={"matched_rule": rule},
            )
        return _hold(
            self.key,
            snapshot,
            "No custom rule matched",
            "RULE_TREE",
            "n/a",
            value=str({k: v for k, v in ctx.items() if v is not None}),
        )


def default_strategy_plugins() -> list[StrategyPort]:
    return [
        TrendFollowingStrategy(),
        MovingAverageCrossStrategy(),
        RsiStrategy(),
        MacdStrategy(),
        BollingerStrategy(),
        BreakoutStrategy(),
        MomentumStrategy(),
        MeanReversionStrategy(),
        CustomRulesStrategy(),
    ]
