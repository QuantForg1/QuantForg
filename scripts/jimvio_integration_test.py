"""Safe Jimvio integration test — no trading, no MT5, no secrets printed."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import httpx

from app.application.services.jimvio_publisher import (
    DEFAULT_JIMVIO_WEBHOOK_URL,
    SIGNATURE_HEADER,
    build_test_payload,
    signed_request,
)
from core.config.settings import get_settings


def _secret() -> str:
    settings = get_settings()
    configured = getattr(settings, "quantforg_webhook_secret", None)
    raw = ""
    if configured is not None:
        getter = getattr(configured, "get_secret_value", None)
        raw = getter() if callable(getter) else str(configured)
    raw = str(raw or "").strip() or (
        os.environ.get("QUANTFORG_WEBHOOK_SECRET")
        or os.environ.get("JIMVIO_WEBHOOK_SECRET")
        or ""
    ).strip()
    return raw


async def send_test_event(*, event_id: str) -> int:
    secret = _secret()
    if not secret:
        print("QUANTFORG_WEBHOOK_SECRET is not configured. Refusing to send.")
        return 2
    settings = get_settings()
    url = str(
        getattr(settings, "jimvio_webhook_url", None) or DEFAULT_JIMVIO_WEBHOOK_URL
    ).strip()
    payload = build_test_payload(event_id=event_id)
    body, signature = signed_request(payload, secret)
    headers = {
        "Content-Type": "application/json",
        SIGNATURE_HEADER: signature,
    }
    timeout = httpx.Timeout(8.0, connect=4.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, content=body, headers=headers)
    print(
        json.dumps(
            {
                "url": url,
                "event_id": payload["event_id"],
                "event_type": payload["event_type"],
                "status_field": payload["status"],
                "http_status": response.status_code,
                "ok": 200 <= response.status_code < 300,
                "signature_header": SIGNATURE_HEADER,
                "signature_hex_len": len(signature),
                "body_bytes": len(body),
            },
            indent=2,
        )
    )
    return 0 if 200 <= response.status_code < 300 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Send a TEST event to Jimvio. Does not trade."
    )
    parser.add_argument(
        "--event-id",
        default="quantforg-integration-test-001",
        help="Stable event_id for Jimvio idempotency",
    )
    args = parser.parse_args(argv)
    try:
        return asyncio.run(send_test_event(event_id=str(args.event_id)))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
