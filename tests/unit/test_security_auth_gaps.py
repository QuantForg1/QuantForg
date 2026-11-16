"""Routes that were reachable without a session (security audit 16 Nov)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.unit]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/ite/research/dashboard"),
        ("get", "/api/v1/ite/research/versions"),
        ("post", "/api/v1/ite/research/simulate"),
        ("post", "/api/v1/ite/research/promotion/evaluate"),
    ],
)
def test_research_routes_require_a_session(method: str, path: str) -> None:
    from app.presentation.routers.institutional_research import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    from app.domain.exceptions.auth import AuthenticationError

    client = TestClient(app)
    with pytest.raises(AuthenticationError):  # mapped to 401 by the app
        client.get(path) if method == "get" else client.post(path, json={})


def test_billing_cron_secret_uses_constant_time_compare() -> None:
    import inspect

    from app.presentation.routers import billing

    src = inspect.getsource(billing.billing_reconcile_trials)
    assert "hmac.compare_digest" in src
    assert "!= expected" not in src
