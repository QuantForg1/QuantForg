"""XAUUSD M1 micro-scalping decisions.

The module is off unless ``QUANTFORG_M1_MICRO_SCALPING`` is true. Live
submission also requires ``QUANTFORG_M1_MICRO_LIVE_SUBMIT`` and the existing
execution switch. The live hook sends only through the guarded OMS port.
"""

from app.domain.institutional_trading.m1_micro.config import m1_micro_enabled
from app.domain.institutional_trading.m1_micro.engine import evaluate_m1

__all__ = ["evaluate_m1", "m1_micro_enabled"]
