#!/usr/bin/env python3
"""Prove RC1 validation ops route returns HTTP 200 under operator auth.

Uses FastAPI dependency overrides — does not hit production auth.
Writes evidence to docs/production/pre_live_evidence/.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    os.environ.setdefault("APP_ENV", "testing")
    os.environ.setdefault("QF_EAGER_ROUTERS", "true")

    from fastapi.testclient import TestClient

    from app.application.dto.auth import AuthUserDTO
    from app.domain.enums.user import UserRole
    from app.main import create_app
    from app.presentation.dependencies.auth import get_current_user

    app = create_app()

    async def _operator() -> AuthUserDTO:
        return AuthUserDTO(
            id=uuid4(),
            email="rc1-operator@example.com",
            display_name="RC1 Operator",
            role=UserRole.OWNER.value,
            status="active",
            auth_user_id=uuid4(),
        )

    app.dependency_overrides[get_current_user] = _operator
    client = TestClient(app)
    path = "/api/v1/ite/ops/rc1-production-validation"
    resp = client.get(path)
    body: object
    try:
        body = resp.json()
    except Exception:
        body = resp.text[:500]
    evidence = {
        "collected_at": _now(),
        "mode": "local_testclient_operator_override",
        "path": path,
        "http_status": resp.status_code,
        "ok": resp.status_code == 200,
        "body_keys": (
            sorted(body.keys()) if isinstance(body, dict) else None
        ),
        "note": (
            "Proves route is wired and returns 200 for OperatorUser. "
            "Does not prove production/staging deployment."
        ),
    }
    out = (
        root
        / "docs"
        / "production"
        / "pre_live_evidence"
        / "rc1_endpoint_local_200.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
