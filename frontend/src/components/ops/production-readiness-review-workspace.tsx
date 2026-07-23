"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function statusTone(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "PASS" || status === "GREEN") return "success";
  if (status === "WARNING" || status === "YELLOW") return "warning";
  if (status === "FAIL" || status === "RED") return "danger";
  return "neutral";
}

function ScoreBanner({
  score,
  recommendation,
  summary,
}: {
  score: number;
  recommendation: string;
  summary: string;
}) {
  const tone =
    score >= 85 ? "success" : score >= 65 ? "warning" : "danger";
  return (
    <div
      className={cn(
        "border px-4 py-4",
        tone === "success" && "border-[var(--success)]/40 bg-[var(--success)]/10",
        tone === "warning" && "border-[var(--warning)]/40 bg-[var(--warning)]/10",
        tone === "danger" && "border-[var(--danger)]/40 bg-[var(--danger)]/10",
      )}
    >
      <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
        Overall Production Readiness Score
      </p>
      <p className="mt-1 text-[28px] font-semibold tracking-tight text-[var(--fg)]">
        {Number.isFinite(score) ? score.toFixed(1) : "—"}
        <span className="text-[14px] font-normal text-[var(--fg-muted)]">
          {" "}
          / 100
        </span>
      </p>
      <p className="mt-2 text-[14px] font-medium text-[var(--fg)]">
        {recommendation || "—"}
      </p>
      <p className="mt-1 text-[12px] text-[var(--fg-muted)]">{summary}</p>
    </div>
  );
}

function ChecklistTable({ rows }: { rows: Record<string, unknown>[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-left text-[12px]">
        <thead>
          <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            <th className="py-2 pr-3 font-medium">Status</th>
            <th className="py-2 pr-3 font-medium">Section</th>
            <th className="py-2 pr-3 font-medium">Subsystem</th>
            <th className="py-2 font-medium">Detail</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => {
            const status = str(row.status, "WARNING");
            return (
              <tr
                key={`${str(row.subsystem)}-${idx}`}
                className="border-b border-[var(--border)]/60"
              >
                <td className="py-2 pr-3">
                  <Badge tone={statusTone(status)}>{status}</Badge>
                </td>
                <td className="py-2 pr-3 font-mono text-[11px] text-[var(--fg-muted)]">
                  {str(row.section, "—")}
                </td>
                <td className="py-2 pr-3 text-[var(--fg)]">
                  {str(row.subsystem, "—")}
                </td>
                <td className="py-2 text-[var(--fg-muted)]">
                  {str(row.detail, "—")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RiskList({
  title,
  items,
}: {
  title: string;
  items: Record<string, unknown>[];
}) {
  if (!items.length) {
    return (
      <OpsPanel title={title}>
        <p className="text-[12px] text-[var(--fg-subtle)]">None recorded.</p>
      </OpsPanel>
    );
  }
  return (
    <OpsPanel title={title}>
      <ul className="space-y-3">
        {items.map((r, i) => (
          <li
            key={`${str(r.id)}-${i}`}
            className="border border-[var(--border)]/70 px-3 py-2"
          >
            <p className="text-[13px] font-medium text-[var(--fg)]">
              {str(r.title, "Risk")}
            </p>
            <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
              Impact · {str(r.impact, "—")}
            </p>
            <p className="text-[11px] text-[var(--fg-muted)]">
              Likelihood · {str(r.likelihood, "—")}
            </p>
            <p className="text-[11px] text-[var(--fg-subtle)]">
              Mitigation · {str(r.mitigation, "—")}
            </p>
          </li>
        ))}
      </ul>
    </OpsPanel>
  );
}

export function ProductionReadinessReviewWorkspace() {
  const q = useQuery({
    queryKey: ["ops", "production-readiness-review"],
    queryFn: () => iteOpsApi.productionReadinessReview(false),
    refetchInterval: 60_000,
  });

  if (q.isLoading) {
    return <DeskSkeleton rows={8} />;
  }
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Production Readiness Review unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }

  const root = asRecord(q.data);
  const sections = asRecord(root.sections);
  const executive = asRecord(sections.executive_summary);
  const checklist = asList(sections.production_checklist).map((x) =>
    asRecord(x),
  );
  const risks = asRecord(sections.risk_register);
  const score = num(
    root.overall_production_readiness_score ??
      executive.overall_production_readiness_score,
    NaN,
  );
  const recommendation = str(
    root.recommendation ?? executive.recommendation,
    "—",
  );
  const summary = str(root.summary ?? executive.summary, "");
  const counts = asRecord(executive.counts);

  const sectionKeys = [
    "architecture",
    "security",
    "reliability",
    "trading",
    "data_integrity",
    "performance",
    "operations",
  ] as const;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">INSTITUTIONAL PRR</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">ENGINES UNCHANGED</Badge>
        <Button size="sm" variant="secondary" onClick={() => void q.refetch()}>
          Re-run audit
        </Button>
        <Button asChild size="sm" variant="outline">
          <Link href="/production-readiness">Production Readiness</Link>
        </Button>
        <Button asChild size="sm" variant="outline">
          <Link href="/portfolio-analytics">Portfolio Analytics</Link>
        </Button>
      </div>

      <p className="text-[11px] text-[var(--fg-subtle)]">
        Advisory audit only — never modifies strategy, risk, safety, OMS,
        execution, auto trading, or thresholds.
      </p>

      <ScoreBanner
        score={score}
        recommendation={recommendation}
        summary={summary}
      />

      <div className="grid gap-3 sm:grid-cols-4">
        <MetricCard label="PASS" value={String(num(counts.pass, 0))} />
        <MetricCard label="WARNING" value={String(num(counts.warning, 0))} />
        <MetricCard label="FAIL" value={String(num(counts.fail, 0))} />
        <MetricCard label="Checks" value={String(num(counts.total, checklist.length))} />
      </div>

      <OpsPanel title="Audit sections">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {sectionKeys.map((key) => {
            const sec = asRecord(sections[key]);
            const checks = asList(sec.checks).map((c) => asRecord(c));
            const fails = checks.filter((c) => str(c.status) === "FAIL").length;
            const warns = checks.filter((c) => str(c.status) === "WARNING").length;
            const passes = checks.filter((c) => str(c.status) === "PASS").length;
            return (
              <div
                key={key}
                className="border border-[var(--border)] px-3 py-3"
              >
                <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                  {key.replaceAll("_", " ")}
                </p>
                <p className="mt-2 font-mono text-[12px] text-[var(--fg)]">
                  {passes}P · {warns}W · {fails}F
                </p>
              </div>
            );
          })}
        </div>
      </OpsPanel>

      <OpsPanel title="Production checklist">
        <ChecklistTable rows={checklist} />
      </OpsPanel>

      <div className="grid gap-4 lg:grid-cols-2">
        <RiskList
          title="Critical risks"
          items={asList(risks.critical).map((x) => asRecord(x))}
        />
        <RiskList
          title="High risks"
          items={asList(risks.high).map((x) => asRecord(x))}
        />
        <RiskList
          title="Medium risks"
          items={asList(risks.medium).map((x) => asRecord(x))}
        />
        <RiskList
          title="Low risks"
          items={asList(risks.low).map((x) => asRecord(x))}
        />
      </div>
    </div>
  );
}
