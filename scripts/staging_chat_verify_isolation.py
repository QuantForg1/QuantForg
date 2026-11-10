"""Verify staging/production isolation and acceptance_test emptiness."""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

SEC = Path.home() / "AppData" / "Local" / "QuantForg" / "secrets" / "staging"
STAGING = "saxsyobktmlyjghumxfz"
PROD = "otqyhlmwaifokrczryrc"


def load_vars(env: str) -> dict:
    cmd = ["railway", "variables", "--json"]
    if env == "production":
        cmd = [
            "railway",
            "variables",
            "--environment",
            "production",
            "--service",
            "QuantForg",
            "--json",
        ]
    raw = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    return json.loads(raw[raw.find("{") :])


def main() -> int:
    url = (SEC / "supabase_url.txt").read_text(encoding="ascii").strip()
    print("local_staging_url_ok", STAGING in url and PROD not in url)

    for path in (
        "/health/live",
        "/api/v1/public/market/chat?channel=acceptance_test&limit=5",
    ):
        with urllib.request.urlopen(
            f"https://quantforg-staging.up.railway.app{path}", timeout=30
        ) as r:
            body = r.read().decode()
            print(r.status, path, body[:140])

    stg = load_vars("staging")
    prod = load_vars("production")
    print("stg_supabase", STAGING in str(stg.get("SUPABASE_URL", "")))
    print(
        "stg_no_prod",
        PROD
        not in str(stg.get("SUPABASE_URL", "")) + str(stg.get("DATABASE_URL", "")),
    )
    print(
        "stg_db_pooler_user",
        f"postgres.{STAGING}" in str(stg.get("DATABASE_URL", "")),
    )
    print("stg_live_submit_multi", stg.get("MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED"))
    print("stg_m1_micro", stg.get("QUANTFORG_M1_MICRO_LIVE_SUBMIT"))
    print("stg_force_first", stg.get("FORCE_FIRST_TRADE"))
    print(
        "stg_qf_allow_worker",
        stg.get("QF_ALLOW_WORKER_ON_LIVE_TERMINAL", "UNSET"),
    )

    su = str(prod.get("SUPABASE_URL", ""))
    du = str(prod.get("DATABASE_URL", ""))
    m = re.search(r"https://([^.]+)", su)
    print("prod_host", m.group(1) if m else "?")
    print("prod_still_otqy", PROD in su + du)
    print("prod_no_staging", STAGING not in su + du)
    print("prod_live_submit_multi", prod.get("MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED"))
    print("prod_m1_micro", prod.get("QUANTFORG_M1_MICRO_LIVE_SUBMIT"))
    print("prod_force_first", prod.get("FORCE_FIRST_TRADE"))
    print(
        "prod_qf_allow_worker",
        prod.get("QF_ALLOW_WORKER_ON_LIVE_TERMINAL", "UNSET"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
