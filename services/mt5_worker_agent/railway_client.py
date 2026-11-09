"""Outbound HTTPS client from local Windows agent → Railway control plane.

No inbound public ports. Credentials/passwords are never sent in heartbeat
payloads. Service identity uses WORKER_SERVICE_TOKEN bearer auth.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("quantforg.mt5_worker_agent.railway")


@dataclass(frozen=True, slots=True)
class RailwayClientConfig:
    api_base_url: str
    service_token: str
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> RailwayClientConfig:
        api = (os.environ.get("QUANTFORG_API_BASE_URL") or "").strip().rstrip("/")
        token = (os.environ.get("WORKER_SERVICE_TOKEN") or "").strip()
        if not api:
            raise ValueError("QUANTFORG_API_BASE_URL is required")
        if len(token) < 16:
            raise ValueError("WORKER_SERVICE_TOKEN missing or too short")
        api_l = api.lower()
        # Allow http://127.0.0.1 for local API dry-runs only.
        if (
            not api_l.startswith("https://")
            and not api_l.startswith("http://127.0.0.1")
            and not api_l.startswith("http://localhost")
        ):
            raise ValueError("QUANTFORG_API_BASE_URL must use https://")
        return cls(api_base_url=api, service_token=token)


class RailwayWorkerClient:
    """Minimal authenticated outbound client (stdlib only)."""

    def __init__(self, config: RailwayClientConfig) -> None:
        self._config = config

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._config.api_base_url}{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(  # noqa: S310
            url,
            data=body,
            method=method.upper(),
            headers={
                "Authorization": f"Bearer {self._config.service_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "quantforg-mt5-worker-agent/1b-local",
            },
        )
        try:
            with urllib.request.urlopen(  # noqa: S310
                req, timeout=self._config.timeout_seconds
            ) as resp:
                raw = resp.read().decode("utf-8") if resp is not None else ""
                if not raw:
                    return {"ok": True, "status": getattr(resp, "status", 0)}
                data = json.loads(raw)
                return data if isinstance(data, dict) else {"ok": True, "data": data}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            logger.warning(
                "railway_http_error method=%s path=%s status=%s detail=%s",
                method,
                path,
                exc.code,
                detail,
            )
            return {"ok": False, "status": exc.code, "error": "http_error"}
        except urllib.error.URLError as exc:
            logger.warning(
                "railway_url_error method=%s path=%s reason=%s",
                method,
                path,
                type(exc.reason).__name__,
            )
            return {"ok": False, "error": "url_error"}

    def health_ping(self) -> dict[str, Any]:
        # Prefer public live health (no secrets) then optional worker route.
        live = self._request("GET", "/api/v1/health/live")
        return live

    def register_worker(self, *, host_code: str, slot_id: str) -> dict[str, Any]:
        """Best-effort registration. Endpoint may not exist yet — report honestly."""
        return self._request(
            "POST",
            "/api/v1/mt5-workers/register",
            {
                "host_code": host_code,
                "slot_id": slot_id,
                "platform": "windows-local",
            },
        )

    def heartbeat(
        self,
        *,
        worker_id: str,
        slot_id: str,
        lifecycle: str,
        ready: bool,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/mt5-workers/heartbeat",
            {
                "worker_id": worker_id,
                "slot_id": slot_id,
                "lifecycle": lifecycle,
                "ready": ready,
            },
        )
