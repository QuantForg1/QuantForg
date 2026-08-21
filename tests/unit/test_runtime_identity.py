"""Runtime identity from Railway-injected env only."""

from __future__ import annotations

import pytest

from app.application.runtime_identity import (
    runtime_deployment_id,
    runtime_git_commit,
)
from app.application.use_cases.get_version import GetVersionUseCase
from tests.unit.fakes import FakeAppInfo

pytestmark = [pytest.mark.unit]


def test_git_commit_unknown_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.delenv("RAILWAY_DEPLOYMENT_ID", raising=False)
    assert runtime_git_commit() == "unknown"
    assert runtime_deployment_id() == "unknown"


def test_git_commit_uses_railway_sha_only(monkeypatch: pytest.MonkeyPatch) -> None:
    sha = "6ab48b45787abcdec2209cc2eebedad6885cfc11"
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", sha)
    monkeypatch.setenv("RAILWAY_DEPLOYMENT_ID", "dep-123")
    monkeypatch.setenv("GITHUB_SHA", "deadbeef" * 5)
    monkeypatch.setenv(
        "VERCEL_GIT_COMMIT_SHA",
        "ffffffffffffffffffffffffffffffffffffffff",
    )
    assert runtime_git_commit() == sha
    assert runtime_deployment_id() == "dep-123"


def test_whitespace_railway_sha_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "   ")
    assert runtime_git_commit() == "unknown"


def test_runtime_identity_import_graph_is_cycle_free() -> None:
    from pathlib import Path

    src = Path("app/application/runtime_identity.py").read_text(encoding="utf-8")
    forbidden = (
        "app.application.services",
        "institutional_ite",
        "gateway_client",
        "control_plane",
        "position_management",
    )
    for token in forbidden:
        assert token not in src
    get_version = Path("app/application/use_cases/get_version.py").read_text(
        encoding="utf-8"
    )
    assert "app.application.runtime_identity" in get_version
    assert "app.application.services" not in get_version


def test_version_use_case_includes_runtime_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abc123")
    monkeypatch.setenv("RAILWAY_DEPLOYMENT_ID", "rail-1")
    info = GetVersionUseCase(app_info=FakeAppInfo(app_version="1.0.0")).execute()
    assert info.git_commit == "abc123"
    assert info.deployment_id == "rail-1"
    assert info.version == "1.0.0"
