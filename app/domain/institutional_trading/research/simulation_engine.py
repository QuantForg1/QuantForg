"""Simulation Engine — candle replay using same institutional decision/manage path.

Uses SimulationOmsPort only. Never MT5 order_send. Never modifies A–D/OMS.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import uuid4

from app.domain.institutional_trading.research.analytics import ResearchAnalyticsEngine
from app.domain.institutional_trading.research.config import (
    DEFAULT_RESEARCH_CONFIG,
    ResearchConfig,
)
from app.domain.institutional_trading.research.models import (
    EquityPoint,
    ResearchBar,
    ResearchTrade,
    SimulationResult,
)
from app.domain.institutional_trading.research.simulation_port import (
    SimulationBook,
    SimulationOmsPort,
)


@dataclass(frozen=True, slots=True)
class SimSignal:
    """Deterministic entry signal emitted by a strategy adapter / test provider."""

    action: str  # BUY | SELL | NONE
    volume: Decimal
    stop_distance: Decimal
    take_distance: Decimal | None = None
    confidence: int = 0
    quality: int = 0
    risk_score: int = 0
    reasons: tuple[str, ...] = ()
    confluence: dict[str, object] = field(default_factory=dict)


class SignalProvider(Protocol):
    def signal(self, bars: list[ResearchBar], index: int) -> SimSignal: ...


@dataclass
class SimulationEngine:
    """Replay bars candle-by-candle; fill at next bar open; manage SL/TP locally."""

    config: ResearchConfig = field(default_factory=lambda: DEFAULT_RESEARCH_CONFIG)
    analytics: ResearchAnalyticsEngine = field(default_factory=ResearchAnalyticsEngine)
    signal_provider: SignalProvider | None = None

    def run(
        self,
        bars: list[ResearchBar],
        *,
        signal_provider: SignalProvider | None = None,
        git_commit: str | None = None,
    ) -> SimulationResult:
        provider = signal_provider or self.signal_provider
        if provider is None:
            raise ValueError("signal_provider required")
        if not bars:
            return self._empty_result(git_commit=git_commit)

        book = SimulationBook()
        oms = SimulationOmsPort(
            book=book,
            spread=self.config.default_spread,
            slippage=self.config.default_slippage,
        )
        balance = self.config.initial_balance
        equity = balance
        peak = balance
        trades: list[ResearchTrade] = []
        open_trade: ResearchTrade | None = None
        curve: list[EquityPoint] = []
        pending_signal: SimSignal | None = None

        for i, bar in enumerate(bars):
            # Fill queued entries at this bar's open
            oms.set_bar_open(bar.open)
            if open_trade is None and book.positions:
                ticket, pos = next(iter(book.positions.items()))
                open_trade = ResearchTrade(
                    trade_id=f"sim-{ticket}",
                    symbol=pos["symbol"],
                    side=pos["side"],
                    entry_time=bar.time,
                    entry_price=Decimal(str(pos["open_price"])),
                    volume=Decimal(str(pos["volume"])),
                    stop_loss=Decimal(str(pos["stop_loss"] or 0)),
                    take_profit=(
                        Decimal(str(pos["take_profit"]))
                        if pos.get("take_profit")
                        else None
                    ),
                    session=bar.session,
                    confidence=pending_signal.confidence if pending_signal else 0,
                    quality=pending_signal.quality if pending_signal else 0,
                    risk_score=pending_signal.risk_score if pending_signal else 0,
                    decision_reasons=(
                        pending_signal.reasons if pending_signal else ()
                    ),
                    confluence=dict(pending_signal.confluence) if pending_signal else {},
                )
                open_trade.events.append(
                    {
                        "type": "entry",
                        "time": bar.time.isoformat(),
                        "price": str(open_trade.entry_price),
                    }
                )
                pending_signal = None

            # Manage open trade on this bar (SL/TP / MAE/MFE)
            if open_trade is not None and open_trade.status == "open":
                open_trade = self._update_excursions(open_trade, bar)
                exited = self._check_exit(open_trade, bar)
                if exited is not None:
                    open_trade = exited
                    balance += open_trade.pnl
                    trades.append(open_trade)
                    # clear sim book
                    book.positions.clear()
                    open_trade = None

            # Emit new signal only when flat (decision path)
            if open_trade is None and not book.pending_entry and not book.positions:
                sig = provider.signal(bars, i)
                if sig.action in {"BUY", "SELL"} and i + 1 < len(bars):
                    pending_signal = sig
                    side = "buy" if sig.action == "BUY" else "sell"
                    # stop relative to close (geometry); fill at next open
                    entry_ref = bar.close
                    if side == "buy":
                        sl = entry_ref - sig.stop_distance
                        tp = (
                            entry_ref + sig.take_distance
                            if sig.take_distance
                            else None
                        )
                    else:
                        sl = entry_ref + sig.stop_distance
                        tp = (
                            entry_ref - sig.take_distance
                            if sig.take_distance
                            else None
                        )
                    from app.application.services.institutional_execution_engine import (
                        parse_order_intent,
                    )

                    intent = parse_order_intent(
                        symbol=self.config.symbol,
                        side=side,
                        order_type="market",
                        volume=str(sig.volume),
                        stop_loss=str(sl),
                        take_profit=str(tp) if tp else None,
                        comment=f"ite:sim:{i}",
                        magic=260720,
                    )
                    oms.next_open = None  # force queue until next bar
                    oms.submit_market(
                        user_id=uuid4(),
                        request_id=f"sim-{i}",
                        intent=intent,
                        connected=True,
                        login=None,
                    )

            # Mark-to-market equity
            equity = balance
            if open_trade is not None and open_trade.status == "open":
                equity += self._unrealized(open_trade, bar.close)
            peak = max(peak, equity)
            dd = (
                ((peak - equity) / peak * Decimal("100"))
                if peak > 0 and equity < peak
                else Decimal("0")
            )
            curve.append(
                EquityPoint(time=bar.time, equity=equity, drawdown_pct=dd)
            )

        # Force-close remnant at last close
        if open_trade is not None and open_trade.status == "open":
            last = bars[-1]
            open_trade = self._force_close(open_trade, last)
            balance += open_trade.pnl
            trades.append(open_trade)
            equity = balance
            peak = max(peak, equity)
            dd = (
                ((peak - equity) / peak * Decimal("100"))
                if peak > 0 and equity < peak
                else Decimal("0")
            )
            curve.append(
                EquityPoint(time=last.time, equity=equity, drawdown_pct=dd)
            )

        report = self.analytics.compute(
            trades=trades,
            equity_curve=curve,
            initial_balance=self.config.initial_balance,
        )
        input_hash = self._hash_bars(bars)
        commit = git_commit if git_commit is not None else _detect_git_commit()
        return SimulationResult(
            run_id=uuid4(),
            trades=tuple(trades),
            equity_curve=tuple(curve),
            analytics=report,
            input_hash=input_hash,
            strategy_version=self.config.strategy_version,
            config_version=self.config.config_version,
            git_commit=commit,
            bars_processed=len(bars),
            deterministic=True,
        )

    def _empty_result(self, *, git_commit: str | None) -> SimulationResult:
        report = self.analytics.compute(
            trades=[],
            equity_curve=[],
            initial_balance=self.config.initial_balance,
        )
        return SimulationResult(
            run_id=uuid4(),
            trades=(),
            equity_curve=(),
            analytics=report,
            input_hash="",
            strategy_version=self.config.strategy_version,
            config_version=self.config.config_version,
            git_commit=git_commit,
            bars_processed=0,
        )

    @staticmethod
    def _hash_bars(bars: list[ResearchBar]) -> str:
        payload = [
            {
                "t": b.time.isoformat(),
                "o": str(b.open),
                "h": str(b.high),
                "l": str(b.low),
                "c": str(b.close),
            }
            for b in bars
        ]
        raw = json.dumps(payload, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _unrealized(trade: ResearchTrade, price: Decimal) -> Decimal:
        # Simplified XAU PnL: (price diff) * volume * 100
        direction = Decimal("1") if trade.side == "buy" else Decimal("-1")
        return (price - trade.entry_price) * direction * trade.volume * Decimal("100")

    def _update_excursions(
        self, trade: ResearchTrade, bar: ResearchBar
    ) -> ResearchTrade:
        if trade.side == "buy":
            adverse = trade.entry_price - bar.low
            favor = bar.high - trade.entry_price
        else:
            adverse = bar.high - trade.entry_price
            favor = trade.entry_price - bar.low
        trade.mae = max(trade.mae, max(adverse, Decimal("0")))
        trade.mfe = max(trade.mfe, max(favor, Decimal("0")))
        return trade

    def _check_exit(
        self, trade: ResearchTrade, bar: ResearchBar
    ) -> ResearchTrade | None:
        hit_sl = hit_tp = False
        exit_px = None
        reason = ""
        if trade.side == "buy":
            if bar.low <= trade.stop_loss:
                hit_sl, exit_px, reason = True, trade.stop_loss, "stop_loss"
            elif trade.take_profit and bar.high >= trade.take_profit:
                hit_tp, exit_px, reason = True, trade.take_profit, "take_profit"
        else:
            if bar.high >= trade.stop_loss:
                hit_sl, exit_px, reason = True, trade.stop_loss, "stop_loss"
            elif trade.take_profit and bar.low <= trade.take_profit:
                hit_tp, exit_px, reason = True, trade.take_profit, "take_profit"
        if not (hit_sl or hit_tp) or exit_px is None:
            return None
        return self._close(trade, bar.time, exit_px, reason)

    def _force_close(self, trade: ResearchTrade, bar: ResearchBar) -> ResearchTrade:
        return self._close(trade, bar.time, bar.close, "end_of_data")

    def _close(
        self,
        trade: ResearchTrade,
        when: datetime,
        price: Decimal,
        reason: str,
    ) -> ResearchTrade:
        trade.exit_time = when
        trade.exit_price = price
        trade.exit_reason = reason
        trade.status = "closed"
        trade.pnl = self._unrealized(trade, price)
        risk = abs(trade.entry_price - trade.stop_loss)
        if risk > 0:
            direction = Decimal("1") if trade.side == "buy" else Decimal("-1")
            move = (price - trade.entry_price) * direction
            trade.r_multiple = (move / risk).quantize(Decimal("0.0001"))
        trade.events.append(
            {
                "type": "exit",
                "time": when.isoformat(),
                "price": str(price),
                "reason": reason,
            }
        )
        return trade


def _detect_git_commit() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        return out.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


@dataclass
class RuleSignalProvider:
    """Simple deterministic long/short provider for tests & baselines."""

    lookback: int = 3
    volume: Decimal = Decimal("0.10")
    stop_distance: Decimal = Decimal("10")
    take_distance: Decimal = Decimal("20")

    def signal(self, bars: list[ResearchBar], index: int) -> SimSignal:
        if index < self.lookback:
            return SimSignal(action="NONE", volume=Decimal("0"), stop_distance=Decimal("0"))
        window = bars[index - self.lookback : index + 1]
        if all(window[i].close < window[i + 1].close for i in range(len(window) - 1)):
            return SimSignal(
                action="BUY",
                volume=self.volume,
                stop_distance=self.stop_distance,
                take_distance=self.take_distance,
                confidence=85,
                quality=85,
                risk_score=20,
                reasons=("deterministic uptrend",),
                confluence={"rule": "up_close_streak"},
            )
        if all(window[i].close > window[i + 1].close for i in range(len(window) - 1)):
            return SimSignal(
                action="SELL",
                volume=self.volume,
                stop_distance=self.stop_distance,
                take_distance=self.take_distance,
                confidence=85,
                quality=85,
                risk_score=20,
                reasons=("deterministic downtrend",),
                confluence={"rule": "down_close_streak"},
            )
        return SimSignal(action="NONE", volume=Decimal("0"), stop_distance=Decimal("0"))
