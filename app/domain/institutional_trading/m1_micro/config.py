"""Feature flags for the M1 micro-scalping module.

Evaluation defaults on so M1 participates in unified LIVE arbitration.
Live order submission stays a separate, default-off flag.
"""

from __future__ import annotations

import os

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _flag(name: str) -> bool | None:
    """Return True/False when set, None when unset."""
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return None
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    return None


def _overlay(key: str) -> str | None:
    try:
        from app.domain.institutional_trading.runtime_policy import m1_overlay_mode
    except Exception:
        return None
    try:
        return m1_overlay_mode(key)
    except Exception:
        return None


def m1_micro_enabled() -> bool:
    """True when M1 may evaluate inside the LIVE decision pipeline.

    Default on (PR #180) so M1 is not permanently unused. A saved policy can
    force the module off. An explicit ``QUANTFORG_M1_MICRO_SCALPING=false``
    also disables evaluation. This does not authorize a broker order.
    """
    mode = _overlay("m1_micro_enabled")
    if mode == "off":
        return False
    flagged = _flag("QUANTFORG_M1_MICRO_SCALPING")
    if flagged is None:
        return True
    return flagged


def m1_live_submit_enabled() -> bool:
    """Both evaluation and an explicit LIVE submit flag are required.

    Neither flag invents a stop or bypasses Risk/OMS. A saved policy can
    disable live submit. It cannot enable submit when the deployment flag is off.
    Default off until costed shadow/LIVE readiness is confirmed.
    """
    if not m1_micro_enabled():
        return False
    mode = _overlay("m1_live_submit")
    if mode == "off":
        return False
    flagged = _flag("QUANTFORG_M1_MICRO_LIVE_SUBMIT")
    return flagged is True
