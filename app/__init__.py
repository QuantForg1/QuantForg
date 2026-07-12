"""QuantForg application package.

Organised according to Clean Architecture:

- ``domain``         — entities, value objects, domain exceptions, ports
- ``application``    — use cases / application services, DTOs
- ``infrastructure`` — adapters (DB, cache, repositories)
- ``presentation``   — HTTP routers, middleware, FastAPI dependencies

No trading, AI, indicator, or strategy logic lives in this foundation.
"""

__version__ = "1.0.0"
