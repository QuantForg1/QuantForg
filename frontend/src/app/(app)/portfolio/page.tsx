"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Briefcase } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { portfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord, metric, num, str, toneFromNumber } from "@/lib/desk";
import { formatCurrency } from "@/lib/utils";

export default function PortfolioPage() {
  const q = useQuery({ queryKey: ["portfolio"], queryFn: portfolioApi.get, retry: false });
  const account = asRecord(q.data?.account);
  const positions = asList(q.data?.positions).map(asRecord);
  const pending = asList(q.data?.pending_orders).map(asRecord);
  const profit = metric(account, "profit");

  return (
    <div>
      <PageHeader
        title="Portfolio"
        description="Synchronized account snapshot, positions, and pending orders."
        actions={
          <Button variant="secondary" asChild>
            <Link href="/mt5">Sync MT5</Link>
          </Button>
        }
      />
      {q.isLoading ? (
        <DeskSkeleton rows={4} />
      ) : q.isError ? (
        <DeskError
          message="Unable to load portfolio. Connect MT5 and retry."
          onRetry={() => q.refetch()}
        />
      ) : (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Balance"
              value={formatCurrency(metric(account, "balance"))}
              hint={str(account.currency, "USD")}
            />
            <StatCard
              label="Equity"
              value={formatCurrency(metric(account, "equity"))}
              tone={toneFromNumber(profit)}
            />
            <StatCard label="Free Margin" value={formatCurrency(metric(account, "free_margin"))} />
            <StatCard
              label="Open Positions"
              value={String(q.data?.position_count ?? positions.length)}
            />
          </div>
          <div className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>Positions</CardTitle>
                <Badge tone="accent">{str(account.server, "Desk")}</Badge>
              </CardHeader>
              <CardContent>
                {positions.length === 0 ? (
                  <DeskEmpty
                    icon={Briefcase}
                    title="No open positions"
                    description="Connect MT5 and sync to populate live exposure."
                    actionLabel="Connect MT5"
                    onAction={() => {
                      window.location.href = "/mt5";
                    }}
                  />
                ) : (
                  <DeskTable
                    columns={["Symbol", "Side", "Volume", "Open", "Current", "PnL"]}
                    rows={positions.map((p) => [
                      str(p.symbol),
                      <Badge key="s" tone={str(p.side) === "buy" ? "success" : "warning"}>
                        {str(p.side)}
                      </Badge>,
                      str(p.volume),
                      str(p.open_price),
                      str(p.current_price),
                      <span
                        key="p"
                        className={
                          num(p.profit, 0) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"
                        }
                      >
                        {formatCurrency(num(p.profit, 0))}
                      </span>,
                    ])}
                  />
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>Pending orders</CardTitle>
                <Button variant="ghost" size="sm" asChild>
                  <Link href="/orders">View all</Link>
                </Button>
              </CardHeader>
              <CardContent>
                {pending.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">No pending orders.</p>
                ) : (
                  <DeskTable
                    columns={["Symbol", "Type", "Volume", "Price"]}
                    rows={pending.slice(0, 8).map((o) => [
                      str(o.symbol),
                      str(o.order_type),
                      str(o.volume),
                      str(o.price),
                    ])}
                  />
                )}
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-[var(--fg-subtle)]">
                  <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3">
                    <p>Margin level</p>
                    <p className="mt-1 text-sm text-[var(--fg)]">{str(account.margin_level, "—")}</p>
                  </div>
                  <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3">
                    <p>Leverage</p>
                    <p className="mt-1 text-sm text-[var(--fg)]">{str(account.leverage, "—")}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </motion.div>
      )}
    </div>
  );
}
