"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { aqsApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/ai-quant-scientist", label: "Dashboard" },
  { href: "/ai-quant-scientist/feed", label: "Research Feed" },
  { href: "/ai-quant-scientist/recommendations", label: "Recommendations" },
  { href: "/ai-quant-scientist/patterns", label: "Patterns" },
  { href: "/ai-quant-scientist/compare", label: "Comparator" },
  { href: "/ai-quant-scientist/explain", label: "Explainability" },
  { href: "/ai-quant-scientist/reports", label: "Reports" },
] as const;

export function AqsNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/ai-quant-scientist"
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

function useAqsDashboard() {
  return useQuery({
    queryKey: ["aqs", "dashboard"],
    queryFn: () => aqsApi.dashboard(),
    refetchInterval: 60_000,
  });
}

export function AqsDashboardWorkspace() {
  const q = useAqsDashboard();
  const [question, setQuestion] = useState("Which regime produces highest PF?");
  const [answer, setAnswer] = useState<Record<string, unknown> | null>(null);
  const ask = useMutation({
    mutationFn: () => aqsApi.ask(question),
    onSuccess: (data) => setAnswer(asRecord(data)),
  });

  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "AQS unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }

  const root = asRecord(q.data);
  const scores = asRecord(root.institutional_scores);
  const sections = asRecord(root.sections);
  const feed = asList(root.feed).map(asRecord);
  const availability = asRecord(asRecord(root.context).availability);

  return (
    <div className="space-y-4">
      <AqsNav />
      <div className="flex flex-wrap gap-2">
        <Badge tone="neutral">AI QUANT SCIENTIST</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">RECOMMENDATIONS ONLY</Badge>
        <Badge tone="warning">HUMANS DECIDE</Badge>
      </div>
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Studies IRL, IDW, replay, portfolio, regimes, and reports. Never modifies
        production, thresholds, strategy, risk, safety, OMS, or gateway.
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Research confidence"
          value={str(scores.research_confidence_score, "—")}
        />
        <MetricCard
          label="Evidence strength"
          value={str(scores.evidence_strength, "—")}
        />
        <MetricCard
          label="Statistical reliability"
          value={str(scores.statistical_reliability, "—")}
        />
        <MetricCard
          label="Recommendation strength"
          value={str(scores.recommendation_strength, "—")}
        />
      </div>

      <OpsPanel title="Source availability">
        <div className="flex flex-wrap gap-2">
          {Object.entries(availability).map(([k, v]) => (
            <Badge key={k} tone={v ? "success" : "warning"}>
              {k}:{v ? "ok" : "—"}
            </Badge>
          ))}
        </div>
      </OpsPanel>

      <OpsPanel title="Natural language research">
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            aria-label="Ask AQS"
            className="flex-1 border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px]"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <Button
            size="sm"
            variant="secondary"
            disabled={ask.isPending || !question.trim()}
            onClick={() => ask.mutate()}
          >
            Ask
          </Button>
        </div>
        {answer ? (
          <div className="mt-3 border border-[var(--border)] px-3 py-3 text-[13px]">
            <p className="text-[var(--fg)]">{str(answer.answer)}</p>
            <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
              Advisory only — never modifies production.
            </p>
          </div>
        ) : null}
      </OpsPanel>

      <OpsPanel title="Research feed">
        <ul className="space-y-2">
          {feed.slice(0, 8).map((r) => (
            <li
              key={str(r.id)}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge tone="neutral">{str(r.type)}</Badge>
              <Badge tone="warning">{str(r.status)}</Badge>
              <span>{str(r.title)}</span>
            </li>
          ))}
        </ul>
        <div className="mt-3">
          <Button asChild size="sm" variant="outline">
            <Link href="/ai-quant-scientist/recommendations">
              Recommendation center
            </Link>
          </Button>
        </div>
      </OpsPanel>

      <OpsPanel title="Recommendation center snapshot">
        <div className="grid gap-2 sm:grid-cols-4">
          <MetricCard
            label="Open"
            value={String(asList(asRecord(sections.recommendation_center).open).length)}
          />
          <MetricCard
            label="Accepted"
            value={String(
              asList(asRecord(sections.recommendation_center).accepted).length,
            )}
          />
          <MetricCard
            label="Rejected"
            value={String(
              asList(asRecord(sections.recommendation_center).rejected).length,
            )}
          />
          <MetricCard
            label="Archived"
            value={String(
              asList(asRecord(sections.recommendation_center).archived).length,
            )}
          />
        </div>
      </OpsPanel>
    </div>
  );
}

export function AqsFeedWorkspace() {
  const q = useAqsDashboard();
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Feed unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const feed = asList(asRecord(q.data).feed).map(asRecord);
  return (
    <div className="space-y-4">
      <AqsNav />
      <OpsPanel title="Research feed">
        <ul className="space-y-3">
          {feed.map((r) => (
            <li key={str(r.id)} className="border border-[var(--border)] px-3 py-3">
              <div className="flex flex-wrap gap-2">
                <Badge tone="neutral">{str(r.type)}</Badge>
                <Badge tone="warning">{str(r.status)}</Badge>
              </div>
              <p className="mt-2 text-[14px] text-[var(--fg)]">{str(r.title)}</p>
              <p className="mt-1 text-[12px] text-[var(--fg-muted)]">{str(r.summary)}</p>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function AqsRecommendationsWorkspace() {
  const qc = useQueryClient();
  const q = useAqsDashboard();
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      aqsApi.setStatus(id, status),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["aqs"] });
    },
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Recommendations unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const rows = asList(asRecord(q.data).recommendations).map(asRecord);
  return (
    <div className="space-y-4">
      <AqsNav />
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Accepted never changes production automatically — governance remains human.
      </p>
      <OpsPanel title="Recommendation center">
        <ul className="space-y-3">
          {rows.map((r) => (
            <li key={str(r.id)} className="border border-[var(--border)] px-3 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="neutral">{str(r.type)}</Badge>
                <Badge tone="warning">{str(r.status)}</Badge>
                <span className="text-[13px] font-medium text-[var(--fg)]">
                  {str(r.title)}
                </span>
              </div>
              <p className="mt-1 text-[12px] text-[var(--fg-muted)]">{str(r.summary)}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {["Open", "Accepted", "Rejected", "Archived"].map((s) => (
                  <Button
                    key={s}
                    size="sm"
                    variant={str(r.status) === s ? "secondary" : "outline"}
                    disabled={setStatus.isPending}
                    onClick={() =>
                      setStatus.mutate({ id: str(r.id), status: s })
                    }
                  >
                    {s}
                  </Button>
                ))}
              </div>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function AqsPatternsWorkspace() {
  const q = useAqsDashboard();
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Patterns unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const patterns = asList(asRecord(q.data).patterns).map(asRecord);
  const weaknesses = asList(asRecord(q.data).weaknesses).map(asRecord);
  return (
    <div className="space-y-4">
      <AqsNav />
      <OpsPanel title="Pattern explorer">
        <ul className="space-y-2">
          {patterns.map((p) => (
            <li key={str(p.id)} className="border border-[var(--border)]/70 px-3 py-2 text-[12px]">
              <Badge tone="neutral">{str(p.kind)}</Badge>{" "}
              <span className="text-[var(--fg)]">{str(p.title)}</span>
              <p className="mt-1 text-[var(--fg-muted)]">{str(p.summary)}</p>
            </li>
          ))}
        </ul>
      </OpsPanel>
      <OpsPanel title="Weakness detection">
        <ul className="space-y-2">
          {weaknesses.map((w) => (
            <li key={str(w.id)} className="border border-[var(--border)]/70 px-3 py-2 text-[12px]">
              <Badge tone="danger">{str(w.kind)}</Badge>{" "}
              <span>{str(w.title)}</span>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function AqsCompareWorkspace() {
  const q = useAqsDashboard();
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Comparator unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const comparison = asRecord(asRecord(q.data).comparison);
  const production = asRecord(comparison.production);
  const candidates = asList(comparison.candidates).map(asRecord);
  const sensitivity = asRecord(asRecord(q.data).sensitivity);
  const stable = asRecord(sensitivity.most_stable);
  return (
    <div className="space-y-4">
      <AqsNav />
      <OpsPanel title="Strategy comparator">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard label="Prod PF" value={str(production.profit_factor, "—")} />
          <MetricCard label="Prod WR" value={str(production.win_rate, "—")} />
          <MetricCard label="Prod DD%" value={str(production.maximum_drawdown_pct, "—")} />
          <MetricCard
            label="PF Δ%"
            value={str(comparison.profit_factor_difference_pct, "—")}
          />
        </div>
        <ul className="mt-3 space-y-2 text-[12px]">
          {candidates.map((c) => (
            <li key={str(c.uuid)} className="flex justify-between gap-2 border-b border-[var(--border)]/40 py-2">
              <span>{str(c.name)}</span>
              <span className="font-mono text-[var(--fg-muted)]">
                PF {str(c.profit_factor, "—")} · composite {str(c.composite_score, "—")}
              </span>
            </li>
          ))}
        </ul>
      </OpsPanel>
      <OpsPanel title="Parameter sensitivity (research only)">
        <p className="text-[12px] text-[var(--fg-muted)]">
          Most stable research band · Q={str(stable.quality, "—")} · C=
          {str(stable.confluence, "—")} · stability={str(stable.stability_score, "—")}
        </p>
        <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
          Never changes live thresholds.
        </p>
      </OpsPanel>
    </div>
  );
}

export function AqsExplainWorkspace() {
  const q = useAqsDashboard();
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Explainability unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const rows = asList(asRecord(asRecord(q.data).sections).explainability).map(
    asRecord,
  );
  return (
    <div className="space-y-4">
      <AqsNav />
      <OpsPanel title="Explainability viewer">
        <ul className="space-y-3">
          {rows.map((r) => {
            const ex = asRecord(r.explainability);
            return (
              <li key={str(r.id)} className="border border-[var(--border)] px-3 py-3 text-[12px]">
                <p className="text-[13px] font-medium text-[var(--fg)]">{str(r.title)}</p>
                <p className="mt-2 text-[var(--fg-muted)]">
                  Confidence · {str(ex.confidence, "—")} · Sample ·{" "}
                  {str(ex.historical_sample_size, "—")}
                </p>
                <p className="mt-1">Evidence · {asList(ex.evidence).map(String).join("; ")}</p>
                <p className="mt-1 text-[var(--fg-subtle)]">
                  Counter · {asList(ex.counter_arguments).map(String).join("; ")}
                </p>
                <p className="mt-1 text-[var(--fg-subtle)]">
                  Risks · {asList(ex.potential_risks).map(String).join("; ")}
                </p>
              </li>
            );
          })}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function AqsReportsWorkspace() {
  const q = useAqsDashboard();
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Reports unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const reports = asList(
    asRecord(asRecord(q.data).sections).executive_reports,
  ).map(asRecord);
  const latest = asRecord(asRecord(q.data).latest_report);
  return (
    <div className="space-y-4">
      <AqsNav />
      <OpsPanel title="Latest executive report">
        <p className="text-[14px] font-medium text-[var(--fg)]">{str(latest.title)}</p>
        <p className="mt-2 text-[13px] text-[var(--fg-muted)]">
          {str(latest.executive_summary)}
        </p>
        <p className="mt-2 font-mono text-[11px] text-[var(--fg-subtle)]">
          Confidence · {str(latest.confidence, "—")}
        </p>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-[12px] text-[var(--fg-muted)]">
          {asList(latest.findings)
            .map(String)
            .slice(0, 8)
            .map((f) => (
              <li key={f}>{f}</li>
            ))}
        </ul>
      </OpsPanel>
      <OpsPanel title="Report archive">
        <ul className="space-y-2 text-[12px]">
          {reports.map((r) => (
            <li key={str(r.report_id)} className="border-b border-[var(--border)]/50 py-2">
              {str(r.title)} · {str(r.created_at, "").slice(0, 19)}
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}
