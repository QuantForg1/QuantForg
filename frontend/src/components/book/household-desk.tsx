"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { householdPortfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

type DeskTab =
  | "overview"
  | "accounts"
  | "exposure"
  | "risk"
  | "performance"
  | "attribution"
  | "reports";

const TABS: { id: DeskTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "accounts", label: "Accounts" },
  { id: "exposure", label: "Exposure" },
  { id: "risk", label: "Risk allocation" },
  { id: "performance", label: "Strategy" },
  { id: "attribution", label: "Attribution" },
  { id: "reports", label: "Reports" },
];

function statusTone(status: string): string {
  if (status === "live") return "text-[var(--success)]";
  if (status === "cached") return "text-[var(--accent)]";
  if (status === "stale") return "text-[var(--warning)]";
  return "text-[var(--fg-muted)]";
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  return (
    <div className="min-w-0">
      <div className="qf-caption text-[var(--fg-muted)]">{label}</div>
      <div className="truncate font-mono text-[13px] tabular text-[var(--fg)]">
        {value == null || value === "" ? "—" : value}
      </div>
    </div>
  );
}

/**
 * Phase 3 household portfolio desk — honest nulls, RC4 Book chrome.
 * Wired into BookShell; does not restyle frozen panels.
 */
export function HouseholdDesk() {
  const [tab, setTab] = useState<DeskTab>("overview");

  const householdQ = useQuery({
    queryKey: ["portfolio-household"],
    queryFn: householdPortfolioApi.get,
    retry: false,
    staleTime: 12_000,
  });
  const exposureQ = useQuery({
    queryKey: ["portfolio-household-exposure"],
    queryFn: householdPortfolioApi.exposure,
    retry: false,
    staleTime: 12_000,
    enabled: tab === "exposure" || tab === "overview",
  });
  const riskQ = useQuery({
    queryKey: ["portfolio-household-risk"],
    queryFn: () => householdPortfolioApi.riskCheck({}),
    retry: false,
    staleTime: 12_000,
    enabled: tab === "risk" || tab === "overview",
  });
  const perfQ = useQuery({
    queryKey: ["portfolio-household-performance"],
    queryFn: () => householdPortfolioApi.performance(),
    retry: false,
    staleTime: 30_000,
    enabled: tab === "performance" || tab === "attribution" || tab === "reports",
  });
  const stopsQ = useQuery({
    queryKey: ["portfolio-household-stops"],
    queryFn: householdPortfolioApi.emergencyStops,
    retry: false,
    staleTime: 10_000,
    enabled: tab === "risk",
  });

  const data = asRecord(householdQ.data);
  const totals = asRecord(data.totals);
  const accounts = asList(data.accounts).map(asRecord);

  const overviewNote = useMemo(() => {
    if (householdQ.isLoading) return "Loading household…";
    if (householdQ.isError) return "Household unavailable — registry or session error.";
    if (!accounts.length) return "No registered broker accounts.";
    const excluded = str(totals.accounts_excluded);
    if (excluded && excluded !== "0") {
      return `${excluded} account(s) excluded from totals (missing/stale/FX).`;
    }
    return null;
  }, [householdQ.isError, householdQ.isLoading, accounts.length, totals.accounts_excluded]);

  return (
    <section
      className="flex min-h-0 flex-col gap-2 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-3"
      aria-label="Household portfolio"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-[13px] font-semibold text-[var(--fg)]">
            Household portfolio
          </h2>
          <p className="qf-caption text-[var(--fg-muted)]">
            All your broker accounts in one view. Figures show “—” until the broker reports them.
          </p>
        </div>
        <div className="flex flex-wrap gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={cn(
                "rounded px-2 py-1 text-[11px]",
                tab === t.id
                  ? "bg-[var(--accent-muted)] text-[var(--accent)]"
                  : "text-[var(--fg-muted)] hover:text-[var(--fg)]",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {overviewNote ? (
        <p className="qf-caption text-[var(--fg-subtle)]">{overviewNote}</p>
      ) : null}

      {tab === "overview" || tab === "accounts" ? (
        <div className="grid gap-3">
          {tab === "overview" ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
              <Metric label="Balance" value={str(totals.balance)} />
              <Metric label="Equity" value={str(totals.equity)} />
              <Metric label="Free margin" value={str(totals.free_margin)} />
              <Metric label="Used margin" value={str(totals.used_margin)} />
              <Metric label="Floating P&L" value={str(totals.floating_pnl)} />
              <Metric label="Return %" value={str(totals.overall_return_pct)} />
              <Metric label="Daily P&L" value={str(totals.daily_pnl)} />
              <Metric label="Weekly P&L" value={str(totals.weekly_pnl)} />
              <Metric label="Monthly P&L" value={str(totals.monthly_pnl)} />
              <Metric
                label="Positions"
                value={str(totals.active_positions)}
              />
              <Metric
                label="Pending"
                value={str(totals.pending_orders)}
              />
              <Metric
                label="Connected"
                value={str(totals.connected_accounts)}
              />
            </div>
          ) : null}
          <div className="min-h-0 overflow-auto">
            <table className="w-full text-left text-[12px]">
              <thead className="text-[var(--fg-muted)]">
                <tr>
                  <th className="py-1 font-medium">Broker</th>
                  <th className="py-1 font-medium">Status</th>
                  <th className="py-1 font-medium">Equity</th>
                  <th className="py-1 font-medium">Floating</th>
                  <th className="py-1 font-medium">Currency</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((a) => (
                  <tr
                    key={str(a.broker_account_id) || str(a.login)}
                    className="border-t border-[var(--border)]"
                  >
                    <td className="py-1.5 text-[var(--fg)]">
                      {str(a.broker_name) || str(a.broker_code) || "—"}
                    </td>
                    <td
                      className={cn(
                        "py-1.5 font-mono",
                        statusTone(str(a.data_status) || ""),
                      )}
                    >
                      {str(a.data_status) || "—"}
                    </td>
                    <td className="py-1.5 font-mono tabular">
                      {str(a.equity) || "—"}
                    </td>
                    <td className="py-1.5 font-mono tabular">
                      {str(a.floating_pnl) || "—"}
                    </td>
                    <td className="py-1.5">{str(a.currency) || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {tab === "exposure" ? (
        <ExposurePanel data={asRecord(exposureQ.data)} loading={exposureQ.isLoading} />
      ) : null}

      {tab === "risk" ? (
        <RiskPanel
          risk={asRecord(riskQ.data)}
          stops={asRecord(stopsQ.data)}
          loading={riskQ.isLoading}
        />
      ) : null}

      {tab === "performance" || tab === "attribution" || tab === "reports" ? (
        <PerformancePanel
          data={asRecord(perfQ.data)}
          mode={tab}
          loading={perfQ.isLoading}
        />
      ) : null}
    </section>
  );
}

function ExposurePanel({
  data,
  loading,
}: {
  data: Record<string, unknown>;
  loading: boolean;
}) {
  if (loading) return <p className="qf-caption">Loading exposure…</p>;
  const bySymbol = asList(data.by_symbol).map(asRecord);
  const overlapping = asList(data.overlapping).map(asRecord);
  return (
    <div className="grid gap-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Long volume" value={str(data.total_long_volume)} />
        <Metric label="Short volume" value={str(data.total_short_volume)} />
      </div>
      <div className="overflow-auto">
        <table className="w-full text-left text-[12px]">
          <thead className="text-[var(--fg-muted)]">
            <tr>
              <th className="py-1">Symbol</th>
              <th className="py-1">Net</th>
              <th className="py-1">Share %</th>
              <th className="py-1">Flag</th>
            </tr>
          </thead>
          <tbody>
            {bySymbol.map((b) => (
              <tr key={str(b.key)} className="border-t border-[var(--border)]">
                <td className="py-1.5">{str(b.key)}</td>
                <td className="py-1.5 font-mono">{str(b.net_volume)}</td>
                <td className="py-1.5 font-mono">
                  {str(b.share_of_equity_pct) || "—"}
                </td>
                <td className="py-1.5">
                  {b.concentration_flag ? "concentration" : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {overlapping.length ? (
        <p className="qf-caption text-[var(--warning)]">
          Overlapping exposure on{" "}
          {overlapping.map((o) => str(o.symbol)).join(", ")}
        </p>
      ) : (
        <p className="qf-caption text-[var(--fg-muted)]">No overlapping flags.</p>
      )}
    </div>
  );
}

function RiskPanel({
  risk,
  stops,
  loading,
}: {
  risk: Record<string, unknown>;
  stops: Record<string, unknown>;
  loading: boolean;
}) {
  if (loading) return <p className="qf-caption">Loading risk allocation…</p>;
  return (
    <div className="grid gap-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric
          label="Allowed"
          value={risk.allowed === false ? "blocked" : risk.allowed ? "yes" : "—"}
        />
        <Metric label="Open risk used %" value={str(risk.aggregate_open_risk_used_pct)} />
        <Metric label="Open risk cap %" value={str(risk.aggregate_open_risk_pct)} />
        <Metric
          label="User stop"
          value={stops.user_armed ? "armed" : "clear"}
        />
      </div>
      {str(risk.block_reason) ? (
        <p className="qf-caption text-[var(--danger)]">{str(risk.block_reason)}</p>
      ) : null}
      <p className="qf-caption text-[var(--fg-muted)]">
        New orders only — open positions are not auto-closed.{" "}
        <Link href="/risk-center" className="text-[var(--accent)] underline">
          Risk Center
        </Link>
      </p>
    </div>
  );
}

function PerformancePanel({
  data,
  mode,
  loading,
}: {
  data: Record<string, unknown>;
  mode: DeskTab;
  loading: boolean;
}) {
  if (loading) return <p className="qf-caption">Loading performance…</p>;
  const overall = asRecord(data.overall);
  const attribution = asList(data.attribution).map(asRecord);

  if (mode === "attribution" || mode === "reports") {
    return (
      <div className="grid gap-2">
        {mode === "reports" ? (
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              className="h-7 text-[11px]"
              type="button"
              onClick={() => {
                const rows = attribution;
                const header =
                  "trade_id,symbol,strategy,broker,realized_pnl,chain_complete,missing_links";
                const lines = rows.map((r) =>
                  [
                    str(r.trade_id),
                    str(r.symbol),
                    str(r.strategy),
                    str(r.broker_code),
                    str(r.realized_pnl),
                    r.chain_complete ? "1" : "0",
                    asList(r.missing_links).join("|"),
                  ].join(","),
                );
                const blob = new Blob([[header, ...lines].join("\n")], {
                  type: "text/csv",
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "household-attribution.csv";
                a.click();
                URL.revokeObjectURL(url);
              }}
            >
              Export CSV
            </Button>
            <span className="qf-caption text-[var(--fg-muted)]">
              Credentials never included
            </span>
          </div>
        ) : null}
        <div className="max-h-48 overflow-auto">
          <table className="w-full text-left text-[12px]">
            <thead className="text-[var(--fg-muted)]">
              <tr>
                <th className="py-1">Trade</th>
                <th className="py-1">Symbol</th>
                <th className="py-1">PnL</th>
                <th className="py-1">Chain</th>
              </tr>
            </thead>
            <tbody>
              {attribution.map((r) => (
                <tr key={str(r.trade_id)} className="border-t border-[var(--border)]">
                  <td className="py-1.5 font-mono">{str(r.trade_id)}</td>
                  <td className="py-1.5">{str(r.symbol)}</td>
                  <td className="py-1.5 font-mono">{str(r.realized_pnl)}</td>
                  <td className="py-1.5">
                    {r.chain_complete
                      ? "complete"
                      : (asList(r.missing_links).join(", ") || "incomplete")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!attribution.length ? (
          <p className="qf-caption text-[var(--fg-muted)]">
            No confirmed closed trades for attribution.
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Metric label="Trades" value={str(overall.total_trades)} />
      <Metric label="Win rate %" value={str(overall.win_rate)} />
      <Metric label="Net profit" value={str(overall.net_profit)} />
      <Metric label="Profit factor" value={str(overall.profit_factor)} />
      <Metric label="Expectancy" value={str(overall.expectancy)} />
      <Metric label="Max DD" value={str(overall.max_drawdown)} />
      <Metric label="Avg RR" value={str(overall.average_rr)} />
      <Metric
        label="Excluded unconfirmed"
        value={str(data.trades_excluded_unconfirmed)}
      />
    </div>
  );
}
