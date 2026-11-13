"""Sanitized credential checker report — never asserts secret values."""

from __future__ import annotations

import json

from services.mt5_worker_agent.check_broker_credentials import (
    build_credential_status_rows,
    main,
)

_MIDS = (
    "WELTRADE",
    "XM",
    "EXNESS",
    "HFM",
    "JUSTMARKETS",
    "IC_MARKETS",
    "PEPPERSTONE",
    "FP_MARKETS",
)


def _clear_all(monkeypatch) -> None:
    for slug_mid in _MIDS:
        for env_tag in ("DEMO", "LIVE"):
            for suffix in ("LOGIN", "PASSWORD", "SERVER"):
                monkeypatch.delenv(f"QF_{env_tag}_{slug_mid}_{suffix}", raising=False)
    for generic in ("QF_DEMO_LOGIN", "QF_DEMO_PASSWORD", "QF_DEMO_SERVER"):
        monkeypatch.delenv(generic, raising=False)


def test_build_rows_include_all_eight_brokers_and_envs(monkeypatch) -> None:
    _clear_all(monkeypatch)
    rows = build_credential_status_rows()
    assert len(rows) == 16  # 8 brokers x demo/live
    ordered = []
    for r in rows:
        if r["env"] == "demo":
            ordered.append(r["broker"])
    assert ordered == [
        "weltrade",
        "xm",
        "exness",
        "hfm",
        "justmarkets",
        "ic-markets",
        "pepperstone",
        "fp-markets",
    ]
    assert all(r["status"] == "BLOCKED_MISSING_CREDENTIALS" for r in rows)
    jm_live = next(
        r for r in rows if r["broker"] == "justmarkets" and r["env"] == "live"
    )
    assert jm_live["missing_keys"] == [
        "QF_LIVE_JUSTMARKETS_LOGIN",
        "QF_LIVE_JUSTMARKETS_PASSWORD",
        "QF_LIVE_JUSTMARKETS_SERVER",
    ]


def test_main_exit_code_blocked(monkeypatch, capsys) -> None:
    _clear_all(monkeypatch)
    code = main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert code == 1
    assert data["ok"] is True
    assert data["blocked"] == 16
    assert "QF_LIVE_JUSTMARKETS_PASSWORD=" not in captured.out


def test_justmarkets_ready_sanitized(monkeypatch, capsys) -> None:
    _clear_all(monkeypatch)
    monkeypatch.setenv("QF_LIVE_JUSTMARKETS_LOGIN", "7788")
    monkeypatch.setenv("QF_LIVE_JUSTMARKETS_PASSWORD", "do-not-print-this-secret")
    monkeypatch.setenv("QF_LIVE_JUSTMARKETS_SERVER", "JustMarkets-Live2")
    code = main()
    out = capsys.readouterr().out
    assert "do-not-print-this-secret" not in out
    assert "7788" not in out
    data = json.loads(out)
    jm_live = next(
        r for r in data["rows"] if r["broker"] == "justmarkets" and r["env"] == "live"
    )
    assert jm_live["status"] == "READY_TO_VERIFY"
    assert jm_live["login_set"] is True
    assert jm_live["password_set"] is True
    assert jm_live["server_set"] is True
    assert code == 1  # other brokers still blocked
