"""Capital Scaling Advisor — recommendations only; never auto-increases capital."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.release_candidate.config import (
    DEFAULT_RC1_CONFIG,
)


def advise_capital_scale(
    *,
    current_capital: float,
    win_rate: float | None = None,
    drawdown_pct: float | None = None,
    sharpe: float | None = None,
    go_live_score: float | None = None,
) -> dict[str, Any]:
    """Suggest next capital step. Hard lock: never applies automatically."""
    cfg = DEFAULT_RC1_CONFIG
    assert cfg.never_auto_scale_capital is True

    reasons: list[str] = []
    blockers: list[str] = []

    if win_rate is not None:
        if win_rate >= cfg.min_win_rate_for_scale:
            reasons.append(f"Stable win rate ({win_rate:.1f}% ≥ {cfg.min_win_rate_for_scale}%)")
        else:
            blockers.append(f"Win rate {win_rate:.1f}% below {cfg.min_win_rate_for_scale}%")

    if drawdown_pct is not None:
        if abs(drawdown_pct) <= cfg.max_drawdown_pct_for_scale:
            reasons.append(
                f"Drawdown {abs(drawdown_pct):.1f}% within {cfg.max_drawdown_pct_for_scale}% threshold"
            )
        else:
            blockers.append(
                f"Drawdown {abs(drawdown_pct):.1f}% exceeds {cfg.max_drawdown_pct_for_scale}%"
            )

    if sharpe is not None:
        if sharpe >= cfg.min_sharpe_for_scale:
            reasons.append(f"Sharpe {sharpe:.2f} ≥ {cfg.min_sharpe_for_scale}")
        else:
            blockers.append(f"Sharpe {sharpe:.2f} below {cfg.min_sharpe_for_scale}")

    if go_live_score is not None:
        if go_live_score >= cfg.go_live_score_threshold:
            reasons.append(
                f"Go Live Score {go_live_score:.1f} ≥ threshold {cfg.go_live_score_threshold}"
            )
        else:
            blockers.append(
                f"Go Live Score {go_live_score:.1f} below {cfg.go_live_score_threshold}"
            )

    eligible = len(blockers) == 0 and len(reasons) > 0
    factor = min(cfg.capital_scale_factor, cfg.max_suggested_scale_factor)
    suggested = round(float(current_capital) * factor, 2) if eligible else float(current_capital)

    return {
        "current_capital": float(current_capital),
        "suggested_next_capital": suggested if eligible else None,
        "eligible": eligible,
        "reasons": reasons,
        "blockers": blockers,
        "auto_applied": False,
        "never_auto_scale_capital": True,
        "message": (
            f"Suggested next capital: ${suggested:,.2f}"
            if eligible
            else "Do not increase capital yet — resolve blockers and continue evidence collection."
        ),
    }
