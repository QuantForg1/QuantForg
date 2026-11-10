"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Layers, Loader2, Radio } from "lucide-react";
import { brokersApi, multiAccountOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function maskAccountNumber(raw: unknown): string {
  const s = String(raw ?? "").trim();
  if (!s || s === "—") return "—";
  if (s.length <= 4) return "****";
  return `****${s.slice(-4)}`;
}

function reasonLabel(code: string): string {
  const map: Record<string, string> = {
    multi_account_dispatch_disabled:
      "Multi-account dispatch is not enabled for your account yet.",
    live_submit_disabled: "Live order fan-out remains off.",
    awaiting_owner_enablement: "Awaiting owner enablement.",
    readiness_context_required: "Worker/account readiness context is required.",
  };
  return map[code] || code.replace(/_/g, " ");
}

/**
 * Observe-only customer multi-account strip.
 * Uses existing /broker-accounts + /multi-account/dispatch/status — no fabricated eligibility.
 */
export function CustomerMultiAccountPanel() {
  const accountsQ = useQuery({
    queryKey: ["broker-accounts"],
    queryFn: brokersApi.accounts,
    staleTime: 15_000,
    refetchInterval: 30_000,
    retry: false,
  });
  const dispatchQ = useQuery({
    queryKey: ["multi-account-dispatch-status"],
    queryFn: multiAccountOpsApi.myDispatchStatus,
    staleTime: 10_000,
    refetchInterval: 20_000,
    retry: false,
  });

  const accounts = asList(accountsQ.data).map((row) => asRecord(row));
  const dispatch = asRecord(dispatchQ.data);
  const eligibility = asRecord(dispatch.eligibility);
  const blockedReasons = asList(eligibility.blocked_reasons).map(String);
  const jobs = asList(dispatch.jobs).map((row) => asRecord(row));
  const readiness = asRecord(dispatch.readiness);
  const worker = asRecord(dispatch.worker_availability);
  const verification = asRecord(dispatch.connection_verification);
  const loading = accountsQ.isLoading || dispatchQ.isLoading;

  return (
    <section
      className="mt-6 w-full space-y-3 rounded-2xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_50%,transparent)] px-4 py-4 sm:px-5"
      aria-labelledby="customer-multi-account-heading"
    >
      <div className="flex items-start gap-3">
        <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--bg)]/40 text-[var(--accent)]">
          <Layers className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2
            id="customer-multi-account-heading"
            className="text-sm font-semibold text-[var(--fg)]"
          >
            Multi-account status
          </h2>
          <p className="mt-0.5 text-xs text-[var(--fg-muted)]">
            Own accounts and dispatch jobs only. Broker connection is not trading eligibility.
            LIVE fan-out stays off.
          </p>
        </div>
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin text-[var(--accent)]" aria-hidden />
        ) : null}
      </div>

      <div className="space-y-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Connected broker accounts
        </p>
        {!accounts.length ? (
          <p className="rounded-xl border border-dashed border-[var(--border)] px-3 py-3 text-xs text-[var(--fg-muted)]">
            No registered broker accounts yet. Connect MT5 above to establish ownership.
          </p>
        ) : (
          <ul className="space-y-2">
            {accounts.map((acct) => {
              const id = str(acct.id, str(acct.external_account_id, "account"));
              const env = str(acct.environment, "").toLowerCase() === "demo" ? "Demo" : "Live";
              return (
                <li
                  key={id}
                  className="rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg)_40%,transparent)] px-3 py-2.5"
                >
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-medium text-[var(--fg)]">
                      {str(acct.label, "MT5 account")}
                    </span>
                    <span className="rounded-md bg-[var(--surface-2)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--fg-muted)]">
                      {env}
                    </span>
                    <span className="text-xs text-[var(--fg-subtle)]">
                      {maskAccountNumber(acct.external_account_id)}
                    </span>
                  </div>
                  <p className="mt-1 truncate text-[11px] text-[var(--fg-muted)]">
                    Server: {str(acct.server, "—")} · Status: {str(acct.status, "—")}
                    {acct.connection_status
                      ? ` · Connection: ${String(acct.connection_status)}`
                      : ""}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <div className="rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg)_35%,transparent)] px-3 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Eligibility
          </p>
          {eligibility.blocked ? (
            <div className="mt-2 flex items-start gap-2 text-xs text-[var(--warning)]">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              <div className="space-y-1">
                <p className="font-medium">Blocked</p>
                {blockedReasons.length ? (
                  <ul className="list-disc space-y-0.5 pl-4 text-[var(--fg-muted)]">
                    {blockedReasons.map((reason) => (
                      <li key={reason}>{reasonLabel(reason)}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[var(--fg-muted)]">No reasons returned.</p>
                )}
              </div>
            </div>
          ) : (
            <p className="mt-2 text-xs text-[var(--fg-muted)]">
              {dispatchQ.isError
                ? "Eligibility status unavailable."
                : "Not blocked by reported reasons — LIVE submit remains disabled."}
            </p>
          )}
          <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
            {str(
              eligibility.note,
              "Eligibility comes from the platform API — never calculated in the browser.",
            )}
          </p>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--bg)_35%,transparent)] px-3 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Dispatch & readiness
          </p>
          <div className="mt-2 flex items-center gap-2 text-xs text-[var(--fg)]">
            <Radio className="h-3.5 w-3.5 text-[var(--fg-subtle)]" aria-hidden />
            <span>
              Jobs: {Number(dispatch.job_count ?? jobs.length) || 0}
              {dispatch.dispatch_enabled ? " · Dispatch flag on" : " · Dispatch disabled"}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
            Verification: {verification.verified ? "Verified" : "Unverified"} · Worker reported:{" "}
            {worker.reported ? "Yes" : "No"}
          </p>
          <p className="mt-1 text-[11px] text-[var(--fg-subtle)]">
            {str(readiness.evidence_note, str(verification.note, ""))}
          </p>
        </div>
      </div>

      {jobs.length ? (
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Your dispatch jobs
          </p>
          <ul className="max-h-40 space-y-1.5 overflow-y-auto">
            {jobs.slice(0, 12).map((job) => (
              <li
                key={str(job.intent_id, str(job.idempotency_key, Math.random().toString()))}
                className={cn(
                  "rounded-lg border border-[var(--border)] px-2.5 py-2 text-[11px] text-[var(--fg-muted)]",
                )}
              >
                <span className="font-medium text-[var(--fg)]">
                  {str(job.delivery_status, str(job.state, "unknown"))}
                </span>
                {" · "}
                account {maskAccountNumber(str(job.broker_account_id, "").slice(-8))}
                {job.block_reason ? ` · ${String(job.block_reason)}` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
