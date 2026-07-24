"""QuantForg Canonical Data Model (QCDM) — enterprise data contract.

Completely read-only. Exposes schema metadata, relationships, and governance.
Never executes trades or modifies production or strategies.
"""

from __future__ import annotations

from app.domain.quantforg_canonical_data_model.platform import (
    QuantForgCanonicalDataModel,
)

__all__ = ["QuantForgCanonicalDataModel", "get_qcdm"]

_QCDM: QuantForgCanonicalDataModel | None = None


def get_qcdm() -> QuantForgCanonicalDataModel:
    global _QCDM
    if _QCDM is None:
        _QCDM = QuantForgCanonicalDataModel()
    return _QCDM
