"""AQC platform orchestrator — operational AI, advisory only."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.ai_quant_copilot.analysis import (
    build_executive_summaries,
    build_historical_comparison,
    build_investigations,
    build_operational_timeline,
    correlate_systems,
    search_aqs_recommendations,
)
from app.domain.ai_quant_copilot.gather import gather_ops_context
from app.domain.ai_quant_copilot.models import ISOLATION_FLAGS
from app.domain.ai_quant_copilot.nli import answer_question
from app.domain.ai_quant_copilot.store import AqcStore


class AiQuantCopilot:
    def __init__(self, store: AqcStore | None = None) -> None:
        self.store = store or AqcStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run_ops(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_ops_context()
        investigations = build_investigations(ctx)
        comparison = build_historical_comparison(ctx)
        timeline = build_operational_timeline(ctx)
        summaries = build_executive_summaries(ctx)
        correlations = correlate_systems(ctx)
        recommendations = search_aqs_recommendations(ctx, limit=100)

        if persist:
            for inv in investigations[:40]:
                self.store.upsert_investigation(inv)
            for period, body in summaries.items():
                if period in {"daily", "weekly", "monthly"} and isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"exec-{period}-{datetime.now(UTC).date()}",
                            "kind": "executive_summary",
                            "period": period,
                            **body,
                        }
                    )

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "schema_version": "1.0.0",
            "mode": "ai_quant_copilot",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "investigations": investigations,
            "comparison": comparison,
            "timeline": timeline,
            "executive_summaries": summaries,
            "correlations": correlations,
            "recommendations": recommendations,
            "execution_explain": (ctx.get("sources") or {}).get("execution_explain"),
            "read_only": True,
            "never_modifies_production": True,
            "_ctx": ctx,
        }

    def dashboard(self) -> dict[str, Any]:
        pack = self.run_ops(persist=True)
        pack["sections"] = {
            "ask_copilot": {"hint": "Use /aqc/ask"},
            "investigations": pack["investigations"][:15],
            "evidence_viewer": {
                "investigations": pack["investigations"][:5],
                "correlations": pack["correlations"],
            },
            "timeline_explorer": pack["timeline"][:40],
            "executive_reports": self.store.list_reports(limit=15),
            "recommendations_explorer": pack["recommendations"][:30],
            "conversation_history": self.store.list_conversations(limit=30),
            "historical_comparison": pack["comparison"],
        }
        # Do not leak internal ctx to API consumers
        pack.pop("_ctx", None)
        return pack

    def ask(self, question: str, *, persist_conversation: bool = True) -> dict[str, Any]:
        pack = self.run_ops(persist=False)
        ctx = pack.pop("_ctx", {}) or gather_ops_context()
        result = answer_question(question, ctx=ctx, pack=pack)
        result["id"] = str(uuid4())
        result["question"] = question
        if persist_conversation:
            self.store.append_conversation(
                {
                    "id": result["id"],
                    "question": question,
                    "answer": result.get("answer"),
                    "source_subsystem": result.get("source_subsystem"),
                    "confidence": result.get("confidence"),
                    "evidence_count": len(result.get("evidence") or [])
                    if isinstance(result.get("evidence"), list)
                    else 1,
                }
            )
        result["conversation_history"] = self.store.list_conversations(limit=20)
        result["isolation"] = self.isolation
        return result

    def list_conversations(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.list_conversations(limit=limit)

    def list_investigations(self, *, limit: int = 40) -> list[dict[str, Any]]:
        stored = self.store.list_investigations(limit=limit)
        if stored:
            return stored
        return build_investigations(gather_ops_context())[:limit]
