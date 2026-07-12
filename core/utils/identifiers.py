"""Identifier generation helpers."""

from __future__ import annotations

import uuid


def new_uuid() -> str:
    """Return a new RFC 4122 version-4 UUID as a string."""
    return str(uuid.uuid4())


def new_request_id() -> str:
    """Return a unique request correlation identifier.

    Format: ``req_<uuid4 hex without dashes>`` for easy log grepping.
    """
    return f"req_{uuid.uuid4().hex}"
