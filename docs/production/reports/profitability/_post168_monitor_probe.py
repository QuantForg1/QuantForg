"""Post-#168 broker + session probe (gateway-authoritative)."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path


def _token() -> str:
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("MT5_GATEWAY_TOKEN="):
            return s.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no token")


def _get(path: str, token: str) -> object:
    req = urllib.request.Request(
        f"https://gateway.quantforg.com{path}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Gateway-Token": token,
            "X-QuantForg-Gateway-Token": token,
            "User-Agent": "QuantForg-Post168Monitor/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    token = _token()
    out = {
        "session": _get("/session/status", token),
        "account": _get("/account", token),
        "positions": _get("/positions", token),
        "quotes": _get("/quotes/XAUUSD", token),
        "symbol": _get("/symbols/XAUUSD", token),
    }
    path = Path("docs/production/reports/profitability/post168_monitor_probe.json")
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("account", "positions")}, indent=2))
    print("wrote", path)


if __name__ == "__main__":
    main()
