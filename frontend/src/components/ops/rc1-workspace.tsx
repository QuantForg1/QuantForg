"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { iteReliabilityApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "border border-[var(--border)] bg-[var(--surface)]",
        className,
      )}
    >
      <header className="border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-[var(--border)]/70 bg-[var(--bg)] px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
        {label}
      </div>
      <div className="mt-1 font-mono text-lg text-[var(--fg)]">{value}</div>
    </div>
  );
}

function fmt(v: unknown, digits = 2): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (Number.isFinite(n)) return n.toFixed(digits);
  return str(v, "—");
}

function statusTone(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "PASS") return "success";
  if (status === "WARNING") return "warning";
  if (status === "FAIL") return "danger";
  return "neutral";
}

export function Rc1Workspace() {
  const qc = useQueryClient();
  const dash = useQuery({
    queryKey: ["rc1-dashboard"],
    queryFn: () => iteReliabilityApi.rc1(200),
    retry: false,
    refetchInterval: 30_000,
  });

  const smokeMut = useMutation({
    mutationFn: () => iteReliabilityApi.rc1Smoke(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rc1-dashboard"] }),
  });

  const reportMut = useMutation({
    mutationFn: (period: "daily" | "weekly" | "monthly") =>
      iteReliabilityApi.rc1Report(period),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rc1-dashboard"] }),
  });

  if (dash.isLoading) return <DeskSkeleton rows={8} />;
  if (dash.isError) {
    return (
      <DeskError message="RC1 desk unavailable (OWNER/ADMIN · /ite/reliability/rc1)." />
    );
  }

  const d = asRecord(dash.data);
  const safeguards = asRecord(d.safeguards);
  const checklist = asRecord(d.checklist);
  const checklistItems = asList(checklist.items).map(asRecord);
  const counts = asRecord(checklist.counts);
  const score = asRecord(d.go_live_score);
  const components = asRecord(score.components);
  const live = asRecord(d.live_statistics);
  const validation = asRecord(d.rc_validation);
  const vMetrics = asRecord(validation.metrics);
  const evidence = asRecord(validation.evidence);
  const venues = asRecord(asRecord(d.venues).venues);
  const capital = asRecord(d.capital_advisor);
  const smokeRecent = asList(d.smoke_recent).map(asRecord);
  const docs = asList(d.documentation).map(asRecord);
  const reports = asList(d.performance_reports).map(asRecord);

  return (
    <div className="space-y-3">
      <Panel title="Mission">
        <p className="text-sm text-[var(--fg-muted)]">{str(d.mission)}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge tone="success">
            smoke_orders={String(safeguards.smoke_never_places_orders !== false)}
          </Badge>
          <Badge tone="success">
            auto_scale={String(safeguards.never_auto_scale_capital !== false)}
          </Badge>
          <Badge tone="success">
            venues_isolated={String(safeguards.never_mix_trading_venues !== false)}
          </Badge>
        </div>
      </Panel>

      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Go Live Score" value={fmt(score.score, 1)} />
        <Metric label="Threshold" value={fmt(score.threshold, 0)} />
        <Metric
          label="Scale-up"
          value={score.recommend_production_scale_up === true ? "Eligible*" : "Hold"}
        />
        <Metric label="Checklist" value={str(checklist.overall, "—")} />
      </div>
      <p className="text-xs text-[var(--fg-subtle)]">
        {str(score.recommendation)} · *Manual approval still required · never auto-scale
      </p>

      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          onClick={() => smokeMut.mutate()}
          disabled={smokeMut.isPending}
        >
          {smokeMut.isPending ? "Running smoke…" : "Run smoke test"}
        </Button>
        {(["daily", "weekly", "monthly"] as const).map((p) => (
          <Button
            key={p}
            size="sm"
            variant="outline"
            onClick={() => reportMut.mutate(p)}
            disabled={reportMut.isPending}
          >
            {p} report
          </Button>
        ))}
      </div>

      <Panel title="Production checklist">
        <div className="mb-2 flex flex-wrap gap-2 text-xs">
          <Badge tone="success">PASS {str(counts.PASS, "0")}</Badge>
          <Badge tone="warning">WARNING {str(counts.WARNING, "0")}</Badge>
          <Badge tone="danger">FAIL {str(counts.FAIL, "0")}</Badge>
        </div>
        <ul className="max-h-56 space-y-1 overflow-auto text-sm">
          {checklistItems.map((item) => (
            <li
              key={str(item.id)}
              className="flex items-start justify-between gap-2 border-b border-[var(--border)]/50 py-1"
            >
              <span className="font-mono text-xs text-[var(--fg)]">
                {str(item.id)} — {str(item.detail)}
              </span>
              <Badge tone={statusTone(str(item.status))}>{str(item.status)}</Badge>
            </li>
          ))}
        </ul>
      </Panel>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Live statistics">
          <div className="grid grid-cols-2 gap-2">
            <Metric label="Today trades" value={fmt(live.todays_trades, 0)} />
            <Metric label="Win rate" value={fmt(live.win_rate, 1)} />
            <Metric label="Drawdown" value={fmt(live.current_drawdown, 2)} />
            <Metric label="Profit factor" value={fmt(live.profit_factor, 2)} />
            <Metric label="Avg RR" value={fmt(live.average_rr, 2)} />
            <Metric label="Daily PnL" value={fmt(live.daily_pnl, 2)} />
            <Metric label="Weekly PnL" value={fmt(live.weekly_pnl, 2)} />
            <Metric label="Monthly PnL" value={fmt(live.monthly_pnl, 2)} />
            <Metric label="Latency ms" value={fmt(live.execution_latency_ms, 1)} />
            <Metric label="Slippage" value={fmt(live.slippage, 4)} />
          </div>
        </Panel>

        <Panel title="RC validation">
          <p className="mb-2 text-sm text-[var(--fg-muted)]">{str(evidence.message)}</p>
          <div className="grid grid-cols-2 gap-2">
            <Metric
              label="Consecutive days"
              value={fmt(vMetrics.consecutive_successful_trading_days, 0)}
            />
            <Metric label="System uptime %" value={fmt(vMetrics.system_uptime_pct, 1)} />
            <Metric label="Gateway uptime %" value={fmt(vMetrics.gateway_uptime_pct, 1)} />
            <Metric label="Avg latency" value={fmt(vMetrics.average_latency_ms, 1)} />
            <Metric label="Avg slippage" value={fmt(vMetrics.average_slippage, 4)} />
            <Metric label="Error rate" value={fmt(vMetrics.error_rate, 4)} />
            <Metric label="Broker rejects" value={fmt(vMetrics.broker_rejects, 0)} />
            <Metric label="Retry rate" value={fmt(vMetrics.retry_rate, 4)} />
          </div>
        </Panel>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        {(["paper", "demo", "live"] as const).map((venue) => {
          const row = asRecord(venues[venue]);
          return (
            <Panel key={venue} title={`${venue} (isolated)`}>
              <div className="grid grid-cols-2 gap-2">
                <Metric label="Trades" value={fmt(row.trades, 0)} />
                <Metric label="Win rate" value={fmt(row.win_rate, 1)} />
                <Metric label="PF" value={fmt(row.profit_factor, 2)} />
                <Metric label="PnL" value={fmt(row.pnl, 2)} />
              </div>
            </Panel>
          );
        })}
      </div>

      <Panel title="Capital scaling advisor">
        <p className="text-sm text-[var(--fg-muted)]">{str(capital.message)}</p>
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Metric label="Current" value={`$${fmt(capital.current_capital, 0)}`} />
          <Metric
            label="Suggested next"
            value={
              capital.suggested_next_capital == null
                ? "—"
                : `$${fmt(capital.suggested_next_capital, 0)}`
            }
          />
          <Metric
            label="Eligible"
            value={capital.eligible === true ? "Yes*" : "No"}
          />
          <Metric
            label="Auto-applied"
            value={String(capital.auto_applied === true)}
          />
        </div>
        <ul className="mt-2 list-inside list-disc text-xs text-[var(--fg-subtle)]">
          {asList(capital.reasons).map((r, i) => (
            <li key={`r-${i}`}>{str(r)}</li>
          ))}
          {asList(capital.blockers).map((r, i) => (
            <li key={`b-${i}`} className="text-[var(--danger)]">
              {str(r)}
            </li>
          ))}
        </ul>
      </Panel>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Go Live components">
          <ul className="space-y-1 text-sm">
            {Object.entries(components).map(([k, v]) => (
              <li key={k} className="flex justify-between font-mono text-xs">
                <span>{k}</span>
                <span>{fmt(v, 1)}</span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Smoke history">
          {smokeRecent.length === 0 ? (
            <p className="text-sm text-[var(--fg-subtle)]">No smoke runs yet.</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {smokeRecent.map((run) => (
                <li key={str(run.id)} className="flex justify-between gap-2">
                  <span className="font-mono text-xs">{str(run.at)}</span>
                  <Badge tone={statusTone(str(run.overall))}>{str(run.overall)}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Documentation">
        <ul className="space-y-1 text-sm">
          {docs.map((doc) => (
            <li key={str(doc.id)} className="font-mono text-xs text-[var(--fg-muted)]">
              {str(doc.title)} · {str(doc.path)}
            </li>
          ))}
        </ul>
        {reports.length > 0 && (
          <p className="mt-2 text-xs text-[var(--fg-subtle)]">
            Stored reports: {reports.length}
          </p>
        )}
      </Panel>
    </div>
  );
}
