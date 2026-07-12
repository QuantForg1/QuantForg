"""Adapters that expose core Settings as domain AppInfoPort."""

from __future__ import annotations

from dataclasses import dataclass

from core.config.settings import Settings


@dataclass(frozen=True, slots=True)
class SettingsAppInfo:
    """Adapt :class:`~core.config.settings.Settings` to :class:`AppInfoPort`."""

    settings: Settings

    @property
    def app_name(self) -> str:
        return self.settings.app_name

    @property
    def app_version(self) -> str:
        return self.settings.app_version

    @property
    def environment(self) -> str:
        return self.settings.app_env.value

    @property
    def api_prefix(self) -> str:
        return self.settings.api_prefix

    @property
    def health_check_timeout_seconds(self) -> float:
        return self.settings.health_check_timeout_seconds
