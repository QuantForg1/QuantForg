"""Sanitized broker credential presence report for Windows hosts.

Prints READY / BLOCKED status and missing env key NAMES only.
Never prints credential values.
"""

from __future__ import annotations

import json
import sys

from services.mt5_worker_agent.broker_demo_adapters import (
    missing_credential_keys,
    resolve_credentials,
    supported_brokers,
)


def build_credential_status_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for slug in supported_brokers():
        for env in ("demo", "live"):
            missing = missing_credential_keys(slug, environment=env)  # type: ignore[arg-type]
            creds = resolve_credentials(slug, environment=env)  # type: ignore[arg-type]
            rows.append(
                {
                    "broker": slug,
                    "env": env,
                    "status": (
                        "READY_TO_VERIFY"
                        if creds is not None
                        else "BLOCKED_MISSING_CREDENTIALS"
                    ),
                    "login_set": bool(getattr(creds, "login", None)) if creds else False,
                    "password_set": bool(getattr(creds, "password", None))
                    if creds
                    else False,
                    "server_set": bool(getattr(creds, "server", None))
                    if creds
                    else False,
                    "missing_keys": missing,
                }
            )
    return rows


def main() -> int:
    rows = build_credential_status_rows()
    blocked = sum(1 for r in rows if r["status"] != "READY_TO_VERIFY")
    print(
        json.dumps(
            {
                "ok": True,
                "blocked": blocked,
                "rows": rows,
            },
            indent=2,
        )
    )
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
