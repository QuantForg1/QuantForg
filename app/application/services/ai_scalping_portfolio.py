"""Application façade — multi-asset institutional scalping scan (v7)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.ai_scalping.portfolio_risk import (
    aggregate_portfolio_risk,
)
from app.domain.institutional_trading.ai_scalping.portfolio_scanner import (
    PortfolioScanResult,
    scan_multi_asset_portfolio,
)
from app.domain.institutional_trading.ai_scalping.portfolio_scheduler import (
    get_multi_asset_scheduler,
)
from app.domain.institutional_trading.ai_scalping.symbol_state import (
    get_symbol_state_book,
)
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import AccountRiskState


def run_multi_asset_scan(
    scored: list[dict[str, Any]],
    *,
    account: AccountRiskState | None = None,
    open_positions: int | None = None,
    daily_loss_pct: Decimal | float | str | None = None,
    exposure_pct: Decimal | float | str | None = None,
    position_risk_pcts: Sequence[Decimal] | None = None,
    ite_config: ITEConfig | None = None,
    config: AiScalpingConfig | None = None,
) -> dict[str, Any]:
    """Begin scheduler cycle → aggregate portfolio risk → scan/rank → complete."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    sched = get_multi_asset_scheduler(cfg)
    cycle = sched.begin_cycle()
    risk = aggregate_portfolio_risk(
        account,
        config=cfg,
        ite_config=ite_config,
        position_risk_pcts=position_risk_pcts,
        open_positions_override=open_positions,
    )
    result: PortfolioScanResult = scan_multi_asset_portfolio(
        scored,
        account=account,
        open_positions=open_positions if open_positions is not None else risk.open_positions,
        daily_loss_pct=(
            daily_loss_pct if daily_loss_pct is not None else risk.daily_loss_pct
        ),
        exposure_pct=exposure_pct if exposure_pct is not None else risk.exposure_pct,
        max_open_positions=risk.max_open_positions,
        max_daily_loss_pct=risk.max_daily_loss_pct,
        max_exposure_pct=risk.max_exposure_pct,
        ite_config=ite_config,
        position_risk_pcts=list(position_risk_pcts) if position_risk_pcts else None,
        config=cfg,
        state_book=get_symbol_state_book(),
    )
    best_sym = None
    if result.best:
        best_sym = str(result.best.get("symbol") or "") or None
    sched.complete_cycle(
        best_symbol=best_sym,
        eligible_count=len(result.ranked),
    )
    payload = result.to_dict()
    payload["portfolio_risk"] = risk.to_dict()
    payload["scheduler"] = sched.snapshot()
    payload["cycle"] = cycle
    payload["symbol_state"] = get_symbol_state_book().snapshot(cfg.universe)
    return payload
