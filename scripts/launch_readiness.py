#!/usr/bin/env python3
"""Launch Readiness CLI — audit blockers; optional official promote.

Never bypasses Risk/Safety. Never flips EXECUTION_ENABLED.
Never fabricates gateway state. Demo Certification is not a LIVE gate.

Usage (in-process, default):
  poetry run python scripts/launch_readiness.py
  poetry run python scripts/launch_readiness.py --promote --confirm \\
      --reason "OWNER live promotion"

Remote (OWNER bearer or login credentials):
  set QUANTFORG_API_URL=https://quantforg-production.up.railway.app/api/v1
  set QUANTFORG_OWNER_TOKEN=<jwt>
  # OR:
  set QUANTFORG_OWNER_EMAIL=...
  set QUANTFORG_OWNER_PASSWORD=...
  # OR E2E_EMAIL / E2E_PASSWORD
  poetry run python scripts/launch_readiness.py --remote --promote --confirm
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _print_report(payload: dict) -> None:
    print(json.dumps(payload, indent=2, default=str))
    blockers = payload.get("blockers") or []
    if blockers:
        print("\n=== BLOCKERS ===")
        for b in blockers:
            print(f"\n[{b.get('key')}] {b.get('label')} = {b.get('value')}")
            print(f"  WHY: {b.get('why')}")
            print(f"  HOW: {b.get('how_to_resolve')}")
    else:
        print("\nNo required blockers.")
    print(f"\nready_for_promotion={payload.get('ready_for_promotion')}")
    print(f"ready_for_gate_enabled={payload.get('ready_for_gate_enabled')}")
    print(f"next_promotion_target={payload.get('next_promotion_target')}")
    ver = payload.get("verification") or {}
    if ver:
        print(f"ops_mode={ver.get('ops_mode')}")
        print(f"gate={ver.get('gate')}")
        print(f"auto_trading={ver.get('auto_trading')}")


def _run_local(*, promote: bool, confirm: bool, reason: str) -> int:
    from app.application.services.launch_readiness import (
        build_launch_readiness,
        promote_to_live_execution,
    )
    from app.domain.institutional_trading.operations.control_plane import (
        get_control_plane,
    )
    from app.domain.institutional_trading.operations.models import OperatorIdentity
    from core.config.settings import get_settings

    plane = get_control_plane()
    settings = get_settings()
    report = build_launch_readiness(
        plane, settings=settings, owner_authorized=confirm
    )
    _print_report(report.to_dict())

    if not promote:
        return 0 if report.ready_for_promotion else 2

    op = OperatorIdentity(
        user_id=uuid4(),
        role="owner",
        display_name="launch_readiness_cli",
    )
    result = promote_to_live_execution(
        plane,
        op,
        reason=reason,
        confirmed=confirm,
        settings=settings,
    )
    print("\n=== PROMOTE RESULT ===")
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("promoted") or result.get("ok") else 3


def _resolve_owner_token(base: str) -> str:
    token = (os.environ.get("QUANTFORG_OWNER_TOKEN") or "").strip()
    if token:
        return token
    email = (
        os.environ.get("QUANTFORG_OWNER_EMAIL")
        or os.environ.get("E2E_EMAIL")
        or ""
    ).strip()
    password = (
        os.environ.get("QUANTFORG_OWNER_PASSWORD")
        or os.environ.get("E2E_PASSWORD")
        or ""
    ).strip()
    if not email or not password:
        return ""
    import urllib.request

    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310
        f"{base}/auth/login",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        body = json.loads(resp.read().decode("utf-8"))
    access = str(body.get("access_token") or body.get("access") or "").strip()
    return access


def _run_remote(*, promote: bool, confirm: bool, reason: str) -> int:
    import urllib.error
    import urllib.request

    base = (
        os.environ.get("QUANTFORG_API_URL")
        or os.environ.get("QF_API_BASE")
        or "https://quantforg-production.up.railway.app/api/v1"
    ).rstrip("/")
    try:
        token = _resolve_owner_token(base)
    except Exception as exc:
        print(f"OWNER login failed: {exc}", file=sys.stderr)
        return 1
    if not token:
        print(
            "Remote mode requires QUANTFORG_OWNER_TOKEN or "
            "QUANTFORG_OWNER_EMAIL+QUANTFORG_OWNER_PASSWORD (or E2E_*)",
            file=sys.stderr,
        )
        return 1

    def _call(method: str, path: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode("utf-8")
        url = f"{base}{path}"
        if not url.startswith(("https://", "http://")):
            raise ValueError("QUANTFORG_API_URL must be http(s)")
        req = urllib.request.Request(  # noqa: S310
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=45) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    try:
        payload = _call("GET", "/ite/ops/launch-readiness")
    except urllib.error.HTTPError as exc:
        print(f"GET launch-readiness failed: {exc.code} {exc.read()[:400]!r}")
        return 1
    _print_report(payload)

    if not promote:
        return 0 if payload.get("ready_for_promotion") else 2

    if not confirm:
        print("PROMOTE refused: --confirm required", file=sys.stderr)
        return 3

    try:
        result = _call(
            "POST",
            "/ite/ops/launch-readiness/promote",
            {
                "reason": reason,
                "confirmed": True,
                "activate_auto_trading": True,
            },
        )
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(f"PROMOTE failed: {exc.code} {raw[:800]}")
        return 3
    print("\n=== PROMOTE RESULT ===")
    print(json.dumps(result, indent=2, default=str))

    # Post-verify
    try:
        post = _call("GET", "/ite/ops/launch-readiness")
        print("\n=== POST VERIFY ===")
        ver = post.get("verification") or {}
        print(json.dumps(ver, indent=2, default=str))
        mode = str(ver.get("ops_mode") or "").upper()
        if mode != "LIVE":
            return 3
    except Exception as exc:
        print(f"post-verify failed: {exc}", file=sys.stderr)
        return 3
    return 0 if result.get("promoted") or result.get("ok") else 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Run official SHADOW→CANARY→LIVE when ready",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="OWNER confirmation (required to promote)",
    )
    parser.add_argument(
        "--reason",
        default="OWNER official LIVE promotion (Demo cert not required)",
        help="Audit reason",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Call production API with OWNER token or login",
    )
    args = parser.parse_args()
    if args.remote:
        return _run_remote(
            promote=args.promote, confirm=args.confirm, reason=args.reason
        )
    return _run_local(
        promote=args.promote, confirm=args.confirm, reason=args.reason
    )


if __name__ == "__main__":
    raise SystemExit(main())
