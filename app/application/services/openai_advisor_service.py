"""OpenAI advisory service — validates model output; never authorizes trades."""

from __future__ import annotations

import json
import re
from typing import Any

from app.domain.interfaces.openai_advisor import (
    ALLOWED_STANCES,
    OpenAIAdvice,
    OpenAIAdvisorPort,
    OpenAIProviderStatus,
)
from app.infrastructure.ai.openai_responses import (
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
    OpenAIProviderError,
    OpenAIResponsesClient,
    extract_output_text,
)
from core.logging import get_logger

logger = get_logger(__name__)

# Process-local last OpenAI failure (code + safe detail). Never stores keys.
_LAST_OPENAI_ERROR: dict[str, str] | None = None


def last_openai_provider_error() -> dict[str, str] | None:
    return dict(_LAST_OPENAI_ERROR) if _LAST_OPENAI_ERROR else None


def _record_openai_error(code: str, detail: str) -> None:
    global _LAST_OPENAI_ERROR
    _LAST_OPENAI_ERROR = {
        "code": str(code or "unknown")[:64],
        "detail": str(detail or "")[:200],
    }


def clear_openai_provider_error_for_tests() -> None:
    global _LAST_OPENAI_ERROR
    _LAST_OPENAI_ERROR = None


_ADVICE_INSTRUCTIONS = (
    "You are QuantForg's advisory analyst (ADR-0015). "
    "Return ONLY a JSON object with keys: stance, confidence, summary, risks. "
    "stance must be one of HOLD, LEAN_LONG, LEAN_SHORT, NO_TRADE. "
    "confidence is a number from 0 to 1. summary is a short string. "
    "risks is an array of short strings. "
    "You must NOT authorize trades, place orders, or claim execution capability. "
    "Never request or repeat API keys, passwords, tokens, or account credentials."
)

_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")


def _safe_snapshot(market_snapshot: dict[str, Any]) -> dict[str, Any]:
    """Drop fields that commonly hold secrets before prompting."""
    blocked = {
        "password",
        "token",
        "api_key",
        "secret",
        "authorization",
        "login",
        "account",
        "investor",
    }
    out: dict[str, Any] = {}
    for key, value in market_snapshot.items():
        lk = str(key).lower()
        if any(b in lk for b in blocked):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            if isinstance(value, str) and len(value) > 500:
                out[key] = value[:500] + "…"
            else:
                out[key] = value
        elif isinstance(value, (list, dict)):
            # Keep shallow structure only — avoid dumping large blobs.
            out[key] = (
                value if len(json.dumps(value, default=str)) < 2000 else "<omitted>"
            )
    return out


def parse_advice_payload(
    raw_text: str,
    *,
    model: str,
) -> OpenAIAdvice:
    """Parse and validate model JSON. Always forces authorizes_trade=False."""
    text = (raw_text or "").strip()
    if not text:
        return OpenAIAdvice(
            advisory_only=True,
            stance="UNKNOWN",
            confidence=0.0,
            summary="",
            model=model,
            authorizes_trade=False,
            provider_status="malformed_response",
            detail="empty_model_output",
        )

    candidate = text
    if not candidate.startswith("{"):
        match = _JSON_OBJECT_RE.search(candidate)
        if match:
            candidate = match.group(0)

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return OpenAIAdvice(
            advisory_only=True,
            stance="UNKNOWN",
            confidence=0.0,
            summary="",
            model=model,
            authorizes_trade=False,
            provider_status="malformed_response",
            detail="json_parse_failed",
        )

    if not isinstance(data, dict):
        return OpenAIAdvice(
            advisory_only=True,
            stance="UNKNOWN",
            confidence=0.0,
            summary="",
            model=model,
            authorizes_trade=False,
            provider_status="malformed_response",
            detail="non_object_json",
        )

    stance = str(data.get("stance") or "UNKNOWN").strip().upper()
    if stance not in ALLOWED_STANCES:
        stance = "UNKNOWN"

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    summary = str(data.get("summary") or "").strip()[:1000]
    risks_raw = data.get("risks") or []
    risks: list[str] = []
    if isinstance(risks_raw, list):
        for item in risks_raw[:12]:
            s = str(item).strip()
            if s:
                risks.append(s[:200])

    # Model may hallucinate authorization — always force false.
    if data.get("authorizes_trade") is True:
        logger.warning(
            "openai_advice_authorizes_trade_stripped",
            model=model,
        )

    return OpenAIAdvice(
        advisory_only=True,
        stance=stance,
        confidence=confidence,
        summary=summary,
        risks=tuple(risks),
        model=model,
        authorizes_trade=False,
        provider_status="ok",
        detail="",
        raw_keys=tuple(sorted(str(k) for k in data)),
    )


class OpenAIAdvisorService(OpenAIAdvisorPort):
    """Application façade over OpenAIResponsesClient."""

    def __init__(
        self,
        client: OpenAIResponsesClient | None,
        *,
        enabled: bool,
        model: str = DEFAULT_OPENAI_MODEL,
        base_url: str = DEFAULT_OPENAI_BASE_URL,
    ) -> None:
        self._client = client
        self._enabled = bool(enabled)
        self._model = model
        self._base_url = base_url

    def provider_status(self) -> OpenAIProviderStatus:
        configured = bool(self._client and self._client.configured)
        if not self._enabled:
            status, detail = "disabled", "OPENAI_ENABLED=false"
        elif not configured:
            status, detail = "not_configured", "OPENAI_API_KEY missing"
        else:
            status, detail = "configured", "key_present_model_ready"
        return OpenAIProviderStatus(
            configured=configured,
            enabled=self._enabled,
            model=self._model,
            status=status,
            detail=detail,
            base_url=self._base_url,
        )

    async def advise(
        self,
        *,
        symbol: str,
        market_snapshot: dict[str, Any],
        instructions: str | None = None,
    ) -> OpenAIAdvice:
        status = self.provider_status()
        if status.status != "configured":
            return OpenAIAdvice(
                advisory_only=True,
                stance="NO_TRADE",
                confidence=0.0,
                summary="OpenAI advisor unavailable",
                model=self._model,
                authorizes_trade=False,
                provider_status=status.status,
                detail=status.detail,
            )

        assert self._client is not None
        safe = _safe_snapshot(market_snapshot)
        input_text = json.dumps(
            {"symbol": str(symbol).strip().upper()[:32], "market": safe},
            default=str,
        )
        try:
            payload = await self._client.create_response(
                input_text=input_text,
                instructions=instructions or _ADVICE_INSTRUCTIONS,
            )
            text = extract_output_text(payload)
            advice = parse_advice_payload(text, model=self._model)
            # Fail-closed for trading: advice never authorizes.
            if advice.provider_status != "ok":
                _record_openai_error(advice.provider_status, advice.detail)
                return advice
            global _LAST_OPENAI_ERROR
            _LAST_OPENAI_ERROR = None
            return advice
        except OpenAIProviderError as exc:
            _record_openai_error(exc.code, exc.message)
            logger.warning(
                "openai_advise_failed",
                code=exc.code,
                model=self._model,
            )
            return OpenAIAdvice(
                advisory_only=True,
                stance="NO_TRADE",
                confidence=0.0,
                summary="OpenAI advisor unavailable",
                model=self._model,
                authorizes_trade=False,
                provider_status=exc.code,
                detail=exc.message,
            )


def build_openai_advisor_from_settings(settings: Any) -> OpenAIAdvisorService:
    """Factory used by presentation deps — never logs the key.

    Enablement:
    - ``OPENAI_ENABLED=false`` (or 0/off/no) explicitly disables the advisor.
    - ``OPENAI_ENABLED=true`` enables when a key is present.
    - If ``OPENAI_ENABLED`` is unset, a present ``OPENAI_API_KEY`` enables the
      client (Railway-friendly). Explicit false always wins.
    """
    import os

    model = str(getattr(settings, "openai_model", "") or DEFAULT_OPENAI_MODEL).strip()
    base_url = str(
        getattr(settings, "openai_base_url", "") or DEFAULT_OPENAI_BASE_URL
    ).strip()
    timeout = float(getattr(settings, "openai_timeout_seconds", 20.0) or 20.0)
    retries = int(getattr(settings, "openai_max_retries", 1) or 0)
    secret = getattr(settings, "openai_api_key", None)
    api_key = ""
    if secret is not None:
        getter = getattr(secret, "get_secret_value", None)
        api_key = str(getter() if callable(getter) else secret or "").strip()

    env_flag = os.environ.get("OPENAI_ENABLED")
    if env_flag is not None:
        enabled = env_flag.strip().lower() in {"1", "true", "yes", "on"}
    else:
        # Unset → enable when a server-side key is configured.
        enabled = bool(api_key) or bool(getattr(settings, "openai_enabled", False))

    client: OpenAIResponsesClient | None = None
    if enabled and api_key:
        client = OpenAIResponsesClient(
            api_key=api_key,
            model=model or DEFAULT_OPENAI_MODEL,
            base_url=base_url or DEFAULT_OPENAI_BASE_URL,
            timeout_seconds=timeout,
            max_retries=retries,
        )
    return OpenAIAdvisorService(
        client,
        enabled=enabled,
        model=model or DEFAULT_OPENAI_MODEL,
        base_url=base_url or DEFAULT_OPENAI_BASE_URL,
    )


def advice_cannot_bypass_risk(advice: OpenAIAdvice) -> bool:
    """Invariant: advice never authorizes trade execution."""
    return advice.authorizes_trade is False and advice.advisory_only is True
