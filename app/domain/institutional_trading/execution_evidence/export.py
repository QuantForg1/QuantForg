"""Export execution evidence artifacts under docs/production/execution/."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.institutional_trading.execution_evidence.models import (
    EXECUTION_TIMELINE,
    ExecutionEvidencePackage,
)
from core.logging import get_logger

logger = get_logger(__name__)

EXECUTION_DIR = Path("docs/production/execution")
CERTIFICATE_DIR = Path("docs/production/certificates")
CERTIFICATE_PATH = CERTIFICATE_DIR / "Production_Acceptance_Certificate.md"

LATEST_JSON = "latest_execution.json"
LATEST_MD = "latest_execution.md"
HISTORY_CSV = "execution_history.csv"
HISTORY_JSONL = "execution_history.jsonl"

WAITING_MESSAGE = "Waiting for first eligible production execution."


def _repo_dir(rel: Path, override: Path | None = None) -> Path:
    if override is not None:
        return override
    cwd = Path.cwd() / rel
    if (Path.cwd() / "docs" / "production").exists():
        return cwd
    alt = Path("/workspace") / rel
    return alt if alt.parent.exists() else cwd


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _fmt(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def _markdown_report(package: ExecutionEvidencePackage) -> str:
    lat = package.execution_latency_ms()
    lines = [
        f"# Production Execution Evidence — `{package.validation_id}`",
        "",
        "> Observe-only. Real production execution. Never fabricated.",
        "",
        "## General",
        "",
        f"- **Validation ID:** {package.validation_id}",
        f"- **Signal ID:** {_fmt(package.signal_id)}",
        f"- **Timestamp:** {package.timestamp}",
        f"- **Environment:** {_fmt(package.environment)}",
        f"- **Commit SHA:** {_fmt(package.commit_sha)}",
        f"- **Deployment ID:** {_fmt(package.deployment_id)}",
        "",
        "## AI",
        "",
        f"- **Decision:** {_fmt(package.decision)}",
        f"- **Quality Score:** {_fmt(package.quality_score)}",
        f"- **Confidence:** {_fmt(package.confidence)}",
        f"- **Session:** {_fmt(package.session)}",
        f"- **Symbol:** {_fmt(package.symbol)}",
        f"- **Reasons:** {', '.join(package.reasons) if package.reasons else '—'}",
        "",
        "## Risk",
        "",
        f"- **Risk Score:** {_fmt(package.risk_score)}",
        f"- **RR:** {_fmt(package.rr)}",
        f"- **Position Size:** {_fmt(package.position_size)}",
        f"- **Eligibility Result:** {_fmt(package.eligibility_result)}",
        "",
        "## OMS",
        "",
        f"- **Submit timestamp:** {_fmt(package.oms_submit_timestamp)}",
        f"- **Payload hash:** {_fmt(package.oms_payload_hash)}",
        f"- **Latency (ms):** {_fmt(package.oms_latency_ms)}",
        f"- **Response:** `{json.dumps(package.oms_response, default=str)}`",
        "",
        "## Gateway",
        "",
        f"- **Request ID:** {_fmt(package.gateway_request_id)}",
        f"- **HTTP Status:** {_fmt(package.gateway_http_status)}",
        f"- **order_send latency (ms):** {_fmt(package.order_send_latency_ms)}",
        "",
        "## MT5",
        "",
        f"- **Ticket:** {_fmt(package.mt5_ticket)}",
        f"- **Retcode:** {_fmt(package.mt5_retcode)}",
        f"- **Comment:** {_fmt(package.mt5_comment)}",
        f"- **Fill Price:** {_fmt(package.fill_price)}",
        f"- **Volume:** {_fmt(package.volume)}",
        "",
        "## Broker",
        "",
        f"- **Execution status:** {_fmt(package.broker_execution_status)}",
        f"- **Slippage:** {_fmt(package.slippage)}",
        f"- **Final fill:** {_fmt(package.final_fill)}",
        "",
        "## Trade",
        "",
        f"- **Entry:** {_fmt(package.entry)}",
        f"- **Exit:** {_fmt(package.exit)}",
        f"- **Stop Loss:** {_fmt(package.stop_loss)}",
        f"- **Take Profit:** {_fmt(package.take_profit)}",
        f"- **Duration:** {_fmt(package.duration)}",
        f"- **Gross P/L:** {_fmt(package.gross_pnl)}",
        f"- **Net P/L:** {_fmt(package.net_pnl)}",
        f"- **Swap:** {_fmt(package.swap)}",
        f"- **Commission:** {_fmt(package.commission)}",
        "",
        "## System",
        "",
        f"- **CPU:** {_fmt(package.cpu)}",
        f"- **Memory:** {_fmt(package.memory)}",
        f"- **Gateway latency (ms):** {_fmt(package.system_gateway_latency_ms)}",
        f"- **OMS latency (ms):** {_fmt(package.system_oms_latency_ms)}",
        "",
        "## Execution Timeline",
        "",
        "```",
        "Scheduler",
        "↓",
        "Market",
        "↓",
        "AI",
        "↓",
        "Risk",
        "↓",
        "OMS",
        "↓",
        "Gateway",
        "↓",
        "MT5",
        "↓",
        "Broker",
        "↓",
        "Position Open",
        "↓",
        "Position Close",
        "```",
        "",
        "| Stage | PASS / FAIL | Latency (ms) | Reason |",
        "| --- | --- | --- | --- |",
    ]
    for stage in package.timeline:
        lat_s = (
            f"{stage.latency_ms:.2f}" if stage.latency_ms is not None else "—"
        )
        reason = (stage.reason or "—").replace("|", "/")
        lines.append(
            f"| {stage.stage} | {stage.status} | {lat_s} | {reason} |"
        )
    lines.extend(
        [
            "",
            "## Result",
            "",
            f"- **Final result:** {package.final_result}",
            f"- **Accepted:** {package.accepted}",
            f"- **Execution latency (ms):** {_fmt(lat)}",
            f"- **Certificate eligible:** {package.certificate_eligible}",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _certificate_markdown(package: ExecutionEvidencePackage) -> str:
    lat = package.execution_latency_ms()
    stage_map = {t.stage: t.status for t in package.timeline}

    def gate(name: str) -> str:
        return "PASS" if stage_map.get(name) == "PASS" else stage_map.get(name, "—")

    return "\n".join(
        [
            "# Production Acceptance Certificate",
            "",
            "> Issued only after a complete successful real production execution.",
            "> Observe-only evidence. Never fabricated.",
            "",
            f"- **Commit SHA:** {_fmt(package.commit_sha)}",
            f"- **Deployment ID:** {_fmt(package.deployment_id)}",
            f"- **Validation ID:** {package.validation_id}",
            f"- **Broker Ticket:** {_fmt(package.mt5_ticket)}",
            f"- **Execution latency (ms):** {_fmt(lat)}",
            f"- **OMS:** {gate('OMS')}",
            f"- **Gateway:** {gate('Gateway')}",
            f"- **MT5:** {gate('MT5')}",
            f"- **Broker:** {gate('Broker')}",
            f"- **Generated timestamp:** {_now_iso()}",
            f"- **Symbol:** {_fmt(package.symbol)}",
            f"- **Decision:** {_fmt(package.decision)}",
            f"- **Environment:** {_fmt(package.environment)}",
            "",
            "## Status",
            "",
            "**VERIFIED**",
            "",
        ]
    ) + "\n"


def _history_row(package: ExecutionEvidencePackage) -> dict[str, Any]:
    return {
        "validation_id": package.validation_id,
        "signal_id": package.signal_id or "",
        "timestamp": package.timestamp,
        "environment": package.environment or "",
        "commit_sha": package.commit_sha or "",
        "deployment_id": package.deployment_id or "",
        "decision": package.decision or "",
        "symbol": package.symbol or "",
        "session": package.session or "",
        "quality_score": package.quality_score
        if package.quality_score is not None
        else "",
        "confidence": package.confidence if package.confidence is not None else "",
        "risk_score": package.risk_score if package.risk_score is not None else "",
        "rr": package.rr or "",
        "position_size": package.position_size or "",
        "eligibility_result": package.eligibility_result or "",
        "oms_payload_hash": package.oms_payload_hash or "",
        "oms_latency_ms": package.oms_latency_ms
        if package.oms_latency_ms is not None
        else "",
        "gateway_request_id": package.gateway_request_id or "",
        "gateway_http_status": package.gateway_http_status
        if package.gateway_http_status is not None
        else "",
        "order_send_latency_ms": package.order_send_latency_ms
        if package.order_send_latency_ms is not None
        else "",
        "mt5_ticket": package.mt5_ticket if package.mt5_ticket is not None else "",
        "mt5_retcode": package.mt5_retcode if package.mt5_retcode is not None else "",
        "fill_price": package.fill_price or "",
        "volume": package.volume or "",
        "slippage": package.slippage or "",
        "broker_execution_status": package.broker_execution_status or "",
        "entry": package.entry or "",
        "exit": package.exit or "",
        "stop_loss": package.stop_loss or "",
        "take_profit": package.take_profit or "",
        "gross_pnl": package.gross_pnl or "",
        "net_pnl": package.net_pnl or "",
        "swap": package.swap or "",
        "commission": package.commission or "",
        "final_result": package.final_result,
        "accepted": package.accepted,
        "certificate_eligible": package.certificate_eligible,
        "execution_latency_ms": package.execution_latency_ms()
        if package.execution_latency_ms() is not None
        else "",
    }


def _append_history_csv(out_dir: Path, package: ExecutionEvidencePackage) -> Path:
    csv_path = out_dir / HISTORY_CSV
    row = _history_row(package)
    fieldnames = list(row.keys())
    write_header = not csv_path.exists()
    # Deduplicate by validation_id if already present
    if csv_path.exists():
        try:
            with csv_path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                existing = list(reader)
            if any(r.get("validation_id") == package.validation_id for r in existing):
                # Rewrite latest row for same validation_id
                updated = [
                    r
                    for r in existing
                    if r.get("validation_id") != package.validation_id
                ]
                updated.append({k: str(v) for k, v in row.items()})
                with csv_path.open("w", encoding="utf-8", newline="") as fh:
                    writer = csv.DictWriter(fh, fieldnames=fieldnames)
                    writer.writeheader()
                    for r in updated:
                        writer.writerow({k: r.get(k, "") for k in fieldnames})
                return csv_path
        except Exception:
            logger.exception("execution_evidence_history_dedupe_failed")
    with csv_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    return csv_path


def _append_history_jsonl(out_dir: Path, package: ExecutionEvidencePackage) -> Path:
    path = out_dir / HISTORY_JSONL
    # Rewrite file without duplicate validation_id
    rows: list[dict[str, Any]] = []
    if path.exists():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("validation_id") == package.validation_id:
                    continue
                rows.append(obj)
        except Exception:
            logger.exception("execution_evidence_jsonl_read_failed")
            rows = []
    rows.append(package.to_dict())
    with path.open("w", encoding="utf-8") as fh:
        for obj in rows:
            fh.write(json.dumps(obj, default=str) + "\n")
    return path


def export_waiting_state(*, export_dir: Path | None = None) -> dict[str, str]:
    """Write waiting placeholders when no eligible execution exists."""
    out_dir = _repo_dir(EXECUTION_DIR, export_dir)
    paths: dict[str, str] = {}
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": "NOT_VERIFIED",
            "message": WAITING_MESSAGE,
            "latest": None,
            "observe_only": True,
            "never_fabricated": True,
            "as_of": _now_iso(),
        }
        json_path = out_dir / LATEST_JSON
        md_path = out_dir / LATEST_MD
        # Do not overwrite a real latest_execution with waiting if history exists
        history = out_dir / HISTORY_CSV
        if history.exists() and history.stat().st_size > 0:
            try:
                with history.open("r", encoding="utf-8", newline="") as fh:
                    rows = list(csv.DictReader(fh))
                if rows:
                    return {
                        "json": str(out_dir / LATEST_JSON),
                        "markdown": str(out_dir / LATEST_MD),
                        "csv": str(history),
                        "skipped_waiting": "history_present",
                    }
            except Exception:
                logger.exception("execution_evidence_waiting_history_check_failed")

        json_path.write_text(
            json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
        )
        md_path.write_text(
            "\n".join(
                [
                    "# Production Execution Evidence",
                    "",
                    WAITING_MESSAGE,
                    "",
                    "- **Status:** NOT VERIFIED",
                    f"- **As of:** {payload['as_of']}",
                    "",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        csv_path = out_dir / HISTORY_CSV
        if not csv_path.exists():
            with csv_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "validation_id",
                        "timestamp",
                        "decision",
                        "symbol",
                        "mt5_ticket",
                        "final_result",
                        "accepted",
                        "execution_latency_ms",
                    ],
                )
                writer.writeheader()
        paths = {
            "json": str(json_path),
            "markdown": str(md_path),
            "csv": str(csv_path),
        }
    except Exception:
        logger.exception("execution_evidence_waiting_export_failed")
    return paths


def export_evidence_package(
    package: ExecutionEvidencePackage,
    *,
    export_dir: Path | None = None,
    certificate_dir: Path | None = None,
) -> dict[str, str]:
    """Write latest_execution.md/json, append history CSV, optional certificate."""
    out_dir = _repo_dir(EXECUTION_DIR, export_dir)
    cert_dir = _repo_dir(CERTIFICATE_DIR, certificate_dir)
    paths: dict[str, str] = {}
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": "VERIFIED" if package.certificate_eligible else "CAPTURED",
            "message": None,
            "latest": package.to_dict(),
            "observe_only": True,
            "never_fabricated": True,
            "as_of": _now_iso(),
        }
        json_path = out_dir / LATEST_JSON
        md_path = out_dir / LATEST_MD
        json_path.write_text(
            json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
        )
        md_path.write_text(_markdown_report(package), encoding="utf-8")
        csv_path = _append_history_csv(out_dir, package)
        jsonl_path = _append_history_jsonl(out_dir, package)
        paths = {
            "json": str(json_path),
            "markdown": str(md_path),
            "csv": str(csv_path),
            "jsonl": str(jsonl_path),
        }

        if package.certificate_eligible:
            cert_dir.mkdir(parents=True, exist_ok=True)
            cert_path = cert_dir / "Production_Acceptance_Certificate.md"
            cert_path.write_text(_certificate_markdown(package), encoding="utf-8")
            # Also stamp a dated copy for audit trail
            stamp = package.timestamp.replace(":", "").replace("-", "")[:15]
            vid = package.validation_id
            dated = (
                cert_dir
                / f"Production_Acceptance_Certificate_{stamp}_{vid}.md"
            )
            dated.write_text(_certificate_markdown(package), encoding="utf-8")
            paths["certificate"] = str(cert_path)
            paths["certificate_dated"] = str(dated)

        logger.info(
            "execution_evidence_exported",
            validation_id=package.validation_id,
            ticket=package.mt5_ticket,
            certificate_eligible=package.certificate_eligible,
            paths=paths,
        )
    except Exception:
        logger.exception(
            "execution_evidence_export_failed",
            validation_id=package.validation_id,
        )
    return paths


def load_latest_evidence(*, export_dir: Path | None = None) -> dict[str, Any]:
    out_dir = _repo_dir(EXECUTION_DIR, export_dir)
    path = out_dir / LATEST_JSON
    if not path.exists():
        return {
            "status": "NOT_VERIFIED",
            "message": WAITING_MESSAGE,
            "latest": None,
            "observe_only": True,
            "never_fabricated": True,
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {
            "status": "NOT_VERIFIED",
            "message": WAITING_MESSAGE,
            "latest": None,
        }
    except Exception:
        logger.exception("execution_evidence_latest_read_failed")
        return {
            "status": "NOT_VERIFIED",
            "message": WAITING_MESSAGE,
            "latest": None,
            "observe_only": True,
            "never_fabricated": True,
        }


def certificate_exists(*, certificate_dir: Path | None = None) -> bool:
    cert_dir = _repo_dir(CERTIFICATE_DIR, certificate_dir)
    path = cert_dir / "Production_Acceptance_Certificate.md"
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
        return "VERIFIED" in text and "Broker Ticket" in text
    except Exception:
        return False


def build_acceptance_status(
    *,
    export_dir: Path | None = None,
    certificate_dir: Path | None = None,
) -> dict[str, Any]:
    """NOC Production Acceptance widget payload — never fabricates."""
    latest = load_latest_evidence(export_dir=export_dir)
    pkg = latest.get("latest") if isinstance(latest.get("latest"), dict) else None
    cert_ok = certificate_exists(certificate_dir=certificate_dir)
    eligible = bool(pkg and pkg.get("certificate_eligible"))
    verified = bool(
        (latest.get("status") == "VERIFIED" or eligible) and cert_ok
    )
    if pkg is None:
        return {
            "status": "NOT VERIFIED",
            "verified": False,
            "message": WAITING_MESSAGE,
            "latest_broker_ticket": None,
            "latest_execution": None,
            "latest_latency_ms": None,
            "latest_certificate": None,
            "validation_id": None,
            "observe_only": True,
            "never_fabricated": True,
        }
    lat = None
    trade = pkg.get("trade") if isinstance(pkg.get("trade"), dict) else {}
    gw = pkg.get("gateway") if isinstance(pkg.get("gateway"), dict) else {}
    oms = pkg.get("oms") if isinstance(pkg.get("oms"), dict) else {}
    if gw.get("order_send_latency_ms") is not None:
        lat = gw.get("order_send_latency_ms")
    elif oms.get("latency_ms") is not None:
        lat = oms.get("latency_ms")
    mt5 = pkg.get("mt5") if isinstance(pkg.get("mt5"), dict) else {}
    cert_path = str(CERTIFICATE_PATH) if verified else None
    return {
        "status": "VERIFIED" if verified else "NOT VERIFIED",
        "verified": verified,
        "message": None if pkg else WAITING_MESSAGE,
        "latest_broker_ticket": mt5.get("ticket"),
        "latest_execution": {
            "validation_id": pkg.get("validation_id"),
            "timestamp": pkg.get("timestamp"),
            "decision": (pkg.get("ai") or {}).get("decision")
            if isinstance(pkg.get("ai"), dict)
            else None,
            "symbol": (pkg.get("ai") or {}).get("symbol")
            if isinstance(pkg.get("ai"), dict)
            else pkg.get("symbol"),
            "final_result": pkg.get("final_result"),
            "accepted": pkg.get("accepted"),
            "entry": trade.get("entry") if isinstance(trade, dict) else None,
            "exit": trade.get("exit") if isinstance(trade, dict) else None,
        },
        "latest_latency_ms": lat,
        "latest_certificate": cert_path,
        "validation_id": pkg.get("validation_id"),
        "commit_sha": pkg.get("commit_sha"),
        "deployment_id": pkg.get("deployment_id"),
        "observe_only": True,
        "never_fabricated": True,
        "timeline_stages": list(EXECUTION_TIMELINE),
    }
