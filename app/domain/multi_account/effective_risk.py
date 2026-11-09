"""Strictest-of-three effective risk resolution.

User may propose only the five editable knobs. Admin supplies allowed
ranges and platform defaults. Global hard ceilings come from
``owner_live_limits`` and can never be exceeded.

Missing or invalid inputs fail closed (block new entries) — never
substitute a more permissive default for LIVE eligibility.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.institutional_trading.owner_live_limits import (
    OWNER_DAILY_LOSS_PCT,
    OWNER_MAX_AGGREGATE_OPEN_RISK_PCT,
    OWNER_MAX_LOT,
    OWNER_MAX_OPEN_POSITIONS,
    OWNER_MAX_PLANNED_RISK_PCT,
)

USER_EDITABLE_RISK_KEYS = frozenset(
    {
        "planned_risk_pct",
        "aggregate_open_risk_pct",
        "max_lot",
        "daily_loss_pct",
        "max_concurrent_positions",
    }
)

ADMIN_ONLY_RISK_KEYS = frozenset(
    {
        "stop_atr_multiplier",
        "xauusd_commission",
        "max_spread",
        "min_trade_quality",
        "min_reward_risk",
    }
)


def _dec(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


@dataclass(frozen=True, slots=True)
class RiskSettingProposal:
    """User-requested values for the five editable settings."""

    planned_risk_pct: Decimal | None = None
    aggregate_open_risk_pct: Decimal | None = None
    max_lot: Decimal | None = None
    daily_loss_pct: Decimal | None = None
    max_concurrent_positions: int | None = None


@dataclass(frozen=True, slots=True)
class EffectiveRiskProfile:
    """Resolved limits after strictest-of-three enforcement."""

    planned_risk_pct: Decimal
    aggregate_open_risk_pct: Decimal
    max_lot: Decimal
    daily_loss_pct: Decimal
    max_concurrent_positions: int
    ok: bool
    block_reason: str | None = None
    rejected_fields: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "planned_risk_pct": str(self.planned_risk_pct),
            "aggregate_open_risk_pct": str(self.aggregate_open_risk_pct),
            "max_lot": str(self.max_lot),
            "daily_loss_pct": str(self.daily_loss_pct),
            "max_concurrent_positions": self.max_concurrent_positions,
            "ok": self.ok,
            "block_reason": self.block_reason,
            "rejected_fields": list(self.rejected_fields),
        }


def _clip_pct(
    *,
    user: Decimal | None,
    admin_max: Decimal | None,
    hard_ceiling: Decimal,
) -> tuple[Decimal | None, str | None]:
    """Return effective percent (strictest) or None + reason if invalid."""
    if user is None:
        return None, "missing_user_value"
    if user <= 0:
        return None, "non_positive"
    ceiling = hard_ceiling
    if admin_max is not None:
        if admin_max <= 0:
            return None, "invalid_admin_max"
        ceiling = min(ceiling, admin_max)
    if user > ceiling:
        return None, "exceeds_allowed_ceiling"
    return user, None


def _clip_lot(
    *,
    user: Decimal | None,
    admin_max: Decimal | None,
    hard_ceiling: Decimal,
) -> tuple[Decimal | None, str | None]:
    if user is None:
        return None, "missing_user_value"
    if user <= 0:
        return None, "non_positive"
    ceiling = hard_ceiling
    if admin_max is not None:
        if admin_max <= 0:
            return None, "invalid_admin_max"
        ceiling = min(ceiling, admin_max)
    if user > ceiling:
        return None, "exceeds_allowed_ceiling"
    return user, None


def _clip_positions(
    *,
    user: int | None,
    admin_max: int | None,
    hard_ceiling: int,
) -> tuple[int | None, str | None]:
    if user is None:
        return None, "missing_user_value"
    if user < 1:
        return None, "non_positive"
    ceiling = hard_ceiling
    if admin_max is not None:
        if admin_max < 1:
            return None, "invalid_admin_max"
        ceiling = min(ceiling, admin_max)
    if user > ceiling:
        return None, "exceeds_allowed_ceiling"
    return user, None


def resolve_effective_risk(
    proposal: RiskSettingProposal,
    *,
    admin_maxima: Mapping[str, object] | None = None,
) -> EffectiveRiskProfile:
    """Compute effective risk. Fail closed on any invalid editable field."""
    admin = dict(admin_maxima or {})
    rejected: list[str] = []

    planned, planned_err = _clip_pct(
        user=proposal.planned_risk_pct,
        admin_max=_dec(admin.get("planned_risk_pct")),
        hard_ceiling=OWNER_MAX_PLANNED_RISK_PCT,
    )
    if planned_err:
        rejected.append(f"planned_risk_pct:{planned_err}")

    aggregate, aggregate_err = _clip_pct(
        user=proposal.aggregate_open_risk_pct,
        admin_max=_dec(admin.get("aggregate_open_risk_pct")),
        hard_ceiling=OWNER_MAX_AGGREGATE_OPEN_RISK_PCT,
    )
    if aggregate_err:
        rejected.append(f"aggregate_open_risk_pct:{aggregate_err}")

    max_lot, lot_err = _clip_lot(
        user=proposal.max_lot,
        admin_max=_dec(admin.get("max_lot")),
        hard_ceiling=OWNER_MAX_LOT,
    )
    if lot_err:
        rejected.append(f"max_lot:{lot_err}")

    daily, daily_err = _clip_pct(
        user=proposal.daily_loss_pct,
        admin_max=_dec(admin.get("daily_loss_pct")),
        hard_ceiling=OWNER_DAILY_LOSS_PCT,
    )
    if daily_err:
        rejected.append(f"daily_loss_pct:{daily_err}")

    concurrent_raw = proposal.max_concurrent_positions
    admin_concurrent = admin.get("max_concurrent_positions")
    admin_concurrent_i: int | None = None
    if admin_concurrent is not None:
        try:
            admin_concurrent_i = int(str(admin_concurrent))
        except (TypeError, ValueError):
            rejected.append("max_concurrent_positions:invalid_admin_max")

    concurrent, concurrent_err = _clip_positions(
        user=concurrent_raw,
        admin_max=admin_concurrent_i,
        hard_ceiling=OWNER_MAX_OPEN_POSITIONS,
    )
    if concurrent_err:
        rejected.append(f"max_concurrent_positions:{concurrent_err}")

    if rejected or None in (planned, aggregate, max_lot, daily, concurrent):
        return EffectiveRiskProfile(
            planned_risk_pct=OWNER_MAX_PLANNED_RISK_PCT,
            aggregate_open_risk_pct=OWNER_MAX_AGGREGATE_OPEN_RISK_PCT,
            max_lot=OWNER_MAX_LOT,
            daily_loss_pct=OWNER_DAILY_LOSS_PCT,
            max_concurrent_positions=OWNER_MAX_OPEN_POSITIONS,
            ok=False,
            block_reason="invalid_or_missing_risk_profile",
            rejected_fields=tuple(rejected),
        )

    assert planned is not None
    assert aggregate is not None
    assert max_lot is not None
    assert daily is not None
    assert concurrent is not None

    # Aggregate open risk must not sit below planned risk (same invariant as
    # runtime_policy). Fail closed rather than silently raise aggregate.
    if aggregate < planned:
        return EffectiveRiskProfile(
            planned_risk_pct=planned,
            aggregate_open_risk_pct=aggregate,
            max_lot=max_lot,
            daily_loss_pct=daily,
            max_concurrent_positions=concurrent,
            ok=False,
            block_reason="aggregate_open_risk_below_planned_risk",
            rejected_fields=("aggregate_open_risk_pct:below_planned",),
        )

    return EffectiveRiskProfile(
        planned_risk_pct=planned,
        aggregate_open_risk_pct=aggregate,
        max_lot=max_lot,
        daily_loss_pct=daily,
        max_concurrent_positions=concurrent,
        ok=True,
        block_reason=None,
        rejected_fields=(),
    )


def default_user_risk_proposal() -> RiskSettingProposal:
    """Independent copy of Admin-approved defaults (= current hard ceilings).

    Callers must persist a per-user row — never share one mutable record.
    """
    return RiskSettingProposal(
        planned_risk_pct=OWNER_MAX_PLANNED_RISK_PCT,
        aggregate_open_risk_pct=OWNER_MAX_AGGREGATE_OPEN_RISK_PCT,
        max_lot=OWNER_MAX_LOT,
        daily_loss_pct=OWNER_DAILY_LOSS_PCT,
        max_concurrent_positions=OWNER_MAX_OPEN_POSITIONS,
    )
