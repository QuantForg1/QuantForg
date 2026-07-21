"""Trade journal intelligence — pattern extraction, never fabricated fills."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class JournalTradeView:
    symbol: str
    side: str
    pnl: Decimal
    session: str | None = None
    strategy_id: str | None = None
    r_multiple: Decimal | None = None
    exit_reason: str | None = None


@dataclass(frozen=True, slots=True)
class JournalIntelligence:
    trade_count: int
    win_rate: Decimal
    net_pnl: Decimal
    best_session: str | None
    worst_session: str | None
    best_strategy: str | None
    common_exit: str | None
    insights: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "trade_count": self.trade_count,
            "win_rate": str(self.win_rate),
            "net_pnl": str(self.net_pnl),
            "best_session": self.best_session,
            "worst_session": self.worst_session,
            "best_strategy": self.best_strategy,
            "common_exit": self.common_exit,
            "insights": list(self.insights),
        }


def analyze_journal(trades: Sequence[JournalTradeView]) -> JournalIntelligence:
    if not trades:
        return JournalIntelligence(
            trade_count=0,
            win_rate=Decimal("0"),
            net_pnl=Decimal("0"),
            best_session=None,
            worst_session=None,
            best_strategy=None,
            common_exit=None,
            insights=("No closed trades in journal — nothing to analyze.",),
        )

    wins = sum(1 for t in trades if t.pnl > 0)
    net = sum((t.pnl for t in trades), Decimal("0")).quantize(Decimal("0.01"))
    wr = (Decimal(wins) / Decimal(len(trades)) * Decimal("100")).quantize(
        Decimal("0.01")
    )

    session_pnl: dict[str, Decimal] = {}
    strategy_pnl: dict[str, Decimal] = {}
    exits: Counter[str] = Counter()
    for t in trades:
        if t.session:
            session_pnl[t.session] = session_pnl.get(t.session, Decimal("0")) + t.pnl
        if t.strategy_id:
            strategy_pnl[t.strategy_id] = (
                strategy_pnl.get(t.strategy_id, Decimal("0")) + t.pnl
            )
        if t.exit_reason:
            exits[t.exit_reason] += 1

    best_session = (
        max(session_pnl, key=lambda k: session_pnl[k]) if session_pnl else None
    )
    worst_session = (
        min(session_pnl, key=lambda k: session_pnl[k]) if session_pnl else None
    )
    best_strategy = (
        max(strategy_pnl, key=lambda k: strategy_pnl[k]) if strategy_pnl else None
    )
    common_exit = exits.most_common(1)[0][0] if exits else None

    insights: list[str] = []
    if wr < Decimal("40") and len(trades) >= 5:
        insights.append(
            f"Win rate {wr}% across {len(trades)} trades — tighten filters, "
            "do not increase risk."
        )
    if net < 0:
        insights.append(
            "Net journal PnL is negative — capital preservation mode: "
            "reduce size after drawdown; never martingale."
        )
    if best_session and worst_session and best_session != worst_session:
        insights.append(
            f"Session edge: {best_session} outperforms {worst_session} in sample."
        )
    if common_exit:
        insights.append(f"Most common exit reason: {common_exit}.")
    if not insights:
        insights.append(
            "Journal sample is thin or mixed — keep Risk/Safety gates mandatory."
        )

    return JournalIntelligence(
        trade_count=len(trades),
        win_rate=wr,
        net_pnl=net,
        best_session=best_session,
        worst_session=worst_session,
        best_strategy=best_strategy,
        common_exit=common_exit,
        insights=tuple(insights),
    )
