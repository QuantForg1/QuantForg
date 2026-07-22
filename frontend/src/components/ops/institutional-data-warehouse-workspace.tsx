"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Database } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { institutionalDataWarehouseApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-[var(--border)] bg-[var(--bg)]/40 px-2.5 py-2">
      <p className="text-[9px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p className="mt-1 font-mono text-sm tabular text-[var(--fg)]">{value}</p>
    </div>
  );
}

function fmt(v: unknown, d = 2): string {
  const n = num(v);
  return Number.isFinite(n) ? formatNumber(n, d) : "—";
}

function fmtPct(v: unknown): string {
  const n = num(v);
  return Number.isFinite(n) ? `${formatNumber(n * 100, 1)}%` : "—";
}

const DOMAINS = [
  "market",
  "trades",
  "orders",
  "signals",
  "risk",
  "safety",
  "execution",
  "performance",
  "replay",
  "evidence",
  "governance",
  "configuration",
  "reports",
] as const;

/**
 * Institutional Data Warehouse desk — analytics infrastructure only.
 * Never modifies production records or trading behaviour.
 */
export function InstitutionalDataWarehouseWorkspace() {
  const [domain, setDomain] = useState<string>("trades");
  const [q, setQ] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [session, setSession] = useState("");

  const dashQ = useQuery({
    queryKey: ["idw-dashboard"],
    queryFn: () => institutionalDataWarehouseApi.dashboard(),
    retry: false,
    staleTime: 15_000,
  });

  const dataQ = useQuery({
    queryKey: ["idw-dataset", domain, q, since, until, session],
    queryFn: () =>
      institutionalDataWarehouseApi.dataset(domain, {
        limit: 200,
        q: q || undefined,
        since: since || undefined,
        until: until || undefined,
        session: session || undefined,
      }),
    retry: false,
    staleTime: 10_000,
  });

  const reportsQ = useQuery({
    queryKey: ["idw-reports"],
    queryFn: () => institutionalDataWarehouseApi.reports(),
    retry: false,
    staleTime: 20_000,
  });

  if (dashQ.isLoading && !dashQ.data) return <DeskSkeleton rows={8} />;
  if (dashQ.isError) {
    return (
      <DeskError
        message="Institutional Data Warehouse unavailable."
        onRetry={() => void dashQ.refetch()}
      />
    );
  }

  const d = asRecord(dashQ.data);
  const inventory = asRecord(d.inventory);
  const domains = asRecord(inventory.domains);
  const analytics = asRecord(d.analytics);
  const bySession = asRecord(
    asRecord(analytics.performance_by_session).by_session,
  );
  const byRegime = asRecord(asRecord(analytics.performance_by_regime).by_regime);
  const noTrade = asRecord(analytics.no_trade_analysis);
  const coverage = asRecord(
    asRecord(asRecord(d.reports).data_coverage_report).coverage,
  );
  const quality = asRecord(asRecord(d.reports).data_quality_report);
  const correlation = asRecord(asRecord(d.reports).correlation_report);
  const summary = asRecord(d.evidence_summary);
  const recs = asList(asRecord(reportsQ.data).recommendations).map(String);
  const items = asList(asRecord(dataQ.data).items).map(asRecord);

  const empty = num(inventory.total_records) === 0;

  if (empty) {
    return (
      <DeskEmpty
        icon={Database}
        title="Warehouse empty"
        description="Snapshot journals or POST rows to /institutional-data-warehouse/ingest. The warehouse stays empty rather than fabricating analytics."
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Institutional Data Warehouse
          </span>
          <Badge tone="neutral">v{str(d.version, "1.0.1")}</Badge>
          <Badge tone="success">read-only</Badge>
          <Badge tone="neutral">
            n={str(summary.total_records ?? inventory.total_records, "0")}
          </Badge>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            void dashQ.refetch();
            void dataQ.refetch();
            void reportsQ.refetch();
          }}
        >
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-6">
        <Stat label="Total records" value={str(inventory.total_records, "0")} />
        <Stat
          label="Domains populated"
          value={`${str(summary.domains_populated, "0")}/${str(summary.domains_total, "13")}`}
        />
        <Stat label="Completeness" value={fmtPct(quality.completeness_ratio)} />
        <Stat
          label="Cross-domain corr"
          value={str(correlation.cross_domain_correlations, "0")}
        />
        <Stat label="NO_TRADE" value={str(noTrade.no_trade_count, "0")} />
        <Stat
          label="Replay coverage"
          value={fmtPct(asRecord(analytics.replay_coverage).coverage_ratio)}
        />
      </div>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Dataset explorer
        </h3>
        <div className="mt-2 flex flex-wrap gap-1">
          {DOMAINS.map((name) => (
            <Button
              key={name}
              size="sm"
              variant={domain === name ? "default" : "outline"}
              onClick={() => setDomain(name)}
            >
              {name} ({str(domains[name], "0")})
            </Button>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <input
            className="min-w-[160px] flex-1 border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[12px]"
            placeholder="Search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <input
            className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[12px]"
            placeholder="Session"
            value={session}
            onChange={(e) => setSession(e.target.value)}
          />
          <input
            type="datetime-local"
            className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[12px]"
            value={since}
            onChange={(e) => setSince(e.target.value)}
            aria-label="Since"
          />
          <input
            type="datetime-local"
            className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[12px]"
            value={until}
            onChange={(e) => setUntil(e.target.value)}
            aria-label="Until"
          />
        </div>
        <div className="mt-2 max-h-56 overflow-auto">
          <table className="w-full text-left text-[11px]">
            <thead className="text-[var(--fg-subtle)]">
              <tr>
                <th className="py-1 pr-2">Time</th>
                <th className="py-1 pr-2">Trade</th>
                <th className="py-1 pr-2">Session</th>
                <th className="py-1 pr-2">Corr</th>
                <th className="py-1">Strategy</th>
              </tr>
            </thead>
            <tbody>
              {items
                .slice()
                .reverse()
                .slice(0, 50)
                .map((row) => (
                  <tr
                    key={str(row.warehouse_id)}
                    className="border-t border-[var(--border)]"
                  >
                    <td className="py-1 pr-2 font-mono">
                      {str(row.timestamp, "—")}
                    </td>
                    <td className="py-1 pr-2 font-mono">
                      {str(row.trade_id, "—")}
                    </td>
                    <td className="py-1 pr-2">{str(row.session, "—")}</td>
                    <td className="py-1 pr-2 font-mono">
                      {str(row.correlation_id, "—")}
                    </td>
                    <td className="py-1">{str(row.strategy_version, "—")}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Performance by session
          </h3>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {Object.entries(bySession).map(([k, v]) => {
              const row = asRecord(v);
              return (
                <Stat
                  key={k}
                  label={`${k} (n=${str(row.trades, "0")})`}
                  value={`WR ${fmtPct(row.win_rate)} · ${fmt(row.net_pnl)}`}
                />
              );
            })}
          </div>
        </section>
        <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Performance by regime
          </h3>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {Object.entries(byRegime).map(([k, v]) => {
              const row = asRecord(v);
              return (
                <Stat
                  key={k}
                  label={`${k} (n=${str(row.trades, "0")})`}
                  value={`WR ${fmtPct(row.win_rate)} · ${fmt(row.net_pnl)}`}
                />
              );
            })}
          </div>
        </section>
      </div>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Coverage targets
        </h3>
        <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
          {(["trades", "replay", "evidence", "governance"] as const).map((name) => {
            const row = asRecord(coverage[name]);
            return (
              <Stat
                key={name}
                label={name}
                value={`${str(row.observed, "0")}/${str(row.target, "—")} · ${fmtPct(row.ratio)}`}
              />
            );
          })}
        </div>
      </section>

      <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Recommendations
        </h3>
        <ul className="mt-2 list-disc space-y-1 pl-4 text-[12px]">
          {recs.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
