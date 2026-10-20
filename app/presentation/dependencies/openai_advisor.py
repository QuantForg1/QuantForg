"""FastAPI dependency for the OpenAI advisor service."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.application.services.openai_advisor_service import (
    OpenAIAdvisorService,
    build_openai_advisor_from_settings,
)
from core.config.settings import Settings, get_settings


def get_openai_advisor(
    settings: Annotated[Settings, Depends(get_settings)],
) -> OpenAIAdvisorService:
    return build_openai_advisor_from_settings(settings)


OpenAIAdvisorDep = Annotated[OpenAIAdvisorService, Depends(get_openai_advisor)]
