"""Execution Audit Engine repository port."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.execution_audit import ExecutionAudit


class ExecutionAuditRepository(Protocol):
    """Persist and query immutable execution-stage audits."""

    async def add(self, audit: ExecutionAudit) -> ExecutionAudit:
        """Insert one audit row and return it."""
        ...

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[ExecutionAudit]:
        """Return newest audits for a user."""
        ...

    async def list_by_request_id(
        self, user_id: UUID, request_id: str
    ) -> list[ExecutionAudit]:
        """Return the stage timeline for one request_id (oldest first)."""
        ...

    async def list_recent(self, *, limit: int = 500) -> list[ExecutionAudit]:
        """Return newest audits across users (ops/service role)."""
        ...
