"""Keep the production worker on the latest worker code without manual steps.

Only the worker's own folders are refreshed from ``origin/main``; secrets
(``local.production.env``) and the rest of the checkout are never touched.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger("quantforg.mt5_worker_agent.self_update")

UPDATE_PATHS = ("services/mt5_worker_agent", "deploy/mt5_worker_agent")


def _git(root: Path, *args: str, run: Callable[..., Any]) -> Any:
    return run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def check_and_apply(
    root: Path,
    *,
    paths: tuple[str, ...] = UPDATE_PATHS,
    run: Callable[..., Any] = subprocess.run,
) -> bool:
    """True when newer worker code was applied and a restart is needed."""
    try:
        fetched = _git(root, "fetch", "--quiet", "origin", "main", run=run)
        if fetched.returncode != 0:
            return False
        diff = _git(root, "diff", "--quiet", "origin/main", "--", *paths, run=run)
        if diff.returncode == 0:
            return False
        if diff.returncode != 1:
            return False
        applied = _git(root, "checkout", "origin/main", "--", *paths, run=run)
        if applied.returncode != 0:
            logger.warning("worker_self_update_checkout_failed")
            return False
        logger.info("worker_self_update_applied paths=%s", ",".join(paths))
        return True
    except Exception:
        logger.exception("worker_self_update_failed")
        return False
