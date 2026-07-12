"""Backtest Metrics Engine — performance statistics from simulated results.

Offline only. Never connects to a live broker.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import sqrt

from app.domain.entities.backtest import (
    BacktestMetrics,
    EquityPoint,
    SimulatedTrade,
)
from app.domain.enums.backtest import SimulatedTradeStatus


@dataclass(frozen=True, slots=True)
class MetricsEngine:
    """Calculate backtest performance metrics from trades and equity curve."""

    risk_free_rate: Decimal = Decimal("0")  # annualized, decimal form (0.02 = 2%)
    periods_per_year: Decimal = Decimal("252")

    def compute(
        self,
        *,
        trades: list[SimulatedTrade],
        equity_curve: list[EquityPoint],
        initial_balance: Decimal,
    ) -> BacktestMetrics:
        closed = [t for t in trades if t.status is SimulatedTradeStatus.CLOSED]
        trade_count = len(closed)
        wins = [t for t in closed if t.pnl > 0]
        losses = [t for t in closed if t.pnl < 0]
        win_count = len(wins)
        loss_count = len(losses)

        final_equity = equity_curve[-1].equity if equity_curve else initial_balance
        total_return = (
            (final_equity - initial_balance) / initial_balance * Decimal("100")
            if initial_balance > 0
            else Decimal("0")
        )

        max_dd = Decimal("0")
        for point in equity_curve:
            if point.drawdown_pct > max_dd:
                max_dd = point.drawdown_pct

        gross_profit = sum((t.pnl for t in wins), Decimal("0"))
        gross_loss = abs(sum((t.pnl for t in losses), Decimal("0")))
        profit_factor: Decimal | None
        if gross_loss > 0:
            profit_factor = (gross_profit / gross_loss).quantize(Decimal("0.0001"))
        elif gross_profit > 0:
            profit_factor = Decimal("999")
        else:
            profit_factor = None

        expectancy = (
            (sum((t.pnl for t in closed), Decimal("0")) / Decimal(trade_count))
            if trade_count
            else Decimal("0")
        )
        win_rate = (
            (Decimal(win_count) / Decimal(trade_count) * Decimal("100"))
            if trade_count
            else Decimal("0")
        )

        average_r = self._average_r(closed)
        sharpe = self._sharpe(equity_curve, initial_balance)
        sortino = self._sortino(equity_curve, initial_balance)
        cagr = self._cagr(equity_curve, initial_balance, final_equity)
        recovery: Decimal | None = None
        if max_dd > 0:
            net = final_equity - initial_balance
            recovery = (net / (initial_balance * max_dd / Decimal("100"))).quantize(
                Decimal("0.0001")
            )

        return BacktestMetrics(
            total_return_pct=total_return.quantize(Decimal("0.0001")),
            cagr_pct=cagr,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            profit_factor=profit_factor,
            expectancy=expectancy.quantize(Decimal("0.0001")),
            win_rate=win_rate.quantize(Decimal("0.0001")),
            average_r=average_r,
            max_drawdown_pct=max_dd.quantize(Decimal("0.0001")),
            recovery_factor=recovery,
            trade_count=trade_count,
            win_count=win_count,
            loss_count=loss_count,
        )

    def _average_r(self, closed: list[SimulatedTrade]) -> Decimal | None:
        rs: list[Decimal] = []
        for trade in closed:
            if trade.stop_loss is None:
                continue
            risk = abs(trade.entry_price - trade.stop_loss)
            if risk <= 0:
                continue
            direction = Decimal("1") if trade.side.value == "buy" else Decimal("-1")
            move = (trade.exit_price or trade.entry_price) - trade.entry_price
            rs.append((move * direction) / risk)
        if not rs:
            return None
        return (sum(rs, Decimal("0")) / Decimal(len(rs))).quantize(Decimal("0.0001"))

    def _period_returns(
        self, equity_curve: list[EquityPoint], initial: Decimal
    ) -> list[float]:
        if len(equity_curve) < 2:
            return []
        returns: list[float] = []
        prev = float(initial)
        for point in equity_curve:
            eq = float(point.equity)
            if prev > 0:
                returns.append((eq - prev) / prev)
            prev = eq
        return returns

    def _sharpe(
        self, equity_curve: list[EquityPoint], initial: Decimal
    ) -> Decimal | None:
        rets = self._period_returns(equity_curve, initial)
        if len(rets) < 2:
            return None
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        std = sqrt(var) if var > 0 else 0.0
        if std == 0.0:
            return None
        rf_period = float(self.risk_free_rate) / float(self.periods_per_year)
        sharpe = (mean - rf_period) / std * sqrt(float(self.periods_per_year))
        return Decimal(str(round(sharpe, 4)))

    def _sortino(
        self, equity_curve: list[EquityPoint], initial: Decimal
    ) -> Decimal | None:
        rets = self._period_returns(equity_curve, initial)
        if len(rets) < 2:
            return None
        mean = sum(rets) / len(rets)
        downside = [r for r in rets if r < 0]
        if not downside:
            return Decimal("999") if mean > 0 else None
        dvar = sum(r**2 for r in downside) / len(downside)
        dstd = sqrt(dvar) if dvar > 0 else 0.0
        if dstd == 0.0:
            return None
        rf_period = float(self.risk_free_rate) / float(self.periods_per_year)
        sortino = (mean - rf_period) / dstd * sqrt(float(self.periods_per_year))
        return Decimal(str(round(sortino, 4)))

    def _cagr(
        self,
        equity_curve: list[EquityPoint],
        initial: Decimal,
        final: Decimal,
    ) -> Decimal | None:
        if len(equity_curve) < 2 or initial <= 0 or final <= 0:
            return None
        start = equity_curve[0].timestamp
        end = equity_curve[-1].timestamp
        days = max((end - start).total_seconds() / 86400.0, 1.0)
        years = days / 365.25
        if years <= 0:
            return None
        ratio = float(final / initial)
        if ratio <= 0:
            return None
        cagr = (ratio ** (1.0 / years) - 1.0) * 100.0
        return Decimal(str(round(cagr, 4)))
