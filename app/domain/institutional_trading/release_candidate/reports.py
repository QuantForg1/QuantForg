"""RC1 performance reports — daily / weekly / monthly + CSV / PDF-text."""

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

from core.logging import get_logger

logger = get_logger(__name__)

PERIODS = ("daily", "weekly", "monthly")


def _gather() -> dict[str, Any]:
    sections: dict[str, Any] = {
        "performance": {},
        "risk": {},
        "portfolio": {},
        "strategy": {},
        "ai": {},
        "execution": {},
        "recommendations": [],
    }
    try:
        from app.domain.institutional_trading.release_candidate.live_stats import (
            build_live_statistics,
        )

        sections["performance"] = build_live_statistics().get("live_statistics") or {}
    except Exception:
        logger.exception("rc1_report_performance_failed")
    try:
        from app.domain.institutional_trading.portfolio_intelligence import (
            get_dynamic_risk_budget,
        )

        sections["risk"] = get_dynamic_risk_budget().snapshot()
        sections["portfolio"] = sections["risk"]
    except Exception:
        pass
    try:
        from app.domain.institutional_trading.ai_validation import (
            get_execution_quality_monitor,
            get_strategy_performance_store,
        )

        sections["strategy"] = get_strategy_performance_store().snapshot()
        sections["execution"] = get_execution_quality_monitor().snapshot()
    except Exception:
        pass
    try:
        from app.domain.institutional_trading.performance_lab import (
            get_calibration_store,
            get_recommendation_engine,
        )

        sections["ai"] = get_calibration_store().chart()
        sections["recommendations"] = get_recommendation_engine().recent(limit=20)
    except Exception:
        pass
    return sections


def report_to_csv(report: dict[str, Any]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["section", "key", "value"])
    for section, payload in (report.get("sections") or {}).items():
        if isinstance(payload, dict):
            for k, v in payload.items():
                writer.writerow(
                    [
                        section,
                        k,
                        json.dumps(v, default=str) if isinstance(v, (dict, list)) else v,
                    ]
                )
        elif isinstance(payload, list):
            for i, row in enumerate(payload):
                writer.writerow([section, str(i), json.dumps(row, default=str)])
        else:
            writer.writerow([section, "value", payload])
    return buf.getvalue()


def report_to_pdf_text(report: dict[str, Any]) -> str:
    lines = [
        f"QuantForg RC1 Performance Report — {report.get('period', '')}",
        f"Generated: {report.get('at', '')}",
        "",
    ]
    for section, payload in (report.get("sections") or {}).items():
        lines.append(f"## {section}")
        lines.append(json.dumps(payload, indent=2, default=str)[:4000])
        lines.append("")
    return "\n".join(lines)


@dataclass
class Rc1ReportingStore:
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
            self._path = base / "rc1_reports.json"

    def generate(self, period: str) -> dict[str, Any]:
        if period not in PERIODS:
            period = "daily"
        report = {
            "id": str(uuid4()),
            "period": period,
            "at": datetime.now(UTC).isoformat(),
            "sections": _gather(),
            "affects_production": False,
        }
        with self._lock:
            self._reports.append(report)
            self._reports = self._reports[-365:]
            payload = list(self._reports)
        try:
            if self._path is not None:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._path.write_text(
                    json.dumps({"reports": payload}, indent=2, default=str),
                    encoding="utf-8",
                )
        except Exception:
            logger.exception("rc1_report_persist_failed")
        return report

    def recent(self, *, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._reports[-max(1, limit) :]))


_STORE: Rc1ReportingStore | None = None
_LOCK = threading.Lock()


def get_rc1_reporting_store() -> Rc1ReportingStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = Rc1ReportingStore()
        return _STORE
