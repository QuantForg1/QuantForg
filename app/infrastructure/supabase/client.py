"""Supabase client adapter.

Thin infrastructure wrapper around the official Supabase Python client.
Domain and application layers must not import this module directly; obtain
the client via the DI container when a use case needs Supabase I/O.
"""

from __future__ import annotations

from typing import Any

import httpx
from supabase import Client, create_client

from core.config.settings import Settings
from core.logging import get_logger

logger = get_logger(__name__)


class SupabaseClient:
    """Lazy Supabase client bound to application settings.

    Parameters
    ----------
    settings:
        Application settings providing ``SUPABASE_URL`` and API keys.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Client | None = None
        self._admin_client: Client | None = None

    @property
    def configured(self) -> bool:
        """Return True when URL and an API key are available."""
        return self._settings.supabase_configured

    @property
    def client(self) -> Client:
        """Return the initialised Supabase SDK client (anon/publishable)."""
        if self._client is None:
            msg = "SupabaseClient is not connected; call connect() first"
            raise RuntimeError(msg)
        return self._client

    @property
    def admin_client(self) -> Client:
        """Return service-role client when configured, else the public client.

        Service role bypasses RLS and is required for server-side profile
        upserts during registration before an end-user JWT exists.
        """
        if self._admin_client is not None:
            return self._admin_client
        return self.client

    def connect(self) -> None:
        """Create the Supabase SDK client from settings."""
        if self._client is not None:
            return
        if not self._settings.supabase_configured:
            msg = "Supabase is not configured (SUPABASE_URL / API key missing)"
            raise RuntimeError(msg)
        api_key = self._settings.supabase_api_key
        assert api_key is not None  # guarded by supabase_configured
        base = self._settings.supabase_url.strip()
        self._client = create_client(base, api_key)
        service = self._settings.supabase_service_role_key
        if service is not None:
            secret = service.get_secret_value().strip()
            if secret:
                self._admin_client = create_client(base, secret)
        logger.info("supabase_client_connected", url=self._settings.supabase_url)

    def disconnect(self) -> None:
        """Drop the client reference (SDK has no explicit close)."""
        self._client = None
        self._admin_client = None
        logger.info("supabase_client_disconnected")

    @property
    def settings(self) -> Settings:
        return self._settings

    def verify_connection(self, *, timeout: float = 5.0) -> dict[str, Any]:
        """Probe Supabase Auth health without writing data.

        Uses the Auth health endpoint so verification works even when no
        application tables exist yet.
        """
        if not self._settings.supabase_configured:
            msg = "Supabase is not configured"
            raise RuntimeError(msg)
        api_key = self._settings.supabase_api_key
        assert api_key is not None
        base = self._settings.supabase_url.rstrip("/")
        response = httpx.get(
            f"{base}/auth/v1/health",
            headers={
                "apikey": api_key,
                "Authorization": f"Bearer {api_key}",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload: dict[str, Any]
        try:
            body = response.json()
            payload = body if isinstance(body, dict) else {"raw": body}
        except ValueError:
            payload = {"status_code": response.status_code}
        return {
            "ok": True,
            "status_code": response.status_code,
            "endpoint": f"{base}/auth/v1/health",
            "details": payload,
        }
