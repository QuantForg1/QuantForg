"""Per-user risk profile: defaults, validation, effective resolution.

Every user owns one profile. A field the user never set (``None``) uses the
approved DEFAULT. Saved values are validated against the non-overridable
SYSTEM bounds; broker specifications stay authoritative at execution time.
The effective profile is overlaid on the system document for that user's
trade evaluation only (see ``runtime_policy.PROFILE_POLICY_KEYS``). Another
user's profile is never a fallback.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.institutional_trading.owner_live_limits import (
    OWNER_DAILY_LOSS_PCT,
    OWNER_MAX_AGGREGATE_OPEN_RISK_PCT,
    OWNER_MAX_DRAWDOWN_PCT,
    OWNER_MAX_LOT,
    OWNER_MAX_OPEN_POSITIONS,
    OWNER_MAX_PLANNED_RISK_PCT,
    OWNER_MAX_SPREAD,
    OWNER_MIN_REWARD_RISK,
    OWNER_MIN_TRADE_QUALITY,
    OWNER_MIN_TRADE_QUALITY_FLOOR,
    OWNER_MONTHLY_LOSS_PCT,
    OWNER_WEEKLY_LOSS_PCT,
    SYSTEM_MAX_AGGREGATE_OPEN_RISK_PCT,
    SYSTEM_MAX_DAILY_LOSS_PCT,
    SYSTEM_MAX_LOT,
    SYSTEM_MAX_OPEN_POSITIONS,
    SYSTEM_MAX_PERIOD_LOSS_PCT,
    SYSTEM_MAX_PLANNED_RISK_PCT,
    SYSTEM_MAX_SPREAD,
    SYSTEM_MIN_REWARD_RISK_FLOOR,
)

PROFILE_SCHEMA_VERSION = 1
SOURCE_DEFAULT = "DEFAULT"
SOURCE_CUSTOM = "CUSTOM"
DEFAULT_TRADING_DAYS: tuple[int, ...] = (0, 1, 2, 3, 4)
DEFAULT_TRADING_HOURS = "00:00-24:00"


@dataclass(frozen=True, slots=True)
class FieldSpec:
    key: str
    kind: str  # "pct" | "pct_off" | "decimal" | "int" | "days" | "hours"
    default: Any
    lo: Any = None
    hi: Any = None
    label: str = ""
    unit: str = ""
    help: str = ""


FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(
        "planned_risk_pct",
        "pct",
        OWNER_MAX_PLANNED_RISK_PCT,
        Decimal("0.1"),
        SYSTEM_MAX_PLANNED_RISK_PCT,
        "Risk per trade",
        "% of equity",
        "Maximum planned loss of one position, including spread, slippage and "
        "commission.",
    ),
    FieldSpec(
        "aggregate_open_risk_pct",
        "pct",
        OWNER_MAX_AGGREGATE_OPEN_RISK_PCT,
        Decimal("0.1"),
        SYSTEM_MAX_AGGREGATE_OPEN_RISK_PCT,
        "Aggregate open risk",
        "% of equity",
        "Combined remaining risk of all your open positions and pending orders. "
        "Must be at least the risk per trade.",
    ),
    FieldSpec(
        "daily_loss_pct",
        "pct",
        OWNER_DAILY_LOSS_PCT,
        Decimal("0.1"),
        SYSTEM_MAX_DAILY_LOSS_PCT,
        "Daily loss limit",
        "% of day-start equity",
        "Realised plus floating loss since 00:00 UTC at which new entries stop.",
    ),
    FieldSpec(
        "weekly_loss_pct",
        "pct_off",
        OWNER_WEEKLY_LOSS_PCT,
        Decimal("0"),
        SYSTEM_MAX_PERIOD_LOSS_PCT,
        "Weekly loss limit",
        "% (0 = OFF)",
        "Loss this week at which new entries stop. 0 turns it off.",
    ),
    FieldSpec(
        "monthly_loss_pct",
        "pct_off",
        OWNER_MONTHLY_LOSS_PCT,
        Decimal("0"),
        SYSTEM_MAX_PERIOD_LOSS_PCT,
        "Monthly loss limit",
        "% (0 = OFF)",
        "Loss this month at which new entries stop. 0 turns it off.",
    ),
    FieldSpec(
        "max_drawdown_pct",
        "pct_off",
        OWNER_MAX_DRAWDOWN_PCT,
        Decimal("0"),
        SYSTEM_MAX_PERIOD_LOSS_PCT,
        "Maximum drawdown halt",
        "% of peak equity (0 = OFF)",
        "Drop from the equity high-water mark at which new entries stop.",
    ),
    FieldSpec(
        "min_reward_risk",
        "decimal",
        OWNER_MIN_REWARD_RISK,
        SYSTEM_MIN_REWARD_RISK_FLOOR,
        Decimal("10"),
        "Minimum reward:risk (net)",
        "ratio",
        "Target over stop after spread, slippage and commission.",
    ),
    FieldSpec(
        "max_spread",
        "decimal",
        OWNER_MAX_SPREAD,
        Decimal("0.05"),
        SYSTEM_MAX_SPREAD,
        "Maximum spread",
        "USD per oz",
        "Entries are skipped while the live spread is wider.",
    ),
    FieldSpec(
        "max_lot",
        "decimal",
        OWNER_MAX_LOT,
        Decimal("0.01"),
        SYSTEM_MAX_LOT,
        "Maximum lot",
        "lots",
        "Largest volume of one order. The broker minimum, step and maximum "
        "still apply.",
    ),
    FieldSpec(
        "max_open_positions",
        "int",
        OWNER_MAX_OPEN_POSITIONS,
        1,
        SYSTEM_MAX_OPEN_POSITIONS,
        "Maximum open positions",
        "positions",
        "Concurrent positions. Aggregate open risk still caps the total.",
    ),
    FieldSpec(
        "min_trade_quality",
        "int",
        OWNER_MIN_TRADE_QUALITY,
        OWNER_MIN_TRADE_QUALITY_FLOOR,
        100,
        "Minimum signal quality",
        "score /100",
        "Signals below this AI quality score are not traded.",
    ),
    FieldSpec(
        "trading_days",
        "days",
        DEFAULT_TRADING_DAYS,
        label="Trading days",
        unit="weekdays (UTC)",
        help="Days on which new entries may open. Broker market hours still apply.",
    ),
    FieldSpec(
        "trading_hours_utc",
        "hours",
        DEFAULT_TRADING_HOURS,
        label="Trading hours",
        unit="UTC",
        help="Daily window for new entries, e.g. 00:00-24:00 (24h) or 07:00-17:00.",
    ),
)
FIELD_BY_KEY: dict[str, FieldSpec] = {f.key: f for f in FIELDS}
PROFILE_KEYS = frozenset(FIELD_BY_KEY)


def _dec(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None
    return out if out.is_finite() else None


def _clean_value(spec: FieldSpec, raw: object) -> tuple[Any, str | None]:
    """Validated storage value for one field, or an error message."""
    if spec.kind in {"pct", "pct_off", "decimal"}:
        value = _dec(raw)
        if value is None:
            return None, f"{spec.label} must be a number"
        if spec.kind == "pct_off" and value == 0:
            return Decimal("0"), None
        lo = Decimal("0.1") if spec.kind == "pct_off" else spec.lo
        if value < lo or value > spec.hi:
            off = " (or 0 for OFF)" if spec.kind == "pct_off" else ""
            return None, f"{spec.label} must be between {lo} and {spec.hi}{off}"
        if spec.key == "max_lot" and (value * 100) % 1 != 0:
            return None, "Maximum lot must be a multiple of 0.01"
        return value, None
    if spec.kind == "int":
        if isinstance(raw, bool):
            return None, f"{spec.label} must be a whole number"
        value_d = _dec(raw)
        if value_d is None or value_d != value_d.to_integral_value():
            return None, f"{spec.label} must be a whole number"
        value_i = int(value_d)
        if value_i < int(spec.lo) or value_i > int(spec.hi):
            return None, f"{spec.label} must be between {spec.lo} and {spec.hi}"
        return value_i, None
    if spec.kind == "days":
        from app.domain.institutional_trading.runtime_policy import parse_trading_days

        days = parse_trading_days(raw)
        if days is None:
            return None, "Trading days must be a non-empty list of weekdays 0-6"
        return sorted(days), None
    if spec.kind == "hours":
        from app.domain.institutional_trading.runtime_policy import (
            parse_trading_hours,
        )

        if parse_trading_hours(raw) is None:
            return None, "Trading hours must look like 00:00-24:00 or 07:00-17:00"
        text = str(raw).strip().lower()
        return ("00:00-24:00" if text in {"24h", "24/5", "all"} else text), None
    return None, f"{spec.key} is not supported"


@dataclass(frozen=True, slots=True)
class ProfileValidation:
    ok: bool
    values: dict[str, Any]
    errors: dict[str, str]


def validate_profile_changes(
    current: Mapping[str, Any] | None, changes: Mapping[str, Any]
) -> ProfileValidation:
    """Validate a partial update. ``None`` for a key resets it to DEFAULT.

    Returns the merged stored values (unset keys stay absent).
    """
    merged: dict[str, Any] = {}
    for key, raw_current in dict(current or {}).items():
        if key not in PROFILE_KEYS or raw_current is None or raw_current == "":
            continue
        cleaned, bad = _clean_value(FIELD_BY_KEY[key], raw_current)
        if bad is None:
            merged[key] = cleaned  # a stored value that no longer validates drops
    errors: dict[str, str] = {}
    unknown = sorted(set(changes) - PROFILE_KEYS)
    for key in unknown:
        errors[key] = "Unknown or non-editable setting"
    for key, raw in changes.items():
        if key not in PROFILE_KEYS:
            continue
        if raw is None or raw == "":
            merged.pop(key, None)
            continue
        value, err = _clean_value(FIELD_BY_KEY[key], raw)
        if err:
            errors[key] = err
        else:
            merged[key] = value
    if not errors:
        planned = merged.get(
            "planned_risk_pct", FIELD_BY_KEY["planned_risk_pct"].default
        )
        aggregate = merged.get(
            "aggregate_open_risk_pct", FIELD_BY_KEY["aggregate_open_risk_pct"].default
        )
        if aggregate < planned:
            errors["aggregate_open_risk_pct"] = (
                "Aggregate open risk must be at least the risk per trade "
                f"({planned}%)"
            )
    return ProfileValidation(ok=not errors, values=merged, errors=errors)


@dataclass(frozen=True, slots=True)
class EffectiveProfile:
    values: dict[str, Any]
    sources: dict[str, str]
    warnings: tuple[str, ...]
    version: int = 0

    def to_policy_overlay(self) -> dict[str, Any]:
        """Keys of ``runtime_policy`` built from this profile."""
        v = self.values
        return {
            "max_planned_risk_pct": format(v["planned_risk_pct"], "f"),
            "max_aggregate_open_risk_pct": format(v["aggregate_open_risk_pct"], "f"),
            "daily_loss_pct": format(v["daily_loss_pct"], "f"),
            "weekly_loss_pct": format(v["weekly_loss_pct"], "f"),
            "monthly_loss_pct": format(v["monthly_loss_pct"], "f"),
            "max_drawdown_pct": format(v["max_drawdown_pct"], "f"),
            "min_reward_risk": format(v["min_reward_risk"], "f"),
            "preferred_reward_risk": format(v["min_reward_risk"], "f"),
            "max_spread": format(v["max_spread"], "f"),
            "max_lot": format(v["max_lot"], "f"),
            "max_concurrent_positions": int(v["max_open_positions"]),
            "min_trade_quality": int(v["min_trade_quality"]),
            "trading_days": list(v["trading_days"]),
            "trading_hours_utc": str(v["trading_hours_utc"]),
            "session_utc": f"{v['trading_hours_utc']} days={list(v['trading_days'])}",
        }

    def to_dict(self) -> dict[str, Any]:
        def fmt(value: Any) -> Any:
            if isinstance(value, Decimal):
                return format(value, "f")
            if isinstance(value, tuple):
                return list(value)
            return value

        return {
            "values": {k: fmt(v) for k, v in self.values.items()},
            "sources": dict(self.sources),
            "warnings": list(self.warnings),
            "version": self.version,
            "schema_version": PROFILE_SCHEMA_VERSION,
        }


def resolve_profile(
    saved: Mapping[str, Any] | None, *, version: int = 0
) -> EffectiveProfile:
    """Merge saved values with defaults. Invalid stored values -> DEFAULT."""
    data = dict(saved or {})
    values: dict[str, Any] = {}
    sources: dict[str, str] = {}
    warnings: list[str] = []
    for spec in FIELDS:
        raw = data.get(spec.key)
        if raw is None or raw == "":
            values[spec.key] = spec.default
            sources[spec.key] = SOURCE_DEFAULT
            continue
        value, err = _clean_value(spec, raw)
        if err:
            values[spec.key] = spec.default
            sources[spec.key] = SOURCE_DEFAULT
            warnings.append(f"{spec.key}: stored value invalid, default used ({err})")
            continue
        values[spec.key] = value
        sources[spec.key] = SOURCE_CUSTOM
    # Invariant: the book never holds less than one full trade. Tighten the
    # per-trade value rather than loosen the book.
    if values["aggregate_open_risk_pct"] < values["planned_risk_pct"]:
        warnings.append("planned_risk_pct reduced to aggregate_open_risk_pct")
        values["planned_risk_pct"] = values["aggregate_open_risk_pct"]
    if isinstance(values["trading_days"], list):
        values["trading_days"] = tuple(values["trading_days"])
    return EffectiveProfile(
        values=values, sources=sources, warnings=tuple(warnings), version=version
    )


def aggressive_warnings(values: Mapping[str, Any]) -> list[str]:
    """Plain-language warnings shown next to aggressive settings."""
    out: list[str] = []
    planned = Decimal(str(values.get("planned_risk_pct", 0)))
    daily = Decimal(str(values.get("daily_loss_pct", 0)))
    if planned >= Decimal("5"):
        losses = int((Decimal("100") / planned).to_integral_value())
        out.append(
            f"Risk per trade of {planned}% means about {losses} full-stop losses in a "
            "row could wipe most of the account. Higher risk does not mean higher "
            "returns."
        )
    if daily >= Decimal("20"):
        out.append(
            f"A {daily}% daily loss limit allows a large part of the account to be "
            "lost in one day."
        )
    if (
        Decimal(str(values.get("weekly_loss_pct", 0))) == 0
        and Decimal(str(values.get("max_drawdown_pct", 0))) == 0
    ):
        out.append("Weekly loss and drawdown halts are OFF.")
    return out
