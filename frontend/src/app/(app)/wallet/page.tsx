"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowLeftRight,
  ArrowUpFromLine,
  Download,
  Wallet,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { LazyEquityChart } from "@/components/charts/lazy";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { PageMotion } from "@/components/desk/motion";
import { SessionStrip } from "@/components/broker/session-strip";
import { portfolioApi } from "@/lib/api/endpoints";
import { useTradingSession } from "@/providers/trading-session-provider";
import { asList, asRecord, metric, num, str, toneFromNumber } from "@/lib/desk";
import { formatCurrency } from "@/lib/utils";
import { buildEquitySeries } from "@/lib/dashboard/derive";

function money(v: unknown) {
  const n = num(v);
  return Number.isFinite(n) ? formatCurrency(n) : "—";
}

export default function WalletPage() {
  const session = useTradingSession();
  const portfolio = useQuery({
    queryKey: ["portfolio"],
    queryFn: portfolioApi.get,
    retry: false,
    staleTime: 12_000,
    enabled: session.connected,
  });
  const history = useQuery({
    queryKey: ["history"],
    queryFn: portfolioApi.history,
    retry: false,
    staleTime: 20_000,
    enabled: session.connected,
  });

  const account = asRecord(portfolio.data?.account);
  const balance = metric(account, "balance");
  const equity = metric(account, "equity");
  const freeMargin = metric(account, "free_margin");
  const margin = metric(account, "margin");
  const profit = metric(account, "profit");
  const deals = asList(history.data?.deals).map(asRecord);
  const deposits = deals.filter((d) => {
    const t = str(d.deal_type, "").toLowerCase();
    const p = num(d.profit, 0);
    return t.includes("balance") || t.includes("deposit") || (t.includes("credit") && p > 0);
  });
  const withdrawals = deals.filter((d) => {
    const t = str(d.deal_type, "").toLowerCase();
    const p = num(d.profit, 0);
    return t.includes("withdrawal") || (t.includes("balance") && p < 0);
  });
  const curve =
    Number.isFinite(equity) && deals.length ? buildEquitySeries(deals, equity) : [];

  const exportCsv = () => {
    const rows = [["ticket", "symbol", "side", "volume", "price", "profit", "time"]];
    for (const d of deals) {
      rows.push([
        str(d.ticket, ""),
        str(d.symbol, ""),
        str(d.side, ""),
        str(d.volume, ""),
        str(d.price, ""),
        str(d.profit, ""),
        str(d.time, ""),
      ]);
    }
    const blob = new Blob([rows.map((r) => r.join(",")).join("\n")], {
      type: "text/csv",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "quantforg-wallet-history.csv";
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Exported deal history");
  };

  const fundingHint = () =>
    toast.message("Funding is managed at your broker", {
      description: "Use MT5 or your broker portal for deposits, withdrawals, and transfers.",
    });

  return (
    <div>
      <PageHeader
        title="Wallet"
        description="Account balance, margin, and funding activity from your synced portfolio."
        actions={
          <>
            <Button variant="secondary" size="sm" onClick={fundingHint}>
              <ArrowDownToLine className="h-3.5 w-3.5" /> Deposit
            </Button>
            <Button variant="secondary" size="sm" onClick={fundingHint}>
              <ArrowUpFromLine className="h-3.5 w-3.5" /> Withdraw
            </Button>
            <Button variant="secondary" size="sm" onClick={fundingHint}>
              <ArrowLeftRight className="h-3.5 w-3.5" /> Transfer
            </Button>
            <Button size="sm" onClick={exportCsv} disabled={!deals.length}>
              <Download className="h-3.5 w-3.5" /> Export
            </Button>
          </>
        }
      />

      <SessionStrip className="mb-4" />

      {portfolio.isLoading ? (
        <DeskSkeleton variant="page" />
      ) : portfolio.isError ? (
        <DeskError
          message="Unable to load wallet. Connect MT5 and sync portfolio."
          onRetry={() => portfolio.refetch()}
        />
      ) : (
        <PageMotion>
          <Card className="border-[var(--accent)]/25 bg-[var(--accent-soft)]/20">
            <CardContent className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-medium text-[var(--fg)]">Broker funding notice</p>
                <p className="text-xs text-[var(--fg-muted)]">
                  Deposits, withdrawals, and transfers are processed at your broker. QuantForg
                  mirrors synced balance and margin only.
                </p>
              </div>
              <Button size="sm" variant="secondary" asChild>
                <Link href="/broker">Broker Workspace</Link>
              </Button>
            </CardContent>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
            <StatCard label="Account Balance" value={money(balance)} hint={str(account.currency, "USD")} />
            <StatCard label="Equity" value={money(equity)} tone={toneFromNumber(profit)} />
            <StatCard label="Free Margin" value={money(freeMargin)} />
            <StatCard label="Margin Used" value={money(margin)} />
            <StatCard
              label="Buying Power"
              value={money(freeMargin)}
              hint="Available free margin"
            />
            <StatCard
              label="Today's PnL"
              value={money(profit)}
              tone={toneFromNumber(profit)}
              hint="Account profit field"
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>Equity Curve</CardTitle>
                <Badge tone="accent">Live</Badge>
              </CardHeader>
              <CardContent>
                <LazyEquityChart
                  data={curve}
                  emptyLabel="No completed trades — equity path appears after deal sync"
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>Balance History</CardTitle>
                <Button variant="ghost" size="sm" asChild>
                  <Link href="/history">Full history</Link>
                </Button>
              </CardHeader>
              <CardContent>
                {history.isLoading ? (
                  <DeskSkeleton rows={3} />
                ) : deals.length === 0 ? (
                  <div className="flex h-64 flex-col items-center justify-center gap-2 text-center">
                    <Wallet className="h-8 w-8 text-[var(--fg-subtle)]" />
                    <p className="text-sm text-[var(--fg-muted)]">No completed trades</p>
                  </div>
                ) : (
                  <DeskTable
                    columns={["Time", "Symbol", "Side", "Profit"]}
                    rows={deals.slice(0, 8).map((d) => [
                      str(d.time).slice(0, 16),
                      str(d.symbol),
                      <Badge key="s" tone="neutral">
                        {str(d.side)}
                      </Badge>,
                      <span
                        key="p"
                        className={
                          num(d.profit, 0) >= 0
                            ? "text-[var(--success)]"
                            : "text-[var(--danger)]"
                        }
                      >
                        {money(d.profit)}
                      </span>,
                    ])}
                  />
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Deposits</CardTitle>
              </CardHeader>
              <CardContent>
                {deposits.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">No deposit deals detected.</p>
                ) : (
                  <DeskTable
                    columns={["Time", "Amount", "Ticket"]}
                    rows={deposits.slice(0, 6).map((d) => [
                      str(d.time).slice(0, 16),
                      money(d.profit),
                      str(d.ticket),
                    ])}
                  />
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Withdrawals</CardTitle>
              </CardHeader>
              <CardContent>
                {withdrawals.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">No withdrawal deals detected.</p>
                ) : (
                  <DeskTable
                    columns={["Time", "Amount", "Ticket"]}
                    rows={withdrawals.slice(0, 6).map((d) => [
                      str(d.time).slice(0, 16),
                      money(d.profit),
                      str(d.ticket),
                    ])}
                  />
                )}
              </CardContent>
            </Card>
          </div>
        </PageMotion>
      )}
    </div>
  );
}
