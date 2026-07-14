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


class AttachRequest(BaseModel):
    """Reuse an already logged-in MT5 terminal session (no broker password).

    Suitable when the Windows terminal is already authenticated (e.g. XM demo).
    Broker secrets still never leave the Windows host / terminal.
    """

    path: str = Field(
        default="",
        max_length=512,
        description="Optional path to terminal64.exe; otherwise MT5_TERMINAL_PATH",
    )
