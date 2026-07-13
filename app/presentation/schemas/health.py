"""Health endpoint response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DependencyStatusSchema(BaseModel):
    """Schema for a single dependency health status."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="Dependency identifier")
    status: str = Field(description="healthy | unhealthy | degraded | disabled")
    latency_ms: float = Field(description="Probe latency in milliseconds")


class HealthResponse(BaseModel):
    """Schema for the aggregated health report."""

    model_config = ConfigDict(from_attributes=True)

    status: str = Field(description="Overall health status")
    version: str = Field(description="Application semantic version")
    environment: str = Field(description="Runtime environment name")
    dependencies: list[DependencyStatusSchema] = Field(
        default_factory=list,
        description="Per-dependency health statuses",
    )
