"""Public runtime deployment identity.

Reads only Railway-injected identity variables. Never fabricates a SHA,
never walks the filesystem, never spawns git, never returns secrets.
"""

from __future__ import annotations

import os

_UNKNOWN = "unknown"


def runtime_git_commit() -> str:
    """Return RAILWAY_GIT_COMMIT_SHA, or 'unknown' when absent."""
    value = (os.environ.get("RAILWAY_GIT_COMMIT_SHA") or "").strip()
    return value if value else _UNKNOWN


def runtime_deployment_id() -> str:
    """Return RAILWAY_DEPLOYMENT_ID, or 'unknown' when absent."""
    value = (os.environ.get("RAILWAY_DEPLOYMENT_ID") or "").strip()
    return value if value else _UNKNOWN
