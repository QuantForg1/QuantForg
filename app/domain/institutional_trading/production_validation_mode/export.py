"""Export validation reports to docs/production/validation/ (JSON, Markdown, CSV)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from app.domain.institutional_trading.production_validation_mode.models import (
    PIPELINE_ORDER,
    ValidationAttempt,
)
from app.domain.institutional_trading.production_validation_mode.recorder import (
    ProductionValidationRecorder,
)
from core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_EXPORT_DIR = Path("docs/production/validation")


def _repo_export_dir(base: Path | None = None) -> Path:
    if base is not None:
        return base
    # Prefer repo-relative path from CWD; fall back to /workspace if present.
    cwd = Path.cwd() / "docs" / "production" / "validation"
    if (Path.cwd() / "docs" / "production").exists():
        return cwd
    alt = Path("/workspace/docs/production/validation")
    return alt if alt.parent.exists() else cwd


def _markdown_report(
    attempt: ValidationAttempt, summary: dict[str, Any]
) -> str:
    lines = [
        f"# Production Validation Report — `{attempt.validation_id}`",
        "",
        "> Observability only. No fabricated trades. Real production events.",
        "",
        f"- **Timestamp:** {attempt.timestamp}",
        f"- **Symbol:** {attempt.symbol or '—'}",
        f"- **Session:** {attempt.market_session or '—'}",
        f"- **Execution mode:** {attempt.execution_mode or '—'}",
        f"- **Signal ID:** {attempt.signal_id or '—'}",
        f"- **AI action:** {attempt.ai_action or '—'}",
        f"- **AI confidence:** {attempt.ai_confidence if attempt.ai_confidence is not None else '—'}",
        f"- **Quality score:** {attempt.quality_score if attempt.quality_score is not None else '—'}",
        f"- **Confluence:** {attempt.confluence if attempt.confluence is not None else '—'}",
        f"- **MTF alignment:** {attempt.mtf_alignment if attempt.mtf_alignment is not None else '—'}",
        f"- **Risk score:** {attempt.risk_score if attempt.risk_score is not None else '—'}",
        f"- **Expected RR:** {attempt.expected_rr or '—'}",
        f"- **Spread:** {attempt.spread or '—'}",
        f"- **ATR:** {attempt.atr or '—'}",
        "",
        "## Pipeline Summary",
        "",
        "| Stage | Status | Latency (ms) | Reason |",
        "| --- | --- | --- | --- |",
    ]
    for stage in PIPELINE_ORDER:
        rec = attempt.stages.get(stage.value)
        if rec is None:
            lines.append(f"| {stage.value} | PENDING | — | — |")
        else:
            lat = (
                f"{rec.latency_ms:.2f}"
                if rec.latency_ms is not None
                else "—"
            )
            reason = (rec.reason or "—").replace("|", "/")
            lines.append(
                f"| {stage.value} | {rec.status.value} | {lat} | {reason} |"
            )
    lines.extend(
        [
            "",
            "## Acceptance",
            "",
            f"- **Final result:** {attempt.final_result}",
            f"- **Accepted:** {attempt.accepted}",
            f"- **Broker ticket:** {summary.get('broker_ticket') or '—'}",
            f"- **Execution latency (ms):** {summary.get('execution_latency_ms') if summary.get('execution_latency_ms') is not None else '—'}",
            f"- **First blocker:** {attempt.first_blocker or '—'}",
            "",
        ]
    )
    if attempt.no_trade_reasons:
        lines.append("## NO_TRADE Reasons (individual)")
        lines.append("")
        for r in attempt.no_trade_reasons:
            lines.append(f"- {r}")
        lines.append("")
    if attempt.oms:
        lines.extend(
            [
                "## OMS",
                "",
                f"- **Latency (ms):** {attempt.oms.latency_ms if attempt.oms.latency_ms is not None else '—'}",
                f"- **Retry count:** {attempt.oms.retry_count}",
                "",
                "```json",
                json.dumps(
                    {
                        "payload": attempt.oms.payload,
                        "response": attempt.oms.response,
                    },
                    indent=2,
                    default=str,
                ),
                "```",
                "",
            ]
        )
    if attempt.gateway:
        lines.extend(
            [
                "## Gateway",
                "",
                f"- **HTTP code:** {attempt.gateway.http_code if attempt.gateway.http_code is not None else '—'}",
                f"- **Gateway latency (ms):** {attempt.gateway.gateway_latency_ms if attempt.gateway.gateway_latency_ms is not None else '—'}",
                f"- **order_send latency (ms):** {attempt.gateway.order_send_latency_ms if attempt.gateway.order_send_latency_ms is not None else '—'}",
                "",
            ]
        )
    if attempt.mt5:
        lines.extend(
            [
                "## MT5",
                "",
                f"- **Ticket:** {attempt.mt5.ticket if attempt.mt5.ticket is not None else '—'}",
                f"- **Retcode:** {attempt.mt5.retcode if attempt.mt5.retcode is not None else '—'}",
                f"- **Comment:** {attempt.mt5.comment or '—'}",
                f"- **Fill price:** {attempt.mt5.fill_price or '—'}",
                f"- **Slippage:** {attempt.mt5.slippage or '—'}",
                f"- **Execution time (ms):** {attempt.mt5.execution_time_ms if attempt.mt5.execution_time_ms is not None else '—'}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def _csv_rows(attempt: ValidationAttempt) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage in PIPELINE_ORDER:
        rec = attempt.stages.get(stage.value)
        rows.append(
            {
                "validation_id": attempt.validation_id,
                "timestamp": attempt.timestamp,
                "symbol": attempt.symbol,
                "market_session": attempt.market_session,
                "ai_action": attempt.ai_action or "",
                "quality_score": attempt.quality_score
                if attempt.quality_score is not None
                else "",
                "stage": stage.value,
                "status": rec.status.value if rec else "PENDING",
                "stage_timestamp": rec.timestamp if rec else "",
                "latency_ms": rec.latency_ms if rec and rec.latency_ms is not None else "",
                "reason": rec.reason if rec else "",
                "first_blocker": attempt.first_blocker or "",
                "final_result": attempt.final_result,
                "accepted": attempt.accepted,
                "ticket": attempt.mt5.ticket if attempt.mt5 else "",
                "no_trade_reasons": " | ".join(attempt.no_trade_reasons),
            }
        )
    return rows


def export_validation_report(
    attempt: ValidationAttempt,
    *,
    recorder: ProductionValidationRecorder | None = None,
    export_dir: Path | None = None,
) -> dict[str, str]:
    """Write JSON + Markdown + CSV under docs/production/validation/."""
    out_dir = _repo_export_dir(export_dir)
    paths: dict[str, str] = {}
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        summary = (
            recorder.report_summary(attempt)
            if recorder is not None
            else {
                "validation_id": attempt.validation_id,
                "final_result": attempt.final_result,
                "accepted": attempt.accepted,
                "first_blocker": attempt.first_blocker,
                "broker_ticket": attempt.mt5.ticket if attempt.mt5 else None,
                "execution_latency_ms": None,
                "pipeline_summary": [],
                "ai_action": attempt.ai_action,
                "no_trade_reasons": list(attempt.no_trade_reasons),
            }
        )
        payload = {
            "report": attempt.to_dict(),
            "summary": summary,
            "observe_only": True,
        }
        stem = f"{attempt.timestamp.replace(':', '').replace('-', '')}_{attempt.validation_id}"
        # Keep filename filesystem-safe
        stem = stem.replace("/", "_")[:120]

        json_path = out_dir / f"{stem}.json"
        md_path = out_dir / f"{stem}.md"
        csv_path = out_dir / f"{stem}.csv"

        json_path.write_text(
            json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
        )
        md_path.write_text(_markdown_report(attempt, summary), encoding="utf-8")

        rows = _csv_rows(attempt)
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=list(rows[0].keys()) if rows else ["validation_id"],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        paths = {
            "json": str(json_path),
            "markdown": str(md_path),
            "csv": str(csv_path),
        }
        attempt.export_paths = dict(paths)
        # Latest pointer files for ops convenience
        (out_dir / "LATEST.json").write_text(
            json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
        )
        (out_dir / "LATEST.md").write_text(
            _markdown_report(attempt, summary), encoding="utf-8"
        )
        logger.info(
            "production_validation_exported",
            validation_id=attempt.validation_id,
            paths=paths,
            accepted=attempt.accepted,
            final_result=attempt.final_result,
        )
    except Exception:
        logger.exception(
            "production_validation_export_failed",
            validation_id=attempt.validation_id,
        )
    return paths
