"use client";

import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { DeskQueryState } from "@/components/desk/query-state";
import { ApiError } from "@/lib/api/client";
import {
  TRUST_METRICS,
  figureLabel,
  loadTrustPerformance,
  statusLabel,
  type TrustReport,
} from "@/lib/trust/performance";

const SCOPES: Record<string, string> = {
  live: "Real account",
  demo: "Demo account",
  paper: "Paper trading",
  backtest: "Backtest",
  unknown: "Account type not confirmed",
};

function scopeLabel(report: TrustReport): string {
  const key = String(report.account_scope || "").toLowerCase();
  const scope = SCOPES[key] ?? (key ? key.replaceAll("_", " ") : "Account type not confirmed");
  if (report.live_performance) return `${scope} · broker-verified live results`;
  return `${scope} · not verified as live results yet`;
}

export function TrustPerformancePanel() {
  const query = useQuery({
    queryKey: ["trust-performance"],
    queryFn: loadTrustPerformance,
    retry: false,
    staleTime: 15_000,
  });
  const disabled = query.error instanceof ApiError && query.error.status === 404;
  const report = query.data;

  return (
    <div className="qf-desk min-w-0 space-y-5">
      <PageHeader
        eyebrow="Performance"
        title="Verified performance"
        description="Broker history for this account. Missing money stays unavailable."
      />
      <DeskQueryState
        isLoading={query.isLoading}
        isError={query.isError && !disabled}
        errorMessage="The verified performance report could not be loaded."
        onRetry={() => void query.refetch()}
        isEmpty={disabled || !report}
        empty={{
          icon: ShieldCheck,
          title: disabled ? "Verified performance is not enabled" : "No report",
          description: disabled
            ? "The report stays hidden until Trust Engine is enabled for this environment."
            : "No performance report was returned.",
        }}
      >
        {report ? <TrustReportView report={report} /> : null}
      </DeskQueryState>
    </div>
  );
}

function TrustReportView({ report }: { report: TrustReport }) {
  const performance = report.performance ?? {};
  const trades = report.trades ?? [];
  return (
    <div className="space-y-5">
      <p className="text-sm text-[var(--text-secondary)]">
        {scopeLabel(report)}
        {report.read_at ? ` · read ${report.read_at}` : ""}
        {report.account_id_masked ? ` · account ${report.account_id_masked}` : ""}
      </p>
      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {TRUST_METRICS.map((metric) => {
          const figure = performance[metric.key];
          return (
            <div key={metric.key} className="rounded-lg border border-[var(--border)] p-3">
              <dt className="text-xs text-[var(--text-secondary)]">{metric.label}</dt>
              <dd className="mt-1 font-mono text-sm">{figureLabel(figure)}</dd>
              <dd className="mt-1 text-xs text-[var(--text-secondary)]">
                {statusLabel(figure?.status)}
              </dd>
            </div>
          );
        })}
      </dl>
      <section className="space-y-2">
        <h2 className="text-sm font-medium">Closed trades</h2>
        {trades.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">No closed trades in this report.</p>
        ) : (
          <ul className="divide-y divide-[var(--border)] text-sm">
            {trades.slice(0, 50).map((trade) => (
              <li key={String(trade.position_id)} className="flex justify-between gap-3 py-2">
                <span>
                  {trade.symbol || "Symbol unavailable"} · {figureLabel(trade.direction)}
                </span>
                <span className="font-mono">{figureLabel(trade.net_pnl)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      {report.known_limitations && report.known_limitations.length > 0 ? (
        <ul className="list-disc space-y-1 pl-5 text-xs text-[var(--text-secondary)]">
          {report.known_limitations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
