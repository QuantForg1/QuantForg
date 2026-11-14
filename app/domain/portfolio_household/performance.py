"""Strategy performance + trade attribution from confirmed closed trades only."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def _dec(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


@dataclass(frozen=True, slots=True)
class ClosedTrade:
    trade_id: str
    symbol: str
    side: str
    pnl: Decimal
    commission: Decimal | None
    swap: Decimal | None
    opened_at: datetime | None
    closed_at: datetime | None
    hold_seconds: float | None
    strategy: str | None
    broker_code: str | None
    account_key: str | None
    signal_id: str | None
    order_ticket: int | None
    position_ticket: int | None
    session: str | None
    confirmed: bool


@dataclass(frozen=True, slots=True)
class StrategyMetrics:
    strategy: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal | None
    net_profit: Decimal
    gross_profit: Decimal
    gross_loss: Decimal
    profit_factor: Decimal | None
    average_win: Decimal | None
    average_loss: Decimal | None
    average_rr: Decimal | None
    max_drawdown: Decimal | None
    expectancy: Decimal | None
    average_holding_seconds: float | None


@dataclass(frozen=True, slots=True)
class AttributionRow:
    trade_id: str
    signal_id: str | None
    strategy: str | None
    broker_code: str | None
    account_key: str | None
    symbol: str
    order_ticket: int | None
    position_ticket: int | None
    entry_at: datetime | None
    exit_at: datetime | None
    realized_pnl: Decimal
    fees: Decimal | None
    slippage: Decimal | None
    chain_complete: bool
    missing_links: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PerformanceReport:
    trades_considered: int
    trades_excluded_unconfirmed: int
    overall: StrategyMetrics
    by_strategy: tuple[StrategyMetrics, ...]
    by_symbol: tuple[StrategyMetrics, ...]
    by_broker: tuple[StrategyMetrics, ...]
    by_session: tuple[StrategyMetrics, ...]
    attribution: tuple[AttributionRow, ...]
    methodology: dict[str, Any] = field(default_factory=dict)


def _metrics(name: str, trades: list[ClosedTrade]) -> StrategyMetrics:
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    gross_profit = sum((t.pnl for t in wins), Decimal("0"))
    gross_loss = abs(sum((t.pnl for t in losses), Decimal("0")))
    net = sum((t.pnl for t in trades), Decimal("0"))
    win_rate = (
        (Decimal(len(wins)) / Decimal(len(trades))) * Decimal("100") if trades else None
    )
    pf = (gross_profit / gross_loss) if gross_loss > 0 else None
    avg_win = (gross_profit / Decimal(len(wins))) if wins else None
    avg_loss = (gross_loss / Decimal(len(losses))) if losses else None
    avg_rr = None
    if avg_win is not None and avg_loss is not None and avg_loss > 0:
        avg_rr = avg_win / avg_loss
    expectancy = (net / Decimal(len(trades))) if trades else None

    # Max drawdown on cumulative PnL curve
    peak = Decimal("0")
    equity = Decimal("0")
    max_dd = Decimal("0")
    for t in sorted(trades, key=lambda x: x.closed_at or datetime.min):
        equity += t.pnl
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    holds = [t.hold_seconds for t in trades if t.hold_seconds is not None]
    avg_hold = (sum(holds) / len(holds)) if holds else None

    return StrategyMetrics(
        strategy=name,
        total_trades=len(trades),
        winning_trades=len(wins),
        losing_trades=len(losses),
        win_rate=win_rate,
        net_profit=net,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=pf,
        average_win=avg_win,
        average_loss=avg_loss,
        average_rr=avg_rr,
        max_drawdown=max_dd if trades else None,
        expectancy=expectancy,
        average_holding_seconds=avg_hold,
    )


def _group(
    trades: list[ClosedTrade],
    key_fn: Callable[[ClosedTrade], str | None],
) -> tuple[StrategyMetrics, ...]:
    buckets: dict[str, list[ClosedTrade]] = {}
    for t in trades:
        buckets.setdefault(key_fn(t) or "unspecified", []).append(t)
    return tuple(_metrics(k, v) for k, v in sorted(buckets.items()))


def build_performance_report(
    trades: list[ClosedTrade],
    *,
    require_confirmed: bool = True,
) -> PerformanceReport:
    excluded = 0
    considered: list[ClosedTrade] = []
    for t in trades:
        if require_confirmed and not t.confirmed:
            excluded += 1
            continue
        considered.append(t)

    attribution: list[AttributionRow] = []
    for t in considered:
        missing: list[str] = []
        if not t.signal_id:
            missing.append("signal")
        if not t.strategy:
            missing.append("strategy")
        if not t.broker_code:
            missing.append("broker")
        if not t.account_key:
            missing.append("account")
        if t.order_ticket is None:
            missing.append("order")
        if t.position_ticket is None:
            missing.append("position")
        fees = None
        if t.commission is not None or t.swap is not None:
            fees = (t.commission or Decimal("0")) + (t.swap or Decimal("0"))
        attribution.append(
            AttributionRow(
                trade_id=t.trade_id,
                signal_id=t.signal_id,
                strategy=t.strategy,
                broker_code=t.broker_code,
                account_key=t.account_key,
                symbol=t.symbol,
                order_ticket=t.order_ticket,
                position_ticket=t.position_ticket,
                entry_at=t.opened_at,
                exit_at=t.closed_at,
                realized_pnl=t.pnl,
                fees=fees,
                slippage=None,  # only when measurable by caller
                chain_complete=not missing,
                missing_links=tuple(missing),
            )
        )

    return PerformanceReport(
        trades_considered=len(considered),
        trades_excluded_unconfirmed=excluded,
        overall=_metrics("all", considered),
        by_strategy=_group(considered, lambda t: t.strategy),
        by_symbol=_group(considered, lambda t: t.symbol),
        by_broker=_group(considered, lambda t: t.broker_code),
        by_session=_group(considered, lambda t: t.session),
        attribution=tuple(attribution),
        methodology={
            "source": "confirmed_closed_trades_only",
            "profit_factor": "gross_profit / abs(gross_loss)",
            "max_drawdown": "peak_to_trough_on_cumulative_pnl",
            "expectancy": "net_profit / n",
            "unconfirmed": "excluded",
            "slippage": "null_unless_measurable",
        },
    )


def performance_to_csv(report: PerformanceReport) -> str:
    """Export attribution rows without secrets."""
    lines = [
        "trade_id,symbol,strategy,broker,account,signal_id,order_ticket,"
        "position_ticket,realized_pnl,fees,chain_complete,missing_links"
    ]
    for row in report.attribution:
        lines.append(
            ",".join(
                [
                    row.trade_id,
                    row.symbol,
                    row.strategy or "",
                    row.broker_code or "",
                    row.account_key or "",
                    row.signal_id or "",
                    str(row.order_ticket or ""),
                    str(row.position_ticket or ""),
                    str(row.realized_pnl),
                    str(row.fees) if row.fees is not None else "",
                    "1" if row.chain_complete else "0",
                    "|".join(row.missing_links),
                ]
            )
        )
    return "\n".join(lines) + "\n"
