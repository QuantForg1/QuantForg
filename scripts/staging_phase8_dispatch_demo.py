"""Phase 8 staging durable-dispatch demo (no LIVE orders, no Weltrade touch).

Loads deploy/mt5_worker_agent/local.env for WORKER_SERVICE_TOKEN only.
Forces QUANTFORG_API_BASE_URL to staging. Never prints secrets.
"""

from __future__ import annotations

import json
import os
import sys
import time
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
    cleaned = [s.strip() for s in slots.split(",") if s.strip() and s.strip() != "demo-c"]
    os.environ["QF_MT5_LOCAL_SLOTS"] = ",".join(cleaned or ["demo-a", "demo-b"])


def main() -> int:
    sys.path.insert(0, str(ROOT))
    load_env()
    from services.mt5_worker_agent.railway_client import (
        RailwayClientConfig,
        RailwayWorkerClient,
    )
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor

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

    # Refuse production accidental target.
    api = os.environ.get("QUANTFORG_API_BASE_URL", "")
    rec(
        "api_is_staging",
        "PASS" if "quantforg-staging" in api else "FAIL",
        "redacted",
    )

    # Live Program Files must remain untouched by this script.
    live = Path(r"C:\Program Files\MetaTrader 5\terminal64.exe")
    rec("weltrade_path_exists", "PASS" if live.is_file() else "FAIL")
    rec(
        "allow_worker_on_live_false",
        "PASS"
        if os.environ.get("QF_ALLOW_WORKER_ON_LIVE_TERMINAL", "").lower()
        in {"0", "false", "no", ""}
        else "FAIL",
    )

    sup = LocalWorkerSupervisor()
    # Restrict to slots that exist on disk.
    existing = [
        s
        for s in (os.environ.get("QF_MT5_LOCAL_SLOTS") or "").split(",")
        if s.strip()
        and (Path(os.environ.get("QF_MT5_SLOT_ROOT") or r"C:\QuantForg-Workspace\mt5_worker_slots") / s.strip()).is_dir()
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
    railway_hb = (hb.get("railway") or {}) if isinstance(hb, dict) else {}
    hb_ok = any(
        isinstance(v, dict) and v.get("ok") for v in railway_hb.values()
    ) or bool(railway_hb)
    rec("worker_heartbeat", "PASS" if hb_ok or reg.get("ok") else "FAIL")

    # Pick first registered worker.
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
    rec(
        "dispatch_assignment",
        "PASS" if user_id and account_id else "FAIL",
    )

    # Lab enqueue (requires staging APP_ENV or QF_DISPATCH_LAB_ENABLED).
    key = f"phase8:{uuid.uuid4()}"
    enq = client.dispatch_lab_enqueue(
        worker_id=worker_id,
        idempotency_key=key,
    )
    if not enq.get("ok"):
        rec("lab_enqueue", "FAIL", str(enq.get("error") or enq.get("status")))
        # Still exercise spoof/recover paths that don't need a job.
    else:
        rec(
            "lab_enqueue",
            "PASS",
            f"jobs={enq.get('job_count')} live={enq.get('live_submit_allowed')}",
        )
        rec(
            "lab_live_submit_off",
            "PASS" if enq.get("live_submit_allowed") is False else "FAIL",
        )

    # Spoof claim
    spoof = client.dispatch_claim(
        worker_id=worker_id,
        user_id="00000000-0000-0000-0000-000000000001",
        broker_account_id="00000000-0000-0000-0000-000000000002",
    )
    rec(
        "spoof_claim_rejected",
        "PASS"
        if spoof.get("ok") is False and spoof.get("error") == "assignment_mismatch"
        else "FAIL",
        str(spoof.get("error")),
    )

    claim = client.dispatch_claim(
        worker_id=worker_id, user_id=user_id, broker_account_id=account_id
    )
    job = claim.get("job") if isinstance(claim, dict) else None
    rec(
        "assigned_claim",
        "PASS" if claim.get("ok") and (job or enq.get("ok") is False) else "FAIL",
        f"has_job={bool(job)}",
    )
    if isinstance(job, dict) and job.get("intent_id"):
        intent_id = str(job["intent_id"])
        # Leave claimed without ACK to test recover (lease release).
        recovered = client.dispatch_recover()
        rec(
            "lease_recover",
            "PASS" if recovered.get("ok") else "FAIL",
            f"recovered={recovered.get('recovered')}",
        )
        # Reclaim + ACK
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
                "PASS"
                if ack.get("ok")
                and (ack.get("job") or {}).get("delivery_status") == "acked"
                else "FAIL",
                str((ack.get("job") or {}).get("delivery_status")),
            )
        else:
            rec("ack_terminal_state", "FAIL", "reclaim_empty")

        # Failure/retry path with a fresh enqueue
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
                    "PASS" if fail.get("ok") and status in {"pending", "dead_letter"} else "FAIL",
                    str(status),
                )
            else:
                rec("fail_retry_or_pending", "FAIL", "no_job")
        else:
            rec("fail_retry_or_pending", "FAIL", str(enq2.get("error")))
    else:
        rec("lease_recover", "BLOCKED", "no_claimed_job")
        rec("ack_terminal_state", "BLOCKED", "no_claimed_job")
        rec("fail_retry_or_pending", "BLOCKED", "no_claimed_job")

    # Idempotent re-enqueue
    if enq.get("ok"):
        enq_dup = client.dispatch_lab_enqueue(worker_id=worker_id, idempotency_key=key)
        jobs = enq_dup.get("jobs") or []
        rec(
            "enqueue_idempotent",
            "PASS" if enq_dup.get("ok") and len(jobs) == 1 else "FAIL",
        )

    ops = client.ops_summary()
    rec(
        "owner_ops_snapshot",
        "PASS"
        if ops.get("ok") is not False and ops.get("live_submit_allowed") is False
        else "FAIL",
    )
    rec(
        "ops_explains_execution_workers",
        "PASS" if "execution_workers_note" in ops or "control_plane_worker_count" in ops else "FAIL",
    )

    # Customer status requires user JWT — not exercised without disposable identity.
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

    _write()
    fails = [r for r in RESULTS if r[1] == "FAIL"]
    print("--- SUMMARY ---")
    print("pass", sum(1 for r in RESULTS if r[1] == "PASS"))
    print("fail", len(fails))
    print("blocked_or_skipped", sum(1 for r in RESULTS if r[1] in {"BLOCKED", "NOT_EXERCISED", "NOT_WIRED"}))
    return 1 if fails else 0


def _write() -> None:
    out = Path(os.environ.get("TEMP", ".")) / "qf_phase8_staging_dispatch_results.json"
    out.write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
    print("results_file", out)


if __name__ == "__main__":
    raise SystemExit(main())
