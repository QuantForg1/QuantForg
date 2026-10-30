"""Authoritative runtime trading policy.

Hard caps are the approved owner limits. A saved document may be stricter.
It cannot loosen them, disable gold-only, drop protective stops, bypass the
kill switch, or reintroduce a shorter UTC session gate.

Weekly loss percent defaults to 0 (off). A nonzero weekly halt is stored
only when an owner save sets it. There is no hidden weekly default.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.owner_live_limits import (
    OWNER_DAILY_LOSS_PCT,
    OWNER_MAX_LOT,
    OWNER_MAX_OPEN_POSITIONS,
    OWNER_MAX_PLANNED_RISK_PCT,
    OWNER_MAX_SPREAD,
    OWNER_MIN_REWARD_RISK,
    OWNER_MIN_TRADE_QUALITY,
    OWNER_MIN_TRADE_QUALITY_FLOOR,
    OWNER_SL_ATR_MULTIPLIER,
    OWNER_WEEKLY_LOSS_PCT,
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
    if raw is None:
        return fallback
    return _dec(raw)


def active_max_planned_risk_pct() -> Decimal:
    value = _active_decimal("max_planned_risk_pct", OWNER_MAX_PLANNED_RISK_PCT)
    if value <= 0 or value > OWNER_MAX_PLANNED_RISK_PCT:
        return OWNER_MAX_PLANNED_RISK_PCT
    return value


def active_daily_loss_pct() -> Decimal:
    value = _active_decimal("daily_loss_pct", OWNER_DAILY_LOSS_PCT)
    if value <= 0 or value > OWNER_DAILY_LOSS_PCT:
        return OWNER_DAILY_LOSS_PCT
    return value


def active_max_lot() -> Decimal:
    value = _active_decimal("max_lot", OWNER_MAX_LOT)
    if value <= 0 or value > OWNER_MAX_LOT:
        return OWNER_MAX_LOT
    return value


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
        return OWNER_MAX_LOT
    if value <= 0 or value > OWNER_MAX_LOT:
        return OWNER_MAX_LOT
    return value


def active_max_aggregate_open_risk_pct() -> Decimal:
    """Saved book cap. It cannot exceed the 14% ceiling."""
    value = _active_decimal("max_aggregate_open_risk_pct", OWNER_MAX_PLANNED_RISK_PCT)
    if value <= 0 or value > OWNER_MAX_PLANNED_RISK_PCT:
        return OWNER_MAX_PLANNED_RISK_PCT
    return value


def active_max_open_positions() -> int:
    """Saved concurrent-position cap. It cannot exceed one."""
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
    if value < 1 or value > OWNER_MAX_OPEN_POSITIONS:
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
    if value <= 0 or value > OWNER_MAX_SPREAD:
        return OWNER_MAX_SPREAD
    return value


def active_min_reward_risk() -> Decimal:
    """Published default is 1.50.

    A saved 0.10, 0.15, or 0.20 stays inactive unless this document was
    explicitly promoted. Any other value below 1.50 fails closed to 1.50.
    A saved value above 1.50 stays, because it is stricter.
    """
    from app.domain.institutional_trading.owner_live_limits import (
        authorized_min_reward_risk,
    )

    value = _active_decimal("min_reward_risk", OWNER_MIN_REWARD_RISK)
    authorized = authorized_min_reward_risk(value)
    if authorized is None or authorized >= OWNER_MIN_REWARD_RISK:
        return authorized or OWNER_MIN_REWARD_RISK
    doc = _POLICY.get()
    if isinstance(doc, dict) and doc.get("experimental_promoted") is True:
        return authorized
    return OWNER_MIN_REWARD_RISK


def active_min_trade_quality() -> int:
    """Unset policy stays 70. A saved integer from 70 to 100 is used.

    Below 70 or a non-integer fails closed to 70.
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


def weekly_loss_limit_pct() -> Decimal:
    """0 means the weekly halt is off. Never invents a nonzero default."""
    doc = _POLICY.get()
    if not isinstance(doc, dict) or doc.get("unavailable"):
        return OWNER_WEEKLY_LOSS_PCT
    raw = doc.get("weekly_loss_pct")
    if raw is None:
        return Decimal("0")
    value = _dec(raw)
    if value <= 0:
        return Decimal("0")
    return min(value, OWNER_DAILY_LOSS_PCT)


def drawdown_limit_pct() -> Decimal:
    """0 means the overall drawdown halt is off until an owner save."""
    doc = _POLICY.get()
    if not isinstance(doc, dict) or doc.get("unavailable"):
        return Decimal("0")
    raw = doc.get("max_drawdown_pct")
    if raw is None:
        return Decimal("0")
    value = _dec(raw)
    if value <= 0:
        return Decimal("0")
    return min(value, active_daily_loss_pct(), OWNER_DAILY_LOSS_PCT)


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
    """Approved live policy. Weekly halt is explicitly off."""
    return {
        "max_planned_risk_pct": "14.0",
        "daily_loss_pct": "19.0",
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
        "max_aggregate_open_risk_pct": "14.0",
        "max_concurrent_positions": OWNER_MAX_OPEN_POSITIONS,
        "min_lot": None,
        "max_lot": "0.01",
        "max_spread": "0.45",
        "min_reward_risk": "1.50",
        "min_trade_quality": OWNER_MIN_TRADE_QUALITY,
        "stop_atr_multiplier": "1.00",
        "gold_only": True,
        "protective_stop_required": True,
        "evaluate_full_utc_day": True,
        "ite_enabled": True,
        "unified_decision_enabled": True,
        "m1_micro_enabled": None,
        "m1_live_submit": None,
        "session_utc": "00:00-23:59",
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
        hi=OWNER_MAX_PLANNED_RISK_PCT,
    )
    _reject_number(
        errors,
        raw,
        "daily_loss_pct",
        lo=Decimal("0.01"),
        hi=OWNER_DAILY_LOSS_PCT,
    )
    _reject_number(errors, raw, "max_lot", lo=Decimal("0.01"), hi=OWNER_MAX_LOT)
    _reject_number(
        errors, raw, "max_spread", lo=Decimal("0.01"), hi=OWNER_MAX_SPREAD
    )
    from app.domain.institutional_trading.owner_live_limits import (
        atr_multiplier_verdict,
        authorized_min_reward_risk,
        authorized_min_trade_quality,
    )

    if "min_reward_risk" not in raw:
        errors.append("experimental min_reward_risk must be 0.10, 0.15, or 0.20")
    else:
        try:
            rr = _dec(raw["min_reward_risk"])
        except Exception:
            errors.append("experimental min_reward_risk is not a number")
        else:
            authorized = authorized_min_reward_risk(rr)
            if authorized is None or authorized >= OWNER_MIN_REWARD_RISK:
                errors.append(
                    "experimental min_reward_risk must be 0.10, 0.15, or 0.20"
                )
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
    if (
        "max_concurrent_positions" in raw
        and raw["max_concurrent_positions"] != OWNER_MAX_OPEN_POSITIONS
    ):
        errors.append(
            "experimental max_concurrent_positions is fixed at "
            f"{OWNER_MAX_OPEN_POSITIONS}"
        )
    if errors:
        return None, errors
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        cleaned[key] = format(value, "f") if isinstance(value, Decimal) else value
    return cleaned, []


def _active_rr_is_candidate(value: object) -> bool:
    from app.domain.institutional_trading.owner_live_limits import (
        authorized_min_reward_risk,
    )

    try:
        rr = _dec(value)
    except Exception:
        return False
    authorized = authorized_min_reward_risk(rr)
    return authorized is not None and authorized < OWNER_MIN_REWARD_RISK


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
        hi=OWNER_MAX_PLANNED_RISK_PCT,
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
                    "active min_reward_risk must be at least 1.50. "
                    "Candidates 0.10, 0.15, and 0.20 belong under experimental "
                    "and stay inactive until that experiment is promoted."
                )
    if "min_trade_quality" in changes:
        try:
            quality = int(changes["min_trade_quality"])
        except (TypeError, ValueError):
            errors.append("min_trade_quality is not an integer")
        else:
            if authorized_min_trade_quality(quality) is None:
                errors.append(
                    "min_trade_quality must be "
                    f"{OWNER_MIN_TRADE_QUALITY_FLOOR} to 100"
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
    if (
        "max_concurrent_positions" in changes
        and changes["max_concurrent_positions"] != OWNER_MAX_OPEN_POSITIONS
    ):
        errors.append(
            f"max_concurrent_positions is fixed at {OWNER_MAX_OPEN_POSITIONS}"
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
        if key in {"reason", "experimental", "promote_experimental"}:
            continue
        if isinstance(value, Decimal):
            merged[key] = format(value, "f")
        else:
            merged[key] = value
    if cleaned_experimental is not None:
        merged["experimental"] = cleaned_experimental
        if promote:
            for key, value in cleaned_experimental.items():
                merged[key] = value
            merged["experimental_promoted"] = True
        else:
            merged["experimental_promoted"] = False
            if _active_rr_is_candidate(merged.get("min_reward_risk")):
                merged["min_reward_risk"] = str(OWNER_MIN_REWARD_RISK)
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
    live_submit = merged.get("m1_live_submit") is True
    micro_off = merged.get("m1_micro_enabled") is False
    if live_submit and micro_off:
        return PolicyDecision(
            False,
            None,
            ("m1_live_submit requires m1_micro_enabled",),
        )
    return PolicyDecision(True, merged, (), source="validated")
