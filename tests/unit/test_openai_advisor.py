"""OpenAI advisor — Responses client, validation, fail-closed trading."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.application.services.openai_advisor_service import (
    OpenAIAdvisorService,
    advice_cannot_bypass_risk,
    build_openai_advisor_from_settings,
    parse_advice_payload,
)
from app.infrastructure.ai.openai_responses import (
    OpenAIProviderError,
    OpenAIResponsesClient,
    extract_output_text,
)
from core.config.environments import testing_settings


class _FakeTransport(httpx.AsyncBaseTransport):
    def __init__(self, handler) -> None:  # noqa: ANN001
        self._handler = handler

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return self._handler(request)


@pytest.mark.unit
def test_provider_status_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_ENABLED", raising=False)
    settings = testing_settings(openai_enabled=True, openai_api_key=None)
    advisor = build_openai_advisor_from_settings(settings)
    status = advisor.provider_status()
    assert status.configured is False
    assert status.enabled is True
    assert status.status == "not_configured"
    assert "key" not in status.detail.lower() or "missing" in status.detail.lower()
    body = status.to_dict()
    assert body["gemini"] is False
    assert "sk-" not in json.dumps(body)


@pytest.mark.unit
def test_provider_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_ENABLED", "false")
    settings = testing_settings(
        openai_enabled=False,
        openai_api_key=SecretStr("sk-test-not-real"),
    )
    advisor = build_openai_advisor_from_settings(settings)
    status = advisor.provider_status()
    assert status.status == "disabled"
    assert status.enabled is False


@pytest.mark.unit
def test_key_present_enables_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_ENABLED", raising=False)
    settings = testing_settings(
        openai_enabled=False,
        openai_api_key=SecretStr("sk-test-not-real"),
    )
    advisor = build_openai_advisor_from_settings(settings)
    status = advisor.provider_status()
    assert status.enabled is True
    assert status.configured is True
    assert status.status == "configured"


@pytest.mark.unit
def test_parse_valid_advice_strips_authorizes_trade() -> None:
    raw = json.dumps(
        {
            "stance": "LEAN_LONG",
            "confidence": 0.77,
            "summary": "Structure supportive",
            "risks": ["spread"],
            "authorizes_trade": True,
        }
    )
    advice = parse_advice_payload(raw, model="gpt-5.4-mini")
    assert advice.stance == "LEAN_LONG"
    assert advice.confidence == 0.77
    assert advice.authorizes_trade is False
    assert advice_cannot_bypass_risk(advice)


@pytest.mark.unit
def test_parse_malformed_advice() -> None:
    advice = parse_advice_payload("not-json", model="gpt-5.4-mini")
    assert advice.provider_status == "malformed_response"
    assert advice.authorizes_trade is False
    assert advice.stance == "UNKNOWN"


@pytest.mark.unit
def test_extract_output_text() -> None:
    payload = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": '{"stance":"HOLD"}'}],
            }
        ]
    }
    assert '{"stance":"HOLD"}' in extract_output_text(payload)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_client_missing_key() -> None:
    client = OpenAIResponsesClient(api_key="")
    with pytest.raises(OpenAIProviderError) as exc:
        await client.create_response(input_text="x", instructions="y")
    assert exc.value.code == "missing_api_key"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_client_auth_failed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" in request.headers
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    client = OpenAIResponsesClient(
        api_key="sk-test",
        transport=_FakeTransport(handler),
    )
    with pytest.raises(OpenAIProviderError) as exc:
        await client.create_response(input_text="hi", instructions="sys")
    assert exc.value.code == "auth_failed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_client_rate_limit_then_success() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": {"message": "rate"}})
        return httpx.Response(
            200,
            json={"output_text": '{"stance":"HOLD","confidence":0.5,"summary":"ok","risks":[]}'},
        )

    client = OpenAIResponsesClient(
        api_key="sk-test",
        max_retries=1,
        transport=_FakeTransport(handler),
    )
    data = await client.create_response(input_text="hi", instructions="sys")
    assert "output_text" in data
    assert calls["n"] == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_client_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    client = OpenAIResponsesClient(
        api_key="sk-test",
        max_retries=0,
        transport=_FakeTransport(handler),
    )
    with pytest.raises(OpenAIProviderError) as exc:
        await client.create_response(input_text="hi", instructions="sys")
    assert exc.value.code == "timeout"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_advise_unavailable_without_key_is_fail_closed() -> None:
    advisor = OpenAIAdvisorService(None, enabled=True, model="gpt-5.4-mini")
    advice = await advisor.advise(symbol="XAUUSD", market_snapshot={"bid": 1})
    assert advice.authorizes_trade is False
    assert advice.stance == "NO_TRADE"
    assert advice_cannot_bypass_risk(advice)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_advise_success_path_fail_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        # Snapshot secrets must be stripped from the model input payload.
        assert "secret-should-drop" not in json.dumps(body.get("input"))
        assert '"password"' not in str(body.get("input"))
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "stance": "LEAN_SHORT",
                        "confidence": 0.6,
                        "summary": "fade",
                        "risks": ["news"],
                        "authorizes_trade": True,
                    }
                )
            },
        )

    client = OpenAIResponsesClient(
        api_key="sk-test",
        transport=_FakeTransport(handler),
    )
    advisor = OpenAIAdvisorService(client, enabled=True, model="gpt-5.4-mini")
    advice = await advisor.advise(
        symbol="XAUUSD",
        market_snapshot={"bid": 2650.1, "password": "secret-should-drop"},
    )
    assert advice.stance == "LEAN_SHORT"
    assert advice.authorizes_trade is False
    assert advice_cannot_bypass_risk(advice)


@pytest.mark.unit
def test_no_secret_in_error_strings() -> None:
    err = OpenAIProviderError("auth_failed", "OpenAI authentication failed")
    assert "sk-" not in str(err)
    assert "Bearer" not in str(err)
