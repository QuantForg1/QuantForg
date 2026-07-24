"""Portfolio Intelligence service — risk laboratory over real portfolio data."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.portfolio_intelligence import (
    MODEL_SCENARIOS,
    PositionShockInput,
    analyze_trades,
    apply_model_scenario,
    attribute_returns,
    classify_currency,
    classify_sector,
    cluster_labels,
    correlation_matrix,
    diversification_score,
    expected_shortfall,
    herfindahl,
    historical_from_deals,
    historical_var,
    optimize_allocations,
)


def _f(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _day_key(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date().isoformat()
    try:
        return (
            datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date().isoformat()
        )
    except ValueError:
        return None


@dataclass
class PortfolioIntelligenceService:
    """Compute risk lab analytics from supplied portfolio/history snapshots.

    Never invents market data. Never places trades.
    """

    def build_lab(
        self,
        *,
        account: dict[str, Any] | None,
        positions: list[dict[str, Any]],
        deals: list[dict[str, Any]],
        paper_trades: list[dict[str, Any]] | None = None,
        confidence: float = 0.95,
        optimize: dict[str, Any] | None = None,
        portfolio_available: bool = True,
        portfolio_unavailable_reason: str | None = None,
    ) -> dict[str, Any]:
        trades = list(deals) + list(paper_trades or [])
        risk = self.compute_risk(
            account=account,
            positions=positions,
            deals=deals,
            confidence=confidence,
            portfolio_available=portfolio_available,
            portfolio_unavailable_reason=portfolio_unavailable_reason,
        )
        stress = self.compute_stress(
            account=account,
            positions=positions,
            deals=deals,
            portfolio_available=portfolio_available,
        )
        corr = self.compute_correlation(positions=positions, deals=deals)
        journal = analyze_trades(trades)
        attribution = attribute_returns(trades)
        opt_constraints = optimize or {}
        optimizer = self.compute_optimizer(
            positions=positions,
            deals=deals,
            max_risk_pct=_f(opt_constraints.get("max_risk_pct"), 100.0),
            max_allocation_pct=_f(opt_constraints.get("max_allocation_pct"), 40.0),
            target_volatility=(
                _f(opt_constraints["target_volatility"])
                if opt_constraints.get("target_volatility") is not None
                else None
            ),
            target_return=(
                _f(opt_constraints["target_return"])
                if opt_constraints.get("target_return") is not None
                else None
            ),
        )
        return {
            "portfolio_available": portfolio_available,
            "portfolio_unavailable_reason": portfolio_unavailable_reason,
            "risk": risk,
            "stress": stress,
            "correlation": corr,
            "journal": journal,
            "attribution": attribution,
            "optimizer": optimizer,
            "execution_policy": {
                "autonomous_trading": False,
                "live_requires": "EXECUTION_ENABLED=true",
                "default_path": "paper_or_manual",
            },
        }

    def compute_risk(
        self,
        *,
        account: dict[str, Any] | None,
        positions: list[dict[str, Any]],
        deals: list[dict[str, Any]],
        confidence: float = 0.95,
        portfolio_available: bool = True,
        portfolio_unavailable_reason: str | None = None,
    ) -> dict[str, Any]:
        if not portfolio_available:
            return {
                "status": "unavailable",
                "reason": portfolio_unavailable_reason
                or "Portfolio snapshot unavailable",
                "data_source": "mt5_portfolio_sync",
            }

        equity = _f((account or {}).get("equity"))
        balance = _f((account or {}).get("balance"))
        margin = _f((account or {}).get("margin"))
        leverage = int(_f((account or {}).get("leverage"), 0))
        currency = str((account or {}).get("currency") or "UNK")

        notionals: list[tuple[str, float]] = []
        sector_exp: dict[str, float] = defaultdict(float)
        ccy_exp: dict[str, float] = defaultdict(float)
        for p in positions:
            symbol = str(p.get("symbol") or "").upper()
            vol = _f(p.get("volume"))
            price = _f(p.get("current_price") or p.get("open_price"))
            notional = abs(vol * price)
            notionals.append((symbol, notional))
            sector_exp[classify_sector(symbol)] += notional
            ccy_exp[classify_currency(symbol)] += notional

        total_exposure = sum(n for _, n in notionals)
        exposure_pct = (total_exposure / equity * 100.0) if equity > 0 else None
        margin_usage_pct = (margin / equity * 100.0) if equity > 0 else None
        # Account leverage from broker; effective leverage from exposure
        effective_leverage = (total_exposure / equity) if equity > 0 else None

        weights = [n for _, n in notionals]
        concentration = herfindahl(weights)

        deal_pnls = [_f(d.get("profit")) for d in deals]
        var = historical_var(deal_pnls, confidence)
        cvar = expected_shortfall(deal_pnls, confidence)

        return {
            "status": "available",
            "data_source": "mt5_portfolio_sync + history_deals",
            "account_currency": currency,
            "equity": equity,
            "balance": balance,
            "metrics": {
                "portfolio_var": var,
                "portfolio_var_confidence": confidence,
                "portfolio_var_status": (
                    "available" if var is not None else "unavailable"
                ),
                "portfolio_var_reason": (
                    None
                    if var is not None
                    else f"Need >=5 deal PnLs for VaR (have {len(deal_pnls)})"
                ),
                "expected_shortfall": cvar,
                "expected_shortfall_status": (
                    "available" if cvar is not None else "unavailable"
                ),
                "exposure": round(total_exposure, 4),
                "exposure_pct_equity": (
                    round(exposure_pct, 4) if exposure_pct is not None else None
                ),
                "leverage_account": leverage,
                "leverage_effective": (
                    round(effective_leverage, 4)
                    if effective_leverage is not None
                    else None
                ),
                "margin": margin,
                "margin_usage_pct": (
                    round(margin_usage_pct, 4) if margin_usage_pct is not None else None
                ),
                "concentration_hhi": round(concentration, 6),
                "position_count": len(positions),
            },
            "sector_allocation": [
                {
                    "sector": k,
                    "exposure": round(v, 4),
                    "weight_pct": (
                        round(v / total_exposure * 100.0, 4)
                        if total_exposure > 0
                        else 0.0
                    ),
                }
                for k, v in sorted(sector_exp.items(), key=lambda x: -x[1])
            ],
            "currency_allocation": [
                {
                    "currency": k,
                    "exposure": round(v, 4),
                    "weight_pct": (
                        round(v / total_exposure * 100.0, 4)
                        if total_exposure > 0
                        else 0.0
                    ),
                }
                for k, v in sorted(ccy_exp.items(), key=lambda x: -x[1])
            ],
            "position_weights": [
                {
                    "symbol": s,
                    "exposure": round(n, 4),
                    "weight_pct": (
                        round(n / total_exposure * 100.0, 4)
                        if total_exposure > 0
                        else 0.0
                    ),
                }
                for s, n in sorted(notionals, key=lambda x: -x[1])
            ],
        }

    def compute_stress(
        self,
        *,
        account: dict[str, Any] | None,
        positions: list[dict[str, Any]],
        deals: list[dict[str, Any]],
        portfolio_available: bool = True,
    ) -> dict[str, Any]:
        if not portfolio_available:
            return {
                "status": "unavailable",
                "reason": "Portfolio unavailable for stress testing",
                "scenarios": [],
            }
        equity = _f((account or {}).get("equity"))
        margin = _f((account or {}).get("margin"))
        shocks: list[PositionShockInput] = []
        for p in positions:
            shocks.append(
                PositionShockInput(
                    symbol=str(p.get("symbol") or "").upper(),
                    side=str(p.get("side") or "buy").lower(),
                    volume=_f(p.get("volume")),
                    price=_f(p.get("current_price") or p.get("open_price")),
                    profit=_f(p.get("profit")),
                    margin_share=0.0,
                )
            )
        scenarios = [
            apply_model_scenario(s, shocks, equity=equity, margin=margin)
            for s in MODEL_SCENARIOS
        ]
        by_day: dict[str, float] = defaultdict(float)
        for d in deals:
            day = _day_key(d.get("time"))
            if day:
                by_day[day] += _f(d.get("profit"))
        scenarios.extend(historical_from_deals(dict(by_day), equity=equity))
        return {
            "status": "available",
            "scenarios": scenarios,
            "note": (
                "Model scenarios use declared assumptions on open positions; "
                "historical scenarios use deal aggregates only"
            ),
        }

    def compute_correlation(
        self,
        *,
        positions: list[dict[str, Any]],
        deals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        symbols = sorted(
            {str(p.get("symbol") or "").upper() for p in positions if p.get("symbol")}
        )
        if len(symbols) < 2:
            # Still allow deal-based symbols
            symbols = sorted(
                {str(d.get("symbol") or "").upper() for d in deals if d.get("symbol")}
            )
        by_sym_day: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        for d in deals:
            sym = str(d.get("symbol") or "").upper()
            day = _day_key(d.get("time"))
            if not sym or not day:
                continue
            by_sym_day[sym][day] += _f(d.get("profit"))

        series: dict[str, list[float]] = {}
        for sym in symbols:
            days = sorted(by_sym_day.get(sym, {}).items(), key=lambda x: x[0])
            series[sym] = [v for _, v in days]

        if len(symbols) < 2:
            return {
                "status": "unavailable",
                "reason": "Need >=2 symbols with history for correlation",
                "labels": symbols,
                "matrix": [],
                "heatmap": [],
                "clusters": [],
                "diversification_score": None,
                "data_source": "history_deals.daily_by_symbol",
            }

        labels, matrix, notes = correlation_matrix(
            {s: series.get(s, []) for s in symbols}
        )
        computed = sum(
            1
            for i in range(len(labels))
            for j in range(i + 1, len(labels))
            if matrix[i][j] is not None
        )
        if computed == 0:
            return {
                "status": "unavailable",
                "reason": (
                    "Insufficient overlapping daily deal PnLs "
                    "(need >=5 overlapping days per pair)"
                ),
                "labels": labels,
                "matrix": matrix,
                "notes": notes,
                "heatmap": [],
                "clusters": [],
                "diversification_score": None,
                "data_source": "history_deals.daily_by_symbol",
            }

        heatmap = []
        for i, a in enumerate(labels):
            for j, b in enumerate(labels):
                heatmap.append(
                    {
                        "x": a,
                        "y": b,
                        "value": matrix[i][j],
                        "note": notes[i][j],
                    }
                )
        div = diversification_score(matrix)
        return {
            "status": "available",
            "labels": labels,
            "matrix": matrix,
            "notes": notes,
            "heatmap": heatmap,
            "clusters": cluster_labels(labels, matrix),
            "diversification_score": div,
            "diversification_status": (
                "available" if div is not None else "unavailable"
            ),
            "data_source": "history_deals.daily_by_symbol",
        }

    def compute_optimizer(
        self,
        *,
        positions: list[dict[str, Any]],
        deals: list[dict[str, Any]],
        max_risk_pct: float = 100.0,
        max_allocation_pct: float = 40.0,
        target_volatility: float | None = None,
        target_return: float | None = None,
    ) -> dict[str, Any]:
        notionals: dict[str, float] = defaultdict(float)
        for p in positions:
            symbol = str(p.get("symbol") or "").upper()
            if not symbol:
                continue
            notionals[symbol] += abs(
                _f(p.get("volume")) * _f(p.get("current_price") or p.get("open_price"))
            )
        symbols = sorted(notionals.keys())
        total = sum(notionals.values())
        current = {s: (notionals[s] / total if total > 0 else 0.0) for s in symbols}
        by_sym: dict[str, list[float]] = defaultdict(list)
        for d in deals:
            sym = str(d.get("symbol") or "").upper()
            if sym:
                by_sym[sym].append(_f(d.get("profit")))
        return optimize_allocations(
            symbols=symbols,
            current_weights=current,
            pnl_series=dict(by_sym),
            max_risk_pct=max_risk_pct,
            max_allocation_pct=max_allocation_pct,
            target_volatility=target_volatility,
            target_return=target_return,
        )
