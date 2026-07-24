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

export function ResearchPlatformWorkspace() {
  const qc = useQueryClient();
  const dash = useQuery({
    queryKey: ["research-platform-v10"],
    queryFn: iteReliabilityApi.researchPlatform,
    retry: false,
    refetchInterval: 30_000,
  });

  const reportMut = useMutation({
    mutationFn: (period: "daily" | "weekly" | "monthly") =>
      iteReliabilityApi.generateInstitutionalReport(period),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["research-platform-v10"] }),
  });

  if (dash.isLoading) return <DeskSkeleton rows={7} />;
  if (dash.isError) {
    return (
      <DeskError message="Research Platform unavailable (OWNER/ADMIN · /ite/reliability/research-platform)." />
    );
  }

  const d = asRecord(dash.data);
  const guidance = asRecord(d.guidance);
  const safeguards = asRecord(d.safeguards);
  const expSummary = asRecord(d.experiments_summary);
  const byStatus = asRecord(expSummary.by_status);
  const active = asList(d.active_experiments).map(asRecord);
  const results = asList(d.research_results).map(asRecord);
  const variants = asList(d.research_variants).map(asRecord);
  const approved = asList(d.approved_models).map(asRecord);
  const pendingModels = asList(d.pending_models).map(asRecord);
  const pendingReviews = asList(d.pending_reviews).map(asRecord);
  const rankings = asList(d.strategy_rankings).map(asRecord);
  const optQueue = asList(d.optimization_queue).map(asRecord);
  const releases = asList(d.release_history).map(asRecord);
  const reports = asList(d.reports).map(asRecord);
  const audit = asList(d.audit_trail).map(asRecord);
  const insights = asList(d.continuous_improvement).map(asRecord);
  const docs = asList(d.generated_docs).map(asRecord);

  return (
    <div className="space-y-3">
      <Panel title="Evidence guidance">
        <p className="text-sm text-[var(--fg-muted)]">{str(guidance.message)}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge tone="warning">
            min {str(guidance.min_days, "14")}d · prefer {str(guidance.recommended_days, "28")}d
          </Badge>
          <Badge tone="success">
            auto_promote={String(safeguards.auto_promote_to_production === true)}
          </Badge>
          <Badge tone="success">
            research_isolated={String(safeguards.research_isolated_from_live !== false)}
          </Badge>
        </div>
      </Panel>

      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Experiments" value={str(expSummary.total, "0")} />
        <Metric label="Running" value={str(byStatus.Running, "0")} />
        <Metric label="Approved models" value={str(approved.length)} />
        <Metric label="Pending reviews" value={str(pendingReviews.length)} />
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Active experiments">
          {active.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No running experiments.</p>
          ) : (
            <div className="max-h-48 space-y-1 overflow-auto font-mono text-[11px]">
              {active.map((e) => (
                <div key={str(e.id)} className="border-b border-[var(--border)]/40 py-1 last:border-0">
                  {str(e.name)} · {str(e.author)} · n={str(e.sample_size)}
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Research variants (isolated)">
          {variants.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No research variants yet.</p>
          ) : (
            <div className="max-h-48 space-y-1 overflow-auto font-mono text-[11px]">
              {variants.map((v) => (
                <div key={str(v.id)} className="border-b border-[var(--border)]/40 py-1 last:border-0">
                  {str(v.name)} · {str(v.author)} · affects_production=false
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <Panel title="Approved models">
          {approved.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">None approved.</p>
          ) : (
            <div className="max-h-40 overflow-auto font-mono text-[11px]">
              {approved.map((m) => (
                <div key={str(m.id)}>
                  {str(m.version)} · {str(m.author)}
                </div>
              ))}
            </div>
          )}
          <p className="mt-2 text-[10px] text-[var(--fg-muted)]">
            Pending: {pendingModels.length}
          </p>
        </Panel>

        <Panel title="Pending promotion reviews">
          {pendingReviews.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No pending promotions.</p>
          ) : (
            <div className="max-h-40 overflow-auto font-mono text-[11px]">
              {pendingReviews.map((p) => (
                <div key={str(p.id)}>
                  {str(p.artifact_type)} {str(p.from_stage)}→{str(p.to_stage)}
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Optimization queue">
          {optQueue.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">Empty.</p>
          ) : (
            <div className="max-h-40 overflow-auto font-mono text-[11px]">
              {optQueue.slice(0, 10).map((r) => (
                <div key={str(r.id)}>
                  {str(r.target)} · score {fmt(r.best_score, 2)} · applied=false
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Strategy rankings">
          {rankings.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No strategy metrics yet.</p>
          ) : (
            <div className="font-mono text-[11px]">
              {rankings.map((s) => (
                <div key={str(s.strategy)} className="flex justify-between">
                  <span>{str(s.strategy)}</span>
                  <span>
                    WR {fmt(s.win_rate, 1)}% · PF {fmt(s.profit_factor, 2)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Research results (completed)">
          {results.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">None completed.</p>
          ) : (
            <div className="max-h-40 overflow-auto font-mono text-[11px]">
              {results.map((e) => (
                <div key={str(e.id)}>
                  {str(e.name)} · {str(e.success_criteria)}
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Institutional reports">
        <div className="mb-2 flex flex-wrap gap-2">
          {(["daily", "weekly", "monthly"] as const).map((p) => (
            <Button
              key={p}
              size="sm"
              variant="outline"
              disabled={reportMut.isPending}
              onClick={() => reportMut.mutate(p)}
            >
              Generate {p}
            </Button>
          ))}
        </div>
        {reports.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">No reports generated yet.</p>
        ) : (
          <div className="max-h-32 overflow-auto font-mono text-[11px]">
            {reports.map((r) => (
              <div key={str(r.id)}>
                {str(r.period)} · {str(r.generated_at).slice(0, 19)} · csv/pdf ready
              </div>
            ))}
          </div>
        )}
      </Panel>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Release history">
          {releases.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No promotions yet.</p>
          ) : (
            <div className="max-h-40 overflow-auto font-mono text-[11px]">
              {releases.map((r) => (
                <div key={str(r.id)}>
                  {str(r.status)} · {str(r.from_stage)}→{str(r.to_stage)} ·{" "}
                  {str(r.artifact_type)}
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Audit trail">
          {audit.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No audit events.</p>
          ) : (
            <div className="max-h-40 overflow-auto font-mono text-[11px]">
              {audit.slice(0, 20).map((a) => (
                <div key={str(a.id)}>
                  {str(a.at).slice(11, 19)} {str(a.user)} · {str(a.category)}/{str(a.key)}
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Continuous improvement (advisory)">
        {insights.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">No insights.</p>
        ) : (
          <div className="max-h-40 space-y-1 overflow-auto text-[11px]">
            {insights.map((i) => (
              <div key={str(i.id)} className="border-b border-[var(--border)]/40 py-1 last:border-0">
                <Badge tone="neutral">{str(i.kind)}</Badge> {str(i.message)}{" "}
                <span className="text-[var(--fg-muted)]">auto_deploy=false</span>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Generated documentation">
        {docs.length === 0 ? (
          <p className="text-sm text-[var(--fg-muted)]">No docs yet.</p>
        ) : (
          <div className="max-h-48 space-y-2 overflow-auto font-mono text-[10px] text-[var(--fg-muted)]">
            {docs.map((doc, idx) => (
              <pre key={`${str(doc.type)}-${idx}`} className="whitespace-pre-wrap border border-[var(--border)]/40 p-2">
                {str(doc.markdown)}
              </pre>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
