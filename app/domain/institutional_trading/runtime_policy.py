"""Authoritative runtime trading policy.

Since 2026-11-18 the document installed for a cycle is the *effective policy
of one user*: the system document (``trading_runtime_config``: gold-only,
protective stop, commission tariff, kill-switch locks and other platform
safeguards) overlaid with that user's own risk profile
(``user_risk_profiles``; unset fields use the approved defaults). The shared
document's trading-profile keys are never used for a user's trade evaluation.

Every value is clamped to the non-overridable ``SYSTEM_*`` bounds. A document
cannot disable gold-only, drop protective stops, bypass the kill switch, or
enable martingale / grid. With no document installed the approved defaults
apply. Weekly, monthly and drawdown halts are 0 (off) unless a profile sets
them.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import time
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
    OWNER_SESSION_END_UTC,
    OWNER_SESSION_START_UTC,
    OWNER_SESSION_WEEKDAYS,
    OWNER_SL_ATR_MULTIPLIER,
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

_POLICY: ContextVar[dict[str, Any] | None] = ContextVar(
    "qf_runtime_policy", default=None
)

FORBIDDEN_KEYS = frozenset(
    {
        "kill_switch_bypass",
        "allow_non_gold",
        "disable_protective_stop",
        "execution_enabled",
        "force_first_trade",
        "martingale",
        "grid",
        "risk_lock_override",
        "allow_martingale",
        "allow_grid_averaging",
    }
)

LOCKED_TRUE = (
    "gold_only",
    "protective_stop_required",
    "evaluate_full_utc_day",
    "ite_enabled",
    "unified_decision_enabled",
)

# Keys owned by a user's risk profile. The shared system document's values for
# these keys are ignored when an effective per-user policy is built.
PROFILE_POLICY_KEYS = frozenset(
    {
        "max_planned_risk_pct",
        "max_aggregate_open_risk_pct",
        "daily_loss_pct",
        "weekly_loss_pct",
        "monthly_loss_pct",
        "max_drawdown_pct",
        "min_reward_risk",
        "preferred_reward_risk",
        "max_spread",
        "max_lot",
        "max_concurrent_positions",
        "min_trade_quality",
        "trading_days",
        "trading_hours_utc",
        "session_utc",
    }
)


def use_runtime_policy(document: dict[str, Any] | None) -> Token[dict[str, Any] | None]:
    return _POLICY.set(document)


def reset_runtime_policy(token: Token[dict[str, Any] | None]) -> None:
    _POLICY.reset(token)


def active_policy() -> dict[str, Any] | None:
    return _POLICY.get()


def policy_unavailable() -> bool:
    doc = _POLICY.get()
    return isinstance(doc, dict) and bool(doc.get("unavailable"))


def _dec(value: object) -> Decimal:
    return Decimal(str(value))


def _active_decimal(key: str, fallback: Decimal) -> Decimal:
    doc = _POLICY.get()
    if not isinstance(doc, dict) or doc.get("unavailable"):
        return fallback
    raw = doc.get(key)
    if raw is None or raw == "":
        return fallback
    try:
        value = _dec(raw)
    except (InvalidOperation, ValueError):
        return fallback
    return value if value.is_finite() else fallback


def _bounded(value: Decimal, *, default: Decimal, ceiling: Decimal) -> Decimal:
    """Positive value up to the system ceiling; anything else -> default."""
    if value <= 0 or value > ceiling:
        return default
    return value


def active_max_planned_risk_pct() -> Decimal:
    value = _active_decimal("max_planned_risk_pct", OWNER_MAX_PLANNED_RISK_PCT)
    return _bounded(
        value, default=OWNER_MAX_PLANNED_RISK_PCT, ceiling=SYSTEM_MAX_PLANNED_RISK_PCT
    )


def active_daily_loss_pct() -> Decimal:
    value = _active_decimal("daily_loss_pct", OWNER_DAILY_LOSS_PCT)
    return _bounded(
        value, default=OWNER_DAILY_LOSS_PCT, ceiling=SYSTEM_MAX_DAILY_LOSS_PCT
    )


def active_max_lot() -> Decimal:
    value = _active_decimal("max_lot", OWNER_MAX_LOT)
    return _bounded(value, default=OWNER_MAX_LOT, ceiling=SYSTEM_MAX_LOT)


def active_min_lot() -> Decimal | None:
    """Saved minimum lot. Missing means the broker minimum still applies."""
    doc = _POLICY.get()
    if not isinstance(doc, dict) or doc.get("unavailable"):
        return None
    raw = doc.get("min_lot")
    if raw is None or raw == "":
        return None
    try:
        value = _dec(raw)
    except Exception:
        return None
    if value <= 0 or value > active_max_lot():
        return None
    return value


def active_max_aggregate_open_risk_pct() -> Decimal:
    """Shared open-risk budget of one user's book. Never below per-trade risk."""
    value = _active_decimal(
        "max_aggregate_open_risk_pct", OWNER_MAX_AGGREGATE_OPEN_RISK_PCT
    )
    value = _bounded(
        value,
        default=OWNER_MAX_AGGREGATE_OPEN_RISK_PCT,
        ceiling=SYSTEM_MAX_AGGREGATE_OPEN_RISK_PCT,
    )
    return value


def active_max_open_positions() -> int:
    """Profile concurrent-position cap, 1 to the system maximum."""
    doc = _POLICY.get()
    if not isinstance(doc, dict) or doc.get("unavailable"):
        return OWNER_MAX_OPEN_POSITIONS
    raw = doc.get("max_concurrent_positions")
    if raw is None:
        return OWNER_MAX_OPEN_POSITIONS
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return OWNER_MAX_OPEN_POSITIONS
    if value < 1 or value > SYSTEM_MAX_OPEN_POSITIONS:
        return OWNER_MAX_OPEN_POSITIONS
    return value


def full_utc_day_required() -> bool:
    """False only when a saved document explicitly disables the full UTC day."""
    doc = _POLICY.get()
    if not isinstance(doc, dict) or doc.get("unavailable"):
        return True
    if "evaluate_full_utc_day" not in doc:
        return True
    return doc.get("evaluate_full_utc_day") is True


def active_max_spread() -> Decimal:
    value = _active_decimal("max_spread", OWNER_MAX_SPREAD)
    return _bounded(value, default=OWNER_MAX_SPREAD, ceiling=SYSTEM_MAX_SPREAD)


def enforced_min_reward_risk(document: dict[str, Any] | None) -> Decimal:
    """Net reward:risk floor of a document after estimated trading costs.

    Default ``OWNER_MIN_REWARD_RISK`` (1.50). A profile may save any value
    from the system floor (1.00) to 10. Anything else fails to the default.
    """
    from app.domain.institutional_trading.owner_live_limits import (
        authorized_min_reward_risk,
    )

    if not isinstance(document, dict) or document.get("unavailable"):
        return OWNER_MIN_REWARD_RISK
    raw = document.get("min_reward_risk")
    if raw is None or raw == "":
        return OWNER_MIN_REWARD_RISK
    try:
        value = _dec(raw)
    except (InvalidOperation, ValueError):
        return OWNER_MIN_REWARD_RISK
    authorized = authorized_min_reward_risk(value)
    if authorized is None:
        return OWNER_MIN_REWARD_RISK
    return authorized


def active_min_reward_risk() -> Decimal:
    """Active net RR floor of the installed (per-user) document."""
    doc = _POLICY.get()
    return enforced_min_reward_risk(doc if isinstance(doc, dict) else None)


def active_min_trade_quality() -> int:
    """Unset policy stays 75. A saved integer from 70 to 100 is used.

    Anything else fails closed to 75.
    """
    from app.domain.institutional_trading.owner_live_limits import (
        authorized_min_trade_quality,
    )

    doc = _POLICY.get()
    if not isinstance(doc, dict) or doc.get("min_trade_quality") is None:
        return OWNER_MIN_TRADE_QUALITY
    authorized = authorized_min_trade_quality(doc.get("min_trade_quality"))
    if authorized is None:
        return OWNER_MIN_TRADE_QUALITY
    return authorized


def active_stop_atr_multiplier() -> Decimal:
    """Experimental default is 1.00. Only 1.00, 1.25, and 1.50 may be saved.

    0.75 and 0.90 are inside one ATR of noise and fail closed to the default.
    """
    from app.domain.institutional_trading.owner_live_limits import (
        atr_multiplier_verdict,
    )

    value = _active_decimal("stop_atr_multiplier", OWNER_SL_ATR_MULTIPLIER)
    if atr_multiplier_verdict(value) != "accepted":
        if atr_multiplier_verdict(OWNER_SL_ATR_MULTIPLIER) == "accepted":
            return OWNER_SL_ATR_MULTIPLIER.quantize(Decimal("0.01"))
        return Decimal("1.50")
    return value.quantize(Decimal("0.01"))


def _period_limit(key: str, default: Decimal) -> Decimal:
    """0 means off. A positive value up to the system bound is enforced."""
    doc = _POLICY.get()
    if not isinstance(doc, dict) or doc.get("unavailable"):
        return default
    raw = doc.get(key)
    if raw is None or raw == "":
        return Decimal("0")
    try:
        value = _dec(raw)
    except (InvalidOperation, ValueError):
        return Decimal("0")
    if not value.is_finite() or value <= 0:
        return Decimal("0")
    return min(value, SYSTEM_MAX_PERIOD_LOSS_PCT)


def weekly_loss_limit_pct() -> Decimal:
    """0 means the weekly halt is off. Never invents a nonzero default."""
    return _period_limit("weekly_loss_pct", OWNER_WEEKLY_LOSS_PCT)


def monthly_loss_limit_pct() -> Decimal:
    """0 means the monthly halt is off. Never invents a nonzero default."""
    return _period_limit("monthly_loss_pct", OWNER_MONTHLY_LOSS_PCT)


def drawdown_limit_pct() -> Decimal:
    """0 means the overall drawdown halt is off until a profile sets it."""
    return _period_limit("max_drawdown_pct", OWNER_MAX_DRAWDOWN_PCT)


_DEFAULT_WINDOW = (
    frozenset(OWNER_SESSION_WEEKDAYS),
    OWNER_SESSION_START_UTC,
    OWNER_SESSION_END_UTC,
)


def parse_trading_hours(raw: object) -> tuple[time, time] | None:
    """``"HH:MM-HH:MM"`` (UTC) or ``"24h"``. ``24:00`` means end of day."""
    text = str(raw or "").strip().lower()
    if text in {"24h", "24/5", "all", "00:00-24:00"}:
        return OWNER_SESSION_START_UTC, OWNER_SESSION_END_UTC
    parts = text.split("-")
    if len(parts) != 2:
        return None
    out: list[time] = []
    for part in parts:
        try:
            hh_s, mm_s = part.strip().split(":")
            hh, mm = int(hh_s), int(mm_s)
        except ValueError:
            return None
        if hh == 24 and mm == 0:
            out.append(time.max)
            continue
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return None
        out.append(time(hh, mm))
    if out[0] == out[1]:
        return None
    return out[0], out[1]


def parse_trading_days(raw: object) -> frozenset[int] | None:
    """Weekday numbers (Monday = 0). Non-empty subset of 0..6."""
    if not isinstance(raw, list | tuple) or not raw:
        return None
    days: set[int] = set()
    for item in raw:
        if isinstance(item, bool):
            return None
        try:
            day = int(item)
        except (TypeError, ValueError):
            return None
        if day < 0 or day > 6:
            return None
        days.add(day)
    return frozenset(days)


def active_trading_window() -> tuple[frozenset[int], time, time]:
    """(weekdays, start, end) of the installed profile; default 24/5 UTC."""
    doc = _POLICY.get()
    if not isinstance(doc, dict) or doc.get("unavailable"):
        return _DEFAULT_WINDOW
    days = parse_trading_days(doc.get("trading_days"))
    hours = parse_trading_hours(doc.get("trading_hours_utc"))
    if days is None and hours is None:
        return _DEFAULT_WINDOW
    start, end = hours or (OWNER_SESSION_START_UTC, OWNER_SESSION_END_UTC)
    return (days or _DEFAULT_WINDOW[0]), start, end


def m1_overlay_mode(key: str) -> str | None:
    """``None`` defers to the deployment flag. ``off`` fails closed."""
    doc = _POLICY.get()
    if doc is None:
        return None
    if doc.get("unavailable"):
        return "off"
    raw = doc.get(key)
    if raw is None:
        return None
    return "on" if bool(raw) else "off"


def approved_baseline() -> dict[str, Any]:
    """Approved system document. Trading-profile keys hold the user defaults."""
    from app.domain.institutional_trading.owner_live_limits import (
        owner_commission_configuration,
    )

    return {
        "max_planned_risk_pct": format(OWNER_MAX_PLANNED_RISK_PCT, "f"),
        "daily_loss_pct": format(OWNER_DAILY_LOSS_PCT, "f"),
        "weekly_loss_pct": "0",
        "weekly_loss_documented": (
            "0 means off. A weekly halt is enforced only after an owner save "
            "sets a percent. No silent weekly default is deployed."
        ),
        "max_drawdown_pct": "0",
        "drawdown_documented": (
            "0 means off. Overall drawdown is measured from the stored equity "
            "high-water mark and is enforced only after an owner save. A missing "
            "mark fails closed while the halt is on."
        ),
        "max_aggregate_open_risk_pct": format(OWNER_MAX_AGGREGATE_OPEN_RISK_PCT, "f"),
        "max_concurrent_positions": OWNER_MAX_OPEN_POSITIONS,
        "min_lot": None,
        "max_lot": format(OWNER_MAX_LOT, "f"),
        "max_spread": format(OWNER_MAX_SPREAD, "f"),
        "min_reward_risk": str(OWNER_MIN_REWARD_RISK),
        "preferred_reward_risk": str(OWNER_MIN_REWARD_RISK),
        "commission": owner_commission_configuration(),
        "min_trade_quality": OWNER_MIN_TRADE_QUALITY,
        "stop_atr_multiplier": "1.00",
        "gold_only": True,
        "protective_stop_required": True,
        "evaluate_full_utc_day": True,
        "ite_enabled": True,
        "unified_decision_enabled": True,
        "allow_martingale": False,
        "allow_grid": False,
        "allow_average_down": False,
        "m1_micro_enabled": None,
        # None defers to QUANTFORG_M1_MICRO_LIVE_SUBMIT. Production Phase-5
        # persists false via Admin policy + Railway env (does not force-close).
        "m1_live_submit": None,
        "experimental_promoted": False,
        "session_utc": "24/5 Mon-Fri UTC",
    }


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    ok: bool
    document: dict[str, Any] | None
    errors: tuple[str, ...] = ()
    version: int = 0
    source: str = ""


def _reject_number(
    errors: list[str],
    changes: dict[str, Any],
    key: str,
    *,
    lo: Decimal,
    hi: Decimal,
    allow_zero: bool = False,
) -> None:
    if key not in changes:
        return
    raw = changes[key]
    try:
        value = _dec(raw)
    except Exception:
        errors.append(f"{key} is not a number")
        return
    if allow_zero and value == 0:
        return
    if value < lo or value > hi:
        errors.append(f"{key} must be between {lo} and {hi}")


_EXPERIMENTAL_KEYS = frozenset(
    {
        "max_planned_risk_pct",
        "max_aggregate_open_risk_pct",
        "daily_loss_pct",
        "max_lot",
        "max_spread",
        "min_reward_risk",
        "min_trade_quality",
        "stop_atr_multiplier",
        "max_concurrent_positions",
    }
)


def _clean_experimental(raw: object) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate a saved experiment. It is not copied onto the active floor."""
    if not isinstance(raw, dict) or not raw:
        return None, ["experimental must be a non-empty object"]
    unknown = sorted(set(raw) - _EXPERIMENTAL_KEYS)
    if unknown:
        return None, ["unknown experimental keys: " + ", ".join(unknown)]
    errors: list[str] = []
    _reject_number(
        errors,
        raw,
        "max_planned_risk_pct",
        lo=Decimal("0.01"),
        hi=OWNER_MAX_PLANNED_RISK_PCT,
    )
    _reject_number(
        errors,
        raw,
        "max_aggregate_open_risk_pct",
        lo=Decimal("0.01"),
        hi=OWNER_MAX_AGGREGATE_OPEN_RISK_PCT,
    )
    _reject_number(
        errors,
        raw,
        "daily_loss_pct",
        lo=Decimal("0.01"),
        hi=OWNER_DAILY_LOSS_PCT,
    )
    _reject_number(errors, raw, "max_lot", lo=Decimal("0.01"), hi=OWNER_MAX_LOT)
    _reject_number(errors, raw, "max_spread", lo=Decimal("0.01"), hi=OWNER_MAX_SPREAD)
    from app.domain.institutional_trading.owner_live_limits import (
        atr_multiplier_verdict,
        authorized_min_reward_risk,
        authorized_min_trade_quality,
    )

    if "min_reward_risk" not in raw:
        errors.append("experimental min_reward_risk must be 0.10 or 0.15")
    else:
        try:
            rr = _dec(raw["min_reward_risk"])
        except Exception:
            errors.append("experimental min_reward_risk is not a number")
        else:
            # Experimental floors below the active floor are retired: every
            # profile floor is at least the system floor (1.00).
            authorized = authorized_min_reward_risk(rr)
            if authorized is None or authorized >= SYSTEM_MIN_REWARD_RISK_FLOOR:
                errors.append("experimental min_reward_risk must be 0.10 or 0.15")
    if "min_trade_quality" in raw:
        authorized_quality = authorized_min_trade_quality(raw.get("min_trade_quality"))
        if authorized_quality is None:
            errors.append(
                "experimental min_trade_quality must be "
                f"{OWNER_MIN_TRADE_QUALITY_FLOOR} to 100"
            )
    if "stop_atr_multiplier" in raw:
        try:
            multiplier = _dec(raw["stop_atr_multiplier"])
        except Exception:
            errors.append("experimental stop_atr_multiplier is not a number")
        else:
            verdict = atr_multiplier_verdict(multiplier)
            if verdict != "accepted":
                errors.append(
                    "experimental stop_atr_multiplier must be 1.00, 1.25, or 1.50"
                )
    if "max_concurrent_positions" in raw:
        try:
            positions = int(raw["max_concurrent_positions"])
        except (TypeError, ValueError):
            positions = 0
        if positions < 1 or positions > OWNER_MAX_OPEN_POSITIONS:
            errors.append(
                "experimental max_concurrent_positions must be from 1 to "
                f"{OWNER_MAX_OPEN_POSITIONS}"
            )
    if errors:
        return None, errors
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        cleaned[key] = format(value, "f") if isinstance(value, Decimal) else value
    return cleaned, []


def _clean_commission(raw: object) -> tuple[dict[str, Any] | None, list[str]]:
    from app.domain.institutional_trading.owner_live_limits import (
        clean_commission_configuration,
    )

    return clean_commission_configuration(raw)


def _active_rr_is_candidate(value: object) -> bool:
    try:
        rr = _dec(value)
    except Exception:
        return False
    # Any parseable value below the owner floor is a stale candidate and is
    # rewritten to the floor (no experimental floor below it exists).
    return rr < OWNER_MIN_REWARD_RISK


def validate_policy_changes(
    current: dict[str, Any], changes: dict[str, Any]
) -> PolicyDecision:
    """Merge ``changes`` into ``current`` or reject the whole update."""
    if not isinstance(changes, dict) or not changes:
        return PolicyDecision(False, None, ("changes must be a non-empty object",))
    unknown = sorted(
        set(changes)
        - set(approved_baseline())
        - {"reason", "experimental", "promote_experimental"}
    )
    forbidden = sorted(set(changes) & FORBIDDEN_KEYS)
    errors: list[str] = []
    if forbidden:
        errors.append("forbidden keys: " + ", ".join(forbidden))
    if unknown:
        errors.append("unknown keys: " + ", ".join(unknown))
    for key in LOCKED_TRUE:
        if key in changes and changes[key] is not True:
            errors.append(f"{key} cannot be disabled")
    _reject_number(
        errors,
        changes,
        "max_planned_risk_pct",
        lo=Decimal("0.01"),
        hi=OWNER_MAX_PLANNED_RISK_PCT,
    )
    _reject_number(
        errors,
        changes,
        "daily_loss_pct",
        lo=Decimal("0.01"),
        hi=OWNER_DAILY_LOSS_PCT,
    )
    _reject_number(
        errors,
        changes,
        "weekly_loss_pct",
        lo=Decimal("0"),
        hi=OWNER_DAILY_LOSS_PCT,
        allow_zero=True,
    )
    _reject_number(
        errors,
        changes,
        "max_drawdown_pct",
        lo=Decimal("0"),
        hi=OWNER_DAILY_LOSS_PCT,
        allow_zero=True,
    )
    _reject_number(
        errors,
        changes,
        "max_aggregate_open_risk_pct",
        lo=Decimal("0.01"),
        hi=OWNER_MAX_AGGREGATE_OPEN_RISK_PCT,
    )
    _reject_number(errors, changes, "max_lot", lo=Decimal("0.01"), hi=OWNER_MAX_LOT)
    _reject_number(
        errors, changes, "max_spread", lo=Decimal("0.01"), hi=OWNER_MAX_SPREAD
    )
    from app.domain.institutional_trading.owner_live_limits import (
        atr_multiplier_verdict,
        authorized_min_reward_risk,
        authorized_min_trade_quality,
    )

    if "min_reward_risk" in changes:
        try:
            rr = _dec(changes["min_reward_risk"])
        except Exception:
            errors.append("min_reward_risk is not a number")
        else:
            authorized = authorized_min_reward_risk(rr)
            if authorized is None or authorized < OWNER_MIN_REWARD_RISK:
                errors.append(
                    f"active min_reward_risk must be at least {OWNER_MIN_REWARD_RISK}"
                )
    if "min_trade_quality" in changes:
        try:
            quality = int(changes["min_trade_quality"])
        except (TypeError, ValueError):
            errors.append("min_trade_quality is not an integer")
        else:
            if authorized_min_trade_quality(quality) is None:
                errors.append(
                    f"min_trade_quality must be {OWNER_MIN_TRADE_QUALITY_FLOOR} to 100"
                )
    if "stop_atr_multiplier" in changes:
        try:
            multiplier = _dec(changes["stop_atr_multiplier"])
        except Exception:
            errors.append("stop_atr_multiplier is not a number")
        else:
            verdict = atr_multiplier_verdict(multiplier)
            if verdict == "inside_noise":
                errors.append(
                    "stop_atr_multiplier is inside normal ATR noise; "
                    "0.75 and 0.90 are rejected. "
                    "Allowed values are 1.00, 1.25, and 1.50"
                )
            elif verdict != "accepted":
                errors.append("stop_atr_multiplier must be 1.00, 1.25, or 1.50")
    if "max_concurrent_positions" in changes:
        try:
            positions = int(changes["max_concurrent_positions"])
        except (TypeError, ValueError):
            positions = 0
        if positions < 1 or positions > OWNER_MAX_OPEN_POSITIONS:
            errors.append(
                f"max_concurrent_positions must be from 1 to {OWNER_MAX_OPEN_POSITIONS}"
            )
    if "min_lot" in changes and changes["min_lot"] is not None:
        try:
            min_lot = _dec(changes["min_lot"])
        except Exception:
            errors.append("min_lot is not a number")
        else:
            if min_lot <= 0 or min_lot > OWNER_MAX_LOT:
                errors.append(f"min_lot must be within (0, {OWNER_MAX_LOT}]")
    for key in ("m1_micro_enabled", "m1_live_submit"):
        if (
            key in changes
            and changes[key] is not None
            and not isinstance(changes[key], bool)
        ):
            errors.append(f"{key} must be true, false, or null")
    cleaned_commission: dict[str, Any] | None = None
    if "commission" in changes:
        cleaned_commission, commission_errors = _clean_commission(
            changes.get("commission")
        )
        errors.extend(commission_errors)
    promote = changes.get("promote_experimental") is True
    cleaned_experimental: dict[str, Any] | None = None
    if "experimental" in changes or promote:
        source = changes.get("experimental", current.get("experimental"))
        cleaned_experimental, experimental_errors = _clean_experimental(source)
        errors.extend(experimental_errors)
    if errors:
        return PolicyDecision(False, None, tuple(errors))

    merged = dict(current)
    for key, value in changes.items():
        if key in {"reason", "experimental", "promote_experimental", "commission"}:
            continue
        if isinstance(value, Decimal):
            merged[key] = format(value, "f")
        else:
            merged[key] = value
    if cleaned_commission is not None:
        merged["commission"] = cleaned_commission
    if cleaned_experimental is not None:
        merged["experimental"] = cleaned_experimental
        if promote:
            # Experimental RR candidates below 0.50 cannot be promoted
            # onto the active document. Other experimental fields may still
            # apply when they pass the normal active validators above.
            exp_rr = cleaned_experimental.get("min_reward_risk")
            if _active_rr_is_candidate(exp_rr):
                return PolicyDecision(
                    False,
                    None,
                    (
                        "promote_experimental cannot lower min_reward_risk "
                        f"below {OWNER_MIN_REWARD_RISK} "
                        "(owner net RR floor lock)",
                    ),
                )
            for key, value in cleaned_experimental.items():
                merged[key] = value
            merged["experimental_promoted"] = True
        else:
            merged["experimental_promoted"] = False
            if _active_rr_is_candidate(merged.get("min_reward_risk")):
                merged["min_reward_risk"] = str(OWNER_MIN_REWARD_RISK)
    # Fail closed: any path that left a sub-0.50 RR on the active document
    # is rewritten to the owner floor (stale promoted experiments included).
    if _active_rr_is_candidate(merged.get("min_reward_risk")):
        merged["min_reward_risk"] = str(OWNER_MIN_REWARD_RISK)
        merged["experimental_promoted"] = False
    weekly = _dec(merged.get("weekly_loss_pct") or 0)
    daily = _dec(merged.get("daily_loss_pct") or OWNER_DAILY_LOSS_PCT)
    drawdown = _dec(merged.get("max_drawdown_pct") or 0)
    if weekly > daily:
        return PolicyDecision(
            False, None, ("weekly_loss_pct cannot exceed daily_loss_pct",)
        )
    if drawdown > daily:
        return PolicyDecision(
            False, None, ("max_drawdown_pct cannot exceed daily_loss_pct",)
        )
    saved_min_lot = merged.get("min_lot")
    saved_max_lot = merged.get("max_lot")
    max_lot_value = OWNER_MAX_LOT if saved_max_lot is None else _dec(saved_max_lot)
    if saved_min_lot is not None and _dec(saved_min_lot) > max_lot_value:
        return PolicyDecision(False, None, ("min_lot cannot exceed max_lot",))
    planned_pct = _dec(merged.get("max_planned_risk_pct") or OWNER_MAX_PLANNED_RISK_PCT)
    aggregate_pct = _dec(
        merged.get("max_aggregate_open_risk_pct") or OWNER_MAX_AGGREGATE_OPEN_RISK_PCT
    )
    if aggregate_pct < planned_pct:
        return PolicyDecision(
            False,
            None,
            ("max_aggregate_open_risk_pct cannot be below max_planned_risk_pct",),
        )
    live_submit = merged.get("m1_live_submit") is True
    micro_off = merged.get("m1_micro_enabled") is False
    if live_submit and micro_off:
        return PolicyDecision(
            False,
            None,
            ("m1_live_submit requires m1_micro_enabled",),
        )
    return PolicyDecision(True, merged, (), source="validated")
