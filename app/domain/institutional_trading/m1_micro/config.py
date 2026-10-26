"""Feature flag for the M1 micro-scalping module. Default off."""

from __future__ import annotations

import os

_TRUE = {"1", "true", "yes", "on"}


def _flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in _TRUE


def _overlay(key: str) -> str | None:
    try:
        from app.domain.institutional_trading.runtime_policy import m1_overlay_mode
    except Exception:
        return "off"
    try:
        return m1_overlay_mode(key)
    except Exception:
        return "off"


def m1_micro_enabled() -> bool:
    """True only when the operator has turned the module on.

    This does not authorize a broker order. Live submission stays a separate
    flag and is also default off. A saved policy can turn the module off.
    It cannot turn the module on when the deployment flag is off. A failed
    policy read fails closed once a policy document is installed.
    """
    mode = _overlay("m1_micro_enabled")
    if mode == "off":
        return False
    return _flag("QUANTFORG_M1_MICRO_SCALPING")


def m1_live_submit_enabled() -> bool:
    """Both flags are required before the live hook may submit.

    Neither flag is set by this code. The hook calls this and still requires
    the existing execution switch and a guarded OMS port. A saved policy can
    disable live submit. It cannot enable submit when the deployment flag is off.
    """
    if not m1_micro_enabled():
        return False
    mode = _overlay("m1_live_submit")
    if mode == "off":
        return False
    return _flag("QUANTFORG_M1_MICRO_LIVE_SUBMIT")
