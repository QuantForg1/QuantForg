"""Release Candidate RC1 executive dashboard — validation & evidence only."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.release_candidate import (
    DEFAULT_RC1_CONFIG,
    advise_capital_scale,
    build_live_statistics,
    build_rc_validation,
    compute_go_live_score,
    get_rc1_reporting_store,
    get_smoke_store,
    get_venue_stats_store,
    guide_summaries,
    run_production_checklist,
    write_rc1_guides,
)
from core.logging import get_logger

logger = get_logger(__name__)


def build_rc1_dashboard(*, current_capital: float = 200.0) -> dict[str, Any]:
    checklist = run_production_checklist()
    live = build_live_statistics()
    validation = build_rc_validation()
    venues = get_venue_stats_store().snapshot()
    smoke_recent = get_smoke_store().recent(limit=5)
    latest_smoke = smoke_recent[0] if smoke_recent else None

    score = compute_go_live_score(
        checklist=checklist,
        validation=validation,
        live_stats=live,
        smoke=latest_smoke,
    )

    stats = live.get("live_statistics") or {}
    wr = stats.get("win_rate")
    dd = stats.get("current_drawdown")
    try:
        wr_f = float(wr) if wr is not None else None
    except (TypeError, ValueError):
        wr_f = None
    try:
        dd_f = float(dd) if dd is not None else None
    except (TypeError, ValueError):
        dd_f = None

    capital = advise_capital_scale(
        current_capital=float(current_capital),
        win_rate=wr_f,
        drawdown_pct=dd_f,
        go_live_score=float(score.get("score") or 0),
    )

    docs_written: list[str] = []
    try:
        docs_written = write_rc1_guides(force=False)
    except Exception:
        logger.exception("rc1_docs_write_failed")

    return {
        "version": DEFAULT_RC1_CONFIG.version,
        "config": DEFAULT_RC1_CONFIG.to_dict(),
        "mission": (
            "Prove profitability, stability, and safety with measurable evidence "
            "before increasing capital. No new strategies. No experimental production logic."
        ),
        "checklist": checklist,
        "smoke_recent": smoke_recent,
        "live_statistics": stats,
        "performance_reports": get_rc1_reporting_store().recent(limit=10),
        "rc_validation": validation,
        "go_live_score": score,
        "venues": venues,
        "capital_advisor": capital,
        "documentation": guide_summaries(),
        "docs_paths": docs_written,
        "safeguards": {
            "smoke_never_places_orders": True,
            "never_auto_scale_capital": True,
            "never_mix_trading_venues": True,
            "no_new_strategies": True,
            "no_experimental_production_logic": True,
        },
    }
