"""Public contact lead capture API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from app.application.services.contact_leads_service import create_contact_lead
from app.presentation.dependencies.auth import get_client_meta

router = APIRouter(prefix="/contact", tags=["contact"])


class ContactLeadRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    message: str = Field(min_length=10, max_length=4000)
    company: str = Field(default="", max_length=160)
    country: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=40)
    subject: str = Field(default="", max_length=160)
    plan_intent: str = Field(default="", max_length=40)
    experience: str = Field(default="", max_length=80)
    contact_method: str = Field(default="", max_length=40)


@router.post("/leads", status_code=status.HTTP_201_CREATED)
async def submit_contact_lead(
    body: ContactLeadRequest,
    request: Request,
) -> dict[str, Any]:
    ip, ua = get_client_meta(request)
    return await create_contact_lead(
        full_name=body.full_name,
        email=body.email,
        message=body.message,
        company=body.company,
        country=body.country,
        phone=body.phone,
        subject=body.subject,
        plan_intent=body.plan_intent,
        experience=body.experience,
        contact_method=body.contact_method,
        source_ip=ip,
        user_agent=ua,
    )
