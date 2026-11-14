"""Portfolio-level risk allocation — blocks new orders only."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from app.domain.portfolio_household.aggregation import (
    AccountMetricSlice,
    PositionSlice,
)
from app.domain.portfolio_household.emergency_stops import get_emergency_stop_store
from app.domain.portfolio_household.exposure import rollup_exposure


def _dec(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d


@dataclass(frozen=True, slots=True)
class HouseholdRiskCheck:
    allowed: bool
    block_reason: str | None
    aggregate_open_risk_pct: Decimal | None
    aggregate_open_risk_used_pct: Decimal | None
    max_portfolio_exposure_pct: Decimal | None
    concentration_flags: tuple[str, ...]
    budgets: dict[str, Any]
    methodology: dict[str, Any]


def evaluate_household_risk(
    *,
    accounts: list[AccountMetricSlice],
    positions: list[PositionSlice],
    effective: dict[str, Any] | None,
    proposed_risk_pct: Decimal | None = None,
    proposed_symbol: str | None = None,
    user_id: UUID | None = None,
    broker_account_id: UUID | str | None = None,
    broker_code: str | None = None,
    concentration_threshold_pct: Decimal = Decimal("40"),
) -> HouseholdRiskCheck:
    stop = get_emergency_stop_store().is_armed(
        user_id=user_id,
        broker_account_id=broker_account_id,
        broker_code=broker_code,
    )
    if stop:
        return HouseholdRiskCheck(
            allowed=False,
            block_reason=stop,
            aggregate_open_risk_pct=_dec(
                (effective or {}).get("aggregate_open_risk_pct")
            ),
            aggregate_open_risk_used_pct=None,
            max_portfolio_exposure_pct=None,
            concentration_flags=(),
            budgets={},
            methodology={"gate": "emergency_stop"},
        )

    eff = effective or {}
    agg_cap = _dec(eff.get("aggregate_open_risk_pct"))
    planned_cap = _dec(eff.get("planned_risk_pct"))

    equities = [a.equity for a in accounts if a.equity is not None and a.equity > 0]
    total_equity = sum(equities, Decimal("0")) if equities else None

    # Open risk proxy: sum of |floating| / equity when both known — honest null else.
    used_pct: Decimal | None = None
    if total_equity and total_equity > 0:
        float_sum = sum(
            (abs(a.floating_pnl) for a in accounts if a.floating_pnl is not None),
            Decimal("0"),
        )
        used_pct = (float_sum / total_equity) * Decimal("100")

    exposure = rollup_exposure(
        positions,
        equity=total_equity,
        concentration_threshold_pct=concentration_threshold_pct,
    )
    conc_flags = tuple(
        f"symbol:{b.key}" for b in exposure.by_symbol if b.concentration_flag
    ) + tuple(f"broker:{b.key}" for b in exposure.by_broker if b.concentration_flag)

    block: str | None = None
    if agg_cap is not None and used_pct is not None:
        projected = used_pct + (proposed_risk_pct or Decimal("0"))
        if projected > agg_cap:
            block = (
                f"HOUSEHOLD_RISK: aggregate open risk {projected}% "
                f"exceeds cap {agg_cap}%"
            )

    if (
        block is None
        and proposed_symbol
        and any(
            b.key == proposed_symbol and b.concentration_flag
            for b in exposure.by_symbol
        )
    ):
        block = f"HOUSEHOLD_RISK: symbol concentration limit for {proposed_symbol}"

    budgets: dict[str, Any] = {
        "aggregate_open_risk_pct": str(agg_cap) if agg_cap is not None else None,
        "planned_risk_pct": str(planned_cap) if planned_cap is not None else None,
        "max_lot": eff.get("max_lot"),
        "daily_loss_pct": eff.get("daily_loss_pct"),
        "max_concurrent_positions": eff.get("max_concurrent_positions"),
        "per_broker": {},
        "per_account": {},
        "per_strategy": {},
        "per_symbol": {},
    }

    return HouseholdRiskCheck(
        allowed=block is None,
        block_reason=block,
        aggregate_open_risk_pct=agg_cap,
        aggregate_open_risk_used_pct=used_pct,
        max_portfolio_exposure_pct=concentration_threshold_pct,
        concentration_flags=conc_flags,
        budgets=budgets,
        methodology={
            "open_risk_proxy": "sum_abs_floating_pnl_over_equity",
            "missing_metrics": "fail_open_on_used_pct_null",
            "new_orders_only": True,
            "auto_close": False,
        },
    )


def household_new_entry_block_reason(
    *,
    user_id: UUID | None,
    intent: Any = None,
    broker_account_id: UUID | str | None = None,
    broker_code: str | None = None,
    accounts: list[AccountMetricSlice] | None = None,
    positions: list[PositionSlice] | None = None,
    effective: dict[str, Any] | None = None,
) -> str | None:
    """Thin OMS hook — block new entries only; never manage/close."""
    stop = get_emergency_stop_store().is_armed(
        user_id=user_id,
        broker_account_id=broker_account_id,
        broker_code=broker_code,
    )
    if stop:
        return stop

    # Without a household snapshot, only emergency stops apply (fail open on
    # metrics — RiskEngine + owner limits remain authoritative).
    if accounts is None and effective is None:
        return None

    symbol: str | None = None
    if intent is not None:
        raw = getattr(intent, "symbol", None)
        if raw is not None and hasattr(raw, "value"):
            raw = getattr(raw, "value", None)
        symbol = str(raw) if raw else None

    check = evaluate_household_risk(
        accounts=accounts or [],
        positions=positions or [],
        effective=effective,
        proposed_symbol=symbol,
        user_id=user_id,
        broker_account_id=broker_account_id,
        broker_code=broker_code,
    )
    return check.block_reason
