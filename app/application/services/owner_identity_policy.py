"""Reconcile platform roles to the verified designated owner.

The authenticated identity must come from the auth provider. This module
never trusts an email that arrived only in a request body.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.domain.entities.audit_log import AuditLog
from app.domain.entities.user import User
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.user import UserRole, UserStatus
from app.domain.exceptions.base import ConflictError
from app.domain.identity.designated_owner import is_designated_owner_email
from app.domain.interfaces.auth import AuthUserIdentity

_PRIVILEGED = frozenset({UserRole.OWNER, UserRole.ADMIN})


async def _privileged_users(repo: Any) -> list[User]:
    lister = getattr(repo, "list_privileged", None)
    if callable(lister):
        return list(await lister())
    items = getattr(repo, "items", None)
    if isinstance(items, dict):
        return [
            user
            for user in items.values()
            if getattr(user, "role", None) in _PRIVILEGED
        ]
    return []


def _decide(user: User, *, is_current: bool, email_confirmed: bool) -> str | None:
    designated = is_designated_owner_email(str(user.email))
    if designated and is_current and email_confirmed:
        if user.role != UserRole.OWNER:
            if user.status == UserStatus.DEACTIVATED:
                return None
            user.change_role(UserRole.OWNER)
            if user.status == UserStatus.PENDING:
                user.activate()
            return "promoted_owner"
        return None
    if designated and not is_current:
        return None
    if user.role in _PRIVILEGED:
        if user.status == UserStatus.DEACTIVATED:
            return None
        user.change_role(UserRole.TRADER)
        if designated:
            return "demoted_unverified_owner"
        return "demoted_not_designated"
    return None


async def reconcile_privileged_roles(
    uow: Any, identity: AuthUserIdentity
) -> list[dict[str, str]]:
    """Promote the verified designated owner and demote every other privileged user.

    Returns the changes applied. Existing trader accounts are left alone.
    """
    current = await uow.users.get_by_auth_user_id(identity.id)
    if current is None:
        from app.domain.value_objects.email import EmailAddress

        current = await uow.users.get_by_email(EmailAddress(value=identity.email))
    users = await _privileged_users(uow.users)
    seen = {user.id for user in users}
    if current is not None and current.id not in seen:
        users.append(current)

    changes: list[dict[str, str]] = []
    actor_id: UUID | None = current.id if current is not None else None
    for user in users:
        is_current = current is not None and user.id == current.id
        confirmed = bool(identity.email_confirmed) if is_current else False
        try:
            action = _decide(user, is_current=is_current, email_confirmed=confirmed)
        except ConflictError:
            action = None
        if action is None:
            continue
        await uow.users.update(user)
        changes.append(
            {
                "user_id": str(user.id),
                "action": action,
                "role": user.role.value,
            }
        )
        audits = getattr(uow, "audit_logs", None)
        if audits is not None and hasattr(audits, "add"):
            await audits.add(
                AuditLog.record(
                    action=AuditAction.UPDATE,
                    outcome=AuditOutcome.SUCCESS,
                    resource_type="user_role",
                    resource_id=user.id,
                    actor_user_id=actor_id or user.id,
                    message=f"privileged role {action}",
                    metadata={"role_action": action, "role": user.role.value},
                )
            )
    return changes
