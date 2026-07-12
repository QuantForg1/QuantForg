"""Dependency injection container for QuantForg.

A lightweight, explicit DI container that wires infrastructure adapters
to application ports. No third-party DI framework is used — the container
is plain Python for transparency and type-checker friendliness.
"""

from core.di.container import Container, get_container, set_container

__all__ = [
    "Container",
    "get_container",
    "set_container",
]
