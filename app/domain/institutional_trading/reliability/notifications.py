"""Notification adapters — email, slack, discord, webhook, telegram."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4


class NotificationAdapter(Protocol):
    name: str

    def send(self, *, subject: str, body: str, meta: dict[str, Any] | None = None) -> bool:
        ...


@dataclass
class RecordingAdapter:
    """Test / dry-run adapter — records outbound notifications."""

    name: str
    sent: list[dict[str, Any]] = field(default_factory=list)

    def send(
        self, *, subject: str, body: str, meta: dict[str, Any] | None = None
    ) -> bool:
        self.sent.append(
            {
                "id": str(uuid4()),
                "at": datetime.now(UTC).isoformat(),
                "subject": subject,
                "body": body,
                "meta": dict(meta or {}),
            }
        )
        return True


@dataclass
class NotificationBus:
    adapters: dict[str, NotificationAdapter] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.adapters:
            for name in ("email", "slack", "discord", "webhook", "telegram"):
                self.adapters[name] = RecordingAdapter(name=name)

    def register(self, adapter: NotificationAdapter) -> None:
        self.adapters[adapter.name] = adapter

    def notify(
        self,
        *,
        channels: list[str] | None = None,
        subject: str,
        body: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        targets = channels or list(self.adapters.keys())
        results: dict[str, bool] = {}
        for name in targets:
            adapter = self.adapters.get(name)
            if adapter is None:
                results[name] = False
                continue
            results[name] = adapter.send(subject=subject, body=body, meta=meta)
        return results

    def outbox(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for name, adapter in self.adapters.items():
            if isinstance(adapter, RecordingAdapter):
                out[name] = list(adapter.sent)
        return out
