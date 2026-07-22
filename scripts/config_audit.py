#!/usr/bin/env python3
"""Configuration audit — unused / duplicate / conflicting / missing Settings keys.

Read-only. Writes ``docs/production/reports/config_audit_*.json``.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


CRITICAL = (
    "secret_key",
    "postgres_host",
    "postgres_password",
    "execution_enabled",
    "mt5_gateway_base_url",
    "mt5_gateway_caller_token",
    "app_env",
)


def main() -> int:
    from core.config.settings import Settings

    fields = list(Settings.model_fields.keys())
    usage: dict[str, int] = dict.fromkeys(fields, 0)
    code_roots = [
        ROOT / "app",
        ROOT / "core",
        ROOT / "services",
        ROOT / "frontend" / "src",
        ROOT / "tests",
    ]
    for root in code_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx", ".mjs", ".js"}:
                continue
            if path.name == "settings.py":
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for f in fields:
                if re.search(rf"\b{re.escape(f)}\b", text):
                    usage[f] += 1
                env = f.upper()
                if env in text or f"NEXT_PUBLIC_{env}" in text:
                    usage[f] += 1

    unused = sorted(f for f, n in usage.items() if n == 0)
    conflicts: list[dict[str, str]] = [
        {
            "keys": "gold_only_mode, multi_symbol_enabled",
            "rule": "multi_symbol_enabled=true overrides gold_only_mode",
            "status": "documented",
        },
        {
            "keys": "mt5_use_mock, mt5_gateway_base_url, execution_enabled",
            "rule": (
                "Live order_send requires gateway URL + "
                "EXECUTION_ENABLED=true + not mock-only path"
            ),
            "status": "documented",
        },
        {
            "keys": "beta_invite_code vs NEXT_PUBLIC_BETA_INVITE_CODE",
            "rule": (
                "Server BETA_INVITE_CODE only; "
                "NEXT_PUBLIC invite must not be used"
            ),
            "status": "enforced",
        },
    ]

    missing_critical = []
    s = Settings()
    if s.execution_enabled and not (s.mt5_gateway_base_url or "").strip():
        missing_critical.append(
            "mt5_gateway_base_url required when EXECUTION_ENABLED"
        )
    if s.beta_mode and not (s.beta_invite_code or "").strip():
        missing_critical.append("beta_invite_code required when BETA_MODE")

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "settings_field_count": len(fields),
        "fields": fields,
        "unused_in_code_scan": unused,
        "usage_counts": usage,
        "conflicts_documented": conflicts,
        "critical_keys": list(CRITICAL),
        "missing_critical_for_current_defaults": missing_critical,
        "notes": [
            "Unused scan is heuristic — some Settings are env-only / future hooks.",
            "Do not delete unused keys without OWNER review.",
        ],
    }

    out_dir = ROOT / "docs" / "production" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"config_audit_{stamp}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "report": str(out), "unused": len(unused)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
