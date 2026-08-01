"""Enterprise Security Center — sessions, devices, IPs, MFA, alerts."""

from __future__ import annotations

from typing import Any

from app.domain.enterprise_platform.persistence import utc_iso
from app.domain.enterprise_platform.production_readers import (
    read_audit_logs,
    read_devices,
    read_sessions,
    read_users,
)


async def build_security_center() -> dict[str, Any]:
    sessions = await read_sessions()
    devices = await read_devices()
    users = await read_users(limit=200)
    audits = await read_audit_logs(limit=100)

    ips = sorted(
        {
            str(s.get("ip"))
            for s in sessions
            if s.get("ip")
        }
    )
    login_history = [
        a
        for a in audits
        if "login" in str(a.get("action") or "").lower()
        or "auth" in str(a.get("action") or "").lower()
    ][:50]

    # MFA status — observe only; never invent enrolled factors
    mfa = {
        "status": "provider_managed",
        "note": (
            "MFA is managed by the existing auth provider. "
            "Enterprise Platform does not modify authentication."
        ),
        "fabricated": False,
        "modifies_auth": False,
    }

    alerts: list[dict[str, Any]] = []
    active_sessions = [
        s for s in sessions if s.get("is_active") and not s.get("revoked")
    ]
    if len(active_sessions) > 50:
        alerts.append(
            {
                "severity": "warn",
                "code": "high_session_count",
                "message": f"{len(active_sessions)} active sessions observed",
            }
        )
    revoked = sum(1 for s in sessions if s.get("revoked"))
    if revoked:
        alerts.append(
            {
                "severity": "info",
                "code": "sessions_revoked",
                "message": f"{revoked} revoked sessions in recent window",
            }
        )

    return {
        "as_of": utc_iso(),
        "sessions": sessions,
        "session_count": len(sessions),
        "active_sessions": len(active_sessions),
        "devices": devices,
        "device_count": len(devices),
        "ips": ips,
        "ip_count": len(ips),
        "mfa": mfa,
        "login_history": login_history,
        "security_alerts": alerts,
        "user_count_sample": len(users),
        "fabricated": False,
        "modifies_auth": False,
    }
