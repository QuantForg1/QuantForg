"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/page-header";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { growthApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";
import { iteOpsAccessDeniedMessage } from "@/lib/auth/ite-ops-access";

function statusLabel(status: string): string {
  if (status === "not_connected") return "Not connected";
  if (status === "unavailable") return "Unavailable";
  if (status === "stopped") return "Stopped";
  return "Unavailable";
}

export default function GrowthIntelligencePage() {
  const { user } = useAuth();
  const query = useQuery({
    queryKey: ["growth-intelligence-status"],
    queryFn: () => growthApi.status(),
  });

  if (query.isLoading) return <DeskSkeleton variant="page" />;

  if (query.isError || !query.data) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(user, query.error, "Growth Intelligence")}
        onRetry={() => void query.refetch()}
      />
    );
  }

  const payload = asRecord(query.data);
  const catalog = asRecord(payload.catalog);
  const plans = asList(catalog.plans);
  const sections = asList(payload.sections);
  const builtAt = str(payload.status_document_built_at, "");

  return (
    <div className="min-w-0">
      <PageHeader
        eyebrow="Owner · read only"
        title="Growth Intelligence"
        description="Integration status for acquisition and subscriptions. Missing sources stay blank. This screen does not publish, spend, or change accounts."
        status={
          <p className="text-xs text-[var(--fg-subtle)]">
            Ads kill switch: {statusLabel(str(payload.ads_kill_switch, "stopped"))}
            {builtAt ? ` · Status document built ${builtAt}` : ""}
          </p>
        }
      />

      <section
        className="mb-6 rounded-[var(--radius-os)] border border-[var(--border)] p-4"
        aria-labelledby="growth-catalog"
      >
        <h2 id="growth-catalog" className="text-sm font-semibold text-[var(--fg)]">
          Published software prices
        </h2>
        <p className="mt-1 text-sm leading-relaxed text-[var(--fg-muted)]">
          {str(catalog.note, "Catalog only.")} Source: {str(catalog.source, "billing catalog")}.
          Trial offered: {catalog.trial_offered === false ? "no" : "unknown"}.
        </p>
        <ul className="mt-3 space-y-1 text-sm">
          {plans.map((row) => {
            const plan = asRecord(row);
            const price = plan.monthly_price_usd;
            return (
              <li key={str(plan.id)} className="flex flex-wrap justify-between gap-2">
                <span>{str(plan.name, str(plan.id, "Plan"))}</span>
                <span className="text-[var(--fg-muted)]">
                  {typeof price === "number" ? `$${price} / month` : "Unavailable"}
                </span>
              </li>
            );
          })}
        </ul>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        {sections.map((row) => {
          const section = asRecord(row);
          const metrics = asList(section.metrics);
          return (
            <section
              key={str(section.id)}
              className="min-w-0 rounded-[var(--radius-os)] border border-[var(--border)] p-4"
              aria-labelledby={`growth-${str(section.id)}`}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 id={`growth-${str(section.id)}`} className="text-sm font-semibold">
                  {str(section.title, "Section")}
                </h2>
                <span className="text-xs font-medium uppercase tracking-wide text-[var(--accent)]">
                  {statusLabel(str(section.status))}
                </span>
              </div>
              <dl className="mt-3 space-y-3">
                {metrics.map((metricRow) => {
                  const metric = asRecord(metricRow);
                  return (
                    <div key={str(metric.id)}>
                      <dt className="text-sm text-[var(--fg)]">{str(metric.label)}</dt>
                      <dd className="text-sm text-[var(--fg-muted)]">
                        {statusLabel(str(metric.status))}
                        {typeof metric.reason === "string" && metric.reason
                          ? ` — ${metric.reason}`
                          : ""}
                      </dd>
                    </div>
                  );
                })}
              </dl>
            </section>
          );
        })}
      </div>
    </div>
  );
}
