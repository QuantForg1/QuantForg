"""Read-only risk insights. They do not change a risk profile or an order."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

SCHEMA_VERSION = "risk-intelligence.v1"


@dataclass(frozen=True, slots=True)
class RiskInsightInput:
    """Numbers the caller already loaded. Missing values stay missing."""

    read_at: datetime
    source: str = "none"
    equity: str | None = None
    balance: str | None = None
    free_margin: str | None = None
    used_margin: str | None = None
    floating_pnl: str | None = None
    realized_pnl: str | None = None
    aggregate_open_risk_pct: str | None = None
    open_risk_limit_pct: str | None = None
    daily_loss_pct_used: str | None = None
    daily_loss_limit_pct: str | None = None
    consecutive_losses: int | None = None
    largest_symbol_share_pct: str | None = None


def build_risk_insight(spec: RiskInsightInput) -> dict[str, Any]:
    """Summarize supplied risk facts. A gap is unknown, not safe."""
    observed = spec.read_at.isoformat()
    source = spec.source.strip() or "none"
    equity = _dec(spec.equity)
    used = _dec(spec.used_margin)
    free = _dec(spec.free_margin)
    open_risk = _dec(spec.aggregate_open_risk_pct)
    open_limit = _dec(spec.open_risk_limit_pct)
    daily_used = _dec(spec.daily_loss_pct_used)
    daily_limit = _dec(spec.daily_loss_limit_pct)
    share = _dec(spec.largest_symbol_share_pct)
    margin_used_pct = None
    if used is not None and free is not None and (used + free) > 0:
        margin_used_pct = (used / (used + free)) * Decimal("100")
    insights = _insights(
        open_risk=open_risk,
        open_limit=open_limit,
        margin_used_pct=margin_used_pct,
        daily_used=daily_used,
        daily_limit=daily_limit,
        share=share,
        losses=spec.consecutive_losses,
        equity_known=equity is not None,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "places_orders": False,
        "changes_risk_policy": False,
        "authoritative_for_execution": False,
        "read_at": observed,
        "source": source,
        "equity": _fig(spec.equity, source, observed, "supplied_equity"),
        "balance": _fig(spec.balance, source, observed, "supplied_balance"),
        "floating_pnl": _fig(
            spec.floating_pnl, source, observed, "supplied_floating_pnl"
        ),
        "realized_pnl": _fig(
            spec.realized_pnl, source, observed, "supplied_realized_pnl"
        ),
        "margin_used_pct": _fig(
            _money(margin_used_pct) if margin_used_pct is not None else None,
            source,
            observed,
            "used_margin_over_used_plus_free",
        ),
        "aggregate_open_risk_pct": _fig(
            spec.aggregate_open_risk_pct,
            source,
            observed,
            "supplied_aggregate_open_risk",
        ),
        "insights": insights,
    }


def _insights(
    *,
    open_risk: Decimal | None,
    open_limit: Decimal | None,
    margin_used_pct: Decimal | None,
    daily_used: Decimal | None,
    daily_limit: Decimal | None,
    share: Decimal | None,
    losses: int | None,
    equity_known: bool,
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    if not equity_known:
        notes.append(_note("unavailable", "Equity was not supplied."))
    if open_risk is not None and open_limit is not None and open_limit > 0:
        if open_risk >= open_limit * Decimal("0.8"):
            notes.append(
                _note(
                    "elevated_open_risk",
                    "Aggregate open risk is at least 80 percent of the supplied limit.",
                )
            )
    elif open_risk is None or open_limit is None:
        notes.append(_note("unknown_open_risk", "Open risk or its limit is missing."))
    if margin_used_pct is not None and margin_used_pct >= Decimal("70"):
        notes.append(
            _note(
                "margin_utilization",
                "Used margin is at least 70 percent of used plus free margin.",
            )
        )
    near_daily = (
        daily_used is not None
        and daily_limit is not None
        and daily_limit > 0
        and daily_used >= daily_limit * Decimal("0.8")
    )
    if near_daily:
        notes.append(
            _note(
                "daily_loss_proximity",
                "Daily loss is at least 80 percent of its limit.",
            )
        )
    if share is not None and share >= Decimal("60"):
        notes.append(
            _note(
                "symbol_concentration",
                "One symbol accounts for at least 60 percent of the supplied exposure.",
            )
        )
    if losses is not None and losses >= 3:
        notes.append(
            _note(
                "consecutive_losses",
                "The supplied loss streak is at least three closed losses.",
            )
        )
    return notes


def _note(code: str, text: str) -> dict[str, Any]:
    return {
        "code": code,
        "text": text,
        "changes_settings": False,
        "execution_instruction": False,
    }


def _fig(value: str | None, source: str, observed: str, method: str) -> dict[str, Any]:
    text = value.strip() if isinstance(value, str) else None
    if text == "":
        text = None
    if text is not None and _dec(text) is None and method != "supplied_equity":
        text = None
    status = "verified" if text is not None else "unavailable"
    if text is not None and _dec(text) is None:
        status = "unavailable"
        text = None
    return {
        "value": text,
        "status": status,
        "source": source,
        "method": method,
        "observed_at": observed,
        "live_performance": False,
    }


def _dec(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")
