"""Feature flag for the M1 micro-scalping module. Default off."""

from __future__ import annotations

import os

_TRUE = {"1", "true", "yes", "on"}


def _flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in _TRUE


def m1_micro_enabled() -> bool:
    """True only when the operator has turned the module on.

    This does not authorize a broker order. Live submission stays a separate
    flag and is also default off.
    """
    return _flag("QUANTFORG_M1_MICRO_SCALPING")


def m1_live_submit_enabled() -> bool:
    """Both flags are required before the live hook may submit.

    Neither flag is set by this code. The hook calls this and still requires
    the existing execution switch and a guarded OMS port.
    """
    return m1_micro_enabled() and _flag("QUANTFORG_M1_MICRO_LIVE_SUBMIT")
