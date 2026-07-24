"""Local health smoke — production-like deferred routers."""
from __future__ import annotations

import os
import threading
import time
import urllib.request

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DURABLE_PERSISTENCE", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-local-healthcheck-32chars")
os.environ.setdefault("PORT", "18765")
os.environ["QF_EAGER_ROUTERS"] = "false"
os.environ["QF_SYNC_STARTUP"] = "false"

from core.config.settings import get_settings

get_settings.cache_clear()

from app.main import create_app
from uvicorn import Config, Server

app = create_app()
port = int(os.environ["PORT"])
server = Server(Config(app=app, host="127.0.0.1", port=port, log_level="error"))
threading.Thread(
    target=lambda: __import__("asyncio").run(server.serve()),
    daemon=True,
).start()

ok = False
for _ in range(80):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health/live", timeout=1) as r:
            body = r.read().decode()
            ok = r.status == 200 and "ok" in body
            print("LIVE", r.status, body)
            break
    except Exception:
        time.sleep(0.1)

print("RESULT", "OK" if ok else "FAIL")
server.should_exit = True
raise SystemExit(0 if ok else 1)
