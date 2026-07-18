"""In-memory paper-mode decision tracker — no DB schema change."""

from __future__ import annotations

import math
import threading
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4


class DecisionPaperTracker:
    """Tracks paper-mode decision outcomes for performance reports."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_user: dict[str, list[dict[str, Any]]] = {}

    def record(
        self,
        *,
        user_id: UUID,
        symbol: str,
        decision: str,
        side: str | None,
        score: float,
        confidence: float,
        expected_rr: float | None = None,
        simulated_pnl: float | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": str(uuid4()),
            "symbol": symbol.upper(),
            "decision": decision,
            "side": side,
            "trade_score": score,
            "confidence_pct": confidence,
            "expected_rr": expected_rr,
            "simulated_pnl": simulated_pnl,
            "meta": deepcopy(meta or {}),
            "created_at": datetime.now(UTC).isoformat(),
            "mode": "paper",
        }
        with self._lock:
            bucket = self._by_user.setdefault(str(user_id), [])
            bucket.append(row)
            # Cap memory
            if len(bucket) > 2000:
                del bucket[:-1500]
        return row

    def update_pnl(
        self, user_id: UUID, signal_id: str, simulated_pnl: float
    ) -> dict[str, Any] | None:
        with self._lock:
            bucket = self._by_user.get(str(user_id), [])
            for i, row in enumerate(bucket):
                if row.get("id") == signal_id:
                    bucket[i] = {**row, "simulated_pnl": float(simulated_pnl)}
                    return deepcopy(bucket[i])
        return None

    def list_for_user(self, user_id: UUID, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._by_user.get(str(user_id), []))
        return list(reversed(rows[-limit:]))

    def performance(self, user_id: UUID) -> dict[str, Any]:
        rows = [
            r
            for r in self.list_for_user(user_id, limit=2000)
            if r.get("decision") == "TRADE_IDEA" and r.get("simulated_pnl") is not None
        ]
        if not rows:
            return {
                "status": "unavailable",
                "reason": "No paper TRADE_IDEA outcomes with simulated PnL yet",
                "mode": "paper",
                "sample_size": 0,
            }

        pnls = [float(r["simulated_pnl"]) for r in rows]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        n = len(pnls)
        win_rate = len(wins) / n
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
        pf = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else None
        expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss
        avg_rr = (avg_win / avg_loss) if avg_loss > 0 else None

        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        cons_loss = 0
        max_cons_loss = 0
        rets: list[float] = []
        prev = 0.0
        for p in pnls:
            equity += p
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)
            if p < 0:
                cons_loss += 1
                max_cons_loss = max(max_cons_loss, cons_loss)
            else:
                cons_loss = 0
            if prev != 0:
                rets.append(p / abs(prev) if prev else 0.0)
            prev = equity if equity != 0 else prev

        sharpe = None
        if len(rets) >= 5:
            mean = sum(rets) / len(rets)
            var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
            std = math.sqrt(var) if var > 0 else 0.0
            if std > 0:
                sharpe = round(mean / std * math.sqrt(252), 4)

        return {
            "status": "available",
            "mode": "paper",
            "sample_size": n,
            "win_rate": round(win_rate, 4),
            "profit_factor": round(pf, 4) if pf is not None else None,
            "sharpe_ratio": sharpe,
            "drawdown": round(max_dd, 4),
            "expectancy": round(expectancy, 4),
            "average_rr": round(avg_rr, 4) if avg_rr is not None else None,
            "max_consecutive_losses": max_cons_loss,
            "autonomous_trading": False,
        }

    def reports(self, user_id: UUID) -> dict[str, Any]:
        rows = self.list_for_user(user_id, limit=2000)
        now = datetime.now(UTC)

        def _window(days: int) -> list[dict[str, Any]]:
            cut = now - timedelta(days=days)
            out = []
            for r in rows:
                try:
                    ts = datetime.fromisoformat(
                        str(r["created_at"]).replace("Z", "+00:00")
                    )
                except ValueError:
                    continue
                if ts >= cut:
                    out.append(r)
            return out

        def _summary(label: str, subset: list[dict[str, Any]]) -> dict[str, Any]:
            ideas = [r for r in subset if r.get("decision") == "TRADE_IDEA"]
            waits = [r for r in subset if r.get("decision") == "WAIT"]
            pnls = [
                float(r["simulated_pnl"])
                for r in ideas
                if r.get("simulated_pnl") is not None
            ]
            return {
                "period": label,
                "signals": len(subset),
                "trade_ideas": len(ideas),
                "waits": len(waits),
                "wait_ratio": round(len(waits) / len(subset), 4) if subset else None,
                "realized_sim_pnl": round(sum(pnls), 4) if pnls else 0.0,
                "avg_score": (
                    round(sum(float(r["trade_score"]) for r in subset) / len(subset), 2)
                    if subset
                    else None
                ),
            }

        return {
            "status": "available",
            "daily": _summary("daily", _window(1)),
            "weekly": _summary("weekly", _window(7)),
            "monthly": _summary("monthly", _window(30)),
            "signal_quality": {
                "note": "WAIT dominance is intentional — capital preservation first",
                "paper_performance": self.performance(user_id),
            },
            "autonomous_trading": False,
        }


_TRACKER = DecisionPaperTracker()


def get_paper_tracker() -> DecisionPaperTracker:
    return _TRACKER
