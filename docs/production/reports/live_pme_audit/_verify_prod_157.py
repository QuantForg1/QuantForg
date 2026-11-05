"""Read-only production verification after PR #157. No secrets printed."""

from __future__ import annotations

import importlib.util
import json
import os
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent / "prod_verify_157.json"


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _token() -> str:
    spec = importlib.util.spec_from_file_location(
        "phase4_monitor", ROOT / "scripts" / "phase4_continuous_monitor.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.obtain_owner_token()


def _get(url: str, tok: str | None = None) -> tuple[int, object]:
    headers = {"Accept": "application/json"}
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return int(resp.status), json.loads(raw)
            except json.JSONDecodeError:
                return int(resp.status), {"_raw": raw[:2000]}
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    _load_dotenv()
    tok = _token()
    root = "https://quantforg-production.up.railway.app"
    base = f"{root}/api/v1"
    endpoints = {
        "health": f"{root}/health",
        "ready": f"{root}/ready",
        "policy": f"{base}/admin/control/policy",
        "overview": f"{base}/admin/control/overview",
        "auto_trading": f"{base}/ite/ops/auto-trading",
        "control_center": f"{base}/ite/ops/control-center",
        "robot_health": f"{base}/ite/ops/robot-health-monitor",
        "portfolio": f"{base}/mt5/portfolio",
    }
    raw: dict[str, object] = {}
    for name, url in endpoints.items():
        need_auth = name not in {"health", "ready"}
        status, body = _get(url, tok if need_auth else None)
        raw[name] = {"status": status, "body": body}
        print(f"{name}: HTTP {status}")

    summary = {
        "fetched_at_utc": datetime.now(UTC).isoformat(),
        "expected_commit": "98f173aab3ad07a462243980ed611b7510c79b9e",
        "railway_deployment_id": "75db8c3d-1316-4ef3-bf19-2e89e28c72e2",
        "pr": 157,
        "raw_status": {k: (v.get("status") if isinstance(v, dict) else None) for k, v in raw.items()},
    }
    OUT.write_text(json.dumps({"summary": summary, "raw": raw}, indent=2, default=str), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
