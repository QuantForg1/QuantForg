"""Deterministic stress scenarios applied to open positions only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PositionShockInput:
    symbol: str
    side: str  # buy | sell
    volume: float
    price: float
    profit: float
    margin_share: float  # portion of account margin attributed


@dataclass(frozen=True, slots=True)
class StressScenarioDef:
    key: str
    name: str
    kind: str  # model_assumption | historical_from_deals
    description: str
    # For model assumptions: adverse price move fraction (positive number)
    price_shock_pct: float | None = None
    spread_widen_pct: float | None = None
    margin_mult: float | None = None


MODEL_SCENARIOS: tuple[StressScenarioDef, ...] = (
    StressScenarioDef(
        key="flash_crash",
        name="Flash Crash",
        kind="model_assumption",
        description="Assumed -5% adverse price move on all open positions",
        price_shock_pct=5.0,
    ),
    StressScenarioDef(
        key="high_volatility",
        name="High Volatility",
        kind="model_assumption",
        description="Assumed -3% adverse price move on all open positions",
        price_shock_pct=3.0,
    ),
    StressScenarioDef(
        key="spread_widening",
        name="Spread Widening",
        kind="model_assumption",
        description="Assumed 0.2% extra cost of volumexprice (spread proxy)",
        spread_widen_pct=0.2,
    ),
    StressScenarioDef(
        key="margin_compression",
        name="Margin Compression",
        kind="model_assumption",
        description="Assumed margin requirement x2 on current margin",
        margin_mult=2.0,
    ),
    StressScenarioDef(
        key="drawdown_shock",
        name="Drawdown Shock",
        kind="model_assumption",
        description="Assumed -8% adverse price move on all open positions",
        price_shock_pct=8.0,
    ),
)


def shock_pnl(pos: PositionShockInput, price_shock_pct: float) -> float:
    """Adverse PnL for a signed position under a price shock percentage."""
    notional = abs(pos.volume * pos.price)
    move = notional * (price_shock_pct / 100.0)
    # Adverse: long loses on down move; short loses on up move — use absolute adverse
    return -move


def apply_model_scenario(
    scenario: StressScenarioDef,
    positions: list[PositionShockInput],
    *,
    equity: float,
    margin: float,
) -> dict[str, Any]:
    if not positions:
        return {
            "key": scenario.key,
            "name": scenario.name,
            "kind": scenario.kind,
            "status": "unavailable",
            "reason": "No open positions to stress",
            "assumption": scenario.description,
            "data_source": "open_positions",
        }

    impact = 0.0
    details: list[dict[str, Any]] = []
    if scenario.price_shock_pct is not None:
        for p in positions:
            pnl = shock_pnl(p, scenario.price_shock_pct)
            impact += pnl
            details.append(
                {
                    "symbol": p.symbol,
                    "impact_pnl": round(pnl, 4),
                    "shock_pct": scenario.price_shock_pct,
                }
            )
    if scenario.spread_widen_pct is not None:
        for p in positions:
            cost = -abs(p.volume * p.price) * (scenario.spread_widen_pct / 100.0)
            impact += cost
            details.append(
                {
                    "symbol": p.symbol,
                    "impact_pnl": round(cost, 4),
                    "spread_widen_pct": scenario.spread_widen_pct,
                }
            )

    post_equity = equity + impact
    margin_after = margin
    margin_note = None
    if scenario.margin_mult is not None:
        margin_after = margin * scenario.margin_mult
        margin_note = f"margin x{scenario.margin_mult}"
        free = post_equity - margin_after
        details.append(
            {
                "symbol": "*",
                "margin_after": round(margin_after, 4),
                "free_margin_after": round(free, 4),
            }
        )

    return {
        "key": scenario.key,
        "name": scenario.name,
        "kind": scenario.kind,
        "status": "available",
        "assumption": scenario.description,
        "impact_pnl": round(impact, 4),
        "equity_before": round(equity, 4),
        "equity_after": round(post_equity, 4),
        "equity_change_pct": (
            round((impact / equity) * 100.0, 4) if equity > 0 else None
        ),
        "margin_before": round(margin, 4),
        "margin_after": round(margin_after, 4),
        "margin_note": margin_note,
        "details": details,
        "data_source": "open_positions + declared_model_assumption",
        "autonomous_trading": False,
    }


def historical_from_deals(
    deal_pnls_by_day: dict[str, float],
    *,
    equity: float,
) -> list[dict[str, Any]]:
    """Build historical stress rows from real daily deal aggregates only."""
    if len(deal_pnls_by_day) < 1:
        return [
            {
                "key": "historical_worst_day",
                "name": "Historical Worst Day",
                "kind": "historical_from_deals",
                "status": "unavailable",
                "reason": "No deal PnL history available",
                "data_source": "history_deals",
            },
            {
                "key": "historical_worst_week",
                "name": "Historical Worst Week",
                "kind": "historical_from_deals",
                "status": "unavailable",
                "reason": "No deal PnL history available",
                "data_source": "history_deals",
            },
        ]

    days = sorted(deal_pnls_by_day.items(), key=lambda x: x[1])
    worst_day_key, worst_day_pnl = days[0]
    week_rows: list[dict[str, Any]] = [
        {
            "key": "historical_worst_day",
            "name": "Historical Worst Day",
            "kind": "historical_from_deals",
            "status": "available",
            "assumption": f"Replay of worst observed deal-day PnL ({worst_day_key})",
            "impact_pnl": round(worst_day_pnl, 4),
            "equity_before": round(equity, 4),
            "equity_after": round(equity + worst_day_pnl, 4),
            "equity_change_pct": (
                round((worst_day_pnl / equity) * 100.0, 4) if equity > 0 else None
            ),
            "data_source": "history_deals.daily_aggregate",
            "autonomous_trading": False,
        }
    ]

    # Rolling 5-trading-day windows on sorted date keys
    ordered = sorted(deal_pnls_by_day.items(), key=lambda x: x[0])
    if len(ordered) < 5:
        week_rows.append(
            {
                "key": "historical_worst_week",
                "name": "Historical Worst Week",
                "kind": "historical_from_deals",
                "status": "unavailable",
                "reason": f"Need >=5 deal-days for week window (have {len(ordered)})",
                "data_source": "history_deals",
            }
        )
    else:
        worst_sum = None
        worst_label = ""
        for i in range(len(ordered) - 4):
            window = ordered[i : i + 5]
            s = sum(p for _, p in window)
            if worst_sum is None or s < worst_sum:
                worst_sum = s
                worst_label = f"{window[0][0]}→{window[-1][0]}"
        assert worst_sum is not None
        week_rows.append(
            {
                "key": "historical_worst_week",
                "name": "Historical Worst Week",
                "kind": "historical_from_deals",
                "status": "available",
                "assumption": f"Worst 5-deal-day window ({worst_label})",
                "impact_pnl": round(worst_sum, 4),
                "equity_before": round(equity, 4),
                "equity_after": round(equity + worst_sum, 4),
                "equity_change_pct": (
                    round((worst_sum / equity) * 100.0, 4) if equity > 0 else None
                ),
                "data_source": "history_deals.daily_aggregate",
                "autonomous_trading": False,
            }
        )
    return week_rows
