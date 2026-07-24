"""Human-readable permanent explainability for Performance Lab."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.production_hardening.explainability import (
    build_explanation,
    get_explainability_store,
)


def store_lab_explanation(
    *,
    decision: Any,
    ticket: str | None = None,
    risk_pct: str | None = None,
    why_now: str | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Permanent why-* narrative; does not alter trading."""
    conf = getattr(decision, "confidence", None)
    reasons = tuple(getattr(decision, "reasons", ()) or ())
    symbol = str(getattr(decision, "symbol", "") or "")
    direction = str(
        getattr(getattr(decision, "direction", None), "value", None)
        or getattr(decision, "direction", "")
        or ""
    )
    lots = getattr(decision, "approved_lots", None)
    stop = getattr(decision, "stop_zone", None)
    target = getattr(decision, "target_zone", None)
    now_reason = why_now or ("; ".join(str(r) for r in reasons[:4]) or "setup met gates")

    expl = build_explanation(
        symbol=symbol,
        direction=direction,
        ticket=ticket,
        why_entered=f"Why now: {now_reason}",
        why_risk_pct=f"Why this risk: risk_per_trade={risk_pct or 'plane/default'}% aligned with account equity and ATR stop",
        why_lot_size=f"Why this lot size: approved_lots={lots} from risk budget ÷ stop distance",
        why_tp=f"Why this TP: target_zone={getattr(target, 'mid', target)} for estimated RR",
        why_sl=f"Why this SL: stop_zone={getattr(stop, 'mid', stop)} beyond invalidation / ATR multiple",
        why_confidence=f"Why this confidence: confluence score={conf}",
        why_symbol=f"Why this symbol: selected {symbol} as highest-quality eligible opportunity",
        why_session=f"Why this session: {getattr(decision, 'expected_duration', 'session window')}",
        why_regime=f"Why this regime: market structure supportive of {direction}",
        extras={**(extras or {}), "lab_version": "v8"},
    )
    get_explainability_store().record(expl)
    return expl.to_dict()
