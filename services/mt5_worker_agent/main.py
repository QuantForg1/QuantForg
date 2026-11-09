"""Entrypoint for the Windows MT5 worker agent (local + future VPS).

Modes:
  idle            — token-gated idle loop (no MT5)
  prepare-slots   — copy portable MT5 installs for configured slots
  start-slots     — start portable terminals (no login)
  status          — print slot + resource status (no secrets)
  supervise       — local supervisor heartbeat loop
  connect-demo    — real MT5 login+verify for one slot (requires env creds)
  railway-ping    — outbound HTTPS health check to Railway/API

Never attaches to the LIVE Program Files terminal by default.
Never enables MULTI_ACCOUNT_LIVE_SUBMIT.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("mt5_worker_agent")


def _token_ok(raw: str | None) -> bool:
    return bool(raw and len(raw.strip()) >= 16)


def cmd_idle() -> int:
    token = os.environ.get("WORKER_SERVICE_TOKEN")
    api = (os.environ.get("QUANTFORG_API_BASE_URL") or "").strip()
    if not _token_ok(token):
        logger.error("WORKER_SERVICE_TOKEN missing or too short — refusing to start")
        return 2
    logger.info(
        "mt5_worker_agent idle api_configured=%s token_len=%s",
        bool(api),
        len(token.strip()) if token else 0,
    )
    while True:
        time.sleep(30)
        logger.info("mt5_worker_agent heartbeat idle=true ready=false")


def cmd_prepare_slots(*, force: bool) -> int:
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor

    sup = LocalWorkerSupervisor()
    result = sup.prepare_all(force=force)
    print(json.dumps(result, indent=2))
    return 0 if all(v.get("ok") for v in result.values()) else 1


def cmd_start_slots() -> int:
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor

    sup = LocalWorkerSupervisor()
    result = sup.start_all_terminals()
    print(json.dumps(result, indent=2))
    return 0 if all(v.get("ok") for v in result.values()) else 1


def cmd_stop_slots() -> int:
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor

    sup = LocalWorkerSupervisor()
    result = sup.stop_all()
    print(json.dumps(result, indent=2))
    return 0


def cmd_status() -> int:
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor
    from services.mt5_worker_agent.resources import (
        host_memory_summary,
        sample_terminal_processes,
    )

    sup = LocalWorkerSupervisor()
    report = {
        "slots": sup.refresh_status(),
        "terminals": [
            {
                "pid": s.pid,
                "exe_path": s.exe_path,
                "working_set_mb": s.working_set_mb,
                "cpu_seconds": s.cpu_seconds,
            }
            for s in sample_terminal_processes()
        ],
        "host_memory": host_memory_summary(),
        "note": "Status only — ready=false until connect-demo succeeds for a slot",
    }
    print(json.dumps(report, indent=2))
    return 0


def cmd_supervise() -> int:
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor

    if not _token_ok(os.environ.get("WORKER_SERVICE_TOKEN")):
        logger.warning(
            "WORKER_SERVICE_TOKEN missing — supervising locally "
            "without Railway heartbeats"
        )
    LocalWorkerSupervisor().run_forever()
    return 0


def cmd_railway_ping() -> int:
    from services.mt5_worker_agent.railway_client import (
        RailwayClientConfig,
        RailwayWorkerClient,
    )

    try:
        client = RailwayWorkerClient(RailwayClientConfig.from_env())
    except ValueError as exc:
        logger.error("railway_config_invalid error=%s", exc)
        return 2
    result = client.health_ping()
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") or result.get("status") == "ok" else 1


def cmd_railway_register() -> int:
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor

    if not _token_ok(os.environ.get("WORKER_SERVICE_TOKEN")):
        logger.error("WORKER_SERVICE_TOKEN missing or too short")
        return 2
    result = LocalWorkerSupervisor().register_with_railway()
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def cmd_railway_heartbeat() -> int:
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor

    if not _token_ok(os.environ.get("WORKER_SERVICE_TOKEN")):
        logger.error("WORKER_SERVICE_TOKEN missing or too short")
        return 2
    sup = LocalWorkerSupervisor()
    reg = sup.register_with_railway()
    if not reg.get("ok"):
        print(json.dumps({"ok": False, "register": reg}, indent=2))
        return 1
    hb = sup.heartbeat_once()
    assign = sup.fetch_assignments()
    print(
        json.dumps(
            {"ok": True, "register": reg, "heartbeat": hb, "assignments": assign},
            indent=2,
        )
    )
    return 0


def cmd_connect_demo(slot_id: str) -> int:
    """Real MT5 authenticate+verify for one portable slot.

    Requires:
      QF_DEMO_LOGIN / QF_DEMO_PASSWORD / QF_DEMO_SERVER
    Never invents success without MetaTrader5 login.
    """
    from services.mt5_worker_agent.local_supervisor import LocalWorkerSupervisor
    from services.mt5_worker_agent.mt5_session import authenticate_and_verify
    from services.mt5_worker_agent.slot_manager import (
        prepare_portable_slot,
        start_slot_terminal,
    )

    login_raw = (os.environ.get("QF_DEMO_LOGIN") or "").strip()
    password = os.environ.get("QF_DEMO_PASSWORD") or ""
    server = (os.environ.get("QF_DEMO_SERVER") or "").strip()
    if not login_raw or not password.strip() or not server:
        logger.error(
            "Missing QF_DEMO_LOGIN / QF_DEMO_PASSWORD / QF_DEMO_SERVER — "
            "cannot claim a real authenticated session"
        )
        print(
            json.dumps(
                {
                    "ok": False,
                    "authenticated_demo_accounts": 0,
                    "error": "demo_credentials_not_provided",
                    "required_env": [
                        "QF_DEMO_LOGIN",
                        "QF_DEMO_PASSWORD",
                        "QF_DEMO_SERVER",
                    ],
                },
                indent=2,
            )
        )
        return 2

    prepare_portable_slot(slot_id)
    start_slot_terminal(slot_id)
    # Give the portable terminal a moment to boot IPC.
    time.sleep(5)
    exe = LocalWorkerSupervisor().terminal_exe_for(slot_id)
    result = authenticate_and_verify(
        terminal_exe=exe,
        login=int(login_raw),
        password=password,
        server=server,
    )
    payload = {
        "ok": result.ok,
        "trade_allowed": result.trade_allowed,
        "login": result.login,
        "server": result.server,
        "name": result.name,
        "balance": result.balance,
        "equity": result.equity,
        "currency": result.currency,
        "error": result.error,
        "slot_id": slot_id,
        "note": "Password not included. Mock sessions are not used here.",
    }
    print(json.dumps(payload, indent=2))
    return 0 if result.ok and result.trade_allowed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mt5_worker_agent")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("idle")
    p_prep = sub.add_parser("prepare-slots")
    p_prep.add_argument("--force", action="store_true")
    sub.add_parser("start-slots")
    sub.add_parser("stop-slots")
    sub.add_parser("status")
    sub.add_parser("supervise")
    sub.add_parser("railway-ping")
    sub.add_parser("railway-register")
    sub.add_parser("railway-heartbeat")
    p_conn = sub.add_parser("connect-demo")
    p_conn.add_argument("--slot", default="demo-a")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["idle"]
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "idle"
    if command == "idle":
        return cmd_idle()
    if command == "prepare-slots":
        return cmd_prepare_slots(force=bool(args.force))
    if command == "start-slots":
        return cmd_start_slots()
    if command == "stop-slots":
        return cmd_stop_slots()
    if command == "status":
        return cmd_status()
    if command == "supervise":
        return cmd_supervise()
    if command == "railway-ping":
        return cmd_railway_ping()
    if command == "railway-register":
        return cmd_railway_register()
    if command == "railway-heartbeat":
        return cmd_railway_heartbeat()
    if command == "connect-demo":
        return cmd_connect_demo(str(args.slot))
    parser.error(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
