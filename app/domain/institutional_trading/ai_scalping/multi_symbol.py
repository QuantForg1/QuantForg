"""Multi-symbol opportunity ranking — trade only the highest quality setup."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    DEFAULT_SCALPING_UNIVERSE,
    AiScalpingConfig,
)


def rank_scalping_opportunities(
    scored: list[dict[str, Any]],
    *,
    config: AiScalpingConfig | None = None,
) -> dict[str, Any]:
    """Pick best non-rejected BUY/SELL opportunity across the universe."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    universe = set(cfg.universe or DEFAULT_SCALPING_UNIVERSE)
    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in scored:
        sym = str(row.get("symbol") or "").upper()
        if universe and sym and sym not in universe:
            continue
        if row.get("reject"):
            rejected.append(row)
            continue
        if str(row.get("direction") or "").upper() not in {"BUY", "SELL"}:
            rejected.append(
                {**row, "reject_reason": row.get("reject_reason") or "No direction"}
            )
            continue
        eligible.append(row)

    eligible.sort(
        key=lambda r: (
            -int(r.get("ai_confidence") or r.get("confidence") or 0),
            -float(r.get("expected_rr") or 0),
            -int(r.get("trade_quality") or 0),
            # Ascending symbol tie-break — identical inputs ⇒ identical order
            str(r.get("symbol") or "").upper(),
        ),
    )
    best = eligible[0] if eligible else None
    return {
        "universe": list(cfg.universe),
        "eligible_count": len(eligible),
        "rejected_count": len(rejected),
        "best": best,
        "ranked": eligible[:10],
        "rejected_sample": rejected[:20],
        "note": (
            "Trade only the highest quality opportunity — never grid/martingale. "
            "Ties break by symbol ascending for deterministic ordering."
        ),
    }
