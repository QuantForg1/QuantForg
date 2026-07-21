"""Isolated plugin architecture — intentions only, never execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class KernelPlugin(Protocol):
    @property
    def name(self) -> str: ...

    def evaluate(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Return intentions only — must not call order_send or mutate OMS."""
        ...


@dataclass
class PluginRegistry:
    """Register plugins; invocations isolated (exceptions contained)."""

    _plugins: dict[str, KernelPlugin] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def register(self, plugin: KernelPlugin) -> None:
        with self._lock:
            self._plugins[plugin.name] = plugin

    def unregister(self, name: str) -> None:
        with self._lock:
            self._plugins.pop(name, None)

    def list(self) -> list[str]:
        with self._lock:
            return sorted(self._plugins.keys())

    def run_all(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        with self._lock:
            plugins = list(self._plugins.values())
        results: list[dict[str, Any]] = []
        for plugin in plugins:
            try:
                out = plugin.evaluate(dict(snapshot))
                if not isinstance(out, dict):
                    out = {"status": "invalid", "detail": "non-dict result"}
                out = dict(out)
                out["plugin"] = plugin.name
                out["isolated"] = True
                out["never_order_send"] = True
                # Strip any attempt to claim execution authority.
                out.pop("order_send", None)
                out.pop("risk_engine_passed", None)
                out.pop("safety_engine_passed", None)
                results.append(out)
            except Exception as exc:
                results.append(
                    {
                        "plugin": plugin.name,
                        "status": "error",
                        "detail": str(exc)[:500],
                        "isolated": True,
                        "never_order_send": True,
                    }
                )
        return results
