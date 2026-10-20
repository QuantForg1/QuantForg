"""OpenAI Responses API client (httpx).

Advisory transport only. Never logs API keys, Authorization headers, or
full prompts that may contain account secrets. No Gemini / Google paths.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any

import httpx

from core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
# Documented Responses model — override with OPENAI_MODEL. Prefer a lower-cost
# default for advisory traffic; operators may set gpt-6-astra / gpt-5.5 etc.
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"


class OpenAIProviderError(Exception):
    """Typed provider failure with a safe public code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in {"authorization", "api-key", "x-api-key"}:
            out[key] = "***"
        else:
            out[key] = value
    return out


class OpenAIResponsesClient:
    """Thin async client for ``POST /v1/responses``."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_OPENAI_MODEL,
        base_url: str = DEFAULT_OPENAI_BASE_URL,
        timeout_seconds: float = 20.0,
        max_retries: int = 1,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self.model = (model or DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL
        self.base_url = (base_url or DEFAULT_OPENAI_BASE_URL).rstrip("/")
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self.max_retries = max(0, min(int(max_retries), 2))
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def create_response(
        self,
        *,
        input_text: str,
        instructions: str,
        text_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._api_key:
            raise OpenAIProviderError(
                "missing_api_key",
                "OPENAI_API_KEY is not configured",
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
            "store": False,
        }
        if text_format is not None:
            payload["text"] = {"format": text_format}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/responses"
        last_exc: Exception | None = None
        attempts = self.max_retries + 1

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self._transport,
        ) as client:
            for attempt in range(attempts):
                try:
                    response = await client.post(url, headers=headers, json=payload)
                except httpx.TimeoutException as exc:
                    last_exc = OpenAIProviderError(
                        "timeout",
                        "OpenAI request timed out",
                    )
                    logger.warning(
                        "openai_request_timeout",
                        attempt=attempt + 1,
                        model=self.model,
                        headers=_redact_headers(headers),
                    )
                    continue
                except httpx.HTTPError as exc:
                    last_exc = OpenAIProviderError(
                        "provider_outage",
                        "OpenAI transport error",
                    )
                    logger.warning(
                        "openai_transport_error",
                        attempt=attempt + 1,
                        error_type=type(exc).__name__,
                        model=self.model,
                    )
                    continue

                if response.status_code == 401:
                    raise OpenAIProviderError(
                        "auth_failed",
                        "OpenAI authentication failed",
                    )
                if response.status_code == 429:
                    err_code = ""
                    err_type = ""
                    with contextlib.suppress(Exception):
                        err_body = response.json()
                        if isinstance(err_body, dict):
                            err = err_body.get("error") or {}
                            if isinstance(err, dict):
                                err_code = str(err.get("code") or "")
                                err_type = str(err.get("type") or "")
                    if err_code in {
                        "insufficient_quota",
                        "credit_balance_exhausted",
                        "billing_not_active",
                    } or err_type in {
                        "insufficient_quota",
                        "billing_not_active",
                    }:
                        raise OpenAIProviderError(
                            "insufficient_quota",
                            "OpenAI account has no remaining API credits",
                        )
                    last_exc = OpenAIProviderError(
                        "rate_limited",
                        "OpenAI rate limit exceeded",
                    )
                    logger.warning(
                        "openai_rate_limited",
                        attempt=attempt + 1,
                        model=self.model,
                        error_code=err_code or None,
                        error_type=err_type or None,
                    )
                    continue
                if response.status_code >= 500:
                    last_exc = OpenAIProviderError(
                        "provider_outage",
                        f"OpenAI upstream HTTP {response.status_code}",
                    )
                    logger.warning(
                        "openai_upstream_error",
                        status_code=response.status_code,
                        attempt=attempt + 1,
                        model=self.model,
                    )
                    continue
                if response.status_code >= 400:
                    raise OpenAIProviderError(
                        "bad_request",
                        f"OpenAI rejected the request (HTTP {response.status_code})",
                    )

                try:
                    data = response.json()
                except json.JSONDecodeError as exc:
                    raise OpenAIProviderError(
                        "malformed_response",
                        "OpenAI returned non-JSON body",
                    ) from exc
                if not isinstance(data, dict):
                    raise OpenAIProviderError(
                        "malformed_response",
                        "OpenAI returned unexpected JSON shape",
                    )
                return data

        if last_exc is not None:
            raise last_exc
        raise OpenAIProviderError("provider_outage", "OpenAI request failed")


def extract_output_text(payload: dict[str, Any]) -> str:
    """Best-effort extraction of Responses API output text."""
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    chunks: list[str] = []
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
                elif isinstance(text, dict):
                    value = text.get("value")
                    if isinstance(value, str) and value.strip():
                        chunks.append(value.strip())
    return "\n".join(chunks).strip()
