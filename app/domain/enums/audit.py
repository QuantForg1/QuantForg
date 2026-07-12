"""Audit log enumerations."""

from __future__ import annotations

from enum import StrEnum


class AuditAction(StrEnum):
    """Category of a recorded audit event."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    SUSPEND = "suspend"
    REVOKE = "revoke"
    SUBMIT = "submit"
    CANCEL = "cancel"
    EXPORT = "export"
    SYSTEM = "system"


class AuditOutcome(StrEnum):
    """Result of the audited action."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
