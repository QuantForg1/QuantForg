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
_DASH = "—"


def _or_dash(val: Any) -> Any:
    return val if val is not None else _DASH


def _repo_export_dir(base: Path | None = None) -> Path:
    if base is not None:
        return base
    # Prefer repo-relative path from CWD; fall back to /workspace if present.
    cwd = Path.cwd() / "docs" / "production" / "validation"
    if (Path.cwd() / "docs" / "production").exists():
        return cwd
    alt = Path("/workspace/docs/production/validation")
    return alt if alt.parent.exists() else cwd


def _markdown_report(attempt: ValidationAttempt, summary: dict[str, Any]) -> str:
    lines = [
        f"# Production Validation Report — `{attempt.validation_id}`",
        "",
        "> Observability only. No fabricated trades. Real production events.",
        "",
        f"- **Timestamp:** {attempt.timestamp}",
        f"- **Symbol:** {attempt.symbol or _DASH}",
        f"- **Session:** {attempt.market_session or _DASH}",
        f"- **Execution mode:** {attempt.execution_mode or _DASH}",
        f"- **Signal ID:** {attempt.signal_id or _DASH}",
        f"- **AI action:** {attempt.ai_action or _DASH}",
        f"- **AI confidence:** {_or_dash(attempt.ai_confidence)}",
        f"- **Quality score:** {_or_dash(attempt.quality_score)}",
        f"- **Confluence:** {_or_dash(attempt.confluence)}",
        f"- **MTF alignment:** {_or_dash(attempt.mtf_alignment)}",
        f"- **Risk score:** {_or_dash(attempt.risk_score)}",
        f"- **Expected RR:** {attempt.expected_rr or _DASH}",
        f"- **Spread:** {attempt.spread or _DASH}",
        f"- **ATR:** {attempt.atr or _DASH}",
        "",
        "## Pipeline Summary",
        "",
        "| Stage | Status | Latency (ms) | Reason |",
        "| --- | --- | --- | --- |",
    ]
    for stage in PIPELINE_ORDER:
        rec = attempt.stages.get(stage.value)
        if rec is None:
            lines.append(f"| {stage.value} | PENDING | {_DASH} | {_DASH} |")
        else:
            lat = f"{rec.latency_ms:.2f}" if rec.latency_ms is not None else _DASH
            reason = (rec.reason or _DASH).replace("|", "/")
            lines.append(f"| {stage.value} | {rec.status.value} | {lat} | {reason} |")
    exec_latency_ms = _or_dash(summary.get("execution_latency_ms"))
    lines.extend(
        [
            "",
            "## Acceptance",
            "",
            f"- **Final result:** {attempt.final_result}",
            f"- **Accepted:** {attempt.accepted}",
            f"- **Broker ticket:** {summary.get('broker_ticket') or _DASH}",
            f"- **Execution latency (ms):** {exec_latency_ms}",
            f"- **First blocker:** {attempt.first_blocker or _DASH}",
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
                f"- **Latency (ms):** {_or_dash(attempt.oms.latency_ms)}",
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
        gw_latency_ms = _or_dash(attempt.gateway.gateway_latency_ms)
        order_send_latency_ms = _or_dash(attempt.gateway.order_send_latency_ms)
        lines.extend(
            [
                "## Gateway",
                "",
                f"- **HTTP code:** {_or_dash(attempt.gateway.http_code)}",
                f"- **Gateway latency (ms):** {gw_latency_ms}",
                f"- **order_send latency (ms):** {order_send_latency_ms}",
                "",
            ]
        )
    if attempt.mt5:
        lines.extend(
            [
                "## MT5",
                "",
                f"- **Ticket:** {_or_dash(attempt.mt5.ticket)}",
                f"- **Retcode:** {_or_dash(attempt.mt5.retcode)}",
                f"- **Comment:** {attempt.mt5.comment or _DASH}",
                f"- **Fill price:** {attempt.mt5.fill_price or _DASH}",
                f"- **Slippage:** {attempt.mt5.slippage or _DASH}",
                f"- **Execution time (ms):** {_or_dash(attempt.mt5.execution_time_ms)}",
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
                "quality_score": (
                    attempt.quality_score if attempt.quality_score is not None else ""
                ),
                "stage": stage.value,
                "status": rec.status.value if rec else "PENDING",
                "stage_timestamp": rec.timestamp if rec else "",
                "latency_ms": (
                    rec.latency_ms if rec and rec.latency_ms is not None else ""
                ),
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
        stem = (
            f"{attempt.timestamp.replace(':', '').replace('-', '')}_"
            f"{attempt.validation_id}"
        )
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
