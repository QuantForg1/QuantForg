"""Server-side designated platform owner.

Privileges are granted only when the authenticated identity from the
trusted auth provider has this email and a confirmed address. A request
body that merely contains the email is not an identity.
"""

from __future__ import annotations

DESIGNATED_OWNER_EMAIL = "p7provider@gmail.com"


def normalize_email(value: object) -> str:
    return str(value or "").strip().lower()


def is_designated_owner_email(value: object) -> bool:
    """True when ``value`` is exactly the designated owner address."""
    return normalize_email(value) == DESIGNATED_OWNER_EMAIL
