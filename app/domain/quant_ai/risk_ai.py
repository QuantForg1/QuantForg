"""Quant AI — risk health explanations from real account/position facts."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _f(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


# Naive FX base/quote cluster for correlation awareness (observable symbols only).
_USD_PAIRS = {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY"}


def analyze_risk_ai(
    *,
    account: dict[str, Any] | None,
    positions: list[dict[str, Any]],
) -> dict[str, Any]:
    account = account or {}
    equity = _f(account.get("equity"))
    balance = _f(account.get("balance"))
    margin = _f(account.get("margin"))
    free_margin = _f(account.get("free_margin") or account.get("margin_free"))
    leverage = _f(account.get("leverage"), 0.0)

    flags: list[dict[str, str]] = []
    reasons: list[str] = []

    margin_level = None
    if margin > 0 and equity > 0:
        margin_level = equity / margin * 100.0
        if margin_level < 200:
            flags.append(
                {
                    "code": "margin_risk",
                    "severity": "high",
                    "title": "Margin Risk",
                    "detail": f"Margin level ≈ {margin_level:.1f}%",
                }
            )
            reasons.append("Margin level under 200% — capacity to absorb adverse moves is limited")
        elif margin_level < 500:
            flags.append(
                {
                    "code": "margin_risk",
                    "severity": "moderate",
                    "title": "Margin Risk",
                    "detail": f"Margin level ≈ {margin_level:.1f}%",
                }
            )

    if leverage and leverage >= 200:
        flags.append(
            {
                "code": "over_leveraged",
                "severity": "high",
                "title": "Over Leveraged",
                "detail": f"Account leverage {leverage:.0f}x",
            }
        )
        reasons.append(f"Account leverage {leverage:.0f}x amplifies drawdown speed")
    elif leverage and leverage >= 100:
        flags.append(
            {
                "code": "over_leveraged",
                "severity": "moderate",
                "title": "Over Leveraged",
                "detail": f"Account leverage {leverage:.0f}x",
            }
        )

    if free_margin >= 0 and equity > 0 and free_margin / equity < 0.2:
        flags.append(
            {
                "code": "exposure_risk",
                "severity": "high",
                "title": "Exposure Risk",
                "detail": "Free margin under 20% of equity",
            }
        )
        reasons.append("Free margin is thin relative to equity")

    by_symbol: dict[str, float] = defaultdict(float)
    usd_cluster_volume = 0.0
    for p in positions:
        sym = str(p.get("symbol") or "").upper()
        vol = _f(p.get("volume") or p.get("lots"))
        by_symbol[sym] += vol
        if sym in _USD_PAIRS:
            usd_cluster_volume += vol

    if len([s for s, v in by_symbol.items() if v > 0]) >= 3 and usd_cluster_volume > 0:
        flags.append(
            {
                "code": "correlated_positions",
                "severity": "moderate",
                "title": "Too Many Correlated Positions",
                "detail": f"USD-related cluster volume {usd_cluster_volume:.2f}",
            }
        )
        reasons.append("Multiple USD-sensitive symbols open — correlation stacking risk")

    for sym, vol in by_symbol.items():
        if equity > 0 and vol >= 1.0:
            flags.append(
                {
                    "code": "position_size_risk",
                    "severity": "moderate",
                    "title": "Position Size Risk",
                    "detail": f"{sym} size {vol}",
                }
            )
            reasons.append(f"{sym} position size {vol} is large vs typical micro sizing")

    if equity > 0 and balance > 0:
        dd_pct = max(0.0, (balance - equity) / balance * 100.0)
        if dd_pct >= 10:
            flags.append(
                {
                    "code": "drawdown_risk",
                    "severity": "high",
                    "title": "Drawdown Risk",
                    "detail": f"Open equity vs balance drawdown ≈ {dd_pct:.1f}%",
                }
            )
            reasons.append(f"Floating drawdown ≈ {dd_pct:.1f}% of balance")

    if not positions and not flags:
        reasons.append("No open positions — structural portfolio risk is dormant")

    if not reasons:
        reasons.append("No elevated risk flags from current account/position snapshot")

    severity_rank = {"high": 3, "moderate": 2, "low": 1}
    overall = "healthy"
    if any(f["severity"] == "high" for f in flags):
        overall = "stressed"
    elif any(f["severity"] == "moderate" for f in flags):
        overall = "watch"

    flags.sort(key=lambda f: severity_rank.get(f["severity"], 0), reverse=True)

    return {
        "status": "available" if account or positions else "unavailable",
        "overall": overall,
        "margin_level": round(margin_level, 2) if margin_level is not None else None,
        "leverage": leverage or None,
        "flags": flags,
        "why": {
            "summary": f"Risk health: {overall}",
            "supporting_factors": reasons,
        },
        "data_source": "mt5_account|mt5_positions",
        "autonomous_trading": False,
        "advisory_only": True,
        "news_risk": {
            "status": "unavailable",
            "reason": "News risk requires configured economic calendar feed — not invented",
        },
    }
