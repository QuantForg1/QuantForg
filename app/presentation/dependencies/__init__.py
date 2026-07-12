"""FastAPI dependency providers.

Resolve application services and infrastructure clients from the DI
container. Routers depend on these callables via ``Depends()``.
"""

from app.presentation.dependencies.services import (
    get_health_service,
    get_settings_dependency,
    get_version_service,
)

__all__ = [
    "get_health_service",
    "get_settings_dependency",
    "get_version_service",
]
