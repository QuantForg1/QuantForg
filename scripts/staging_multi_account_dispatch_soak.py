"""Staging soak harness for multi-account dispatch (optional).

Requires DATABASE_URL and applied lease migration.
Does NOT enable LIVE submit. Does NOT send broker orders.

Usage (staging only):
  python scripts/staging_multi_account_dispatch_soak.py

Exits non-zero when prerequisites are missing — never fabricates results.
"""

from __future__ import annotations

import json
import os
import sys
from uuid import uuid4


def main() -> int:
    if os.environ.get("MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        print("REFUSING: MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED must be false")
        return 2
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        print(
            json.dumps(
                {
                    "ok": False,
                    "blocked": True,
                    "reason": "DATABASE_URL missing — staging soak not run",
                }
            )
        )
        return 1
    from app.infrastructure.persistence import postgres_signal_dispatch as pg

    if not pg.table_ready():
        print(
            json.dumps(
                {
                    "ok": False,
                    "blocked": True,
                    "reason": "delivery_status column missing — apply Phase 6.1 migration",
                }
            )
        )
        return 1
    # Probe only: claim against random ids should return None safely.
    job = pg.claim_next_skip_locked(
        worker_id=uuid4(),
        user_id=uuid4(),
        broker_account_id=uuid4(),
        lease_seconds=30,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "skip_locked_callable": True,
                "probe_claim": job,
                "live_submit_allowed": False,
                "note": (
                    "Full multi-worker soak requires seeded staging intents "
                    "and disposable identities — not seeded by this script."
                ),
            },
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
