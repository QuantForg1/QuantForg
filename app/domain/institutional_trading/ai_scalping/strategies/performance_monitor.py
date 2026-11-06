"""Post-PR #182 strategy performance monitoring — observability only.

Builds account-separated and five-pack scorecards from durable trade outcomes.
Does not change LIVE eligibility, cascades, or order submission.
"""

from __future__ import annotations

from datetime import UTC, datetime
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


def _side_scorecard(rows: list[Any], *, side: str) -> dict[str, Any]:
    matched = [r for r in rows if str(r.side or "").upper() == side.upper()]
    card = pm.build_performance_scorecard(_rows_as_pnl(matched), label=side.upper())
    return {
        "side": side.upper(),
        "n": card.n,
        "net": card.net_profit,
        "win_rate": card.win_rate,
        "profit_factor": card.profit_factor,
        "expectancy": card.expectancy,
        "avg_win": card.avg_win,
        "avg_loss": card.avg_loss,
        "max_drawdown": card.max_drawdown,
        "max_consecutive_losses": card.max_consecutive_losses,
        "classification": card.classification,
    }


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
    buy_sc = _side_scorecard(rows, side="BUY")
    sell_sc = _side_scorecard(rows, side="SELL")
    return {
        "label": label,
        "broker_login": account,
        "n": card.n,
        "attributed": attributed,
        "unattributed": card.n - attributed,
        "attribution_coverage_pct": (
            round(100.0 * attributed / card.n, 2) if card.n else None
        ),
        "incomplete_cost_records": incomplete_costs,
        "realized_net_pnl": card.net_profit,
        "unrealized_pnl": None,
        "unrealized_pnl_note": (
            "This monitor reports broker-confirmed closed outcomes only. "
            "Open-position unrealized P&L is not included."
        ),
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
            **{k: v for k, v in buy_sc.items() if k not in {"side", "n", "net"}},
        },
        "sell": {
            "n": len(sells),
            "net": round(sum(float(r.net_pnl) for r in sells), 4),
            **{k: v for k, v in sell_sc.items() if k not in {"side", "n", "net"}},
        },
        "side_comparison": {"buy": buy_sc, "sell": sell_sc},
        "reversal_like_closes": reversal,
        "classification": _classify_with_attribution(
            card_classification=card.classification,
            attributed=attributed,
            n=card.n,
        ),
        "data_quality": {
            "costs_treated_as_authoritative_only_when_complete": True,
            "missing_strategy_id_count": card.n - attributed,
            "incomplete_cost_records": incomplete_costs,
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
        buy_net = round(sum(float(r.net_pnl) for r in buys), 4)
        sell_net = round(sum(float(r.net_pnl) for r in sells), 4)
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
                "max_drawdown": card.max_drawdown,
                "max_consecutive_losses": card.max_consecutive_losses,
                "buy_n": len(buys),
                "sell_n": len(sells),
                "buy_net": buy_net,
                "sell_net": sell_net,
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
    # Unattributed bucket — never assigned to a guessed strategy.
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
            "max_drawdown": u_card.max_drawdown,
            "max_consecutive_losses": u_card.max_consecutive_losses,
            "buy_n": sum(1 for r in unknown if str(r.side or "").upper() == "BUY"),
            "sell_n": sum(1 for r in unknown if str(r.side or "").upper() == "SELL"),
            "attribution_confidence": "unknown",
            "sample_size": u_card.n,
            "classification": (
                "Insufficient attribution" if u_card.n else "Insufficient data"
            ),
        }
    )
    return cards


def build_capital_protection_snapshot(
    rows: list[Any], *, account: int | None
) -> dict[str, Any]:
    """Observability snapshot of cascade anchors + reversal closes.

    Does not claim cascade blocks 'saved' money without counterfactual analysis.
    """
    buy_active: list[dict[str, Any]] = []
    sell_active: list[dict[str, Any]] = []
    buy_trusted: bool | None = None
    sell_trusted: bool | None = None
    buy_error: str | None = None
    sell_error: str | None = None
    try:
        from app.domain.institutional_trading.ai_scalping import (
            buy_cascade_anchor_store as buy_store,
        )

        buy_anchors, buy_trusted = buy_store.load_active_anchors()
        for a in buy_anchors:
            if account is not None and a.broker_login not in (None, account):
                continue
            buy_active.append(
                {
                    "symbol": a.symbol,
                    "position_id": a.position_id,
                    "entry_price": float(a.entry_price),
                    "net_pnl": float(a.net_pnl),
                    "status": a.status,
                    "broker_login": a.broker_login,
                    "closed_at": a.closed_at.isoformat(),
                }
            )
    except Exception as exc:  # pragma: no cover - defensive ops path
        buy_error = str(exc)[:200]
    try:
        from app.domain.institutional_trading.ai_scalping import (
            sell_cascade_anchor_store as sell_store,
        )

        sell_anchors, sell_trusted = sell_store.load_active_anchors()
        for a in sell_anchors:
            if account is not None and a.broker_login not in (None, account):
                continue
            sell_active.append(
                {
                    "symbol": a.symbol,
                    "position_id": a.position_id,
                    "entry_price": float(a.entry_price),
                    "net_pnl": float(a.net_pnl),
                    "status": a.status,
                    "broker_login": a.broker_login,
                    "closed_at": a.closed_at.isoformat(),
                }
            )
    except Exception as exc:  # pragma: no cover - defensive ops path
        sell_error = str(exc)[:200]

    reversal = sum(
        1
        for r in rows
        if "reversal" in str(r.close_reason or "").lower()
        or "structure" in str(r.close_reason or "").lower()
    )
    return {
        "buy_cascade": {
            "active_anchors": len(buy_active),
            "anchors": buy_active,
            "store_trusted": buy_trusted,
            "error": buy_error,
            "historical_block_count": None,
            "note": (
                "Active durable BUY anchors only. Historical block tallies are "
                "not claimed here; blocked entries are not completed trades."
            ),
        },
        "sell_cascade": {
            "active_anchors": len(sell_active),
            "anchors": sell_active,
            "store_trusted": sell_trusted,
            "error": sell_error,
            "historical_block_count": None,
            "note": (
                "Active durable SELL anchors only. No counterfactual $ saved "
                "is asserted without price-path analysis."
            ),
        },
        "reversal": {
            "broker_confirmed_reversal_like_closes": reversal,
            "failed_or_unconfirmed_close_requests": None,
            "note": (
                "Counted from durable outcomes with reversal/structure close "
                "reason. Unconfirmed close requests are not realized P&L."
            ),
        },
        "risk_quality_rejections": {
            "risk_rejections": None,
            "quality_rejections": None,
            "concurrent_position_rejections": None,
            "note": (
                "Process-local rejection tallies live on robot-health / "
                "strategy telemetry; not duplicated as fabricated totals here."
            ),
        },
    }


def build_m1_dashboard_block() -> dict[str, Any]:
    """M1 evaluation vs LIVE submit — never present signals as filled trades."""
    from app.domain.institutional_trading.ai_scalping.strategies.monitoring import (
        _m1_status_block,
    )

    block = dict(_m1_status_block())
    block["broker_confirmed_fills"] = None
    block["signals_evaluated"] = None
    block["qualified_signals"] = None
    block["rejected_signals"] = None
    block["display_rule"] = (
        "M1 signal counts are not completed trades and are not profitability."
    )
    block["m1_live_oms_submission"] = "OFF" if not block.get("m1_live_submit") else "ON"
    return block


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
    post_bucket = build_period_bucket(post182, label="post_pr182", account=broker_login)
    return {
        "as_of": datetime.now(UTC).isoformat(),
        "broker_login": broker_login,
        "reporting_period": "post_pr182",
        "instrument": "XAUUSD",
        "account_12260878_note": (
            "Not included unless broker_login=12260878 is queried separately. "
            "Never merge with 12479147 without an explicit combined label."
        ),
        "periods": periods,
        "post_pr182": post_bucket,
        "overview": post_bucket,
        "five_pack_scorecards_post_pr182": build_five_pack_scorecards(
            post182, account=broker_login
        ),
        "five_pack_scorecards_all_recorded": build_five_pack_scorecards(
            all_rows, account=broker_login
        ),
        "capital_protection": build_capital_protection_snapshot(
            post182, account=broker_login
        ),
        "m1": build_m1_dashboard_block(),
        "features": {
            "changes_trading_decisions": False,
            "observability_only": True,
            "m1_live_submit_unchanged": True,
            "reverse_entry_unchanged": True,
        },
    }
