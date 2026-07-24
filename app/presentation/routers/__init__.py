"""HTTP API routers.

Keep this package init lightweight. Eager imports here break
``importlib.import_module("app.presentation.routers.*")`` during
``create_app`` if any single router has a broken dependency — including
health probes needed by Railway.
"""

from __future__ import annotations

__all__: list[str] = []
