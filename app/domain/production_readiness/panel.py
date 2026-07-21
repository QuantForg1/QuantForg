"""Panel snapshot helpers — available / empty / unavailable only."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

PanelStatus = Literal["available", "empty", "unavailable"]


@dataclass(frozen=True)
class PanelSnapshot:
    panel_id: str
    title: str
    status: PanelStatus
    source: str
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "status": self.status,
            "source": self.source,
            "data": dict(self.data),
            "message": self.message,
        }


def panel(
    panel_id: str,
    title: str,
    *,
    source: str,
    data: dict[str, Any] | None = None,
    status: PanelStatus | None = None,
    message: str = "",
) -> PanelSnapshot:
    payload = dict(data or {})
    if status is None:
        resolved: PanelStatus = "empty" if not payload else "available"
    else:
        resolved = status
    return PanelSnapshot(
        panel_id=panel_id,
        title=title,
        status=resolved,
        source=source,
        data=payload,
        message=message,
    )
