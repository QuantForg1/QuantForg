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
import { RealtimeConnectionBadge, RealtimeMeta } from "@/components/realtime/connection-badge";
import { SessionStrip } from "@/components/broker/session-strip";
import { usePortfolioStream } from "@/hooks/realtime";
import { useTradingSession } from "@/providers/trading-session-provider";
import { portfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord, metric, num, str, toneFromNumber } from "@/lib/desk";
import { formatCurrency } from "@/lib/utils";

export default function PortfolioPage() {
  const realtime = usePortfolioStream();
  const session = useTradingSession();
  const q = useQuery({
    queryKey: ["portfolio"],
    queryFn: portfolioApi.get,
    retry: false,
    staleTime: 12_000,
    enabled: session.connected,
  });
  const account = asRecord(q.data?.account);
  const fromPortfolio = asList(q.data?.positions).map(asRecord);
  const positions = fromPortfolio.length > 0 ? fromPortfolio : session.positions;
  const fromPending = asList(q.data?.pending_orders).map(asRecord);
  const pending = fromPending.length > 0 ? fromPending : session.orders;
  const profit = metric(account, "profit") || num(session.profit, 0);

  return (
    <div>
      <PageHeader
        title="Portfolio"
        description="Live broker account snapshot — balance, equity, margin, and exposure from the attached MT5 session."
        actions={
          <div className="flex items-center gap-2">
            <RealtimeConnectionBadge status={realtime} />
            <Button variant="secondary" asChild>
              <Link href="/broker">Broker Workspace</Link>
            </Button>
          </div>
        }
      />
      <RealtimeMeta status={realtime} className="mb-3" />
      <SessionStrip className="mb-4" />
      {!session.connected ? (
        <DeskEmpty
          icon={Briefcase}
          title="No live session"
          description="Attach MT5 in Broker Workspace to load balance, equity, and positions."
          actionLabel="Open Broker Workspace"
          actionHref="/broker"
        />
      ) : q.isLoading ? (
        <DeskSkeleton rows={4} />
      ) : q.isError ? (
        <DeskError
          message="Unable to load portfolio. Sync the trading session and retry."
          onRetry={() => q.refetch()}
        />
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-6">
            <StatCard
              label="Balance"
              value={formatCurrency(metric(account, "balance") || num(session.balance, 0))}
              hint={session.currency || str(account.currency, "USD")}
            />
            <StatCard
              label="Equity"
              value={formatCurrency(metric(account, "equity") || num(session.equity, 0))}
              tone={toneFromNumber(profit)}
            />
            <StatCard
              label="Free Margin"
              value={formatCurrency(
                metric(account, "free_margin") || num(session.freeMargin, 0),
              )}
            />
            <StatCard
              label="Margin Level"
              value={str(account.margin_level || session.marginLevel, "—")}
            />
            <StatCard
              label="Floating P/L"
              value={formatCurrency(profit)}
              tone={toneFromNumber(profit)}
            />
            <StatCard
              label="Open Positions"
              value={String(q.data?.position_count ?? positions.length)}
            />
          </div>
          <div className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>Positions</CardTitle>
                <Badge tone="accent">{session.server}</Badge>
              </CardHeader>
              <CardContent>
                {positions.length === 0 ? (
                  <DeskEmpty
                    icon={Briefcase}
                    title="No open positions"
                    description="Flat book — exposure will appear when positions sync from MT5."
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
                          num(p.profit, 0) >= 0
                            ? "text-[var(--success)]"
                            : "text-[var(--danger)]"
                        }
                      >
                        {str(p.profit)}
                      </span>,
                    ])}
                  />
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Pending Orders</CardTitle>
              </CardHeader>
              <CardContent>
                {pending.length === 0 ? (
                  <p className="text-sm text-[var(--fg-muted)]">No pending orders.</p>
                ) : (
                  <DeskTable
                    columns={["Symbol", "Type", "Volume", "Price"]}
                    rows={pending.map((o) => [
                      str(o.symbol),
                      str(o.order_type || o.type),
                      str(o.volume),
                      str(o.price),
                    ])}
                  />
                )}
              </CardContent>
            </Card>
          </div>
        </motion.div>
      )}
    </div>
  );
}
