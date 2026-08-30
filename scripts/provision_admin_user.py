#!/usr/bin/env python3
"""Provision the QuantForg admin user via Supabase Auth (hashed password).

Reads credentials ONLY from environment:

  ADMIN_EMAIL
  ADMIN_PASSWORD

Never logs or prints the password. Never hardcodes credentials.

Usage (production operator machine with service-role secrets):

  set ADMIN_EMAIL=<admin-email-from-ops-vault>
  set ADMIN_PASSWORD=<secret from vault>
  python scripts/provision_admin_user.py

Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (existing project secrets).
"""

from __future__ import annotations

import os
import sys
from typing import Any


def _env(name: str) -> str:
    value = str(os.environ.get(name) or "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    email = _env("ADMIN_EMAIL").lower()
    password = _env("ADMIN_PASSWORD")
    if len(password) < 12:
        raise SystemExit("ADMIN_PASSWORD must be at least 12 characters")

    url = _env("SUPABASE_URL")
    service_key = _env("SUPABASE_SERVICE_ROLE_KEY")

    try:
        from supabase import create_client
    except ImportError as exc:
        raise SystemExit("supabase package required") from exc

    client = create_client(url, service_key)
    auth_admin = client.auth.admin

    existing: Any = None
    try:
        listed = auth_admin.list_users()
        users = getattr(listed, "users", None) or listed or []
        for user in users:
            user_email = str(getattr(user, "email", "") or "").lower()
            if user_email == email:
                existing = user
                break
    except Exception as exc:  # noqa: BLE001 — surface provider errors without secrets
        print(f"list_users failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    auth_user_id: str | None = None
    if existing is None:
        try:
            created = auth_admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"display_name": "QuantForg Admin"},
                }
            )
            user = getattr(created, "user", created)
            auth_user_id = str(getattr(user, "id", "") or "")
            print(f"created_auth_user email={email}")
        except Exception as exc:  # noqa: BLE001
            print(f"create_user failed: {type(exc).__name__}", file=sys.stderr)
            return 1
    else:
        auth_user_id = str(getattr(existing, "id", "") or "")
        try:
            auth_admin.update_user_by_id(
                auth_user_id,
                {"password": password, "email_confirm": True},
            )
            print(f"updated_auth_user email={email}")
        except Exception as exc:  # noqa: BLE001
            print(f"update_user failed: {type(exc).__name__}", file=sys.stderr)
            return 1

    if not auth_user_id:
        print("missing auth user id", file=sys.stderr)
        return 1

    # Platform role lives in public.users (not Auth app_metadata alone).
    try:
        row = (
            client.table("users")
            .select("id,email,role,status")
            .eq("email", email)
            .limit(1)
            .execute()
        )
        rows = getattr(row, "data", None) or []
        if rows:
            client.table("users").update(
                {"role": "admin", "status": "active", "auth_user_id": auth_user_id}
            ).eq("id", rows[0]["id"]).execute()
            print(f"updated_platform_role email={email} role=admin")
        else:
            client.table("users").insert(
                {
                    "email": email,
                    "display_name": "QuantForg Admin",
                    "role": "admin",
                    "status": "active",
                    "auth_user_id": auth_user_id,
                }
            ).execute()
            print(f"created_platform_user email={email} role=admin")
    except Exception as exc:  # noqa: BLE001
        print(f"platform_user_role failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    # Drop secret from process locals before exit.
    del password
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
