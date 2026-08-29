"""Process-local execution account binding around the singleton gateway.

One Windows terminal can hold one MT5 login. This module records which
QuantForg user owns that login. It does not create a second gateway or engine.

Mismatch → ACCOUNT_SESSION_MISMATCH (fail closed). Unbound submits are left
to existing Safety/OMS gates so operator restore and unit tests keep working.
"""

from __future__ import annotations

from threading import Lock
from uuid import UUID

ACCOUNT_SESSION_MISMATCH = "ACCOUNT_SESSION_MISMATCH"
SESSION_MATCHED = "MATCHED"
SESSION_NOT_CONNECTED = "NOT_CONNECTED"

_LOCK = Lock()
_BOUND_USER_ID: UUID | None = None
_BOUND_LOGIN: int = 0


def reset_execution_binding_for_tests() -> None:
    global _BOUND_USER_ID, _BOUND_LOGIN
    with _LOCK:
        _BOUND_USER_ID = None
        _BOUND_LOGIN = 0


def bind_execution_account(*, user_id: UUID, login: int) -> None:
    """Record the authenticated owner of the live terminal login."""
    global _BOUND_USER_ID, _BOUND_LOGIN
    owned = int(login or 0)
    if owned <= 1:
        return
    with _LOCK:
        _BOUND_USER_ID = user_id
        _BOUND_LOGIN = owned


def unbind_execution_account(*, user_id: UUID | None = None) -> None:
    """Clear the binding. Another user's disconnect must not unbind the owner."""
    global _BOUND_USER_ID, _BOUND_LOGIN
    with _LOCK:
        if (
            user_id is not None
            and _BOUND_USER_ID is not None
            and user_id != _BOUND_USER_ID
        ):
            return
        _BOUND_USER_ID = None
        _BOUND_LOGIN = 0


def bound_execution_account() -> tuple[UUID | None, int]:
    with _LOCK:
        return _BOUND_USER_ID, _BOUND_LOGIN


def classify_account_session(
    *,
    user_id: UUID,
    owned_login: int,
    live_login: int,
) -> str:
    """Compare authenticated user, owned connection login, and live terminal."""
    owned = int(owned_login or 0)
    live = int(live_login or 0)
    if owned <= 1 or live <= 1:
        return SESSION_NOT_CONNECTED
    if owned != live:
        return ACCOUNT_SESSION_MISMATCH
    bound_user, bound_login = bound_execution_account()
    if bound_user is not None and bound_user != user_id:
        return ACCOUNT_SESSION_MISMATCH
    if bound_login > 1 and bound_login != owned:
        return ACCOUNT_SESSION_MISMATCH
    return SESSION_MATCHED


def submit_blocked_reason(*, user_id: UUID, login: int | None) -> str | None:
    """Return ACCOUNT_SESSION_MISMATCH when the live binding disagrees.

    When nothing is bound, return None so existing Safety/OMS gates remain
    authoritative (no second engine). After a user binds, the singleton must
    not execute for a different user_id or login.
    """
    bound_user, bound_login = bound_execution_account()
    if bound_user is None or bound_login <= 1:
        return None
    if user_id != bound_user:
        return ACCOUNT_SESSION_MISMATCH
    requested = int(login or 0)
    if requested > 1 and requested != bound_login:
        return ACCOUNT_SESSION_MISMATCH
    return None
