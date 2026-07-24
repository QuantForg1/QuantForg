"""QuantForg Event Mesh (QEM) — V6.1 institutional event backbone.

Completely read-only event distribution. Never executes trades, modifies
production, strategies, or risk, or approves releases. Events are immutable.
"""

from __future__ import annotations

from app.domain.quantforg_event_mesh.platform import QuantForgEventMesh

__all__ = ["QuantForgEventMesh", "get_qem"]

_QEM: QuantForgEventMesh | None = None


def get_qem() -> QuantForgEventMesh:
    global _QEM
    if _QEM is None:
        _QEM = QuantForgEventMesh()
    return _QEM
