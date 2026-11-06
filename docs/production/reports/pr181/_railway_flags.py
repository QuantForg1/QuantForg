"""Read Railway production flag presence/values — no secret dumping."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
KEYS = [
    "RAILWAY_GIT_COMMIT_SHA",
    "QUANTFORG_LIVE_REVERSAL_EXITS",
    "QUANTFORG_M1_MICRO_SCALPING",
    "QUANTFORG_M1_MICRO_LIVE_SUBMIT",
    "EXECUTION_ENABLED",
    "QUANTFORG_EXECUTION_ENABLED",
    "OWNER_MAX_PLANNED_RISK_PCT",
    "OWNER_DAILY_LOSS_PCT",
    "OWNER_MAX_LOT",
    "OWNER_MIN_TRADE_QUALITY",
    "OWNER_MIN_REWARD_RISK",
]


def main() -> None:
    proc = subprocess.run(
        ["railway", "variables", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    raw = proc.stdout or ""
    start = raw.find("{")
    if start < 0:
        start = raw.find("[")
    if start < 0:
        raise SystemExit(f"no json: {proc.stderr[:300]}")
    data = json.loads(raw[start:])
    if isinstance(data, dict) and "variables" in data:
        data = data["variables"]
    flat: dict[str, object] = {}
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "name" in item:
                flat[str(item["name"])] = item.get("value")
    elif isinstance(data, dict):
        flat = {str(k): v for k, v in data.items()}

    report = {"var_count": len(flat), "flags": {}, "related": {}}
    for key in KEYS:
        if key in flat:
            val = flat[key]
            report["flags"][key] = {
                "present": True,
                "empty": val is None or str(val).strip() == "",
                "value": val,
            }
        else:
            report["flags"][key] = {"present": False, "empty": True, "value": None}

    for key, val in sorted(flat.items()):
        ku = key.upper()
        if any(
            token in ku
            for token in (
                "M1_MICRO",
                "REVERSAL",
                "EXECUTION_ENABLED",
                "LIVE_REVERSAL",
                "COMMIT",
                "RISK_PCT",
                "DAILY_LOSS",
                "MAX_LOT",
                "TRADE_QUALITY",
            )
        ):
            report["related"][key] = val

    path = OUT / "railway_flags.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(path)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
