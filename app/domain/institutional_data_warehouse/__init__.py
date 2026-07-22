"""Institutional Data Warehouse — analytics infrastructure only.

Never modifies production records or trading behaviour.
"""

from __future__ import annotations

from app.domain.institutional_data_warehouse.analytics import run_analytics
from app.domain.institutional_data_warehouse.models import DATA_DOMAINS, HARD_LOCKS
from app.domain.institutional_data_warehouse.reports import build_warehouse_pack
from app.domain.institutional_data_warehouse.schema import normalize_warehouse_record
from app.domain.institutional_data_warehouse.store import (
    InstitutionalDataWarehouse,
    get_warehouse,
)

__all__ = [
    "DATA_DOMAINS",
    "HARD_LOCKS",
    "InstitutionalDataWarehouse",
    "build_warehouse_pack",
    "get_warehouse",
    "normalize_warehouse_record",
    "run_analytics",
]
