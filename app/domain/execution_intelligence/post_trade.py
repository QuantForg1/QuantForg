"""Post-trade analysis from completed trade rows only."""

from __future__ import annotations

from typing import Any


def _f(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def analyze_post_trade(trade: dict[str, Any]) -> dict[str, Any]:
    """Explainable post-trade blotter entry — no fabricated market facts."""
    symbol = str(trade.get("symbol") or "").upper()
    if not symbol:
        return {
            "status": "unavailable",
            "reason": "Trade missing symbol",
            "data_source": "caller",
        }

    pnl = _f(trade.get("pnl") or trade.get("profit") or trade.get("realized_pnl"))
    requested = trade.get("requested_price") or trade.get("entry_price")
    fill = trade.get("fill_price") or trade.get("exit_price") or trade.get("price")
    slip = trade.get("slippage")
    if slip is None and requested is not None and fill is not None:
        slip = abs(_f(fill) - _f(requested))
    elif slip is not None:
        slip = abs(_f(slip))

    risk_used = trade.get("risk_utilization") or trade.get("margin_used")
    risk_pct = _f(risk_used) if risk_used is not None else None

    quality = None
    if slip is not None:
        # Lower slippage → higher quality (bounded heuristic on observed slip only)
        quality = round(max(0.0, min(1.0, 1.0 - min(1.0, float(slip) * 100.0))), 4)

    reasons = []
    if pnl != 0:
        reasons.append(f"Realized PnL {pnl}")
    if slip is not None:
        reasons.append(f"Observed slippage {slip}")
    else:
        reasons.append("Slippage unavailable — missing price pair")
    if risk_pct is not None:
        reasons.append(f"Risk utilization field={risk_pct}")
    else:
        reasons.append("Risk utilization unavailable — field not on trade")

    return {
        "status": "available",
        "symbol": symbol,
        "side": str(trade.get("side") or "unknown"),
        "execution_quality": quality,
        "execution_quality_status": (
            "available" if quality is not None else "unavailable"
        ),
        "slippage": slip,
        "slippage_status": "available" if slip is not None else "unavailable",
        "risk_utilization": risk_pct,
        "risk_utilization_status": (
            "available" if risk_pct is not None else "unavailable"
        ),
        "pnl_contribution": pnl,
        "journal_entry": {
            "summary": f"{symbol} {trade.get('side', '')} pnl={pnl}",
            "opened_at": trade.get("opened_at") or trade.get("submitted_at"),
            "closed_at": trade.get("closed_at") or trade.get("filled_at"),
            "comment": trade.get("comment") or trade.get("strategy") or "",
        },
        "explanation": {
            "reason": "; ".join(reasons),
            "supporting_metrics": {
                "pnl": pnl,
                "slippage": slip,
                "risk_utilization": risk_pct,
                "requested_price": requested,
                "fill_price": fill,
            },
            "risk_impact": {
                "pnl_contribution": pnl,
                "risk_utilization": risk_pct,
            },
            "confidence": 0.8 if slip is not None else 0.45,
            "data_source": str(trade.get("data_source") or "trade_record"),
        },
        "autonomous_trading": False,
    }


def analyze_post_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "status": "unavailable",
            "reason": "No completed trades available",
            "items": [],
            "data_source": "paper_trades|history_deals",
        }
    items = [analyze_post_trade(t) for t in trades]
    return {
        "status": "available",
        "count": len(items),
        "items": items,
        "data_source": "paper_trades|history_deals",
    }
