"""Entrypoint for the Windows MT5 worker agent.

Without WORKER_SERVICE_TOKEN and a registered host assignment this process
idles safely and refuses to claim READY. It never prints credentials.
"""

from __future__ import annotations

import logging
import os
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("mt5_worker_agent")


def _token_ok(raw: str | None) -> bool:
    return bool(raw and len(raw.strip()) >= 16)


def main() -> int:
    token = os.environ.get("WORKER_SERVICE_TOKEN")
    api = (os.environ.get("QUANTFORG_API_BASE_URL") or "").strip()
    if not _token_ok(token):
        logger.error("WORKER_SERVICE_TOKEN missing or too short — refusing to start")
        return 2
    logger.info(
        "mt5_worker_agent starting api_configured=%s token_len=%s",
        bool(api),
        len(token.strip()) if token else 0,
    )
    logger.info(
        "Agent idle loop — waiting for control-plane assignment. "
        "No READY claim without authenticated MT5 verify."
    )
    # Safe idle: real poll/assignment wiring lands when Windows hosts exist.
    while True:
        time.sleep(30)
        logger.info("mt5_worker_agent heartbeat idle=true ready=false")


if __name__ == "__main__":
    raise SystemExit(main())
