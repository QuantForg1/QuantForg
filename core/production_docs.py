"""Location of generated production evidence (reports, validation, execution).

Generated artifacts go under ``production_docs_dir()``. Production keeps the
repo's ``docs/production``; tests point ``QUANTFORG_PRODUCTION_DOCS_DIR`` at a
temp dir so a test run never rewrites tracked files. Committed guides
(OPERATIONS_GUIDE.md etc.) are still read from the repo.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_VAR = "QUANTFORG_PRODUCTION_DOCS_DIR"


def production_docs_override() -> Path | None:
    raw = (os.environ.get(ENV_VAR) or "").strip()
    return Path(raw) if raw else None


def production_docs_dir() -> Path:
    return production_docs_override() or REPO_ROOT / "docs" / "production"
