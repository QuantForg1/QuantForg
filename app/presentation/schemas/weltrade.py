"""Weltrade presentation schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WeltradeConnectRequest(BaseModel):
    login: int = Field(..., gt=0)
    password: str = Field(default="", max_length=256)
    server: str = Field(default="auto", max_length=128)
    account_type: str = Field(default="demo", pattern="^(demo|live)$")
    prefer_attach: bool = True
    path: str = Field(default="", max_length=512)
    remember_on_gateway: bool = Field(
        default=True,
        description=(
            "The password is encrypted in the broker credential store. "
            "It is never returned to the browser."
        ),
    )
    confirm_leave_exposure: bool = Field(
        default=False,
        description=(
            "Owner confirms that open positions stay on the current account "
            "and are not closed or moved."
        ),
    )


class WeltradeAttachRequest(BaseModel):
    path: str = Field(default="", max_length=512)
