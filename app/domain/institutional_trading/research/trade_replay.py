"""Trade replay builder — entry/SL/TP/partial/trail/exit + decision context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.institutional_trading.research.models import ResearchTrade


@dataclass(frozen=True, slots=True)
class TradeReplayEngine:
    """Serialize every trade into an operator-facing replay timeline."""

    def replay(self, trade: ResearchTrade) -> dict[str, Any]:
        timeline = list(trade.events)
        return {
            "trade_id": trade.trade_id,
            "side": trade.side,
            "entry": {
                "time": trade.entry_time.isoformat(),
                "price": str(trade.entry_price),
            },
            "stop_loss": str(trade.stop_loss),
            "take_profit": str(trade.take_profit) if trade.take_profit else None,
            "exit": {
                "time": trade.exit_time.isoformat() if trade.exit_time else None,
                "price": str(trade.exit_price) if trade.exit_price else None,
                "reason": trade.exit_reason,
            },
            "partial": [e for e in timeline if e.get("type") == "partial"],
            "trailing": [e for e in timeline if e.get("type") in {"trail", "sltp"}],
            "timeline": timeline,
            "decision_reasons": list(trade.decision_reasons),
            "confluence": dict(trade.confluence),
            "quality": trade.quality,
            "confidence": trade.confidence,
            "risk_score": trade.risk_score,
            "mae": str(trade.mae),
            "mfe": str(trade.mfe),
            "r_multiple": (
                str(trade.r_multiple) if trade.r_multiple is not None else None
            ),
            "pnl": str(trade.pnl),
        }

    def replay_all(self, trades: list[ResearchTrade]) -> list[dict[str, Any]]:
        return [self.replay(t) for t in trades if t.status == "closed"]
