"""Generate operator documentation for RC1."""

from __future__ import annotations

from pathlib import Path

from app.domain.institutional_trading.release_candidate.config import (
    DEFAULT_RC1_CONFIG,
)

DOCS_DIR = Path(__file__).resolve().parents[4] / "docs" / "production" / "rc1_guides"


OPERATOR_MANUAL = """# QuantForg RC1 — Operator Manual

## Purpose

Prove, with measurable evidence, that QuantForg is consistently profitable, stable, and safe **before** increasing capital.

## What operators do

1. Run **Production Checklist** (`GET /ite/reliability/rc1`) — expect PASS / WARNING / FAIL per subsystem.
2. Run **Smoke Test** (`POST /ite/reliability/rc1/smoke`) — connectivity only; **never places real trades**.
3. Review **Live Statistics** and **Go Live Score** on the RC1 desk.
4. Keep **Paper / Demo / Live** results separate — never mix.
5. Use **Capital Scaling Advisor** for suggestions only — never auto-applied.
6. Prefer **{min_days}–{rec_days} consecutive successful trading days** before scale-up.

## Hard locks

- Smoke never places orders
- Never auto-scale capital
- No new strategies / experimental production logic in RC1
""".format(
    min_days=DEFAULT_RC1_CONFIG.min_consecutive_trading_days,
    rec_days=DEFAULT_RC1_CONFIG.recommended_evidence_days,
)

DEPLOYMENT_GUIDE = """# QuantForg RC1 — Deployment Guide

1. Confirm Railway environment and secrets (names present; rotate via platform).
2. Confirm database / Supabase URL.
3. Deploy backend; verify `/health/live` and `/health/ready`.
4. Verify MT5 Gateway and broker session (read-only first).
5. Open RC1 desk → run checklist + smoke (no trades).
6. Enable limited live only after Go Live Score ≥ threshold **and** human approval.
"""

RECOVERY_GUIDE = """# QuantForg RC1 — Recovery Guide

1. Acknowledge incidents on Reliability desk.
2. Use gateway / MT5 recovery endpoints (`/ite/reliability/recovery/*`) — safe-read first.
3. Run position recovery from production hardening (observational sync).
4. Re-run RC1 smoke (never places orders) before re-enabling OMS.
5. Document incident with timeline export.
"""

INCIDENT_RESPONSE = """# QuantForg RC1 — Incident Response Guide

1. **Detect** — Health monitoring + Reliability incidents.
2. **Contain** — Disable OMS / kill-switch if needed (human action).
3. **Diagnose** — Timeline, execution attempts, gateway probes.
4. **Recover** — Follow Recovery Guide; re-smoke.
5. **Review** — Update RC validation metrics; do not scale capital after an incident until evidence recovers.
"""

MONITORING_GUIDE = """# QuantForg RC1 — Monitoring Guide

Watch continuously:

- Go Live Score vs threshold ({threshold})
- Consecutive successful trading days
- Gateway / OMS / DB uptime
- Average latency & slippage
- Error rate, broker rejects, retry rate
- Paper vs Demo vs Live (separate)

Dashboards: `/rc1`, `/ite/reliability/*`, Performance Lab, Portfolio Intelligence.
""".format(
    threshold=DEFAULT_RC1_CONFIG.go_live_score_threshold,
)

MAINTENANCE_GUIDE = """# QuantForg RC1 — Maintenance Guide

Weekly:

- Export daily/weekly/monthly RC1 reports (CSV / PDF-text)
- Review Capital Scaling Advisor (do not auto-apply)
- Rotate secrets per platform policy
- Confirm smoke still PASS/WARNING with zero FAIL
- Archive incidents and verify no experimental production logic was introduced
"""


def write_rc1_guides(*, force: bool = False) -> list[str]:
    """Write operator guides under docs/production/rc1_guides/."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    files = {
        "OPERATOR_MANUAL.md": OPERATOR_MANUAL,
        "DEPLOYMENT_GUIDE.md": DEPLOYMENT_GUIDE,
        "RECOVERY_GUIDE.md": RECOVERY_GUIDE,
        "INCIDENT_RESPONSE_GUIDE.md": INCIDENT_RESPONSE,
        "MONITORING_GUIDE.md": MONITORING_GUIDE,
        "MAINTENANCE_GUIDE.md": MAINTENANCE_GUIDE,
    }
    written: list[str] = []
    for name, body in files.items():
        path = DOCS_DIR / name
        if path.exists() and not force:
            written.append(str(path))
            continue
        path.write_text(body.strip() + "\n", encoding="utf-8")
        written.append(str(path))
    return written


def guide_summaries() -> list[dict[str, str]]:
    return [
        {"id": "operator", "title": "Operator Manual", "path": "docs/production/rc1_guides/OPERATOR_MANUAL.md"},
        {"id": "deployment", "title": "Deployment Guide", "path": "docs/production/rc1_guides/DEPLOYMENT_GUIDE.md"},
        {"id": "recovery", "title": "Recovery Guide", "path": "docs/production/rc1_guides/RECOVERY_GUIDE.md"},
        {"id": "incident", "title": "Incident Response Guide", "path": "docs/production/rc1_guides/INCIDENT_RESPONSE_GUIDE.md"},
        {"id": "monitoring", "title": "Monitoring Guide", "path": "docs/production/rc1_guides/MONITORING_GUIDE.md"},
        {"id": "maintenance", "title": "Maintenance Guide", "path": "docs/production/rc1_guides/MAINTENANCE_GUIDE.md"},
    ]
