"""Security Operations — suspicious logins, failed auth, abuse, permissions, keys."""

from __future__ import annotations

from typing import Any

from app.domain.production_reliability.persistence import utc_iso


def build_security_ops() -> dict[str, Any]:
    """Observe-only security operations expansion. Never modifies auth."""
    sessions: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    api_keys: list[dict[str, Any]] = []
    enterprise_alerts: list[dict[str, Any]] = []

    try:
        import asyncio

        from app.domain.enterprise_platform.security_center import build_security_center

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Caller should prefer async path; sync fallback returns partial
            security: dict[str, Any] = {"note": "async_context_partial"}
        else:
            security = asyncio.run(build_security_center())
        sessions = list(security.get("sessions") or [])
        enterprise_alerts = list(security.get("security_alerts") or [])
        audits = list(security.get("login_history") or [])
    except Exception:
        security = {}

    try:
        from app.domain.enterprise_platform.api_keys import list_api_keys

        keys_pack = list_api_keys()
        api_keys = list(keys_pack.get("keys") or [])
    except Exception:  # noqa: S110  # best-effort optional path
        pass

    try:
        import asyncio

        from app.domain.enterprise_platform.audit_center import build_audit_center

        try:
            asyncio.get_running_loop()
            running = True
        except RuntimeError:
            running = False
        if not running:
            audit = asyncio.run(build_audit_center(limit=200))
            audits = list(audit.get("timeline") or audits)
    except Exception:  # noqa: S110  # best-effort optional path
        pass

    failed_auth = [
        a
        for a in audits
        if any(
            x in str(a.get("action") or "").lower()
            for x in ("fail", "denied", "invalid", "unauthorized")
        )
        or "fail" in str(a.get("result") or "").lower()
    ][:50]

    permission_violations = [
        a
        for a in audits
        if "permission" in str(a.get("action") or "").lower()
        or "denied" in str(a.get("action") or "").lower()
        or str(a.get("denied")) == "True"
    ][:50]

    # Suspicious: many sessions from distinct IPs (observe threshold)
    ips = {str(s.get("ip")) for s in sessions if s.get("ip")}
    suspicious_logins: list[dict[str, Any]] = []
    if len(ips) > 20:
        suspicious_logins.append(
            {
                "code": "high_ip_diversity",
                "message": f"{len(ips)} distinct IPs in session sample",
                "severity": "warn",
            }
        )
    for a in failed_auth[:10]:
        suspicious_logins.append(
            {
                "code": "failed_auth_event",
                "message": str(a.get("action") or a.get("id") or "failed_auth")[:200],
                "severity": "info",
                "at": a.get("created_at") or a.get("at"),
            }
        )

    # API abuse — high request error patterns from ops metrics
    api_abuse: list[dict[str, Any]] = []
    try:
        from core.di.container import get_container

        collector = getattr(get_container(), "metrics_collector", None)
        if collector is not None:
            snap = collector.snapshot()
            er = float(getattr(snap, "error_rate", 0.0) or 0.0)
            rc = int(getattr(snap, "request_count", 0) or 0)
            if er >= 0.15 and rc >= 50:
                api_abuse.append(
                    {
                        "code": "elevated_error_rate",
                        "message": f"error_rate={er:.3f} requests={rc}",
                        "severity": "warn",
                    }
                )
    except Exception:  # noqa: S110  # best-effort optional path
        pass

    now = utc_iso()
    expired_keys = []
    for k in api_keys:
        exp = k.get("expires_at")
        status = str(k.get("status") or "").lower()
        if status == "expired" or k.get("expired") is True or (exp and str(exp) < now):
            expired_keys.append(k)

    alerts = list(enterprise_alerts)
    alerts.extend(suspicious_logins)
    alerts.extend(api_abuse)

    return {
        "as_of": now,
        "suspicious_logins": suspicious_logins,
        "failed_auth": failed_auth,
        "failed_auth_count": len(failed_auth),
        "api_abuse": api_abuse,
        "permission_violations": permission_violations,
        "permission_violation_count": len(permission_violations),
        "expired_api_keys": expired_keys,
        "expired_api_key_count": len(expired_keys),
        "active_api_keys": len(
            [k for k in api_keys if str(k.get("status") or "active") == "active"]
        ),
        "session_count": len(sessions),
        "distinct_ips": len(ips),
        "alerts": alerts,
        "alert_count": len(alerts),
        "modifies_auth": False,
        "fabricated": False,
        "observe_only": True,
    }


async def build_security_ops_async() -> dict[str, Any]:
    """Async path — preferred under FastAPI."""
    sessions: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    enterprise_alerts: list[dict[str, Any]] = []
    try:
        from app.domain.enterprise_platform.security_center import build_security_center

        security = await build_security_center()
        sessions = list(security.get("sessions") or [])
        enterprise_alerts = list(security.get("security_alerts") or [])
        audits = list(security.get("login_history") or [])
    except Exception:  # noqa: S110  # best-effort optional path
        pass
    try:
        from app.domain.enterprise_platform.audit_center import build_audit_center

        audit = await build_audit_center(limit=200)
        if audit.get("timeline"):
            audits = list(audit["timeline"])
    except Exception:  # noqa: S110  # best-effort optional path
        pass

    # Reuse sync builder internals by temporarily injecting via sync path fields
    pack = build_security_ops()
    # Overlay async-sourced lists when available
    if sessions or audits or enterprise_alerts:
        # Rebuild key slices with async data
        failed_auth = [
            a
            for a in audits
            if any(
                x in str(a.get("action") or "").lower()
                for x in ("fail", "denied", "invalid", "unauthorized")
            )
            or "fail" in str(a.get("result") or "").lower()
        ][:50]
        permission_violations = [
            a
            for a in audits
            if "permission" in str(a.get("action") or "").lower()
            or "denied" in str(a.get("action") or "").lower()
        ][:50]
        ips = {str(s.get("ip")) for s in sessions if s.get("ip")}
        suspicious_logins: list[dict[str, Any]] = list(
            pack.get("suspicious_logins") or []
        )
        if len(ips) > 20:
            suspicious_logins = [
                {
                    "code": "high_ip_diversity",
                    "message": f"{len(ips)} distinct IPs in session sample",
                    "severity": "warn",
                }
            ] + [s for s in suspicious_logins if s.get("code") != "high_ip_diversity"]
        pack.update(
            {
                "failed_auth": failed_auth,
                "failed_auth_count": len(failed_auth),
                "permission_violations": permission_violations,
                "permission_violation_count": len(permission_violations),
                "session_count": len(sessions),
                "distinct_ips": len(ips),
                "suspicious_logins": suspicious_logins,
                "alerts": (
                    list(enterprise_alerts)
                    + suspicious_logins
                    + list(pack.get("api_abuse") or [])
                ),
            }
        )
        pack["alert_count"] = len(pack["alerts"])
    return pack
