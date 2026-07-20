"""Global ITE kill switch — single source of truth via OperationsControlPlane.

When bound to the ops plane, arm/disarm/enabled all read/write
``OperationsControlPlane.kill_switch_armed``. Unbound instances keep a local
flag for unit tests that construct a bridge without the plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.institutional_trading.operations.control_plane import (
        OperationsControlPlane,
    )


@dataclass
class KillSwitch:
    """Process-scoped emergency stop shared by Bridge, Ops, and PME."""

    plane: OperationsControlPlane | None = None
    _local_enabled: bool = False
    _lock: Lock = field(default_factory=Lock, repr=False)

    def bind(self, plane: OperationsControlPlane) -> KillSwitch:
        """Attach to the ops control plane (shared source of truth)."""
        self.plane = plane
        return self

    @property
    def enabled(self) -> bool:
        if self.plane is not None:
            return bool(self.plane.kill_switch_armed)
        with self._lock:
            return self._local_enabled

    def arm(self) -> None:
        """Enable kill switch — block all OMS forwards / PME mods."""
        if self.plane is not None:
            with self.plane._lock:
                self.plane.kill_switch_armed = True
            return
        with self._lock:
            self._local_enabled = True

    def disarm(self) -> None:
        if self.plane is not None:
            with self.plane._lock:
                self.plane.kill_switch_armed = False
            return
        with self._lock:
            self._local_enabled = False

    def set(self, enabled: bool) -> None:
        if enabled:
            self.arm()
        else:
            self.disarm()
