"""Per-user risk profile API (each authenticated user manages only their own).

The values returned under ``effective`` are exactly what the trading engine
installs for this user's trade evaluation (see
``runtime_policy_store.effective_user_document``), not the form input.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services import user_risk_profile_store as store
from app.domain.exceptions.base import ValidationError
from app.domain.institutional_trading.risk_profile import (
    FIELDS,
    PROFILE_SCHEMA_VERSION,
    aggressive_warnings,
)
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/risk/profile", tags=["risk-profile"])


class RiskProfileUpdate(BaseModel):
    changes: dict[str, Any] = Field(default_factory=dict)
    expected_version: int | None = Field(default=None, ge=0)


class RiskProfileReset(BaseModel):
    expected_version: int | None = Field(default=None, ge=0)


def _fmt(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, tuple):
        return list(value)
    return value


def _field_specs() -> list[dict[str, Any]]:
    return [
        {
            "key": f.key,
            "label": f.label,
            "unit": f.unit,
            "help": f.help,
            "kind": f.kind,
            "default": _fmt(f.default),
            "min": _fmt(f.lo),
            "max": _fmt(f.hi),
            "off_allowed": f.kind == "pct_off",
        }
        for f in FIELDS
    ]


def _payload(user_id: UUID) -> dict[str, Any]:
    from app.application.services.runtime_policy_store import (
        effective_user_document,
        load_runtime_policy,
    )

    try:
        settings, version, updated_at = store.load_settings(user_id, use_cache=False)
        profile = store.effective_profile(user_id, use_cache=False)
    except store.ProfileStoreError as exc:
        raise ValidationError(
            "Risk profile storage is temporarily unavailable",
            code="risk_profile_unavailable",
        ) from exc
    engine: dict[str, Any] | None = None
    system = load_runtime_policy()
    if system.ok and system.document is not None:
        doc = effective_user_document(dict(system.document), user_id)
        engine = {
            k: doc.get(k)
            for k in (
                "max_planned_risk_pct",
                "max_aggregate_open_risk_pct",
                "daily_loss_pct",
                "weekly_loss_pct",
                "monthly_loss_pct",
                "max_drawdown_pct",
                "min_reward_risk",
                "max_spread",
                "max_lot",
                "max_concurrent_positions",
                "min_trade_quality",
                "trading_days",
                "trading_hours_utc",
                "gold_only",
                "protective_stop_required",
                "allow_martingale",
                "allow_grid",
                "risk_profile_version",
            )
        }
        engine["system_policy_version"] = system.version
    eff = profile.to_dict()
    return {
        "user_id": str(user_id),
        "effective": eff["values"],
        "sources": eff["sources"],
        "custom": {k: _fmt(v) for k, v in settings.items()},
        "version": version,
        "schema_version": PROFILE_SCHEMA_VERSION,
        "updated_at": updated_at,
        "warnings": aggressive_warnings(profile.values) + list(profile.warnings),
        "fields": _field_specs(),
        "engine_policy": engine,
        "notes": [
            "Defaults apply to every setting you have not changed.",
            "Changes apply only to your future trade decisions; open positions "
            "are not modified.",
            "Broker minimum lot, lot step, maximum volume, margin and market "
            "hours always apply.",
            "Martingale, grid recovery and forced trades are disabled for "
            "every account.",
        ],
    }


def _validation(exc: store.ProfileValidationError) -> ValidationError:
    return ValidationError(
        "Risk profile update rejected",
        code="risk_profile_rejected",
        details={"errors": exc.errors},
    )


def _conflict() -> ValidationError:
    return ValidationError(
        "Your risk profile changed in another session. Reload and try again.",
        code="risk_profile_conflict",
    )


@router.get("")
async def read_own_profile(user: CurrentUser) -> dict[str, Any]:
    return _payload(UUID(str(user.id)))


@router.put("")
async def update_own_profile(
    body: RiskProfileUpdate, user: CurrentUser
) -> dict[str, Any]:
    uid = UUID(str(user.id))
    if not body.changes:
        raise ValidationError("No changes supplied", code="risk_profile_empty")
    try:
        store.save_profile(
            uid,
            body.changes,
            actor_id=uid,
            expected_version=body.expected_version,
        )
    except store.ProfileValidationError as exc:
        raise _validation(exc) from exc
    except store.ProfileConflictError as exc:
        raise _conflict() from exc
    except store.ProfileStoreError as exc:
        raise ValidationError(
            "Risk profile storage is temporarily unavailable",
            code="risk_profile_unavailable",
        ) from exc
    return _payload(uid)


@router.post("/reset")
async def reset_own_profile(
    body: RiskProfileReset, user: CurrentUser
) -> dict[str, Any]:
    uid = UUID(str(user.id))
    try:
        store.reset_profile(uid, actor_id=uid, expected_version=body.expected_version)
    except store.ProfileConflictError as exc:
        raise _conflict() from exc
    except store.ProfileStoreError as exc:
        raise ValidationError(
            "Risk profile storage is temporarily unavailable",
            code="risk_profile_unavailable",
        ) from exc
    return _payload(uid)


@router.get("/events")
async def read_own_profile_events(
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, Any]:
    return {"items": store.list_events(UUID(str(user.id)), limit=limit)}
