"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { IrlNav } from "@/components/ops/irl-nav";
import { irlApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";

export function IrlDashboardWorkspace() {
  const q = useQuery({
    queryKey: ["irl", "dashboard"],
    queryFn: () => irlApi.dashboard(),
    refetchInterval: 30_000,
  });

  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "IRL unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }

  const root = asRecord(q.data);
  const counts = asRecord(root.counts);
  const top = asList(root.top_leaderboard).map((x) => asRecord(x));
  const recent = asList(root.recent_experiments).map((x) => asRecord(x));

  return (
    <div className="space-y-4">
      <IrlNav />
      <div className="flex flex-wrap gap-2">
        <Badge tone="neutral">INSTITUTIONAL RESEARCH LAB</Badge>
        <Badge tone="success">ISOLATED</Badge>
        <Badge tone="warning">NO LIVE EXECUTION</Badge>
        <Badge tone="warning">NO PRODUCTION WRITES</Badge>
      </div>
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Research workspace only — never modifies strategy, risk, safety, OMS,
        gateway, auto trading, or live thresholds. Never auto-promotes.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard label="Experiments" value={String(num(counts.experiments, 0))} />
        <MetricCard label="Completed" value={String(num(counts.completed, 0))} />
        <MetricCard label="Running" value={String(num(counts.running, 0))} />
        <MetricCard label="Jobs" value={String(num(counts.jobs, 0))} />
        <MetricCard label="Reports" value={String(num(counts.reports, 0))} />
      </div>
      <OpsPanel title="Top leaderboard">
        {top.length === 0 ? (
          <p className="text-[12px] text-[var(--fg-subtle)]">
            No completed experiments yet. Create one and run a replay.
          </p>
        ) : (
          <ul className="space-y-2">
            {top.map((row) => (
              <li key={str(row.uuid)} className="flex flex-wrap items-center gap-2 text-[13px]">
                <span className="font-mono text-[11px] text-[var(--fg-subtle)]">
                  #{num(row.rank, 0)}
                </span>
                <Link
                  href={`/institutional-research-lab/experiments/${str(row.uuid)}`}
                  className="text-[var(--fg)] underline-offset-2 hover:underline"
                >
                  {str(row.name, "Experiment")}
                </Link>
                <span className="font-mono text-[11px] text-[var(--fg-muted)]">
                  composite {str(row.composite_score, "—")} · PF{" "}
                  {str(row.profit_factor, "—")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </OpsPanel>
      <OpsPanel title="Recent experiments">
        <ul className="space-y-2">
          {recent.map((e) => (
            <li key={str(e.uuid)} className="flex flex-wrap items-center gap-2 text-[13px]">
              <Badge tone="neutral">{str(e.status, "—")}</Badge>
              <Link
                href={`/institutional-research-lab/experiments/${str(e.uuid)}`}
                className="text-[var(--fg)] underline-offset-2 hover:underline"
              >
                {str(e.name)}
              </Link>
              <span className="text-[11px] text-[var(--fg-subtle)]">
                {str(e.verdict, "Pending")}
              </span>
            </li>
          ))}
        </ul>
        <div className="mt-3">
          <Button asChild size="sm" variant="secondary">
            <Link href="/institutional-research-lab/experiments">Manage experiments</Link>
          </Button>
        </div>
      </OpsPanel>
    </div>
  );
}

export function IrlExperimentsWorkspace() {
  const qc = useQueryClient();
  const [name, setName] = useState("Candidate experiment");
  const [desc, setDesc] = useState("");
  const q = useQuery({
    queryKey: ["irl", "experiments"],
    queryFn: () => irlApi.experiments(100),
  });
  const create = useMutation({
    mutationFn: () =>
      irlApi.createExperiment({
        name,
        description: desc,
        candidate_params: {
          candidate_mtf_model: "research_mtf_v1",
          candidate_quality_formula: "strict",
          candidate_confluence_formula: "weighted_v2",
          candidate_regime_filter: "trend_or_breakout",
          candidate_session_filters: "london_ny",
        },
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["irl"] });
    },
  });

  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Experiments unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }

  const experiments = asList(asRecord(q.data).experiments).map((x) => asRecord(x));

  return (
    <div className="space-y-4">
      <IrlNav />
      <OpsPanel title="Create experiment">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <label className="flex flex-1 flex-col gap-1 text-[11px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
            Name
            <input
              className="border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px] text-[var(--fg)]"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label className="flex flex-[2] flex-col gap-1 text-[11px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
            Description
            <input
              className="border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px] text-[var(--fg)]"
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
            />
          </label>
          <Button
            size="sm"
            variant="secondary"
            disabled={create.isPending || !name.trim()}
            onClick={() => create.mutate()}
          >
            Create
          </Button>
        </div>
      </OpsPanel>
      <OpsPanel title="Experiments">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-[12px]">
            <thead>
              <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                <th className="py-2 pr-3">Name</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Verdict</th>
                <th className="py-2">Updated</th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((e) => (
                <tr key={str(e.uuid)} className="border-b border-[var(--border)]/50">
                  <td className="py-2 pr-3">
                    <Link
                      href={`/institutional-research-lab/experiments/${str(e.uuid)}`}
                      className="text-[var(--fg)] underline-offset-2 hover:underline"
                    >
                      {str(e.name)}
                    </Link>
                  </td>
                  <td className="py-2 pr-3">{str(e.status)}</td>
                  <td className="py-2 pr-3">{str(e.verdict, "Pending")}</td>
                  <td className="py-2 font-mono text-[11px] text-[var(--fg-muted)]">
                    {str(e.updated_at, "—").slice(0, 19)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </OpsPanel>
    </div>
  );
}

export function IrlJobsWorkspace() {
  const q = useQuery({
    queryKey: ["irl", "jobs"],
    queryFn: () => irlApi.jobs(50),
  });
  if (q.isLoading) return <DeskSkeleton rows={5} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Jobs unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const jobs = asList(asRecord(q.data).jobs).map((x) => asRecord(x));
  return (
    <div className="space-y-4">
      <IrlNav />
      <OpsPanel title="Replay jobs">
        {jobs.length === 0 ? (
          <p className="text-[12px] text-[var(--fg-subtle)]">No replay jobs yet.</p>
        ) : (
          <ul className="space-y-2">
            {jobs.map((j) => (
              <li
                key={str(j.job_id)}
                className="flex flex-wrap gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
              >
                <Badge tone="neutral">{str(j.status)}</Badge>
                <span className="font-mono text-[11px]">{str(j.window)}</span>
                <Link
                  href={`/institutional-research-lab/experiments/${str(j.experiment_id)}`}
                  className="underline-offset-2 hover:underline"
                >
                  experiment
                </Link>
                <span className="text-[var(--fg-subtle)]">
                  trades {str(j.trade_count, "—")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </OpsPanel>
    </div>
  );
}

export function IrlLeaderboardWorkspace() {
  const [rankBy, setRankBy] = useState("composite");
  const q = useQuery({
    queryKey: ["irl", "leaderboard", rankBy],
    queryFn: () => irlApi.leaderboard(rankBy, 50),
  });
  if (q.isLoading) return <DeskSkeleton rows={5} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Leaderboard unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const rows = asList(asRecord(q.data).rows).map((x) => asRecord(x));
  return (
    <div className="space-y-4">
      <IrlNav />
      <div className="flex flex-wrap gap-2">
        {["composite", "profit_factor", "expectancy", "drawdown", "consistency"].map(
          (k) => (
            <Button
              key={k}
              size="sm"
              variant={rankBy === k ? "secondary" : "outline"}
              onClick={() => setRankBy(k)}
            >
              {k}
            </Button>
          ),
        )}
      </div>
      <OpsPanel title="Leaderboard">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-[12px]">
            <thead>
              <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                <th className="py-2 pr-3">Rank</th>
                <th className="py-2 pr-3">Name</th>
                <th className="py-2 pr-3">PF</th>
                <th className="py-2 pr-3">Expectancy</th>
                <th className="py-2 pr-3">DD%</th>
                <th className="py-2">Composite</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={str(r.uuid)} className="border-b border-[var(--border)]/50">
                  <td className="py-2 pr-3 font-mono">{num(r.rank, 0)}</td>
                  <td className="py-2 pr-3">
                    <Link
                      href={`/institutional-research-lab/experiments/${str(r.uuid)}`}
                      className="underline-offset-2 hover:underline"
                    >
                      {str(r.name)}
                    </Link>
                  </td>
                  <td className="py-2 pr-3 font-mono">{str(r.profit_factor, "—")}</td>
                  <td className="py-2 pr-3 font-mono">{str(r.expectancy, "—")}</td>
                  <td className="py-2 pr-3 font-mono">
                    {str(r.maximum_drawdown_pct, "—")}
                  </td>
                  <td className="py-2 font-mono">{str(r.composite_score, "—")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </OpsPanel>
    </div>
  );
}

export function IrlReportsWorkspace() {
  const q = useQuery({
    queryKey: ["irl", "reports"],
    queryFn: () => irlApi.reports(50),
  });
  if (q.isLoading) return <DeskSkeleton rows={5} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Reports unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const reports = asList(asRecord(q.data).reports).map((x) => asRecord(x));
  return (
    <div className="space-y-4">
      <IrlNav />
      <OpsPanel title="Research reports">
        {reports.length === 0 ? (
          <p className="text-[12px] text-[var(--fg-subtle)]">No reports yet.</p>
        ) : (
          <ul className="space-y-3">
            {reports.map((r) => {
              const stats = asRecord(r.statistics);
              const verdict = asRecord(r.verdict);
              return (
                <li
                  key={str(r.report_id)}
                  className="border border-[var(--border)] px-3 py-3 text-[12px]"
                >
                  <div className="flex flex-wrap gap-2">
                    <Badge tone="neutral">{str(verdict.verdict, "—")}</Badge>
                    <Link
                      href={`/institutional-research-lab/experiments/${str(r.experiment_id)}`}
                      className="underline-offset-2 hover:underline"
                    >
                      open experiment
                    </Link>
                  </div>
                  <p className="mt-2 font-mono text-[11px] text-[var(--fg-muted)]">
                    PF {str(stats.profit_factor, "—")} · WR {str(stats.win_rate, "—")}% ·
                    trades {str(stats.total_trades, "—")} ·{" "}
                    {str(r.created_at, "").slice(0, 19)}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </OpsPanel>
    </div>
  );
}

export function IrlBenchmarkWorkspace() {
  const q = useQuery({
    queryKey: ["irl", "benchmark"],
    queryFn: () => irlApi.benchmark(),
  });
  if (q.isLoading) return <DeskSkeleton rows={5} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Benchmark unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const baseline = asRecord(root.production_baseline);
  const experiments = asList(root.experiments).map((x) => asRecord(x));
  return (
    <div className="space-y-4">
      <IrlNav />
      <OpsPanel title="Production baseline (research reference)">
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <MetricCard label="PF" value={str(baseline.profit_factor, "—")} />
          <MetricCard label="Expectancy" value={str(baseline.expectancy, "—")} />
          <MetricCard label="Win rate" value={str(baseline.win_rate, "—")} />
          <MetricCard label="Max DD%" value={str(baseline.maximum_drawdown_pct, "—")} />
          <MetricCard label="Trades" value={str(baseline.total_trades, "—")} />
        </div>
      </OpsPanel>
      <OpsPanel title="Candidate vs production">
        {experiments.length === 0 ? (
          <p className="text-[12px] text-[var(--fg-subtle)]">
            Run a replay to generate benchmark deltas.
          </p>
        ) : (
          <ul className="space-y-3">
            {experiments.map((e) => {
              const b = asRecord(e.benchmark);
              return (
                <li key={str(e.uuid)} className="border border-[var(--border)] px-3 py-3">
                  <Link
                    href={`/institutional-research-lab/experiments/${str(e.uuid)}`}
                    className="text-[13px] underline-offset-2 hover:underline"
                  >
                    {str(e.name)}
                  </Link>
                  <p className="mt-1 font-mono text-[11px] text-[var(--fg-muted)]">
                    PF Δ {str(b.profit_factor_difference_pct, "—")}% · Exp Δ{" "}
                    {str(b.expectancy_difference, "—")} · WR Δ{" "}
                    {str(b.win_rate_difference, "—")} · DD Δ{" "}
                    {str(b.drawdown_difference, "—")} · N Δ{" "}
                    {str(b.trade_count_difference, "—")}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </OpsPanel>
    </div>
  );
}

export function IrlExperimentDetailWorkspace({ experimentId }: { experimentId: string }) {
  const qc = useQueryClient();
  const [window, setWindow] = useState("90d");
  const [note, setNote] = useState("");
  const q = useQuery({
    queryKey: ["irl", "experiment", experimentId],
    queryFn: () => irlApi.experiment(experimentId),
  });
  const replay = useMutation({
    mutationFn: () => irlApi.replay(experimentId, { window }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["irl"] });
    },
  });
  const addNote = useMutation({
    mutationFn: () => irlApi.addNote(experimentId, { body: note }),
    onSuccess: async () => {
      setNote("");
      await qc.invalidateQueries({ queryKey: ["irl", "experiment", experimentId] });
    },
  });

  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Experiment unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }

  const exp = asRecord(asRecord(q.data).experiment);
  const stats = asRecord(exp.statistics);
  const sig = asRecord(exp.significance);
  const bench = asRecord(exp.benchmark);
  const params = asRecord(exp.candidate_params);
  const notes = asList(exp.notes).map((x) => asRecord(x));
  const curve = asList(stats.equity_curve).map((v, i) => ({
    i,
    v: num(v, NaN),
  }));

  return (
    <div className="space-y-4">
      <IrlNav />
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">{str(exp.status)}</Badge>
        <Badge tone="warning">{str(exp.verdict, "Pending")}</Badge>
        <h2 className="text-[18px] font-semibold text-[var(--fg)]">{str(exp.name)}</h2>
      </div>
      <p className="text-[13px] text-[var(--fg-muted)]">{str(exp.description, "")}</p>

      <OpsPanel title="Replay (historical / research only)">
        <div className="flex flex-wrap gap-2">
          {["30d", "90d", "180d", "365d"].map((w) => (
            <Button
              key={w}
              size="sm"
              variant={window === w ? "secondary" : "outline"}
              onClick={() => setWindow(w)}
            >
              {w}
            </Button>
          ))}
          <Button
            size="sm"
            variant="secondary"
            disabled={replay.isPending}
            onClick={() => replay.mutate()}
          >
            {replay.isPending ? "Running…" : "Run replay"}
          </Button>
        </div>
        <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
          Never uses live execution. Never writes production tables.
        </p>
      </OpsPanel>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Trades" value={str(stats.total_trades, "—")} />
        <MetricCard label="Win rate" value={stats.win_rate != null ? `${stats.win_rate}%` : "—"} />
        <MetricCard label="Profit factor" value={str(stats.profit_factor, "—")} />
        <MetricCard label="Expectancy" value={str(stats.expectancy, "—")} />
        <MetricCard label="Sharpe" value={str(stats.sharpe, "—")} />
        <MetricCard label="Sortino" value={str(stats.sortino, "—")} />
        <MetricCard label="Calmar" value={str(stats.calmar, "—")} />
        <MetricCard label="Max DD%" value={str(stats.maximum_drawdown_pct, "—")} />
      </div>

      <OpsPanel title="Significance">
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <MetricCard label="Sample" value={str(sig.sample_size, "—")} />
          <MetricCard label="Confidence" value={str(sig.confidence, "—")} />
          <MetricCard label="Stability" value={str(sig.stability_score, "—")} />
          <MetricCard label="Consistency" value={str(sig.consistency_score, "—")} />
          <MetricCard label="Walk forward" value={str(sig.walk_forward_score, "—")} />
          <MetricCard label="Outliers" value={str(sig.outlier_count, "—")} />
        </div>
      </OpsPanel>

      <OpsPanel title="Benchmark vs production">
        <p className="font-mono text-[12px] text-[var(--fg-muted)]">
          PF Δ {str(bench.profit_factor_difference_pct, "—")}% · Exp Δ{" "}
          {str(bench.expectancy_difference, "—")} · WR Δ{" "}
          {str(bench.win_rate_difference, "—")} · DD Δ{" "}
          {str(bench.drawdown_difference, "—")} · N Δ{" "}
          {str(bench.trade_count_difference, "—")}
        </p>
      </OpsPanel>

      <OpsPanel title="Equity curve (research)">
        {curve.filter((p) => Number.isFinite(p.v)).length < 2 ? (
          <p className="text-[12px] text-[var(--fg-subtle)]">Run replay to populate curve.</p>
        ) : (
          <div className="flex h-28 items-end gap-px">
            {curve
              .filter((p) => Number.isFinite(p.v))
              .slice(-80)
              .map((p) => {
                const vals = curve.map((c) => c.v).filter((v) => Number.isFinite(v));
                const min = Math.min(...vals);
                const max = Math.max(...vals);
                const h =
                  max === min ? 40 : ((p.v - min) / (max - min)) * 100;
                return (
                  <div
                    key={p.i}
                    className="flex-1 bg-[var(--accent)]/70"
                    style={{ height: `${Math.max(4, h)}%` }}
                    title={String(p.v)}
                  />
                );
              })}
          </div>
        )}
      </OpsPanel>

      <OpsPanel title="Candidate parameters (research only)">
        <ul className="grid gap-1 sm:grid-cols-2">
          {Object.entries(params).map(([k, v]) => (
            <li key={k} className="font-mono text-[11px] text-[var(--fg-muted)]">
              {k}: {v == null ? "—" : String(v)}
            </li>
          ))}
        </ul>
      </OpsPanel>

      <OpsPanel title="Research notes">
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            className="flex-1 border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px]"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Operator note…"
          />
          <Button
            size="sm"
            variant="secondary"
            disabled={!note.trim() || addNote.isPending}
            onClick={() => addNote.mutate()}
          >
            Add note
          </Button>
        </div>
        <ul className="mt-3 space-y-2">
          {notes.map((n) => (
            <li key={str(n.note_id)} className="text-[12px] text-[var(--fg-muted)]">
              <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
                {str(n.created_at, "").slice(0, 19)}
              </span>{" "}
              {str(n.body)}
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}
