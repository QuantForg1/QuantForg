"""Version endpoint response schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VersionResponse(BaseModel):
    """Schema for application version metadata."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="Application name")
    version: str = Field(description="Semantic version")
    environment: str = Field(description="Runtime environment")
    api_prefix: str = Field(description="API route prefix")
