"""IRL platform orchestrator — isolated research workspace."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.institutional_research_lab.benchmark import benchmark_against_production
from app.domain.institutional_research_lab.leaderboard import build_leaderboard
from app.domain.institutional_research_lab.models import ExperimentStatus, ReplayWindow
from app.domain.institutional_research_lab.promotion_policy import evaluate_research_verdict
from app.domain.institutional_research_lab.replay import (
    production_baseline_metrics,
    replay_historical,
)
from app.domain.institutional_research_lab.significance import compute_significance
from app.domain.institutional_research_lab.statistics import compute_statistics
from app.domain.institutional_research_lab.store import IrlStore


class InstitutionalResearchLab:
    """Completely isolated research environment."""

    def __init__(self, store: IrlStore | None = None) -> None:
        self.store = store or IrlStore()
        self.isolation = {
            "mutates_production_trading": False,
            "executes_live_trades": False,
            "writes_production_tables": False,
            "influences_production_decisions": False,
            "never_auto_promotes": True,
            "storage": "data/irl (isolated JSON) + process memory",
        }

    def dashboard(self) -> dict[str, Any]:
        experiments = self.store.list_experiments(limit=200)
        jobs = self.store.list_jobs(limit=50)
        completed = [e for e in experiments if e.get("status") == ExperimentStatus.COMPLETED.value]
        board = build_leaderboard(completed, limit=5)
        return {
            "mode": "institutional_research_lab",
            "isolation": self.isolation,
            "counts": {
                "experiments": len(experiments),
                "completed": len(completed),
                "running": sum(
                    1 for e in experiments if e.get("status") == ExperimentStatus.RUNNING.value
                ),
                "jobs": len(jobs),
                "reports": len(self.store.list_reports(limit=500)),
            },
            "top_leaderboard": board,
            "recent_experiments": experiments[:8],
            "recent_jobs": jobs[:8],
            "observed_at": datetime.now(UTC).isoformat(),
        }

    def create_experiment(
        self,
        *,
        name: str,
        description: str = "",
        author: str = "researcher",
        candidate_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.store.create_experiment(
            name=name,
            description=description,
            author=author,
            candidate_params=candidate_params,
        )

    def update_experiment(self, exp_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        return self.store.update_experiment(exp_id, updates)

    def get_experiment(self, exp_id: str) -> dict[str, Any] | None:
        exp = self.store.get_experiment(exp_id)
        if not exp:
            return None
        exp["notes"] = self.store.list_notes(exp_id)
        exp["jobs"] = self.store.list_jobs(experiment_id=exp_id, limit=20)
        return exp

    def list_experiments(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.store.list_experiments(limit=limit)

    def queue_and_run_replay(
        self,
        *,
        experiment_id: str,
        window: str = ReplayWindow.D90.value,
        custom_start: str | None = None,
        custom_end: str | None = None,
        bars: list[dict[str, Any]] | None = None,
        production_baseline: dict[str, Any] | None = None,
        author: str = "researcher",
    ) -> dict[str, Any]:
        exp = self.store.get_experiment(experiment_id)
        if not exp:
            raise KeyError("experiment_not_found")

        self.store.update_experiment(
            experiment_id, {"status": ExperimentStatus.QUEUED.value}
        )
        self.store.update_experiment(
            experiment_id, {"status": ExperimentStatus.RUNNING.value}
        )

        job_id = str(uuid4())
        job: dict[str, Any] = {
            "job_id": job_id,
            "experiment_id": experiment_id,
            "status": "Running",
            "window": window,
            "created_at": datetime.now(UTC).isoformat(),
            "author": author,
            "live_execution": False,
        }
        self.store.save_job(job)

        replay = replay_historical(
            experiment_id=experiment_id,
            candidate_params=exp.get("candidate_params") or {},
            window=window,
            custom_start=custom_start,
            custom_end=custom_end,
            bars=bars,
        )
        stats = compute_statistics(replay["trades"])
        significance = compute_significance(replay["trades"], stats)
        baseline = production_baseline or production_baseline_metrics()
        benchmark = benchmark_against_production(stats, baseline)
        verdict = evaluate_research_verdict(statistics=stats, significance=significance)

        report_id = str(uuid4())
        report = {
            "report_id": report_id,
            "experiment_id": experiment_id,
            "job_id": job_id,
            "created_at": datetime.now(UTC).isoformat(),
            "statistics": stats,
            "significance": significance,
            "benchmark": benchmark,
            "verdict": verdict,
            "replay_meta": {
                k: replay[k]
                for k in (
                    "engine",
                    "live_execution",
                    "writes_production_tables",
                    "influences_production_decisions",
                    "window",
                    "window_days",
                    "source",
                    "bar_count",
                    "replayed_at",
                )
            },
        }
        self.store.save_report(report)

        job.update(
            {
                "status": "Completed",
                "completed_at": datetime.now(UTC).isoformat(),
                "report_id": report_id,
                "trade_count": stats.get("total_trades"),
            }
        )
        self.store.save_job(job)

        updated = self.store.update_experiment(
            experiment_id,
            {
                "status": ExperimentStatus.COMPLETED.value,
                "statistics": stats,
                "significance": significance,
                "benchmark": benchmark,
                "verdict": verdict["verdict"],
                "last_job_id": job_id,
            },
        )
        return {
            "experiment": updated,
            "job": job,
            "report": report,
            "isolation": self.isolation,
        }

    def leaderboard(self, *, rank_by: str = "composite", limit: int = 50) -> dict[str, Any]:
        experiments = self.store.list_experiments(limit=500)
        rows = build_leaderboard(experiments, rank_by=rank_by, limit=limit)
        return {
            "rank_by": rank_by,
            "rows": rows,
            "isolation": self.isolation,
        }

    def list_reports(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.list_reports(limit=limit)

    def list_jobs(self, *, limit: int = 50, experiment_id: str | None = None) -> list[dict[str, Any]]:
        return self.store.list_jobs(limit=limit, experiment_id=experiment_id)

    def add_note(self, experiment_id: str, *, author: str, body: str) -> dict[str, Any]:
        if not self.store.get_experiment(experiment_id):
            raise KeyError("experiment_not_found")
        return self.store.add_note(experiment_id, author=author, body=body)

    def archive_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        return self.store.update_experiment(
            experiment_id, {"status": ExperimentStatus.ARCHIVED.value}
        )

    def mark_verdict(self, experiment_id: str, verdict: str) -> dict[str, Any] | None:
        """Manual research verdict only — never promotes to production."""
        return self.store.update_experiment(experiment_id, {"verdict": verdict})
