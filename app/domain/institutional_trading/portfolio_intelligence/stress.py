"""Portfolio stress tests — estimate impact under adverse scenarios."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.portfolio_intelligence.state import PortfolioState

SCENARIOS: tuple[tuple[str, float, str], ...] = (
    ("high_volatility", 0.035, "ATR/vol expansion shock"),
    ("low_liquidity", 0.02, "Thin book — adverse fill + wider stops"),
    ("spread_expansion", 0.012, "Spread blowout on entries/exits"),
    ("news_shock", 0.045, "Event-driven gap against book"),
    ("flash_crash", 0.08, "Sudden liquidity vacuum"),
    ("gap_open", 0.05, "Weekend/session gap through stops"),
)


def run_stress_tests(state: PortfolioState) -> dict[str, Any]:
    equity = state.equity or 1.0
    exposure = sum(abs(v) for v in state.exposure_by_symbol.values()) or (
        state.open_positions * 0.1
    )
    # Normalize exposure to equity fraction proxy
    book = min(1.5, exposure if exposure < 5 else exposure / max(equity, 1.0))
    rows = []
    worst = None
    for name, shock, detail in SCENARIOS:
        # Correlated books amplify
        amp = 1.0 + 0.15 * len(state.open_symbols)
        loss_pct = round(100.0 * book * shock * amp, 3)
        loss_cash = round(equity * loss_pct / 100.0, 2)
        row = {
            "scenario": name,
            "detail": detail,
            "estimated_loss_pct": loss_pct,
            "estimated_loss_cash": loss_cash,
            "open_positions": state.open_positions,
        }
        rows.append(row)
        if worst is None or loss_pct > worst["estimated_loss_pct"]:
            worst = row
    return {
        "scenarios": rows,
        "worst_case": worst,
        "advisory_only": True,
    }
