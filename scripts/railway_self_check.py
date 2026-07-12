"""In-container HTTP self-check for Railway deploy logs."""

from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.request


def main() -> int:
    port = os.environ.get("PORT", "8000")
    url = f"http://127.0.0.1:{port}/"
    for attempt in range(1, 11):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310
                body = response.read(80)
                print(
                    f"self_check_ok attempt={attempt} "
                    f"status={response.status} body={body!r}",
                    flush=True,
                )
                return 0
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"self_check_wait attempt={attempt} error={exc}", flush=True)
            time.sleep(1)
    print("self_check_fail", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
