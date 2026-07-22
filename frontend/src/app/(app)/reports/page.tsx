"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { WorkspacePage } from "@/components/layout/workspace-page";
import { ecosystemApi, executionApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";

type Period = "daily" | "weekly" | "monthly";

export default function ReportsPage() {
  const [period, setPeriod] = useState<Period>("daily");

  const reportQ = useQuery({
    queryKey: ["ecosystem-reports", period],
    queryFn: () => ecosystemApi.reports(period),
    staleTime: 30_000,
    retry: false,
  });

  const optQ = useQuery({
    queryKey: ["execution-optimization"],
    queryFn: () => executionApi.optimization(200),
    staleTime: 30_000,
    retry: false,
  });

  const report = asRecord(reportQ.data);
  const sections = asRecord(report.sections);
  const opt = asRecord(optQ.data);
  const known = asList(sections.known_issues);
  const recs = asList(sections.recommendations);

  return (
    <WorkspacePage
      title="Reports"
      description="Daily, weekly, and monthly production reports from live fills and ops state."
      icon={FileText}
      actionLabel="Open analytics"
      actionHref="/journal/analytics"
      actions={
        <div className="flex gap-1">
          {(["daily", "weekly", "monthly"] as const).map((p) => (
            <Button
              key={p}
              size="sm"
              variant={period === p ? "default" : "outline"}
              onClick={() => setPeriod(p)}
            >
              {p}
            </Button>
          ))}
        </div>
      }
    >
      {reportQ.isLoading ? <DeskSkeleton rows={5} /> : null}
      {reportQ.isError ? (
        <DeskError
          message={
            reportQ.error instanceof ApiError
              ? reportQ.error.message
              : "Reports unavailable"
          }
        />
      ) : null}
      {!reportQ.isLoading && !reportQ.isError ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
            <span className="text-sm font-medium">
              {str(report.title, `${period} report`)}
            </span>
            <Badge tone="neutral" className="text-[9px] uppercase">
              {str(report.period, period)}
            </Badge>
            <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
              {str(report.generated_at, "—").replace("T", " ").slice(0, 19)}
            </span>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {(
              [
                ["Performance", sections.performance],
                ["Risk", asRecord(opt.risk_trends).trends || sections.risk],
                [
                  "Execution",
                  asRecord(opt.execution).metrics || sections.execution,
                ],
                ["Reliability", sections.reliability],
              ] as const
            ).map(([title, body]) => (
              <section
                key={title}
                className="border border-[var(--border)] bg-[var(--surface)] p-3"
              >
                <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                  {title}
                </h2>
                {!body || Object.keys(asRecord(body)).length === 0 ? (
                  <DeskEmpty
                    icon={FileText}
                    title="Unavailable"
                    description="No live facts for this section yet."
                  />
                ) : (
                  <pre className="max-h-48 overflow-auto font-mono text-[10px] text-[var(--fg-muted)]">
                    {JSON.stringify(body, null, 2)}
                  </pre>
                )}
              </section>
            ))}
          </div>

          <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
            <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
              Known issues
            </h2>
            <ul className="list-disc space-y-1 pl-4 text-xs text-[var(--fg-muted)]">
              {known.map((item, i) => (
                <li key={i}>{str(item)}</li>
              ))}
            </ul>
          </section>

          <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
            <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
              Recommendations
            </h2>
            <ul className="list-disc space-y-1 pl-4 text-xs text-[var(--fg-muted)]">
              {recs.map((item, i) => (
                <li key={i}>{str(item)}</li>
              ))}
            </ul>
          </section>

          {asRecord(opt.broker_quality).score != null ? (
            <p className="font-mono text-[10px] text-[var(--fg-subtle)]">
              Broker quality score: {str(asRecord(opt.broker_quality).score)}
            </p>
          ) : null}
        </div>
      ) : null}
    </WorkspacePage>
  );
}
