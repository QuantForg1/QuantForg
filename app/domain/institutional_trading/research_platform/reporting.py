"""Institutional reporting — daily/weekly/monthly with CSV export."""

from __future__ import annotations

import csv
import io
import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.research_platform.config import (
    DEFAULT_RESEARCH_CONFIG,
)
from core.logging import get_logger

logger = get_logger(__name__)


def _gather_sections() -> dict[str, Any]:
    sections: dict[str, Any] = {
        "portfolio_performance": {},
        "risk_metrics": {},
        "strategy_comparison": {},
        "execution_quality": {},
        "ai_calibration": {},
        "opportunity_quality": {},
        "recommendations": [],
    }
    try:
        from app.domain.institutional_trading.ai_validation import (
            get_execution_quality_monitor,
            get_portfolio_analytics_store,
            get_strategy_performance_store,
        )

        sections["portfolio_performance"] = get_portfolio_analytics_store().snapshot()
        sections["strategy_comparison"] = get_strategy_performance_store().snapshot()
        sections["execution_quality"] = get_execution_quality_monitor().snapshot()
    except Exception:
        logger.exception("report_gather_ai_validation_failed")
    try:
        from app.domain.institutional_trading.performance_lab import (
            get_calibration_store,
            get_opportunity_outcome_store,
            get_recommendation_engine,
        )

        sections["ai_calibration"] = get_calibration_store().chart()
        sections["opportunity_quality"] = get_opportunity_outcome_store().summary()
        sections["recommendations"] = get_recommendation_engine().recent(limit=15)
    except Exception:
        logger.exception("report_gather_lab_failed")
    try:
        from app.domain.institutional_trading.portfolio_intelligence import (
            get_dynamic_risk_budget,
        )

        sections["risk_metrics"] = get_dynamic_risk_budget().snapshot()
    except Exception:
        pass
    return sections


def report_to_csv(report: dict[str, Any]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["section", "key", "value"])
    for section, payload in report.get("sections", {}).items():
        if isinstance(payload, dict):
            for k, v in payload.items():
                writer.writerow([section, k, json.dumps(v, default=str) if isinstance(v, (dict, list)) else v])
        elif isinstance(payload, list):
            for i, row in enumerate(payload):
                writer.writerow([section, str(i), json.dumps(row, default=str)])
        else:
            writer.writerow([section, "value", payload])
    return buf.getvalue()


def report_to_pdf_text(report: dict[str, Any]) -> str:
    """Plain-text PDF surrogate for environments without a PDF lib — still exportable."""
    lines = [
        f"QuantForg Institutional Report — {report.get('period')}",
        f"Generated: {report.get('generated_at')}",
        f"ID: {report.get('id')}",
        "",
        "Guidance: Prefer 2–4 weeks demo/low-risk live evidence before promotions.",
        "",
    ]
    for section, payload in (report.get("sections") or {}).items():
        lines.append(f"## {section}")
        lines.append(json.dumps(payload, indent=2, default=str)[:4000])
        lines.append("")
    return "\n".join(lines)


@dataclass
class ReportingStore:
    _reports: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "institutional_reports_v10.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            with self._lock:
                self._reports = list(raw.get("reports", []))[-DEFAULT_RESEARCH_CONFIG.max_reports :]
        except Exception:
            logger.exception("reports_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "reports": self._reports[-DEFAULT_RESEARCH_CONFIG.max_reports :],
                }
            self._path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        except Exception:
            logger.exception("reports_persist_failed")

    def generate(self, period: str = "daily") -> dict[str, Any]:
        period_u = period.lower()
        if period_u not in {"daily", "weekly", "monthly"}:
            period_u = "daily"
        report = {
            "id": str(uuid4()),
            "period": period_u,
            "generated_at": datetime.now(UTC).isoformat(),
            "sections": _gather_sections(),
            "exports": {"csv": True, "pdf": True},
        }
        with self._lock:
            self._reports.append(report)
            if len(self._reports) > DEFAULT_RESEARCH_CONFIG.max_reports:
                self._reports = self._reports[-DEFAULT_RESEARCH_CONFIG.max_reports :]
        self._persist()
        return report

    def recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._reports[-max(1, limit) :]))


_STORE: ReportingStore | None = None
_LOCK = threading.Lock()


def get_reporting_store() -> ReportingStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = ReportingStore()
        return _STORE
