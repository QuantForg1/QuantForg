"""Operations platform DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class OpsDashboardDTO:
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class OpsMetricsDTO:
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class OpsAlertsDTO:
    rules: list[dict[str, Any]]
    alerts: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class OpsAuditCenterDTO:
    payload: dict[str, Any]
