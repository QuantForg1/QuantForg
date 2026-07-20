"""Global ITE kill switch — Decision Engine continues; OMS receives nothing."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class KillSwitch:
    """Process-scoped emergency stop for the Execution Bridge."""

    _enabled: bool = False
    _lock: Lock = field(default_factory=Lock, repr=False)

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def arm(self) -> None:
        """Enable kill switch — block all OMS forwards."""
        with self._lock:
            self._enabled = True

    def disarm(self) -> None:
        with self._lock:
            self._enabled = False

    def set(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = bool(enabled)
