"""Phase 8 staging durable-dispatch demo (no LIVE orders, no Weltrade touch).

Loads deploy/mt5_worker_agent/local.env for WORKER_SERVICE_TOKEN only.
Forces QUANTFORG_API_BASE_URL to staging. Never prints secrets.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "deploy" / "mt5_worker_agent" / "local.env"
STAGING_API = "https://quantforg-staging.up.railway.app"
RESULTS: list[tuple[str, str, str]] = []


def rec(name: str, status: str, detail: str = "") -> None:
    RESULTS.append((name, status, detail))
    print(f"{status}: {name}" + (f" | {detail}" if detail else ""))


def load_env() -> None:
    if not ENV_PATH.is_file():
        raise SystemExit(f"missing {ENV_PATH}")
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        # Never overwrite an explicitly provided staging URL with production.
        if key == "QUANTFORG_API_BASE_URL":
            continue
        os.environ.setdefault(key, value.strip())
    os.environ["QUANTFORG_API_BASE_URL"] = STAGING_API
    os.environ["QF_ALLOW_WORKER_ON_LIVE_TERMINAL"] = "false"
    # Avoid missing demo-c during register in this proof.
    slots = os.environ.get("QF_MT5_LOCAL_SLOTS") or "demo-a,demo-b"
    cleaned = [
        s.strip() for s in slots.split(",") if s.strip() and s.strip() != "demo-c"
    ]
    os.environ["QF_MT5_LOCAL_SLOTS"] = ",".join(cleaned or ["demo-a", "demo-b"])


def _heartbeat_ok(hb: object) -> bool:
    """Require an explicit successful Railway heartbeat — never registration."""
    if not isinstance(hb, dict):
        return False
    railway_hb = hb.get("railway")
    if not isinstance(railway_hb, dict) or not railway_hb:
        return False
    return any(isinstance(v, dict) and v.get("ok") is True for v in railway_hb.values())


def _assert_no_secrets(payload: object) -> bool:
    blob = json.dumps(payload, default=str).lower()
    banned = ("password", "service_token", "bearer ", "qf_demo_")
    return not any(b in blob for b in banned)


def main() -> int:
    sys.path.insert(0, str(ROOT))
    load_env()
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor
    from services.mt5_worker_agent.railway_client import (
        RailwayClientConfig,
        RailwayWorkerClient,
    )

    try:
        client = RailwayWorkerClient(RailwayClientConfig.from_env())
    except ValueError as exc:
        rec("staging_client_config", "FAIL", type(exc).__name__)
        return 2

    ping = client.health_ping()
    rec(
        "staging_health",
        "PASS" if ping.get("status") == "ok" or ping.get("ok") else "FAIL",
        f"keys={sorted(ping.keys())[:6]}",
    )

    api = os.environ.get("QUANTFORG_API_BASE_URL", "")
    rec(
        "api_is_staging",
        "PASS" if "quantforg-staging" in api else "FAIL",
        "redacted",
    )

    live = Path(r"C:\Program Files\MetaTrader 5\terminal64.exe")
    rec("weltrade_path_exists", "PASS" if live.is_file() else "FAIL")
    rec(
        "allow_worker_on_live_false",
        (
            "PASS"
            if os.environ.get("QF_ALLOW_WORKER_ON_LIVE_TERMINAL", "").lower()
            in {"0", "false", "no", ""}
            else "FAIL"
        ),
    )

    sup = LocalWorkerSupervisor()
    existing = [
        s
        for s in (os.environ.get("QF_MT5_LOCAL_SLOTS") or "").split(",")
        if s.strip()
        and (
            Path(
                os.environ.get("QF_MT5_SLOT_ROOT")
                or r"C:\QuantForg-Workspace\mt5_worker_slots"
            )
            / s.strip()
        ).is_dir()
    ]
    if existing:
        sup.slot_ids = existing
        for sid in existing:
            if sid not in sup.states:
                from services.mt5_worker_agent.local_supervisor import SlotRuntimeState

                sup.states[sid] = SlotRuntimeState(slot_id=sid)

    reg = sup.register_with_railway()
    rec("worker_register", "PASS" if reg.get("ok") else "FAIL")

    hb = sup.heartbeat_once()
    rec(
        "worker_heartbeat",
        "PASS" if _heartbeat_ok(hb) else "FAIL",
        "independent_of_register",
    )

    worker_id = ""
    for _slot, info in (reg.get("slots") or {}).items():
        if isinstance(info, dict) and info.get("worker_id"):
            worker_id = str(info["worker_id"])
            break
    if not worker_id:
        rec("worker_identity", "FAIL", "no_worker_id")
        _write()
        return 1
    rec("worker_identity", "PASS")

    assign = client.get_assignment(worker_id=worker_id)
    assignment = assign.get("assignment") if isinstance(assign, dict) else {}
    user_id = str((assignment or {}).get("user_id") or "")
    account_id = str((assignment or {}).get("broker_account_id") or "")
    rec("dispatch_assignment", "PASS" if user_id and account_id else "FAIL")
    rec(
        "tokens_redacted",
        "PASS" if _assert_no_secrets(assign) else "FAIL",
    )

    # Registration alone must not unlock enqueue — attest after heartbeat.
    attest = client.lab_attest_assignment(worker_id=worker_id)
    rec(
        "lab_assignment_attested",
        "PASS" if attest.get("ok") else "FAIL",
        str(attest.get("error") or attest.get("status") or ""),
    )

    key = f"phase8:{uuid.uuid4()}"
    enq = client.dispatch_lab_enqueue(worker_id=worker_id, idempotency_key=key)
    enq_status = enq.get("status")
    missing_lab = enq_status == 404 or (
        enq.get("ok") is False
        and enq.get("error") == "http_error"
        and enq_status == 404
    )
    if missing_lab:
        rec("lab_enqueue", "FAIL", "lab_endpoint_missing_404")
        # Fail-closed: do not mark lifecycle steps as passed without a job.
        for name in (
            "assigned_claim",
            "lease_recover",
            "ack_terminal_state",
            "fail_retry_or_pending",
            "enqueue_idempotent",
        ):
            rec(name, "FAIL", "lab_enqueue_unavailable")
        _security_only(client, worker_id)
        _tail(client)
        _write()
        return 1

    if not enq.get("ok"):
        rec("lab_enqueue", "FAIL", str(enq.get("error") or enq_status))
        for name in (
            "assigned_claim",
            "lease_recover",
            "ack_terminal_state",
            "fail_retry_or_pending",
            "enqueue_idempotent",
        ):
            rec(name, "FAIL", "lab_enqueue_failed")
        _security_only(client, worker_id)
        _tail(client)
        _write()
        return 1

    rec(
        "lab_enqueue",
        "PASS",
        f"jobs={enq.get('job_count')} live={enq.get('live_submit_allowed')}",
    )
    rec(
        "lab_live_submit_off",
        "PASS" if enq.get("live_submit_allowed") is False else "FAIL",
    )
    rec(
        "tokens_redacted_enqueue",
        "PASS" if _assert_no_secrets(enq) else "FAIL",
    )

    _security_only(client, worker_id)

    claim = client.dispatch_claim(
        worker_id=worker_id, user_id=user_id, broker_account_id=account_id
    )
    job = claim.get("job") if isinstance(claim, dict) else None
    claim_ok = claim.get("ok") and isinstance(job, dict) and bool(job.get("intent_id"))
    rec("assigned_claim", "PASS" if claim_ok else "FAIL", f"has_job={bool(job)}")
    if not (isinstance(job, dict) and job.get("intent_id")):
        for name in ("lease_recover", "ack_terminal_state", "fail_retry_or_pending"):
            rec(name, "FAIL", "no_claimed_job")
        _idempotency(client, worker_id, key, enq_ok=True)
        _tail(client)
        _write()
        return 1 if any(r[1] == "FAIL" for r in RESULTS) else 0

    intent_id = str(job["intent_id"])
    recovered = client.dispatch_recover()
    recover_ok = recovered.get("ok") and int(recovered.get("recovered") or 0) >= 1
    rec(
        "lease_recover",
        "PASS" if recover_ok else "FAIL",
        f"recovered={recovered.get('recovered')}",
    )

    claim2 = client.dispatch_claim(
        worker_id=worker_id, user_id=user_id, broker_account_id=account_id
    )
    job2 = claim2.get("job") if isinstance(claim2, dict) else None
    if isinstance(job2, dict) and job2.get("intent_id"):
        intent_id = str(job2["intent_id"])
        ack = client.dispatch_ack(
            worker_id=worker_id,
            intent_id=intent_id,
            detail="phase8_staging_ack",
        )
        rec(
            "ack_terminal_state",
            (
                "PASS"
                if ack.get("ok")
                and (ack.get("job") or {}).get("delivery_status") == "acked"
                else "FAIL"
            ),
            str((ack.get("job") or {}).get("delivery_status")),
        )
    else:
        rec("ack_terminal_state", "FAIL", "reclaim_empty")

    key2 = f"phase8-fail:{uuid.uuid4()}"
    enq2 = client.dispatch_lab_enqueue(worker_id=worker_id, idempotency_key=key2)
    if enq2.get("ok"):
        c3 = client.dispatch_claim(
            worker_id=worker_id, user_id=user_id, broker_account_id=account_id
        )
        j3 = c3.get("job") if isinstance(c3, dict) else None
        if isinstance(j3, dict) and j3.get("intent_id"):
            fail = client.dispatch_fail(
                worker_id=worker_id,
                intent_id=str(j3["intent_id"]),
                reason="phase8_forced_fail",
            )
            status = (fail.get("job") or {}).get("delivery_status")
            rec(
                "fail_retry_or_pending",
                (
                    "PASS"
                    if fail.get("ok") and status in {"pending", "dead_letter"}
                    else "FAIL"
                ),
                str(status),
            )
        else:
            rec("fail_retry_or_pending", "FAIL", "no_job")
    else:
        rec("fail_retry_or_pending", "FAIL", str(enq2.get("error")))

    _idempotency(client, worker_id, key, enq_ok=True)
    _tail(client)
    _write()
    fails = [r for r in RESULTS if r[1] == "FAIL"]
    print("--- SUMMARY ---")
    print("pass", sum(1 for r in RESULTS if r[1] == "PASS"))
    print("fail", len(fails))
    print(
        "blocked_or_skipped",
        sum(1 for r in RESULTS if r[1] in {"BLOCKED", "NOT_EXERCISED", "NOT_WIRED"}),
    )
    return 1 if fails else 0


def _security_only(client: object, worker_id: str) -> None:
    spoof = client.dispatch_claim(  # type: ignore[attr-defined]
        worker_id=worker_id,
        user_id="00000000-0000-0000-0000-000000000001",
        broker_account_id="00000000-0000-0000-0000-000000000002",
    )
    rec(
        "spoof_claim_rejected",
        (
            "PASS"
            if spoof.get("ok") is False and spoof.get("error") == "assignment_mismatch"
            else "FAIL"
        ),
        str(spoof.get("error")),
    )


def _idempotency(client: object, worker_id: str, key: str, *, enq_ok: bool) -> None:
    if not enq_ok:
        rec("enqueue_idempotent", "FAIL", "lab_enqueue_unavailable")
        return
    enq_dup = client.dispatch_lab_enqueue(  # type: ignore[attr-defined]
        worker_id=worker_id, idempotency_key=key
    )
    jobs = enq_dup.get("jobs") or []
    rec(
        "enqueue_idempotent",
        "PASS" if enq_dup.get("ok") and len(jobs) == 1 else "FAIL",
    )


def _tail(client: object) -> None:
    ops = client.ops_summary()  # type: ignore[attr-defined]
    rec(
        "owner_ops_snapshot",
        (
            "PASS"
            if ops.get("ok") is not False and ops.get("live_submit_allowed") is False
            else "FAIL"
        ),
    )
    rec(
        "ops_explains_execution_workers",
        (
            "PASS"
            if "execution_workers_note" in ops or "control_plane_worker_count" in ops
            else "FAIL"
        ),
    )
    rec(
        "customer_dispatch_status",
        "NOT_EXERCISED",
        "requires_staging_user_session",
    )
    rec(
        "demo_mt5_login",
        "NOT_EXERCISED",
        "QF_DEMO_* credentials absent",
    )
    rec(
        "ite_integration",
        "NOT_WIRED",
        "await_demo_auth_and_owner_flag",
    )


def _write() -> None:
    out = Path(os.environ.get("TEMP", ".")) / "qf_phase8_staging_dispatch_results.json"
    out.write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
    print("results_file", out)


if __name__ == "__main__":
    raise SystemExit(main())
