"""FastAPI dependencies for Trading Ecosystem."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.application.services.ecosystem import EcosystemService


def get_ecosystem() -> EcosystemService:
    return EcosystemService()


EcosystemSvc = Annotated[EcosystemService, Depends(get_ecosystem)]
