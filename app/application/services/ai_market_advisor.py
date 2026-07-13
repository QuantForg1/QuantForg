"""Deterministic AI advisor summaries from real platform snapshots.

ADR-0015: advisor only — never places trades or fabricates market facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AiMarketAdvisor:
    """Explain market context / risk / news / exposure using supplied facts only."""

    def summarize(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        broker = snapshot.get("broker") or {}
        account = snapshot.get("account") or {}
        context = snapshot.get("market_context") or {}
        market = snapshot.get("market") or {}
        news = list(snapshot.get("news") or [])
        events = list(snapshot.get("economic_events") or [])
        positions = list(snapshot.get("positions") or [])
        orders = list(snapshot.get("pending_orders") or [])

        connected = bool(broker.get("connected"))
        session = str(context.get("session") or "unknown")
        volatility = str(context.get("volatility_level") or "unknown")
        liquidity = str(context.get("liquidity_level") or "unknown")
        market_state = str(context.get("market_state") or "unknown")

        conditions: list[str] = []
        if connected:
            conditions.append(
                f"Broker session is connected"
                f"{f' ({broker.get('server')})' if broker.get('server') else ''}."
            )
        else:
            conditions.append(
                "Broker is disconnected — quotes, positions, and account figures "
                "are unavailable until MT5 reconnects."
            )
        conditions.append(
            f"Market context for {context.get('market_code', 'FX')}: "
            f"session={session}, state={market_state}, "
            f"volatility={volatility}, liquidity={liquidity}."
        )
        spreads = list(market.get("spread_movers") or [])
        if spreads:
            top = spreads[0]
            conditions.append(
                f"Widest observed spread among sampled symbols: "
                f"{top.get('symbol')} at {top.get('spread')} "
                f"(from live MT5 symbol book, not estimated)."
            )
        else:
            conditions.append(
                "No live symbol book sample is available to report spreads."
            )

        risk_factors: list[str] = []
        if not connected:
            risk_factors.append("No live risk telemetry while disconnected.")
        margin_level = account.get("margin_level")
        if margin_level not in (None, "", "0", "0.0"):
            risk_factors.append(f"Reported margin level: {margin_level}.")
        if positions:
            risk_factors.append(
                f"{len(positions)} open position(s) synced from MT5."
            )
        else:
            risk_factors.append("No open positions in the synced portfolio snapshot.")
        if orders:
            risk_factors.append(f"{len(orders)} pending order(s) synced from MT5.")
        if volatility in {"high", "very_high", "HIGH", "VERY_HIGH"}:
            risk_factors.append(
                "Session volatility profile is elevated — sizing and stops warrant review."
            )

        news_impact: list[str] = []
        if not events and not news:
            news_impact.append(
                "No configured news or economic calendar feed returned items. "
                "QuantForg will not invent headlines or event prints."
            )
        else:
            for ev in events[:5]:
                news_impact.append(
                    f"Calendar: {ev.get('title')} ({ev.get('country') or 'n/a'}) "
                    f"impact={ev.get('impact')} at {ev.get('scheduled_at') or 'n/a'}."
                )
            for item in news[:5]:
                news_impact.append(
                    f"News: {item.get('title')} — source {item.get('source') or 'n/a'}."
                )

        exposure: list[str] = []
        if account:
            exposure.append(
                "Account snapshot (synced): "
                f"balance={account.get('balance')}, equity={account.get('equity')}, "
                f"margin={account.get('margin')}, free_margin={account.get('free_margin')}."
            )
        symbols = sorted(
            {
                str(p.get("symbol"))
                for p in positions
                if p.get("symbol")
            }
        )
        if symbols:
            exposure.append("Position symbols: " + ", ".join(symbols) + ".")
        else:
            exposure.append("No symbol exposure from open positions.")

        disclaimer = (
            "This analysis is advisory only. It uses broker/MT5 snapshots, "
            "deterministic market-context profiles, and configured news feeds. "
            "It does not place trades or invent missing facts."
        )

        return {
            "advisor": "deterministic_market_advisor",
            "autonomous_trading": False,
            "market_conditions": conditions,
            "risk_factors": risk_factors,
            "news_impact": news_impact,
            "portfolio_exposure": exposure,
            "disclaimer": disclaimer,
        }
