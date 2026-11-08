#!/usr/bin/env python3
"""Grant Premium compensation to the designated owner only.

Uses BillingService.grant_owner_compensation_premium — no invoice, no IPN.

Usage (operator machine with platform DB + secrets):

  python scripts/grant_owner_compensation_premium.py
"""

from __future__ import annotations

import asyncio
import sys

from app.application.services.billing_service import BillingService
from app.domain.identity.designated_owner import DESIGNATED_OWNER_EMAIL
from core.config.settings import Settings


async def _run() -> int:
    settings = Settings()
    service = BillingService(settings)
    try:
        result = await service.grant_owner_compensation_premium(
            email=DESIGNATED_OWNER_EMAIL
        )
    except Exception as exc:  # noqa: BLE001 — operator CLI surfaces typed errors
        print(f"grant_failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        f"granted plan={result.get('plan_id')} "
        f"tier={result.get('license_tier')} "
        f"until={result.get('grace_end')}"
    )
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
