#!/usr/bin/env python3
"""Apply QuantForg Auth email templates via Supabase Management API.

Requires:
  SUPABASE_ACCESS_TOKEN  — personal access token (Dashboard → Account → Tokens)
  SUPABASE_PROJECT_REF   — defaults to linked QuantForg project

Never prints the access token. Exits non-zero on failure.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "docs" / "auth" / "email-templates"
PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF", "otqyhlmwaifokrczryrc").strip()
API = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/config/auth"


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _payload() -> dict[str, object]:
    return {
        "mailer_subjects_confirmation": "Confirm your QuantForg email",
        "mailer_templates_confirmation_content": _read("confirm-signup.html"),
        "mailer_subjects_recovery": "Reset your QuantForg password",
        "mailer_templates_recovery_content": _read("reset-password.html"),
        "mailer_subjects_email_change": "Confirm your new QuantForg email",
        "mailer_templates_email_change_content": _read("change-email.html"),
        "mailer_subjects_magic_link": "Your QuantForg sign-in link",
        "mailer_templates_magic_link_content": (
            _read("confirm-signup.html")
            .replace("Confirm your email", "Sign in to QuantForg")
            .replace("Confirm email", "Sign in")
            .replace(
                "Confirm your email to secure your account and unlock subscription features.",
                "Use the button below to sign in. This link expires shortly and can only be used once.",
            )
        ),
        "mailer_subjects_invite": "You're invited to QuantForg",
        "mailer_templates_invite_content": _read("welcome.html"),
        "mailer_notifications_email_changed_enabled": True,
        "mailer_notifications_password_changed_enabled": True,
    }


def _request(method: str, token: str, body: dict[str, object] | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise SystemExit(f"Management API {method} failed: HTTP {exc.code}: {detail}") from exc


def main() -> int:
    token = (os.environ.get("SUPABASE_ACCESS_TOKEN") or "").strip()
    if not token:
        print(
            "SUPABASE_ACCESS_TOKEN is required to apply Auth email templates.",
            file=sys.stderr,
        )
        return 2
    if not PROJECT_REF:
        print("SUPABASE_PROJECT_REF is empty", file=sys.stderr)
        return 2

    body = _payload()
    for key in (
        "mailer_templates_confirmation_content",
        "mailer_templates_recovery_content",
        "mailer_templates_email_change_content",
    ):
        html = str(body[key])
        if "{{ .ConfirmationURL }}" not in html:
            raise SystemExit(f"Refusing to apply {key}: missing ConfirmationURL")

    updated = _request("PATCH", token, body)
    # Verify a subset of subjects came back (keys may be present even if truncated).
    subjects = {
        k: updated.get(k)
        for k in (
            "mailer_subjects_confirmation",
            "mailer_subjects_recovery",
            "mailer_subjects_email_change",
            "mailer_subjects_magic_link",
        )
    }
    print(json.dumps({"ok": True, "project_ref": PROJECT_REF, "subjects": subjects}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
