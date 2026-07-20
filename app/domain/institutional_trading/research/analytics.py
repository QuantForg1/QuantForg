"""Research analytics engine — institutional performance schema."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from math import sqrt

from app.domain.institutional_trading.research.models import (
    AnalyticsReport,
    EquityPoint,
    ResearchTrade,
)


@dataclass(frozen=True, slots=True)
class ResearchAnalyticsEngine:
    periods_per_year: Decimal = Decimal("252")

    def compute(
        self,
        *,
        trades: list[ResearchTrade],
        equity_curve: list[EquityPoint],
        initial_balance: Decimal,
    ) -> AnalyticsReport:
        closed = [t for t in trades if t.status == "closed"]
        wins = [t for t in closed if t.pnl > 0]
        losses = [t for t in closed if t.pnl < 0]
        n = len(closed)
        win_rate = (
            (Decimal(len(wins)) / Decimal(n) * Decimal("100")) if n else Decimal("0")
        )
        expectancy = (
            (sum((t.pnl for t in closed), Decimal("0")) / Decimal(n))
            if n
            else Decimal("0")
        )
        gp = sum((t.pnl for t in wins), Decimal("0"))
        gl = abs(sum((t.pnl for t in losses), Decimal("0")))
        if gl > 0:
            pf: Decimal | None = (gp / gl).quantize(Decimal("0.0001"))
        elif gp > 0:
            pf = Decimal("999")
        else:
            pf = None

        avg_rr = self._avg_rr(closed)
        max_dd = max((p.drawdown_pct for p in equity_curve), default=Decimal("0"))
        final = equity_curve[-1].equity if equity_curve else initial_balance
        total_ret = (
            ((final - initial_balance) / initial_balance * Decimal("100"))
            if initial_balance > 0
            else Decimal("0")
        )
        sharpe = self._sharpe(equity_curve, initial_balance)
        sortino = self._sortino(equity_curve, initial_balance)
        calmar = None
        if max_dd > 0:
            calmar = (total_ret / max_dd).quantize(Decimal("0.0001"))
        recovery = None
        if max_dd > 0 and initial_balance > 0:
            net = final - initial_balance
            recovery = (net / (initial_balance * max_dd / Decimal("100"))).quantize(
                Decimal("0.0001")
            )

        hold = 0.0
        if closed:
            secs = []
            for t in closed:
                if t.exit_time and t.entry_time:
                    secs.append((t.exit_time - t.entry_time).total_seconds())
            hold = sum(secs) / len(secs) if secs else 0.0

        best_s, worst_s = self._session_rank(closed)
        win_streak, loss_streak = self._streaks(closed)
        mae_avg = (
            sum((t.mae for t in closed), Decimal("0")) / Decimal(n)
            if n
            else Decimal("0")
        )
        mfe_avg = (
            sum((t.mfe for t in closed), Decimal("0")) / Decimal(n)
            if n
            else Decimal("0")
        )
        monthly = self._monthly(closed)
        dist = tuple(str(t.pnl) for t in closed)

        return AnalyticsReport(
            win_rate=win_rate.quantize(Decimal("0.0001")),
            expectancy=expectancy.quantize(Decimal("0.0001")),
            profit_factor=pf,
            average_rr=avg_rr,
            max_drawdown_pct=max_dd.quantize(Decimal("0.0001")),
            sharpe=sharpe,
            sortino=sortino,
            calmar=calmar,
            recovery_factor=recovery,
            average_hold_seconds=hold,
            best_session=best_s,
            worst_session=worst_s,
            longest_win_streak=win_streak,
            longest_loss_streak=loss_streak,
            mae_avg=mae_avg.quantize(Decimal("0.0001")),
            mfe_avg=mfe_avg.quantize(Decimal("0.0001")),
            trade_count=n,
            win_count=len(wins),
            loss_count=len(losses),
            total_return_pct=total_ret.quantize(Decimal("0.0001")),
            monthly_returns=monthly,
            equity_curve=tuple(equity_curve),
            pnl_distribution=dist,
        )

    @staticmethod
    def _avg_rr(closed: list[ResearchTrade]) -> Decimal | None:
        rs = [t.r_multiple for t in closed if t.r_multiple is not None]
        if not rs:
            return None
        return (sum(rs, Decimal("0")) / Decimal(len(rs))).quantize(Decimal("0.0001"))

    def _period_returns(
        self, curve: list[EquityPoint], initial: Decimal
    ) -> list[float]:
        if len(curve) < 2:
            return []
        out: list[float] = []
        prev = float(initial)
        for p in curve:
            cur = float(p.equity)
            if prev > 0:
                out.append((cur - prev) / prev)
            prev = cur
        return out

    def _sharpe(self, curve: list[EquityPoint], initial: Decimal) -> Decimal | None:
        rets = self._period_returns(curve, initial)
        if len(rets) < 2:
            return None
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        if var <= 0:
            return None
        return Decimal(
            str(round(mean / sqrt(var) * sqrt(float(self.periods_per_year)), 4))
        )

    def _sortino(self, curve: list[EquityPoint], initial: Decimal) -> Decimal | None:
        rets = self._period_returns(curve, initial)
        if len(rets) < 2:
            return None
        mean = sum(rets) / len(rets)
        downside = [r for r in rets if r < 0]
        if not downside:
            return Decimal("999")
        var = sum(r**2 for r in downside) / len(downside)
        if var <= 0:
            return None
        return Decimal(
            str(round(mean / sqrt(var) * sqrt(float(self.periods_per_year)), 4))
        )

    @staticmethod
    def _session_rank(closed: list[ResearchTrade]) -> tuple[str, str]:
        buckets: dict[str, list[Decimal]] = defaultdict(list)
        for t in closed:
            buckets[t.session or "unknown"].append(t.pnl)
        if not buckets:
            return "n/a", "n/a"
        scored = {k: sum(v, Decimal("0")) / Decimal(len(v)) for k, v in buckets.items()}
        best = max(scored, key=lambda k: scored[k])
        worst = min(scored, key=lambda k: scored[k])
        return best, worst

    @staticmethod
    def _streaks(closed: list[ResearchTrade]) -> tuple[int, int]:
        best_w = best_l = cur_w = cur_l = 0
        for t in closed:
            if t.pnl > 0:
                cur_w += 1
                cur_l = 0
                best_w = max(best_w, cur_w)
            elif t.pnl < 0:
                cur_l += 1
                cur_w = 0
                best_l = max(best_l, cur_l)
            else:
                cur_w = cur_l = 0
        return best_w, best_l

    @staticmethod
    def _monthly(closed: list[ResearchTrade]) -> dict[str, str]:
        buckets: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for t in closed:
            if t.exit_time:
                key = t.exit_time.strftime("%Y-%m")
                buckets[key] += t.pnl
        return {k: str(v) for k, v in sorted(buckets.items())}
