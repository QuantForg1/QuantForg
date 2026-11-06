"""Post-PR #182 strategy performance monitoring — observability only.

Builds account-separated and five-pack scorecards from durable trade outcomes.
Does not change LIVE eligibility, cascades, or order submission.
"""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.ai_scalping.strategies import (
    profitability_metrics as pm,
    trade_outcome_store as outcomes,
)
from app.domain.institutional_trading.ai_scalping.strategies.registry import (
    ALL_STRATEGIES,
)


def _rows_as_pnl(rows: list[Any]) -> list[dict[str, object]]:
    return [{"net_pnl": float(r.net_pnl)} for r in rows]


def _classify_with_attribution(
    *,
    card_classification: str,
    attributed: int,
    n: int,
) -> str:
    if n <= 0:
        return "Insufficient data"
    if attributed == 0:
        return "Insufficient attribution"
    if attributed < n:
        # Partial attribution — disclose, do not claim full expectancy.
        if card_classification.startswith("Demonstrated"):
            return "Promising but insufficient sample"
        if "Negative" in card_classification:
            return "Negative expectancy observed"
        return "Insufficient attribution"
    if "Demonstrated positive" in card_classification:
        return "Positive expectancy demonstrated"
    if "Negative" in card_classification:
        return "Negative expectancy observed"
    if "Promising" in card_classification:
        return "Promising but insufficient sample"
    return card_classification


def build_period_bucket(
    rows: list[Any], *, label: str, account: int | None
) -> dict[str, Any]:
    card = pm.build_performance_scorecard(_rows_as_pnl(rows), label=label)
    attributed = sum(1 for r in rows if r.strategy_id)
    incomplete_costs = sum(1 for r in rows if not r.costs_complete)
    buys = [r for r in rows if str(r.side or "").upper() == "BUY"]
    sells = [r for r in rows if str(r.side or "").upper() == "SELL"]
    reversal = sum(
        1
        for r in rows
        if "reversal" in str(r.close_reason or "").lower()
        or "structure" in str(r.close_reason or "").lower()
    )
    return {
        "label": label,
        "broker_login": account,
        "n": card.n,
        "attributed": attributed,
        "unattributed": card.n - attributed,
        "incomplete_cost_records": incomplete_costs,
        "win_rate": card.win_rate,
        "net_profit": card.net_profit,
        "profit_factor": card.profit_factor,
        "expectancy": card.expectancy,
        "avg_win": card.avg_win,
        "avg_loss": card.avg_loss,
        "breakeven_win_rate": card.breakeven_win_rate,
        "max_consecutive_losses": card.max_consecutive_losses,
        "max_drawdown": card.max_drawdown,
        "buy": {
            "n": len(buys),
            "net": round(sum(float(r.net_pnl) for r in buys), 4),
        },
        "sell": {
            "n": len(sells),
            "net": round(sum(float(r.net_pnl) for r in sells), 4),
        },
        "reversal_like_closes": reversal,
        "classification": _classify_with_attribution(
            card_classification=card.classification,
            attributed=attributed,
            n=card.n,
        ),
        "data_quality": {
            "costs_treated_as_authoritative_only_when_complete": True,
            "missing_strategy_id_count": card.n - attributed,
            "note": (
                "Commission/swap may be broker-reported zero; "
                "costs_complete=False means fields were absent, not zero."
            ),
        },
    }


def build_five_pack_scorecards(
    rows: list[Any], *, account: int | None
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for definition in ALL_STRATEGIES:
        sid = definition.strategy_id
        matched = [r for r in rows if r.strategy_id == sid]
        card = pm.build_performance_scorecard(_rows_as_pnl(matched), label=sid)
        buys = [r for r in matched if str(r.side or "").upper() == "BUY"]
        sells = [r for r in matched if str(r.side or "").upper() == "SELL"]
        cards.append(
            {
                "strategy_id": sid,
                "strategy_name": definition.name,
                "broker_login": account,
                "closed_trades": card.n,
                "broker_confirmed_fills": card.n,
                "net_pnl": card.net_profit,
                "win_rate": card.win_rate,
                "profit_factor": card.profit_factor,
                "expectancy": card.expectancy,
                "avg_win": card.avg_win,
                "avg_loss": card.avg_loss,
                "buy_n": len(buys),
                "sell_n": len(sells),
                "attribution_confidence": (
                    "bound_five_pack" if matched else "insufficient_data"
                ),
                "sample_size": card.n,
                "classification": (
                    "Insufficient data"
                    if card.n == 0
                    else _classify_with_attribution(
                        card_classification=card.classification,
                        attributed=card.n,
                        n=card.n,
                    )
                ),
                "signal_count": None,
                "qualified_signals": None,
                "note": (
                    "Signal/qualified counts require cycle telemetry; "
                    "closed trades are broker-authoritative only."
                ),
            }
        )
    # Unattributed bucket
    unknown = [r for r in rows if not r.strategy_id]
    u_card = pm.build_performance_scorecard(_rows_as_pnl(unknown), label="unattributed")
    cards.append(
        {
            "strategy_id": None,
            "strategy_name": "Unattributed / unknown",
            "broker_login": account,
            "closed_trades": u_card.n,
            "broker_confirmed_fills": u_card.n,
            "net_pnl": u_card.net_profit,
            "win_rate": u_card.win_rate,
            "profit_factor": u_card.profit_factor,
            "expectancy": u_card.expectancy,
            "avg_win": u_card.avg_win,
            "avg_loss": u_card.avg_loss,
            "attribution_confidence": "unknown",
            "sample_size": u_card.n,
            "classification": (
                "Insufficient attribution" if u_card.n else "Insufficient data"
            ),
        }
    )
    return cards


def build_post182_performance_monitor(
    *,
    broker_login: int | None = None,
) -> dict[str, Any]:
    """Snapshot for ops — account-separated, period-separated, five-pack cards."""
    all_rows = outcomes.list_trade_outcomes(broker_login=broker_login)
    by_period: dict[str, list[Any]] = {
        "pre_pr180": [],
        "post_pr180_pre_pr182": [],
        "post_pr182": [],
        "unknown_time": [],
    }
    for row in all_rows:
        by_period.setdefault(outcomes.period_label(row.closed_at), []).append(row)
    periods = {
        name: build_period_bucket(rows, label=name, account=broker_login)
        for name, rows in by_period.items()
    }
    post182 = by_period.get("post_pr182") or []
    return {
        "broker_login": broker_login,
        "account_12260878_note": (
            "Not included unless broker_login=12260878 is queried separately. "
            "Never merge with 12479147 without an explicit combined label."
        ),
        "periods": periods,
        "post_pr182": build_period_bucket(
            post182, label="post_pr182", account=broker_login
        ),
        "five_pack_scorecards_post_pr182": build_five_pack_scorecards(
            post182, account=broker_login
        ),
        "five_pack_scorecards_all_recorded": build_five_pack_scorecards(
            all_rows, account=broker_login
        ),
        "features": {
            "changes_trading_decisions": False,
            "observability_only": True,
        },
    }
