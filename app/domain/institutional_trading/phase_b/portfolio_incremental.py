"""Portfolio incremental-risk visibility — does NOT replace hard Risk Engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.institutional_trading.phase_a.control_vocab import FinalControlState


USD_MAJOR_SYMBOLS = frozenset(
    {
        "EURUSD",
        "GBPUSD",
        "AUDUSD",
        "NZDUSD",
        "USDCHF",
        "USDCAD",
        "USDJPY",
    }
)


def currency_factors_for_symbol(symbol: str) -> tuple[str, ...]:
    """Surface shared FX currency factors (esp. USD)."""
    sym = str(symbol or "").upper()
    try:
        from app.domain.institutional_trading.ai_scalping.correlation_book import (
            currency_for,
            normalize_book_symbol,
        )

        canon = normalize_book_symbol(sym) or sym
        cur = currency_for(canon)
        factors: list[str] = []
        if cur:
            factors.append(str(cur).upper())
        if canon in USD_MAJOR_SYMBOLS or "USD" in canon:
            if "USD" not in factors:
                factors.append("USD")
        return tuple(factors) or ("UNKNOWN",)
    except Exception:
        if "USD" in sym:
            return ("USD",)
        return ("UNKNOWN",)


@dataclass(frozen=True, slots=True)
class IncrementalRiskView:
    current_open_risk: float | None
    new_trade_risk: float | None
    correlation_penalty: float | None
    currency_factor_exposure: dict[str, float]
    symbol_exposure: float | None
    directional_exposure: float | None
    projected_total_risk: float | None
    decision: str  # ALLOW | REDUCE | BLOCK
    first_blocking_gate: str | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "CURRENT_PORTFOLIO_RISK": self.current_open_risk,
            "NEW_TRADE_INCREMENTAL_RISK": self.new_trade_risk,
            "PROJECTED_PORTFOLIO_RISK": self.projected_total_risk,
            "current_open_risk": self.current_open_risk,
            "new_trade_risk": self.new_trade_risk,
            "correlation_penalty": self.correlation_penalty,
            "currency_factor_exposure": dict(self.currency_factor_exposure),
            "symbol_exposure": self.symbol_exposure,
            "directional_exposure": self.directional_exposure,
            "projected_total_risk": self.projected_total_risk,
            "decision": self.decision,
            "first_blocking_gate": self.first_blocking_gate,
            "detail": self.detail,
        }


def evaluate_incremental_risk(
    *,
    current_open_risk: float | None = None,
    new_trade_risk: float | None = None,
    max_portfolio_risk: float | None = None,
    correlation_score: float | None = None,
    symbol: str = "",
    symbol_exposure: float | None = None,
    directional_exposure: float | None = None,
    existing_symbols: tuple[str, ...] = (),
    hard_blocked: bool = False,
    hard_block_reason: str | None = None,
    reduce_suggested: bool = False,
) -> IncrementalRiskView:
    """Visibility + map to ALLOW/REDUCE/BLOCK using existing hard ceilings only."""
    factors = currency_factors_for_symbol(symbol)
    # Shared USD factor load among open FX majors
    usd_count = sum(
        1
        for s in existing_symbols
        if str(s).upper() in USD_MAJOR_SYMBOLS or "USD" in str(s).upper()
    )
    if symbol.upper() in USD_MAJOR_SYMBOLS or "USD" in symbol.upper():
        usd_count += 1
    currency_exposure = {f: float(usd_count if f == "USD" else 1.0) for f in factors}

    corr_pen = None
    if correlation_score is not None:
        try:
            corr_pen = max(0.0, min(1.0, float(correlation_score)))
        except Exception:
            corr_pen = None

    cur = float(current_open_risk) if current_open_risk is not None else None
    nxt = float(new_trade_risk) if new_trade_risk is not None else None
    projected = None
    if cur is not None and nxt is not None:
        projected = cur + nxt
        if corr_pen is not None and corr_pen > 0:
            # Observational penalty inflate — does not change sizing
            projected = cur + nxt * (1.0 + 0.25 * corr_pen)

    decision = FinalControlState.ALLOW.value
    gate: str | None = None
    detail = "within existing hard ceilings"

    if hard_blocked:
        decision = FinalControlState.BLOCK.value
        gate = hard_block_reason or "PORTFOLIO_HARD_LIMIT"
        detail = "existing hard risk/portfolio gate blocked"
    elif max_portfolio_risk is not None and projected is not None:
        if projected > float(max_portfolio_risk):
            decision = FinalControlState.BLOCK.value
            gate = "PROJECTED_PORTFOLIO_RISK_CEILING"
            detail = "projected risk exceeds existing ceiling (observational map)"
        elif projected > float(max_portfolio_risk) * 0.85 or reduce_suggested:
            decision = FinalControlState.REDUCE.value
            gate = "NEAR_PORTFOLIO_CEILING"
            detail = "near existing ceiling — REDUCE visibility only"
    elif reduce_suggested:
        decision = FinalControlState.REDUCE.value
        gate = "EXISTING_RISK_REDUCE"
        detail = "existing risk path suggested reduce"

    # Same-symbol duplicate visibility
    if symbol and any(str(s).upper() == symbol.upper() for s in existing_symbols):
        if decision == FinalControlState.ALLOW.value:
            decision = FinalControlState.REDUCE.value
            gate = gate or "SAME_SYMBOL_EXPOSURE"
            detail = "same-symbol exposure already open"

    return IncrementalRiskView(
        current_open_risk=cur,
        new_trade_risk=nxt,
        correlation_penalty=corr_pen,
        currency_factor_exposure=currency_exposure,
        symbol_exposure=symbol_exposure,
        directional_exposure=directional_exposure,
        projected_total_risk=projected,
        decision=decision,
        first_blocking_gate=gate,
        detail=detail,
    )
