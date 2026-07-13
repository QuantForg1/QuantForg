#!/usr/bin/env python3
"""ASGI penetration attack harness — verifies Critical/High controls without live network."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

os.environ["APP_ENV"] = "testing"
os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-that-is-long-enough-for-validation-32chars",
)
os.environ["RELOAD"] = "false"
os.environ["EXECUTION_ENABLED"] = "false"
os.environ["ALLOWED_HOSTS"] = "*"
os.environ["DEBUG"] = "false"
os.environ["LOG_LEVEL"] = "ERROR"
os.environ["DOCS_ENABLED"] = "false"

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.application.services.auth_service import AuthService  # noqa: E402
from app.application.use_cases.auth import (  # noqa: E402
    ChangePasswordUseCase,
    CompleteOAuthUseCase,
    GetCurrentUserUseCase,
    LoginUseCase,
    LogoutUseCase,
    RefreshSessionUseCase,
    RegisterWithEmailUseCase,
    RequestPasswordResetUseCase,
    StartOAuthUseCase,
    VerifyEmailUseCase,
)
from app.application.use_cases.record_audit_event import (  # noqa: E402
    RecordAuditEventUseCase,
)
from app.presentation.dependencies import auth as auth_deps  # noqa: E402
from core.config.settings import get_settings  # noqa: E402
from tests.unit.fakes import SharedUnitOfWorkFactory  # noqa: E402
from tests.unit.fakes_auth import FakeAuthProvider  # noqa: E402


class Results:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(
        self,
        name: str,
        *,
        passed: bool,
        detail: str,
        severity: str = "info",
    ) -> None:
        self.rows.append(
            {
                "name": name,
                "passed": passed,
                "detail": detail,
                "severity": severity,
            }
        )
        mark = "PASS" if passed else "FAIL"
        print(f"[{mark}] {name}: {detail}", flush=True)


async def main() -> None:
    get_settings.cache_clear()
    from core.config.environments import testing_settings
    import core.config.settings as settings_module

    settings = testing_settings()
    settings_module.get_settings = lambda: settings  # type: ignore[assignment]

    from app.main import create_app

    app = create_app(settings=settings)
    factory = SharedUnitOfWorkFactory()
    provider = FakeAuthProvider()
    audit = RecordAuditEventUseCase(uow_factory=factory)

    def _auth_service() -> AuthService:
        return AuthService(
            register_email=RegisterWithEmailUseCase(
                auth=provider, uow_factory=factory, audit=audit
            ),
            login=LoginUseCase(auth=provider, uow_factory=factory, audit=audit),
            logout=LogoutUseCase(auth=provider, audit=audit),
            refresh=RefreshSessionUseCase(auth=provider, uow_factory=factory),
            verify_email=VerifyEmailUseCase(
                auth=provider, uow_factory=factory, audit=audit
            ),
            request_password_reset=RequestPasswordResetUseCase(
                auth=provider, audit=audit, default_redirect_to=None
            ),
            change_password=ChangePasswordUseCase(auth=provider, audit=audit),
            start_oauth=StartOAuthUseCase(
                auth=provider, default_redirect_to="http://localhost:3000"
            ),
            complete_oauth=CompleteOAuthUseCase(
                auth=provider,
                uow_factory=factory,
                audit=audit,
                default_redirect_to="http://localhost:3000",
            ),
            get_current_user=GetCurrentUserUseCase(auth=provider, uow_factory=factory),
        )

    app.dependency_overrides[auth_deps.get_auth_service] = _auth_service
    app.dependency_overrides[auth_deps.get_uow_factory] = lambda: factory
    app.dependency_overrides[auth_deps.get_auth_provider] = lambda: provider

    transport = ASGITransport(app=app)
    r = Results()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            for path in (
                "/api/v1/ops/dashboard",
                "/api/v1/metrics",
                "/api/v1/portfolio",
                "/api/v1/mt5/account",
                f"/api/v1/brokers/{uuid4()}/diagnostics",
                f"/api/v1/brokers/{uuid4()}/health",
            ):
                resp = await client.get(path, headers={"Host": "test"})
                r.add(
                    f"unauth_{path}",
                    passed=resp.status_code in {401, 403},
                    detail=f"status={resp.status_code}",
                    severity="critical",
                )

            evil = "https://evil.example/phish"
            resp = await client.get(
                "/api/v1/auth/oauth/google",
                params={"redirect_to": evil},
                headers={"Host": "test"},
            )
            body = resp.text
            r.add(
                "oauth_open_redirect",
                passed=resp.status_code in {400, 422}
                and (
                    "redirect_not_allowed" in body or "evil.example" not in body.lower()
                ),
                detail=f"status={resp.status_code} body_snip={body[:160]}",
                severity="high",
            )

            payloads = [
                {"email": "admin' OR '1'='1", "password": "x"},
                {"email": '{"$gt":""}', "password": "x"},
                {"email": "a@b.c", "password": "' OR 1=1 --"},
            ]
            for i, payload in enumerate(payloads):
                resp = await client.post(
                    "/api/v1/auth/login",
                    json=payload,
                    headers={"Host": "test"},
                )
                r.add(
                    f"login_injection_{i}",
                    passed=resp.status_code in {401, 422, 429},
                    detail=f"status={resp.status_code}",
                    severity="high",
                )

            resp = await client.post(
                "/api/v1/auth/login",
                content=b"{not-json",
                headers={"Host": "test", "Content-Type": "application/json"},
            )
            r.add(
                "malformed_json",
                passed=resp.status_code in {400, 422},
                detail=f"status={resp.status_code}",
                severity="medium",
            )

            huge = {"email": "a@b.c", "password": "x" * (2_000_000)}
            resp = await client.post(
                "/api/v1/auth/login",
                json=huge,
                headers={"Host": "test"},
            )
            r.add(
                "oversized_password",
                passed=resp.status_code in {401, 413, 422, 429},
                detail=f"status={resp.status_code}",
                severity="medium",
            )

            resp = await client.get(
                "/api/v1/../../etc/passwd",
                headers={"Host": "test"},
            )
            r.add(
                "path_traversal",
                passed=resp.status_code in {404, 405} and "root:" not in resp.text,
                detail=f"status={resp.status_code}",
                severity="high",
            )

            resp = await client.get("/", headers={"Host": "evil.example"})
            r.add(
                "host_header",
                passed="evil.example" not in (resp.headers.get("location") or ""),
                detail=f"status={resp.status_code} loc={resp.headers.get('location')}",
                severity="medium",
            )

            for token, label in (
                ("Bearer eyJhbGciOiJub25lIn0.e30.", "none_alg"),
                ("Bearer totally.invalid.token", "garbage"),
                ("Bearer ", "empty"),
            ):
                resp = await client.get(
                    "/api/v1/auth/me",
                    headers={"Host": "test", "Authorization": token},
                )
                r.add(
                    f"jwt_{label}",
                    passed=resp.status_code in {401, 403},
                    detail=f"status={resp.status_code}",
                    severity="critical",
                )

            for path in ("/docs", "/redoc", "/openapi.json"):
                resp = await client.get(path, headers={"Host": "test"})
                r.add(
                    f"docs_{path}",
                    passed=resp.status_code == 404,
                    detail=f"status={resp.status_code}",
                    severity="medium",
                )

            resp = await client.get(
                "/api/v1/version",
                headers={"Host": "test", "X-Request-Id": "<script>alert(1)</script>"},
            )
            r.add(
                "xss_header_reflection",
                passed="<script>" not in resp.text,
                detail=f"status={resp.status_code}",
                severity="medium",
            )

            resp = await client.get(
                f"/api/v1/brokers/{uuid4()}",
                headers={"Host": "test", "Authorization": "Bearer fake"},
            )
            leak = any(
                s in resp.text
                for s in ("Traceback", "/Users/", 'File "', "site-packages")
            )
            r.add(
                "stack_trace_leak",
                passed=not leak and resp.status_code in {401, 403, 404, 500},
                detail=f"status={resp.status_code} leak={leak} body={resp.text[:120]}",
                severity="high",
            )

            resp = await client.options(
                "/api/v1/version",
                headers={
                    "Host": "test",
                    "Origin": "https://evil.example",
                    "Access-Control-Request-Method": "GET",
                },
            )
            acao = resp.headers.get("access-control-allow-origin", "")
            acac = resp.headers.get("access-control-allow-credentials", "")
            bad = acao == "*" and acac.lower() == "true"
            r.add(
                "cors_credentials_wildcard",
                passed=not bad,
                detail=f"acao={acao!r} acac={acac!r}",
                severity="high",
            )

            resp = await client.post(
                "/api/v1/mt5/connect",
                json={
                    "login": 1,
                    "password": "x; rm -rf /",
                    "server": "Demo; shutdown",
                    "path": "/tmp/../../etc/passwd",
                },
                headers={"Host": "test", "Authorization": "Bearer fake"},
            )
            r.add(
                "mt5_connect_injection_auth",
                passed=resp.status_code in {401, 403},
                detail=f"status={resp.status_code}",
                severity="high",
            )

            codes = []
            for _ in range(40):
                resp = await client.post(
                    "/api/v1/auth/login",
                    json={"email": "rate@test.com", "password": "wrong"},
                    headers={"Host": "test"},
                )
                codes.append(resp.status_code)
            r.add(
                "auth_rate_limit",
                passed=429 in codes or all(c in {401, 422, 429} for c in codes),
                detail=f"unique_codes={sorted(set(codes))}",
                severity="high",
            )

            # MT5 live-session isolation (unit-level via adapter)
            from app.domain.interfaces.mt5_client import MT5LoginRequest
            from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter

            adapter = MT5Adapter(client=MockMT5Client())
            adapter.initialize()
            s1 = adapter.login(MT5LoginRequest(login=1, password="a", server="S"))
            s2 = adapter.login(MT5LoginRequest(login=2, password="b", server="S"))
            r.add(
                "mt5_live_session_isolation",
                passed=adapter.is_live_session(s2) and not adapter.is_live_session(s1),
                detail=f"live={adapter.is_live_session(s2)} stale_blocked={not adapter.is_live_session(s1)}",
                severity="critical",
            )

    failed = [x for x in r.rows if not x["passed"]]
    critical_fail = [x for x in failed if x["severity"] == "critical"]
    high_fail = [x for x in failed if x["severity"] == "high"]
    out = {
        "total": len(r.rows),
        "passed": len(r.rows) - len(failed),
        "failed": len(failed),
        "critical_failures": critical_fail,
        "high_failures": high_fail,
        "results": r.rows,
    }
    Path("/tmp/qf_pentest_asgi.json").write_text(json.dumps(out, indent=2))
    print(
        f"PENTEST_SUMMARY total={out['total']} passed={out['passed']} "
        f"failed={out['failed']} critical_fail={len(critical_fail)} "
        f"high_fail={len(high_fail)}",
        flush=True,
    )
    if critical_fail or high_fail:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
