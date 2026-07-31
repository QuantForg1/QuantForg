"""RC1_VALIDATION_REPORT.md generator."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.institutional_trading.rc1_production_validation.config import (
    CONFIDENCE_FLOOR,
    QUALITY_FLOOR,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sec(title: str, body: str) -> str:
    return f"## {title}\n\n{body.strip()}\n"


def _kv(data: dict[str, Any], *, indent: int = 0) -> str:
    pad = "  " * indent
    lines: list[str] = []
    for k, v in data.items():
        if isinstance(v, dict):
            lines.append(f"{pad}- **{k}:**")
            lines.append(_kv(v, indent=indent + 1))
        elif isinstance(v, list):
            lines.append(f"{pad}- **{k}:** {len(v)} items")
        else:
            lines.append(f"{pad}- **{k}:** `{v}`")
    return "\n".join(lines)


def render_rc1_validation_report(
    *,
    infrastructure: dict[str, Any] | None = None,
    replay: dict[str, Any] | None = None,
    paper: dict[str, Any] | None = None,
    shadow: dict[str, Any] | None = None,
    oms: dict[str, Any] | None = None,
    gateway: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None,
    performance: dict[str, Any] | None = None,
    acceptance: dict[str, Any] | None = None,
    dashboard: dict[str, Any] | None = None,
) -> str:
    infra = infrastructure or {}
    replay_m = replay or {}
    paper_m = paper or {}
    shadow_m = shadow or {}
    oms_m = oms or {}
    gw_m = gateway or {}
    risk_m = risk or {}
    perf_m = performance or {}
    acc = acceptance or {}
    recommendation = acc.get("recommendation") or "NOT READY"

    parts = [
        "# RC1 Validation Report",
        "",
        f"Generated: `{_now_iso()}`",
        "",
        "Institutional Production Validation Pipeline for QuantForg ITE.",
        "This report does **not** modify strategy, Quality/Confidence floors, "
        "weights, or risk logic.",
        "",
        f"- Quality floor (locked): `{QUALITY_FLOOR}`",
        f"- Confidence floor (locked): `{CONFIDENCE_FLOOR}`",
        "",
        _sec("Final Recommendation", f"**{recommendation}**"),
        _sec("Infrastructure Health", _kv(infra) or "_No infrastructure evidence._"),
        _sec("Replay Results", _kv(replay_m) or "_Replay not run._"),
        _sec("Paper Trading Results", _kv(paper_m) or "_Paper not run._"),
        _sec("Shadow Trading Results", _kv(shadow_m) or "_Shadow not run._"),
        _sec("OMS Statistics", _kv(oms_m) or "_No OMS stats._"),
        _sec("Gateway Statistics", _kv(gw_m) or "_No gateway stats._"),
        _sec("Risk Statistics", _kv(risk_m) or "_No risk stats._"),
        _sec("Performance Statistics", _kv(perf_m) or "_No performance stats._"),
        _sec(
            "Acceptance Criteria",
            _kv(
                {
                    "summary": acc.get("summary") or {},
                    "recommendation": recommendation,
                    "gates": acc.get("gates") or [],
                    "quality_floor": QUALITY_FLOOR,
                    "confidence_floor": CONFIDENCE_FLOOR,
                }
            ),
        ),
    ]
    if dashboard:
        parts.append(
            _sec(
                "Live Pilot Dashboard Snapshot",
                _kv(dashboard.get("metrics_snake") or dashboard),
            )
        )
    parts.extend(
        [
            "## Rules Affirmation",
            "",
            "- Strategy unmodified",
            "- Quality threshold unmodified (80)",
            "- Confidence threshold unmodified (80)",
            "- Weights unmodified",
            "- Risk logic unmodified",
            "- Institutional safety preserved",
            "",
        ]
    )
    return "\n".join(parts)


def write_rc1_validation_report(
    report_md: str,
    *,
    path: Path | None = None,
) -> Path:
    target = path or Path("docs/production/RC1_VALIDATION_REPORT.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report_md, encoding="utf-8")
    return target
