"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { iseApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/institutional-simulation", label: "Dashboard" },
  { href: "/institutional-simulation/scenarios", label: "Scenarios" },
  { href: "/institutional-simulation/explorer", label: "Explorer" },
  { href: "/institutional-simulation/stress", label: "Stress" },
  { href: "/institutional-simulation/monte-carlo", label: "Monte Carlo" },
  { href: "/institutional-simulation/walk-forward", label: "Walk Forward" },
  { href: "/institutional-simulation/reports", label: "Reports" },
] as const;

export function IseNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/institutional-simulation"
            ? pathname === link.href
            : pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "px-3 py-1.5 text-[12px] uppercase tracking-[0.1em]",
              active
                ? "border border-[var(--border-strong)] bg-[var(--surface-2)] text-[var(--fg)]"
                : "text-[var(--fg-muted)] hover:text-[var(--fg)]",
            )}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}

function MetricsGrid({ metrics }: { metrics: Record<string, unknown> }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      <MetricCard label="Win rate" value={str(metrics.win_rate, "—")} />
      <MetricCard label="Profit factor" value={str(metrics.profit_factor, "—")} />
      <MetricCard label="Expectancy" value={str(metrics.expectancy, "—")} />
      <MetricCard label="Drawdown" value={str(metrics.drawdown, "—")} />
      <MetricCard label="Avg RR" value={str(metrics.average_rr, "—")} />
      <MetricCard label="Trade count" value={str(metrics.trade_count, "—")} />
      <MetricCard label="Exposure" value={str(metrics.exposure, "—")} />
      <MetricCard label="Holding time" value={str(metrics.holding_time, "—")} />
    </div>
  );
}

export function IseDashboardWorkspace() {
  const q = useQuery({
    queryKey: ["ise", "dashboard"],
    queryFn: () => iseApi.dashboard(),
    refetchInterval: 120_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "ISE unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const sims = asList(root.simulations).map(asRecord);
  const catalog = asRecord(root.catalog);

  return (
    <div className="space-y-4">
      <IseNav />
      <div className="flex flex-wrap gap-2">
        <Badge tone="neutral">INSTITUTIONAL SIMULATION ENGINE</Badge>
        <Badge tone="success">DIGITAL TWIN</Badge>
        <Badge tone="warning">ISOLATED</Badge>
        <Badge tone="warning">NEVER EXECUTES</Badge>
      </div>
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Reproduces Market → Signal → MTF → Quality → Confluence → Risk → Safety
        → OMS → Gateway → Execution without touching production.
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Simulations" value={String(sims.length)} />
        <MetricCard
          label="Modes"
          value={String(asList(catalog.modes).length)}
        />
        <MetricCard
          label="Scenarios"
          value={String(asList(catalog.scenarios).length)}
        />
        <MetricCard
          label="KG nodes"
          value={String(asList(root.knowledge_nodes).length)}
        />
      </div>

      <OpsPanel title="Recent simulations">
        <ul className="space-y-2">
          {sims.slice(0, 8).map((s) => (
            <li
              key={str(s.simulation_id)}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge tone="neutral">{str(s.mode)}</Badge>
              <span>{str(s.title)}</span>
              <span className="text-[var(--fg-muted)]">
                PF:{str(asRecord(s.metrics).profit_factor, "—")}
              </span>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button asChild size="sm" variant="outline">
            <Link href="/institutional-simulation/scenarios">Scenario builder</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/institutional-simulation/monte-carlo">Monte Carlo</Link>
          </Button>
        </div>
      </OpsPanel>
    </div>
  );
}

export function IseScenariosWorkspace() {
  const catalogQ = useQuery({
    queryKey: ["ise", "catalog"],
    queryFn: () => iseApi.catalog(),
  });
  const [scenario, setScenario] = useState("higher_spread");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const run = useMutation({
    mutationFn: () =>
      iseApi.simulate("Historical Scenario Builder", scenario),
    onSuccess: (data) => setResult(asRecord(data)),
  });

  return (
    <div className="space-y-4">
      <IseNav />
      <OpsPanel title="Scenario builder">
        <div className="mb-3 flex flex-wrap gap-2">
          {asList(asRecord(catalogQ.data).scenarios).map((s) => (
            <Button
              key={String(s)}
              size="sm"
              variant={scenario === String(s) ? "secondary" : "outline"}
              onClick={() => setScenario(String(s))}
            >
              {String(s)}
            </Button>
          ))}
        </div>
        <Button
          size="sm"
          variant="secondary"
          disabled={run.isPending}
          onClick={() => run.mutate()}
        >
          Run isolated scenario
        </Button>
        {result ? (
          <div className="mt-4 space-y-3">
            <p className="text-[12px]">{str(result.title)}</p>
            <MetricsGrid metrics={asRecord(result.metrics)} />
            <pre className="max-h-40 overflow-auto text-[11px] text-[var(--fg-muted)]">
              {JSON.stringify(result.pipeline, null, 2)}
            </pre>
          </div>
        ) : null}
      </OpsPanel>
    </div>
  );
}

export function IseExplorerWorkspace() {
  const q = useQuery({
    queryKey: ["ise", "simulations"],
    queryFn: () => iseApi.simulations(50),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const rows = asList(asRecord(q.data).simulations).map(asRecord);

  return (
    <div className="space-y-4">
      <IseNav />
      <OpsPanel title="Scenario explorer">
        <ul className="space-y-3">
          {rows.map((s) => (
            <li
              key={str(s.simulation_id)}
              className="border border-[var(--border)] px-3 py-3 text-[12px]"
            >
              <div className="mb-2 flex flex-wrap gap-2">
                <Badge tone="neutral">{str(s.mode)}</Badge>
                <Badge tone="warning">{str(s.scenario)}</Badge>
                <span>{str(s.title)}</span>
              </div>
              <MetricsGrid metrics={asRecord(s.metrics)} />
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IseStressWorkspace() {
  const [stress, setStress] = useState("volatility_spike");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const catalogQ = useQuery({
    queryKey: ["ise", "catalog"],
    queryFn: () => iseApi.catalog(),
  });
  const run = useMutation({
    mutationFn: () => iseApi.stress(stress),
    onSuccess: (data) => setResult(asRecord(data)),
  });

  return (
    <div className="space-y-4">
      <IseNav />
      <OpsPanel title="Stress testing">
        <div className="mb-3 flex flex-wrap gap-2">
          {asList(asRecord(catalogQ.data).stress_tests).map((s) => (
            <Button
              key={String(s)}
              size="sm"
              variant={stress === String(s) ? "secondary" : "outline"}
              onClick={() => setStress(String(s))}
            >
              {String(s)}
            </Button>
          ))}
        </div>
        <Button
          size="sm"
          variant="secondary"
          disabled={run.isPending}
          onClick={() => run.mutate()}
        >
          Run stress simulation
        </Button>
        {result ? (
          <div className="mt-4">
            <MetricsGrid metrics={asRecord(result.metrics)} />
          </div>
        ) : null}
      </OpsPanel>
    </div>
  );
}

export function IseMonteCarloWorkspace() {
  const [paths, setPaths] = useState(100);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const qc = useQueryClient();
  const run = useMutation({
    mutationFn: () => iseApi.monteCarlo(paths),
    onSuccess: (data) => {
      setResult(asRecord(data));
      void qc.invalidateQueries({ queryKey: ["ise"] });
    },
  });
  const mc = asRecord(result?.monte_carlo);

  return (
    <div className="space-y-4">
      <IseNav />
      <OpsPanel title="Monte Carlo">
        <div className="mb-3 flex flex-wrap gap-2">
          {[100, 500, 1000, 5000].map((p) => (
            <Button
              key={p}
              size="sm"
              variant={paths === p ? "secondary" : "outline"}
              onClick={() => setPaths(p)}
            >
              {p} paths
            </Button>
          ))}
        </div>
        <Button
          size="sm"
          variant="secondary"
          disabled={run.isPending}
          onClick={() => run.mutate()}
        >
          Run Monte Carlo
        </Button>
        {result ? (
          <div className="mt-4 space-y-3">
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
              <MetricCard
                label="P(ruin)%"
                value={str(mc.probability_of_ruin, "—")}
              />
              <MetricCard
                label="Worst"
                value={str(mc.worst_case, "—")}
              />
              <MetricCard
                label="Median"
                value={str(mc.median_case, "—")}
              />
              <MetricCard label="Best" value={str(mc.best_case, "—")} />
              <MetricCard
                label="CI p05–p95"
                value={`${str(asRecord(mc.confidence_interval).p05, "—")}–${str(asRecord(mc.confidence_interval).p95, "—")}`}
              />
            </div>
            <MetricsGrid metrics={asRecord(result.metrics)} />
          </div>
        ) : null}
      </OpsPanel>
    </div>
  );
}

export function IseWalkForwardWorkspace() {
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const run = useMutation({
    mutationFn: () => iseApi.walkForward(),
    onSuccess: (data) => setResult(asRecord(data)),
  });
  const wf = asRecord(result?.walk_forward);

  return (
    <div className="space-y-4">
      <IseNav />
      <OpsPanel title="Walk forward">
        <Button
          size="sm"
          variant="secondary"
          disabled={run.isPending}
          onClick={() => run.mutate()}
        >
          Run walk forward
        </Button>
        {result ? (
          <div className="mt-4 space-y-3">
            <MetricCard
              label="Generalization score"
              value={str(wf.generalization_score, "—")}
            />
            <div className="grid gap-3 lg:grid-cols-3">
              {(["train", "validate", "test"] as const).map((split) => (
                <div
                  key={split}
                  className="border border-[var(--border)] px-3 py-2 text-[12px]"
                >
                  <p className="mb-2 font-medium uppercase">{split}</p>
                  <MetricsGrid
                    metrics={asRecord(asRecord(wf[split]).metrics)}
                  />
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </OpsPanel>
    </div>
  );
}

export function IseReportsWorkspace() {
  const q = useQuery({
    queryKey: ["ise", "reports"],
    queryFn: () => iseApi.reports(20),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const rows = asList(asRecord(q.data).reports).map(asRecord);

  return (
    <div className="space-y-4">
      <IseNav />
      <OpsPanel title="Simulation reports">
        <ul className="space-y-2">
          {rows.map((r) => (
            <li
              key={str(r.report_id)}
              className="border border-[var(--border)] px-3 py-2 text-[12px]"
            >
              <Badge tone="neutral">{str(r.kind)}</Badge>{" "}
              <span>{str(r.title)}</span>
              <pre className="mt-2 max-h-32 overflow-auto text-[11px] text-[var(--fg-muted)]">
                {JSON.stringify(r.simulations || r.comparisons || r, null, 2)}
              </pre>
            </li>
          ))}
          {!rows.length ? (
            <li className="text-[var(--fg-muted)]">No reports yet.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}
