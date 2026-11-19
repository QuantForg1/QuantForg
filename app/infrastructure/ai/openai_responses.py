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
        input_text: str | list[dict[str, Any]],
        instructions: str,
        text_format: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
        max_output_tokens: int | None = None,
    ) -> dict[str, Any]:
        """``input_text`` may be a plain string or Responses input items
        (role/content lists with ``input_text`` / ``input_image`` parts)."""
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
        if max_output_tokens is not None:
            payload["max_output_tokens"] = int(max_output_tokens)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/responses"
        last_exc: Exception | None = None
        attempts = self.max_retries + 1

        async with httpx.AsyncClient(
            timeout=max(1.0, float(timeout_seconds or self.timeout_seconds)),
            transport=self._transport,
        ) as client:
            for attempt in range(attempts):
                try:
                    response = await client.post(url, headers=headers, json=payload)
                except httpx.TimeoutException:
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


async def stream_output_text(
    client: OpenAIResponsesClient,
    *,
    input_items: str | list[dict[str, Any]],
    instructions: str,
    max_output_tokens: int | None = None,
    reasoning_effort: str | None = None,
    reasoning_summary: bool = False,
    web_search: bool = False,
    timeout_seconds: float = 90.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Any:
    """Stream ``POST /v1/responses`` events as ``{"type", "text"}`` dicts.

    ``type`` is ``"text"`` for answer deltas and ``"thinking"`` for the
    model's reasoning-summary deltas. Raises ``OpenAIProviderError`` on HTTP
    errors. If the model rejects a reasoning option (HTTP 400) the request is
    retried with less: summary+effort → effort → none.
    """
    if not client.configured:
        raise OpenAIProviderError("missing_api_key", "OPENAI_API_KEY is not configured")

    # Most capable request first; each HTTP 400 drops one optional feature.
    ladder: list[tuple[str | None, bool, bool]] = []
    if web_search:
        ladder.append(
            (reasoning_effort, bool(reasoning_effort and reasoning_summary), True)
        )
    if reasoning_effort and reasoning_summary:
        ladder.append((reasoning_effort, True, False))
    if reasoning_effort:
        ladder.append((reasoning_effort, False, False))
    ladder.append((None, False, False))

    def _payload(effort: str | None, summary: bool, search: bool) -> dict[str, Any]:
        p: dict[str, Any] = {
            "model": client.model,
            "instructions": instructions,
            "input": input_items,
            "store": False,
            "stream": True,
        }
        if max_output_tokens is not None:
            p["max_output_tokens"] = int(max_output_tokens)
        if effort:
            p["reasoning"] = {"effort": effort}
            if summary:
                p["reasoning"]["summary"] = "auto"
        if search:
            p["tools"] = [{"type": "web_search"}]
        return p

    headers = {
        "Authorization": f"Bearer {client._api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    url = f"{client.base_url}/responses"
    timeout = httpx.Timeout(timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(
        timeout=timeout, transport=transport or client._transport
    ) as http:
        for idx, (effort, summary, search) in enumerate(ladder):
            last = idx == len(ladder) - 1
            async with http.stream(
                "POST", url, headers=headers, json=_payload(effort, summary, search)
            ) as resp:
                if resp.status_code == 400 and not last:
                    await resp.aread()
                    logger.info(
                        "openai_stream_downgrade",
                        model=client.model,
                        effort=effort,
                        summary=summary,
                        web_search=search,
                    )
                    continue
                if resp.status_code == 401:
                    raise OpenAIProviderError(
                        "auth_failed", "OpenAI authentication failed"
                    )
                if resp.status_code == 429:
                    body = (await resp.aread()).decode("utf-8", "ignore")
                    code = (
                        "insufficient_quota"
                        if "insufficient_quota" in body or "billing" in body
                        else "rate_limited"
                    )
                    raise OpenAIProviderError(code, "OpenAI rate/quota limit")
                if resp.status_code >= 500:
                    raise OpenAIProviderError(
                        "provider_outage", f"OpenAI upstream HTTP {resp.status_code}"
                    )
                if resp.status_code >= 400:
                    raise OpenAIProviderError(
                        "bad_request",
                        f"OpenAI rejected the request (HTTP {resp.status_code})",
                    )
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    etype = str(event.get("type") or "")
                    delta = event.get("delta")
                    if etype == "response.output_text.delta":
                        if isinstance(delta, str) and delta:
                            yield {"type": "text", "text": delta}
                    elif etype == "response.reasoning_summary_text.delta":
                        if isinstance(delta, str) and delta:
                            yield {"type": "thinking", "text": delta}
                    elif etype == "response.web_search_call.searching":
                        yield {"type": "search", "text": "searching"}
                    elif etype == "response.web_search_call.completed":
                        yield {"type": "search", "text": "done"}
                    elif etype == "response.reasoning_summary_part.done":
                        yield {"type": "thinking", "text": "\n\n"}
                    elif etype in {"response.failed", "error"}:
                        raise OpenAIProviderError(
                            "provider_outage", "OpenAI stream reported an error"
                        )
                    elif etype == "response.completed":
                        return
                return
