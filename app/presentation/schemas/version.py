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
    git_commit: str = Field(
        default="unknown",
        description="Railway RAILWAY_GIT_COMMIT_SHA, or unknown",
    )
    deployment_id: str = Field(
        default="unknown",
        description="Railway RAILWAY_DEPLOYMENT_ID, or unknown",
    )
