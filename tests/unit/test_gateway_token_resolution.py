"""Gateway token load order — fake tokens only; never real secrets."""

from __future__ import annotations

import pytest

from services.mt5_gateway.settings import (
    _PLACEHOLDER_TOKEN,
    _is_placeholder_token,
    _resolve_token,
    get_gateway_settings,
)

pytestmark = [pytest.mark.unit]


def test_placeholder_token_detected_by_length_and_prefix() -> None:
    assert _is_placeholder_token(_PLACEHOLDER_TOKEN) is True
    assert _is_placeholder_token("") is True
    assert _is_placeholder_token("replace-with-anything") is True
    assert _is_placeholder_token("real-fake-token-for-unit-tests-only") is False


def test_real_dotenv_beats_process_placeholder() -> None:
    """NSSM/process placeholder must not win over a real dotenv token."""
    token, source = _resolve_token(
        process_token=_PLACEHOLDER_TOKEN,
        file_token="unit-test-real-token-aaaaaaaa",
        file_source=r"C:\fake\repo\.env",
    )
    assert token == "unit-test-real-token-aaaaaaaa"
    assert source.startswith("dotenv:")
    assert len(token) != len(_PLACEHOLDER_TOKEN) or token != _PLACEHOLDER_TOKEN


def test_real_process_used_when_dotenv_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # _classify_process_source reads os.environ presence, not the arg alone.
    monkeypatch.setenv("MT5_GATEWAY_TOKEN", "unit-test-process-token-bbbbbbbb")
    token, source = _resolve_token(
        process_token="unit-test-process-token-bbbbbbbb",
        file_token="",
        file_source="",
    )
    assert token == "unit-test-process-token-bbbbbbbb"
    assert source == "process_env"


def test_mismatched_real_tokens_prefer_dotenv() -> None:
    token, source = _resolve_token(
        process_token="unit-test-process-token-cccccccc",
        file_token="unit-test-dotenv-token-dddddddd",
        file_source=r"C:\fake\repo\.env",
    )
    assert token == "unit-test-dotenv-token-dddddddd"
    assert "dotenv" in source


def test_get_settings_honors_process_env_when_dotenv_stubbed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT5_GATEWAY_TOKEN", "unit-test-settings-token-eeeeeeee")
    monkeypatch.setenv("MT5_GATEWAY_ENABLE_WEBSOCKET", "false")
    monkeypatch.setenv("MT5_GATEWAY_AUTO_ATTACH", "false")
    monkeypatch.setattr(
        "services.mt5_gateway.settings._read_token_from_dotenv_files",
        lambda: ("", ""),
    )
    get_gateway_settings.cache_clear()
    settings = get_gateway_settings()
    assert settings.mt5_gateway_token == "unit-test-settings-token-eeeeeeee"
    assert settings.mt5_gateway_execution_enabled is False
    get_gateway_settings.cache_clear()
