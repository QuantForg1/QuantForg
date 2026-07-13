"""MT5 Gateway request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConnectRequest(BaseModel):
    """Broker credentials — accepted only by the Windows gateway.

    Never persist these in Railway environment variables.
    """

    login: int = Field(..., gt=0)
    password: str = Field(..., min_length=1)
    server: str = Field(..., min_length=1, max_length=128)
    path: str = Field(default="", max_length=512)
