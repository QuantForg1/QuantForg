"""Capital allocation engine — dynamic shares from scores/correlation (advisory)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.institutional_trading.portfolio_intelligence.config import (
    DEFAULT_PI_CONFIG,
    PortfolioIntelligenceConfig,
)
from app.domain.institutional_trading.portfolio_intelligence.state import PortfolioState


@dataclass(frozen=True, slots=True)
class AllocationSlice:
    symbol: str
    rank: int
    share_pct: float
    opportunity_score: int
    confidence: int
    expected_rr: float
    correlation_penalty: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "rank": self.rank,
            "share_pct": self.share_pct,
            "opportunity_score": self.opportunity_score,
            "confidence": self.confidence,
            "expected_rr": self.expected_rr,
            "correlation_penalty": self.correlation_penalty,
            "reason": self.reason,
        }


def _corr_penalty(symbol: str, open_symbols: list[str], matrix: dict[str, Any]) -> float:
    row = matrix.get(symbol) if isinstance(matrix.get(symbol), dict) else {}
    if not isinstance(row, dict):
        # fallback: alpha group conflict → heavy penalty
        try:
            from app.domain.institutional_trading.alpha_engine.correlation import (
                may_open_with_correlation,
            )

            d = may_open_with_correlation(candidate_symbol=symbol, open_symbols=open_symbols)
            return 0.85 if not d.allow else 0.0
        except Exception:
            return 0.0
    vals = []
    for peer in open_symbols:
        if peer.upper() == symbol.upper():
            continue
        try:
            vals.append(abs(float(row.get(peer, 0))))
        except Exception:
            continue
    return min(0.9, max(vals) if vals else 0.0)


def allocate_capital(
    opportunities: list[dict[str, Any]],
    state: PortfolioState,
    *,
    risk_budget_pct: float,
    new_exposure_scale: float = 1.0,
    config: PortfolioIntelligenceConfig | None = None,
) -> dict[str, Any]:
    """Rank opportunities and assign dynamic capital shares. Advisory only."""
    cfg = config or DEFAULT_PI_CONFIG
    if cfg.capital_reallocation_auto:
        raise RuntimeError("Automatic capital reallocation is forbidden")

    ranked = sorted(
        opportunities,
        key=lambda o: (
            int(o.get("opportunity_score") or 0),
            int(o.get("ai_confidence") or o.get("confidence") or 0),
            float(o.get("expected_rr") or 0),
        ),
        reverse=True,
    )[:5]

    weights: list[float] = []
    meta: list[dict[str, Any]] = []
    for o in ranked:
        sym = str(o.get("symbol") or "").upper()
        score = int(o.get("opportunity_score") or 0)
        conf = int(o.get("ai_confidence") or o.get("confidence") or 0)
        rr = float(o.get("expected_rr") or 0)
        penalty = _corr_penalty(sym, state.open_symbols, state.correlation_matrix)
        raw = max(0.01, (score / 100.0) * (0.5 + conf / 200.0) * (0.7 + min(rr, 3) / 5.0))
        raw *= max(0.1, 1.0 - penalty)
        weights.append(raw)
        meta.append(
            {
                "symbol": sym,
                "score": score,
                "confidence": conf,
                "expected_rr": rr,
                "correlation_penalty": round(penalty, 3),
                "raw": raw,
            }
        )

    deployable = max(0.0, 1.0 - cfg.reserve_floor) * float(new_exposure_scale)
    total_w = sum(weights) or 1.0
    slices: list[AllocationSlice] = []
    for i, m in enumerate(meta, start=1):
        share = deployable * (m["raw"] / total_w) * 100.0
        slices.append(
            AllocationSlice(
                symbol=m["symbol"],
                rank=i,
                share_pct=round(share, 2),
                opportunity_score=m["score"],
                confidence=m["confidence"],
                expected_rr=m["expected_rr"],
                correlation_penalty=m["correlation_penalty"],
                reason=(
                    f"score={m['score']} conf={m['confidence']} rr={m['expected_rr']} "
                    f"corr_penalty={m['correlation_penalty']} budget={risk_budget_pct}%"
                ),
            )
        )

    skipped = [
        str(o.get("symbol") or "")
        for o in opportunities
        if str(o.get("symbol") or "").upper() not in {s.symbol for s in slices}
    ]

    return {
        "risk_budget_pct": risk_budget_pct,
        "reserve_pct": round(cfg.reserve_floor * 100.0, 2),
        "new_exposure_scale": new_exposure_scale,
        "allocations": [s.to_dict() for s in slices],
        "skipped_symbols": skipped,
        "auto_applied": False,
    }
