"""Authoritative SCALP / HOLD / UNKNOWN management overlays.

Does not invent a trade class. Recovered positions without proven evidence
are TRADE_CLASS_UNKNOWN and use the safest existing fallback — never a
silent SCALP or HOLD conversion.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from threading import Lock
from typing import Any

TRADE_CLASS_UNKNOWN = "TRADE_CLASS_UNKNOWN"
PROVEN_TRADE_CLASSES = frozenset({"SCALP", "HOLD"})

HOLD_BREAK_EVEN_AT_R = Decimal("1.0")
HOLD_BREAK_EVEN_OFFSET_R = Decimal("0.2")
HOLD_ABSOLUTE_MAX_HOLD_MINUTES = 0
HOLD_TIME_STOP_MINUTES = 20

SCALP_BREAK_EVEN_AT_R = Decimal("0.5")
SCALP_BREAK_EVEN_OFFSET_R = Decimal("0.2")
SCALP_ABSOLUTE_MAX_HOLD_MINUTES = 25

UNKNOWN_BREAK_EVEN_AT_R = Decimal("1.0")
UNKNOWN_BREAK_EVEN_OFFSET_R = Decimal("0.2")
UNKNOWN_ABSOLUTE_MAX_HOLD_MINUTES = 25
UNKNOWN_TIME_STOP_MINUTES = 25

_COMMENT_CLASS_MARKERS = {"S": "SCALP", "H": "HOLD", "U": TRADE_CLASS_UNKNOWN}
_CLASS_TO_MARKER = {"SCALP": "S", "HOLD": "H", TRADE_CLASS_UNKNOWN: "U"}

_LOCK = Lock()
_LAST_FILL_META: dict[str, Any] = {}


def proven_trade_class(raw: Any) -> str:
    """Return SCALP, HOLD, or TRADE_CLASS_UNKNOWN. Never invent a class."""
    value = str(raw or "").strip().upper()
    if value in PROVEN_TRADE_CLASSES:
        return value
    if value in {TRADE_CLASS_UNKNOWN, "UNKNOWN", "UNPROVEN", ""}:
        return TRADE_CLASS_UNKNOWN
    return TRADE_CLASS_UNKNOWN


def encode_execution_comment(
    prefix: str,
    input_hash: str,
    trade_class: str | None,
) -> str:
    marker = _CLASS_TO_MARKER.get(proven_trade_class(trade_class), "U")
    digest = str(input_hash or "")[:12]
    return f"{prefix}:{marker}:{digest}"


def trade_class_from_comment(comment: str | None) -> str | None:
    """Proven class from MT5 comment marker, or None when unproven."""
    parts = str(comment or "").strip().split(":")
    if len(parts) < 3:
        return None
    marker = parts[2].upper()
    if marker in _COMMENT_CLASS_MARKERS and len(marker) == 1:
        return _COMMENT_CLASS_MARKERS[marker]
    return None


def comment_hash_suffix(comment: str | None) -> str:
    return str(comment or "").strip().split(":")[-1]


def remember_fill_metadata(meta: dict[str, Any] | None) -> None:
    with _LOCK:
        global _LAST_FILL_META
        _LAST_FILL_META = dict(meta or {})


def last_fill_metadata() -> dict[str, Any]:
    with _LOCK:
        return dict(_LAST_FILL_META)


def merge_position_metadata(
    *,
    snapshot: dict[str, Any] | None = None,
    comment: str | None = None,
    live_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Layer snapshot → live in-process fill → comment. Never fabricate class."""
    out: dict[str, Any] = {}
    snap = dict(snapshot or {})
    live = dict(live_meta if live_meta is not None else last_fill_metadata())
    keys = (
        "trade_class",
        "cycle_id",
        "snapshot_id",
        "position_plan_id",
        "opportunity_score",
        "management_profile",
        "magic",
        "comment",
        "symbol",
        "direction",
        "side",
        "volume",
        "entry",
        "sl",
        "tp",
    )
    for key in keys:
        if snap.get(key) not in {None, ""}:
            out[key] = snap[key]
    live_hash = str(live.get("comment_hash") or "")
    comment_text = comment or str(out.get("comment") or "")
    if live_hash and live_hash == comment_hash_suffix(comment_text):
        for key in keys:
            if out.get(key) in {None, ""} and live.get(key) not in {None, ""}:
                out[key] = live[key]
    comment_class = trade_class_from_comment(comment_text)
    proven = proven_trade_class(out.get("trade_class"))
    if proven == TRADE_CLASS_UNKNOWN and comment_class in PROVEN_TRADE_CLASSES:
        proven = comment_class
    out["trade_class"] = proven
    return out


@dataclass(frozen=True, slots=True)
class ClassManagementProfile:
    trade_class: str
    break_even_at_r: Decimal
    break_even_offset_r: Decimal
    absolute_max_hold_minutes: int
    time_stop_minutes: int
    momentum_fade_exit: bool
    volatility_collapse_exit: bool
    profile_name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_class": self.trade_class,
            "break_even_at_r": str(self.break_even_at_r),
            "break_even_offset_r": str(self.break_even_offset_r),
            "absolute_max_hold_minutes": self.absolute_max_hold_minutes,
            "time_stop_minutes": self.time_stop_minutes,
            "momentum_fade_exit": self.momentum_fade_exit,
            "volatility_collapse_exit": self.volatility_collapse_exit,
            "profile_name": self.profile_name,
        }


def resolve_class_management(trade_class: Any) -> ClassManagementProfile:
    cls = proven_trade_class(trade_class)
    if cls == "SCALP":
        from app.domain.institutional_trading.ai_scalping.config import (
            DEFAULT_AI_SCALPING_CONFIG as scalp,
        )

        return ClassManagementProfile(
            trade_class="SCALP",
            break_even_at_r=SCALP_BREAK_EVEN_AT_R,
            break_even_offset_r=SCALP_BREAK_EVEN_OFFSET_R,
            absolute_max_hold_minutes=SCALP_ABSOLUTE_MAX_HOLD_MINUTES,
            time_stop_minutes=int(scalp.time_stop_minutes),
            momentum_fade_exit=bool(scalp.momentum_fade_exit),
            volatility_collapse_exit=bool(scalp.volatility_collapse_exit),
            profile_name="scalp",
        )
    if cls == "HOLD":
        return ClassManagementProfile(
            trade_class="HOLD",
            break_even_at_r=HOLD_BREAK_EVEN_AT_R,
            break_even_offset_r=HOLD_BREAK_EVEN_OFFSET_R,
            absolute_max_hold_minutes=HOLD_ABSOLUTE_MAX_HOLD_MINUTES,
            time_stop_minutes=HOLD_TIME_STOP_MINUTES,
            momentum_fade_exit=False,
            volatility_collapse_exit=False,
            profile_name="hold",
        )
    return ClassManagementProfile(
        trade_class=TRADE_CLASS_UNKNOWN,
        break_even_at_r=UNKNOWN_BREAK_EVEN_AT_R,
        break_even_offset_r=UNKNOWN_BREAK_EVEN_OFFSET_R,
        absolute_max_hold_minutes=UNKNOWN_ABSOLUTE_MAX_HOLD_MINUTES,
        time_stop_minutes=UNKNOWN_TIME_STOP_MINUTES,
        momentum_fade_exit=False,
        volatility_collapse_exit=False,
        profile_name="unknown_safe_fallback",
    )
