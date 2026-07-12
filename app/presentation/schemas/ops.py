"""Operations API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MonitoringDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall: str
    components: list[dict[str, Any]]
    collected_at: str
    execution_enabled: bool = False


class MetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_latency_ms_avg: float
    error_rate: float
    throughput_per_minute: float
    cache_hit_ratio: float
    job_duration_ms_avg: float
    request_count: int = 0
    error_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    job_count: int = 0
    collected_at: str


class AlertsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: list[dict[str, Any]] = Field(default_factory=list)
    alerts: list[dict[str, Any]] = Field(default_factory=list)


class AuditCenterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: list[str]
    events: dict[str, list[dict[str, Any]]]
    counts: dict[str, int]
