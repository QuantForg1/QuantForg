"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["growth-intelligence-status"],
    queryFn: () => growthApi.status(),
  });
  const refresh = () =>
    void queryClient.invalidateQueries({ queryKey: ["growth-intelligence-status"] });
  const stop = useMutation({
    mutationFn: (engaged: boolean) => growthApi.setEmergencyStop(engaged),
    onSuccess: refresh,
  });
  const run = useMutation({
    mutationFn: (jobId: string) => growthApi.runJob(jobId),
    onSuccess: refresh,
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
  const automation = asRecord(payload.automation);
  const jobs = asList(automation.jobs);
  const history = asList(automation.history);
  const builtAt = str(payload.status_document_built_at, "");
  const stopped = automation.emergency_stop !== false;

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

      <section className="mb-6 rounded-[var(--radius-os)] border border-[var(--border)] p-4" aria-labelledby="growth-automation">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="growth-automation" className="text-sm font-semibold text-[var(--fg)]">
            Emergency stop
          </h2>
          <span className="text-xs font-medium uppercase tracking-wide text-[var(--accent)]">
            {stopped ? "Stopped" : "Released"}
          </span>
        </div>
        <p className="mt-1 text-sm leading-relaxed text-[var(--fg-muted)]">
          {str(automation.note, "Growth checks are not on the trading scheduler.")}
          {" "}Ads stay stopped. Releasing the stop only allows an owner to request a check.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" className="rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 text-sm text-[var(--fg)] disabled:opacity-50" disabled={stop.isPending || stopped} onClick={() => stop.mutate(true)}>
            Engage emergency stop
          </button>
          <button type="button" className="rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 text-sm text-[var(--fg)] disabled:opacity-50" disabled={stop.isPending || !stopped} onClick={() => stop.mutate(false)}>
            Release stop for checks
          </button>
        </div>
        <ul className="mt-4 space-y-2">
          {jobs.map((row) => {
            const job = asRecord(row);
            const jobId = str(job.id);
            return (
              <li key={jobId} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span>{str(job.title, jobId)}<span className="text-[var(--fg-muted)]"> · {str(job.source, "source unavailable")}</span></span>
                <button type="button" className="rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-1 text-sm text-[var(--accent)] disabled:opacity-50" disabled={run.isPending || stopped || !jobId} onClick={() => run.mutate(jobId)}>
                  Run check
                </button>
              </li>
            );
          })}
        </ul>
        <p className="mt-3 text-xs text-[var(--fg-subtle)]">
          Recent checks: {history.length}. A stopped run does not execute. This log is process memory.
        </p>
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
