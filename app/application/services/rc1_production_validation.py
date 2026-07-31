"""Application facade — RC1 Production Validation Pipeline (read-only + runners)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.domain.institutional_trading.rc1_production_validation.config import (
    resolve_validation_runtime,
)
from app.domain.institutional_trading.rc1_production_validation.dashboard import (
    build_validation_dashboard,
)
from app.domain.institutional_trading.rc1_production_validation.paper_engine import (
    get_paper_engine,
)
from app.domain.institutional_trading.rc1_production_validation.pipeline import (
    run_rc1_validation_pipeline,
)
from app.domain.institutional_trading.rc1_production_validation.shadow_engine import (
    get_shadow_journal,
)
from app.domain.institutional_trading.rc1_production_validation.trade_recorder import (
    get_trade_recorder,
)


def get_rc1_validation_status() -> dict[str, Any]:
    cfg = resolve_validation_runtime()
    return {
        "config": cfg.to_dict(),
        "trade_stats": get_trade_recorder().stats(),
        "paper": get_paper_engine().performance(),
        "shadow": get_shadow_journal().stats(),
        "never_modifies_strategy": True,
        "never_lowers_thresholds": True,
    }


def get_rc1_validation_dashboard(
    *,
    infrastructure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_validation_dashboard(infrastructure=infrastructure)


def list_rc1_validation_trades(*, limit: int = 50) -> dict[str, Any]:
    rows = get_trade_recorder().recent(limit=limit)
    return {"trades": rows, "count": len(rows)}


def run_rc1_validation(
    *,
    events: list[dict[str, Any]] | None = None,
    infrastructure: dict[str, Any] | None = None,
    write_report: bool = True,
    report_path: str | None = None,
) -> dict[str, Any]:
    path = Path(report_path) if report_path else None
    return run_rc1_validation_pipeline(
        events=events,
        infrastructure=infrastructure,
        write_report=write_report,
        report_path=path,
    )
