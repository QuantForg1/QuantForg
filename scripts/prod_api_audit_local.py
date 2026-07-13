#!/usr/bin/env python3
"""Full QuantForg API audit against ASGI app (testing/memory + FakeAuth).

Used for production-parity endpoint validation when live Supabase signup
is rate-limited. Does not change architecture — exercise every router.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Ensure testing env before settings import.
os.environ["APP_ENV"] = "testing"
os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-that-is-long-enough-for-validation-32chars",
)
os.environ["RELOAD"] = "false"
os.environ["EXECUTION_ENABLED"] = "false"
os.environ["ALLOWED_HOSTS"] = "*"
os.environ["DEBUG"] = "true"
os.environ["LOG_LEVEL"] = "WARNING"

from fastapi.testclient import TestClient  # noqa: E402

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


def main() -> int:
    get_settings.cache_clear()
    from core.config.environments import testing_settings
    import core.config.settings as settings_module

    settings = testing_settings()
    settings_module.get_settings = lambda: settings  # type: ignore[assignment]

    from app.main import create_app

    application = create_app(settings=settings)
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

    application.dependency_overrides[auth_deps.get_auth_service] = _auth_service
    application.dependency_overrides[auth_deps.get_uow_factory] = lambda: factory
    application.dependency_overrides[auth_deps.get_auth_provider] = lambda: provider

    results: list[dict[str, Any]] = []
    uid = uuid.uuid4().hex[:8]
    email = f"audit.{uid}@example.com"
    password = "ProdValTest1!"

    def record(
        method: str,
        path: str,
        status: int,
        *,
        ok: bool,
        body: Any,
        expect: Any,
        ms: float = 0.0,
        note: str = "",
    ) -> None:
        results.append(
            {
                "method": method,
                "path": path,
                "status": status,
                "ok": ok,
                "body": body,
                "expect": expect,
                "ms": ms,
                "note": note,
            }
        )

    def call(
        client: TestClient,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        token: str | None = None,
        expect: Any = 200,
        files: Any = None,
        data: Any = None,
    ) -> dict[str, Any]:
        headers = {"Host": "test", "X-Forwarded-For": "127.0.0.1"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        resp = client.request(
            method,
            path,
            json=json_body,
            headers=headers,
            files=files,
            data=data,
        )
        allowed = expect if isinstance(expect, (list, tuple, set)) else [expect]
        try:
            body: Any = resp.json()
        except Exception:
            body = resp.text[:500]
        ok = resp.status_code in allowed
        record(
            method,
            path,
            resp.status_code,
            ok=ok,
            body=body,
            expect=expect,
            note="" if ok else f"expected {expect}",
        )
        mark = "OK" if ok else "FAIL"
        print(f"{mark} {resp.status_code} {method} {path}", flush=True)
        return {"status": resp.status_code, "body": body, "ok": ok}

    with TestClient(application, raise_server_exceptions=False) as client:
        # Public
        call(client, "GET", "/", expect=200)
        call(client, "GET", "/health", expect=200)
        call(client, "GET", "/api/v1/health", expect=200)
        call(client, "GET", "/api/v1/health/live", expect=200)
        call(client, "GET", "/api/v1/version", expect=200)
        call(client, "GET", "/api/v1/ops/dashboard", expect=401)
        call(client, "GET", "/api/v1/ops/metrics", expect=401)
        call(client, "GET", "/api/v1/ops/alerts", expect=401)
        call(client, "GET", "/api/v1/ops/audit", expect=401)
        call(client, "GET", "/api/v1/metrics", expect=401)

        # Auth validation
        call(
            client,
            "POST",
            "/api/v1/auth/register",
            json_body={"email": "bad", "password": "x", "display_name": ""},
            expect=422,
        )
        call(client, "GET", "/api/v1/profile", expect=401)

        reg = call(
            client,
            "POST",
            "/api/v1/auth/register",
            json_body={
                "email": email,
                "password": password,
                "display_name": f"Audit {uid}",
            },
            expect=[200, 201],
        )
        access = None
        refresh = None
        if isinstance(reg["body"], dict) and reg["body"].get("access_token"):
            access = reg["body"]["access_token"]
            refresh = reg["body"].get("refresh_token")

        call(
            client,
            "POST",
            "/api/v1/auth/register",
            json_body={
                "email": email,
                "password": password,
                "display_name": f"Audit {uid}",
            },
            expect=[409, 400, 401],
        )
        login = call(
            client,
            "POST",
            "/api/v1/auth/login",
            json_body={"email": email, "password": password},
            expect=200,
        )
        if isinstance(login["body"], dict) and login["body"].get("access_token"):
            access = login["body"]["access_token"]
            refresh = login["body"].get("refresh_token", refresh)

        assert access, "no access token"

        # Promote to admin so broker catalogue CRUD (owner/admin-only) can be tested.
        from app.domain.enums.user import UserRole

        for user in list(factory.uow.users.items.values()):
            user.change_role(UserRole.ADMIN)

        call(client, "GET", "/api/v1/auth/me", token=access, expect=200)
        if refresh:
            ref = call(
                client,
                "POST",
                "/api/v1/auth/refresh",
                json_body={"refresh_token": refresh},
                expect=200,
            )
            if isinstance(ref["body"], dict) and ref["body"].get("access_token"):
                access = ref["body"]["access_token"]
                refresh = ref["body"].get("refresh_token", refresh)

        call(
            client,
            "POST",
            "/api/v1/auth/change-password",
            json_body={"new_password": "short"},
            token=access,
            expect=422,
        )
        call(
            client,
            "POST",
            "/api/v1/auth/forgot-password",
            json_body={"email": email},
            expect=200,
        )

        # Profile
        call(client, "GET", "/api/v1/profile", token=access, expect=200)
        call(
            client,
            "PATCH",
            "/api/v1/profile",
            json_body={"full_name": f"Audit {uid} Upd", "bio": "validation"},
            token=access,
            expect=200,
        )
        call(client, "GET", "/api/v1/profile/activity", token=access, expect=200)
        call(
            client,
            "POST",
            "/api/v1/profile/avatar",
            token=access,
            files={
                "file": (
                    "avatar.png",
                    b"\x89PNG\r\n\x1a\n" + b"\x00" * 64,
                    "image/png",
                )
            },
            expect=[200, 201, 400, 415, 422],
        )

        # Settings
        call(client, "GET", "/api/v1/settings", token=access, expect=200)
        call(
            client,
            "PATCH",
            "/api/v1/settings",
            json_body={"theme": "dark", "notifications_enabled": True},
            token=access,
            expect=200,
        )
        call(client, "GET", "/api/v1/settings/devices", token=access, expect=200)
        call(client, "GET", "/api/v1/settings/sessions", token=access, expect=200)

        # Notifications
        call(client, "GET", "/api/v1/notifications", token=access, expect=200)
        prefs = call(
            client, "GET", "/api/v1/notifications/preferences", token=access, expect=200
        )
        if isinstance(prefs["body"], list) and prefs["body"]:
            cat = prefs["body"][0].get("category") or "system"
            call(
                client,
                "PATCH",
                f"/api/v1/notifications/preferences/{cat}",
                json_body={"enabled": True},
                token=access,
                expect=[200, 404, 422],
            )

        # Organizations
        call(client, "GET", "/api/v1/organizations", token=access, expect=200)
        org = call(
            client,
            "POST",
            "/api/v1/organizations",
            json_body={"name": f"Org {uid}", "slug": f"org-{uid}"},
            token=access,
            expect=[200, 201],
        )
        org_id = org["body"].get("id") if isinstance(org["body"], dict) else None
        if org_id:
            call(
                client,
                "POST",
                f"/api/v1/organizations/{org_id}/invitations",
                json_body={"email": f"invite.{uid}@example.com", "role": "member"},
                token=access,
                expect=[200, 201],
            )

        # Brokers
        call(client, "GET", "/api/v1/brokers", token=access, expect=200)
        broker = call(
            client,
            "POST",
            "/api/v1/brokers",
            json_body={
                "name": f"Broker {uid}",
                "slug": f"broker-{uid}",
                "broker_type": "retail",
                "platform_code": "mt5",
                "country_code": "US",
            },
            token=access,
            expect=[200, 201],
        )
        broker_id = (
            broker["body"].get("id") if isinstance(broker["body"], dict) else None
        )
        account_id = None
        if broker_id:
            call(
                client,
                "GET",
                f"/api/v1/brokers/{broker_id}",
                token=access,
                expect=200,
            )
            call(
                client,
                "GET",
                f"/api/v1/brokers/{broker_id}/health",
                token=access,
                expect=200,
            )
            call(
                client,
                "GET",
                f"/api/v1/brokers/{broker_id}/diagnostics",
                token=access,
                expect=200,
            )
            call(
                client,
                "PATCH",
                f"/api/v1/brokers/{broker_id}",
                json_body={"description": "upd", "status": "active"},
                token=access,
                expect=200,
            )
            call(client, "GET", "/api/v1/broker-accounts", token=access, expect=200)
            acc = call(
                client,
                "POST",
                "/api/v1/broker-accounts",
                json_body={
                    "broker_id": broker_id,
                    "external_account_id": "12345678",
                    "label": f"Demo {uid}",
                    "environment": "demo",
                    "server": "Demo-Server",
                    "password": "secretpass",
                },
                token=access,
                expect=[200, 201, 422],
            )
            account_id = (
                acc["body"].get("id") if isinstance(acc["body"], dict) else None
            )
            if account_id:
                call(
                    client,
                    "GET",
                    f"/api/v1/broker-accounts/{account_id}",
                    token=access,
                    expect=200,
                )
                call(
                    client,
                    "GET",
                    "/api/v1/broker-connections",
                    token=access,
                    expect=200,
                )
                call(
                    client,
                    "POST",
                    "/api/v1/broker-connections/connect",
                    json_body={"account_id": account_id},
                    token=access,
                    expect=[200, 201, 400, 422],
                )
                call(
                    client,
                    "POST",
                    "/api/v1/broker-connections/validate",
                    json_body={"account_id": account_id},
                    token=access,
                    expect=[200, 400, 422],
                )
                call(
                    client,
                    "POST",
                    "/api/v1/broker-connections/disconnect",
                    json_body={"account_id": account_id},
                    token=access,
                    expect=[200, 400, 422],
                )

        # MT5
        call(client, "GET", "/api/v1/mt5/status", token=access, expect=200)
        call(
            client,
            "POST",
            "/api/v1/mt5/connect",
            json_body={
                "login": 12345,
                "password": "fakepass",
                "server": "Demo-Server",
            },
            token=access,
            expect=[200, 400, 422],
        )
        call(client, "GET", "/api/v1/mt5/status", token=access, expect=200)
        call(client, "GET", "/api/v1/mt5/account", token=access, expect=[200, 400])
        call(client, "GET", "/api/v1/mt5/symbols", token=access, expect=[200, 400])
        call(
            client,
            "POST",
            "/api/v1/mt5/order/validate",
            json_body={
                "symbol": "EURUSD",
                "side": "buy",
                "order_type": "market",
                "volume": "0.01",
            },
            token=access,
            expect=[200, 400, 422],
        )
        call(
            client,
            "POST",
            "/api/v1/mt5/order/calculate",
            json_body={
                "symbol": "EURUSD",
                "side": "buy",
                "order_type": "market",
                "volume": "0.01",
            },
            token=access,
            expect=[200, 400, 422],
        )
        call(client, "POST", "/api/v1/mt5/disconnect", token=access, expect=200)

        # Strategy
        call(
            client,
            "POST",
            "/api/v1/strategy/evaluate",
            json_body={
                "request_id": f"strat-{uid}",
                "symbol": "EURUSD",
                "timeframe": "m15",
                "market_open": True,
                "session": "london",
                "structure_bias": "up",
            },
            token=access,
            expect=[200, 422],
        )
        call(client, "GET", "/api/v1/strategy/signals", token=access, expect=200)

        # Portfolio / execution require an active MT5 connection — expect 404
        # when disconnected (correct API error, not a crash).
        call(client, "GET", "/api/v1/portfolio", token=access, expect=[200, 400, 404])
        call(client, "GET", "/api/v1/positions", token=access, expect=[200, 400, 404])
        call(client, "GET", "/api/v1/orders", token=access, expect=[200, 400, 404])
        call(client, "GET", "/api/v1/history", token=access, expect=[200, 400, 404])

        # Backtest
        now = datetime.now(UTC)
        bars = []
        price = 1.1000
        for i in range(40):
            ts = (now - timedelta(minutes=15 * (40 - i))).strftime("%Y-%m-%dT%H:%M:%SZ")
            o = price
            h = price + 0.001
            l = price - 0.001
            c = price + 0.0002
            bars.append(
                {
                    "open_time": ts,
                    "open": f"{o:.5f}",
                    "high": f"{h:.5f}",
                    "low": f"{l:.5f}",
                    "close": f"{c:.5f}",
                    "volume": "100",
                }
            )
            price = c
        bt = call(
            client,
            "POST",
            "/api/v1/backtests/run",
            json_body={
                "request_id": f"bt-{uid}",
                "symbol": "EURUSD",
                "timeframe": "m15",
                "initial_balance": "10000",
                "bars": bars,
            },
            token=access,
            expect=200,
        )
        call(client, "GET", "/api/v1/backtests", token=access, expect=200)
        if isinstance(bt["body"], dict) and bt["body"].get("id"):
            call(
                client,
                "GET",
                f"/api/v1/backtests/{bt['body']['id']}",
                token=access,
                expect=200,
            )

        # Paper
        call(
            client,
            "POST",
            "/api/v1/paper/orders",
            json_body={
                "symbol": "EURUSD",
                "side": "buy",
                "order_type": "market",
                "volume": "0.10",
            },
            token=access,
            expect=200,
        )
        call(client, "GET", "/api/v1/paper/positions", token=access, expect=200)
        call(client, "GET", "/api/v1/paper/history", token=access, expect=200)
        call(client, "GET", "/api/v1/paper/performance", token=access, expect=200)

        # Walkforward
        wf_bars = []
        price = 1.1
        for i in range(100):
            ts = (now - timedelta(minutes=15 * (100 - i))).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            o = price
            h = price + 0.001
            l = price - 0.001
            c = price + 0.0001
            wf_bars.append(
                {
                    "open_time": ts,
                    "open": f"{o:.5f}",
                    "high": f"{h:.5f}",
                    "low": f"{l:.5f}",
                    "close": f"{c:.5f}",
                    "volume": "100",
                }
            )
            price = c
        wf = call(
            client,
            "POST",
            "/api/v1/walkforward/run",
            json_body={
                "request_id": f"wf-{uid}",
                "symbol": "EURUSD",
                "timeframe": "m15",
                "initial_balance": "10000",
                "bars": wf_bars,
                "in_sample_bars": 30,
                "out_sample_bars": 10,
                "step_bars": 10,
            },
            token=access,
            expect=200,
        )
        call(client, "GET", "/api/v1/walkforward/results", token=access, expect=200)
        if isinstance(wf["body"], dict) and wf["body"].get("id"):
            call(
                client,
                "GET",
                f"/api/v1/walkforward/{wf['body']['id']}",
                token=access,
                expect=200,
            )

        # Risk
        call(
            client,
            "POST",
            "/api/v1/risk/check",
            json_body={
                "request_id": f"risk-{uid}",
                "symbol": "EURUSD",
                "side": "buy",
                "requested_lots": "0.10",
                "stop_loss_distance": "0.0020",
                "atr": "0.0015",
                "account_balance": "10000",
                "account_equity": "10000",
            },
            token=access,
            expect=200,
        )

        # Execution (disabled)
        call(
            client,
            "POST",
            "/api/v1/execution/check",
            json_body={
                "request_id": f"ex-{uid}",
                "symbol": "EURUSD",
                "side": "buy",
                "volume": "0.01",
            },
            token=access,
            expect=[200, 400, 403, 404, 422],
        )
        call(
            client,
            "POST",
            "/api/v1/execution/submit",
            json_body={
                "request_id": f"exs-{uid}",
                "symbol": "EURUSD",
                "side": "buy",
                "volume": "0.01",
            },
            token=access,
            expect=[200, 400, 403, 404, 422],
        )

        call(
            client,
            "POST",
            "/api/v1/auth/logout",
            json_body={},
            token=access,
            expect=200,
        )

    passed = sum(1 for r in results if r["ok"])
    failed = [r for r in results if not r["ok"]]
    failures = []
    for r in failed:
        body = r["body"]
        if isinstance(body, (dict, list)):
            body_s = json.dumps(body, default=str)[:500]
        else:
            body_s = str(body)[:500]
        failures.append(
            {
                "method": r["method"],
                "path": r["path"],
                "status": r["status"],
                "expect": r["expect"],
                "body": body_s,
            }
        )
    out = {
        "mode": "local_asgi_fake_auth",
        "email": email,
        "total": len(results),
        "passed": passed,
        "failed": len(failed),
        "failures": failures,
        "results": [
            {
                "method": r["method"],
                "path": r["path"],
                "status": r["status"],
                "ok": r["ok"],
                "expect": r["expect"],
            }
            for r in results
        ],
    }

    Path("/tmp/qf_local_api_audit.json").write_text(json.dumps(out, default=str))
    print(f"TOTAL={out['total']} PASSED={out['passed']} FAILED={out['failed']}")
    for f in failures:
        print(
            f"FAIL {f['method']} {f['path']} status={f['status']} "
            f"expect={f['expect']} body={f['body']}"
        )
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
