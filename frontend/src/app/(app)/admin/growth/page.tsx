"use client";

import { useState } from "react";
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
  const [draftTitle, setDraftTitle] = useState("");
  const [draftBody, setDraftBody] = useState("");
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
  const draft = useMutation({
    mutationFn: () => growthApi.saveDraft(draftTitle, draftBody),
    onSuccess: () => {
      setDraftTitle("");
      setDraftBody("");
      refresh();
    },
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
  const drafts = asList(automation.drafts);
  const history = asList(automation.history);
  const permissions = asRecord(automation.permissions);
  const builtAt = str(payload.status_document_built_at, "");
  const stopped = automation.emergency_stop !== false;

  return (
    <div className="min-w-0">
      <PageHeader
        eyebrow="Owner"
        title="Growth Intelligence"
        description="Missing sources stay blank. Checks do not publish, spend, email, or change accounts. Releasing the stop does not enable advertising."
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
            Automation health
          </h2>
          <span className="text-xs font-medium uppercase tracking-wide text-[var(--accent)]">
            {stopped ? "Stopped" : "Released"}
          </span>
        </div>
        <p className="mt-1 text-sm leading-relaxed text-[var(--fg-muted)]">
          {str(automation.note, "No growth job is registered on the trading scheduler.")}
          {" "}Clock: {asRecord(automation.clock).attached === false ? "not attached" : "Unavailable"}.
          {" "}Ads: {str(permissions.ads, "prohibited")}. Publish: {str(permissions.publish, "approval required")}.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 text-sm disabled:opacity-50"
            disabled={stop.isPending || stopped}
            onClick={() => stop.mutate(true)}
          >
            Engage emergency stop
          </button>
          <button
            type="button"
            className="rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 text-sm disabled:opacity-50"
            disabled={stop.isPending || !stopped}
            onClick={() => stop.mutate(false)}
          >
            Release stop for checks
          </button>
        </div>
        <ul className="mt-4 space-y-2">
          {jobs.map((row) => {
            const job = asRecord(row);
            const jobId = str(job.id);
            return (
              <li key={jobId} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span>
                  {str(job.title, jobId)}
                  <span className="text-[var(--fg-muted)]"> · {str(job.source, "source unavailable")}</span>
                </span>
                <button
                  type="button"
                  className="rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-1 text-sm text-[var(--accent)] disabled:opacity-50"
                  disabled={run.isPending || stopped || !jobId}
                  onClick={() => run.mutate(jobId)}
                >
                  Run check
                </button>
              </li>
            );
          })}
        </ul>
        <p className="mt-3 text-xs text-[var(--fg-subtle)]">
          Recent log entries: {history.length}. This log is process memory and is not a traffic or revenue report.
        </p>
      </section>

      <section className="mb-6 rounded-[var(--radius-os)] border border-[var(--border)] p-4" aria-labelledby="growth-drafts">
        <h2 id="growth-drafts" className="text-sm font-semibold text-[var(--fg)]">
          Unpublished drafts
        </h2>
        <p className="mt-1 text-sm leading-relaxed text-[var(--fg-muted)]">
          A saved draft stays internal. This screen cannot publish it, send it, or turn it into an advertisement.
        </p>
        <form
          className="mt-3 space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!stopped && draftTitle.trim() && draftBody.trim()) draft.mutate();
          }}
        >
          <input
            value={draftTitle}
            onChange={(event) => setDraftTitle(event.target.value)}
            maxLength={120}
            placeholder="Draft title"
            aria-label="Draft title"
            className="w-full min-w-0 rounded-[var(--radius-os)] border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          />
          <textarea
            value={draftBody}
            onChange={(event) => setDraftBody(event.target.value)}
            maxLength={4000}
            rows={3}
            placeholder="Draft body"
            aria-label="Draft body"
            className="w-full min-w-0 rounded-[var(--radius-os)] border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          />
          <button
            type="submit"
            className="rounded-[var(--radius-os)] border border-[var(--border)] px-3 py-2 text-sm disabled:opacity-50"
            disabled={draft.isPending || stopped || !draftTitle.trim() || !draftBody.trim()}
          >
            Save unpublished draft
          </button>
        </form>
        <ul className="mt-3 space-y-1 text-sm text-[var(--fg-muted)]">
          {drafts.length === 0 ? <li>No drafts in this process.</li> : null}
          {drafts.map((row) => {
            const item = asRecord(row);
            return (
              <li key={str(item.id)}>
                {str(item.title, "Untitled")} · {item.published === true ? "Published" : "Not published"}
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
