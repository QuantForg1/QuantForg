"""QuantForg Strategy Factory (QSF) — end-to-end governed strategy workflow.

Factory-isolated. Never executes trades, modifies production, approves releases,
deploys strategies, or allocates capital. Every pipeline transition requires
explicit human approval.
"""

from __future__ import annotations

from app.domain.quantforg_strategy_factory.platform import QuantForgStrategyFactory

__all__ = ["QuantForgStrategyFactory", "get_qsf"]

_QSF: QuantForgStrategyFactory | None = None


def get_qsf() -> QuantForgStrategyFactory:
    global _QSF
    if _QSF is None:
        _QSF = QuantForgStrategyFactory()
    return _QSF
