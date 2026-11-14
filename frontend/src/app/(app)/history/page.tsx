"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { History } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskDataTable, type DeskColumn } from "@/components/desk/data-table";
import { DeskEmpty } from "@/components/desk/primitives";
import { DeskQueryState } from "@/components/desk/query-state";
import { PageMotion, StaggerGrid, StaggerItem } from "@/components/desk/motion";
import { portfolioApi } from "@/lib/api/endpoints";
import { SessionStrip } from "@/components/broker/session-strip";
import { useTradingSession } from "@/providers/trading-session-provider";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatCurrency } from "@/lib/utils";

type Row = Record<string, unknown>;

function moneyCell(raw: unknown) {
  const n = num(raw, 0);
  return (
    <span
      className={
        n >= 0 ? "tabular text-[var(--success)]" : "tabular text-[var(--danger)]"
      }
    >
      {formatCurrency(n)}
    </span>
  );
}

function dealNet(r: Row): number {
  return (
    num(r.profit, 0) +
    num(r.commission, 0) +
    num(r.swap, 0) +
    num(r.fee, 0) +
    num(r.fees, 0)
  );
}

export default function HistoryPage() {
  const session = useTradingSession();
  const q = useQuery({
    queryKey: ["history"],
    queryFn: portfolioApi.history,
    retry: false,
    staleTime: 20_000,
    enabled: session.connected,
  });
  const orders = asList(q.data?.orders).map(asRecord);
  const deals =
    asList(q.data?.deals).map(asRecord).length > 0
      ? asList(q.data?.deals).map(asRecord)
      : session.historyDeals;
  const pnl = deals.reduce((s, d) => s + dealNet(d), 0);

  const orderCols: DeskColumn<Row>[] = [
    {
      id: "ticket",
      header: "Ticket",
      sortable: true,
      sticky: true,
      accessor: (r) => str(r.ticket),
      cell: (r) => <span className="tabular">{str(r.ticket)}</span>,
    },
    {
      id: "symbol",
      header: "Symbol",
      sortable: true,
      mobilePrimary: true,
      accessor: (r) => str(r.symbol),
      cell: (r) => <span className="font-medium">{str(r.symbol)}</span>,
    },
    {
      id: "side",
      header: "Direction",
      sortable: true,
      accessor: (r) => str(r.side),
      cell: (r) => str(r.side).toUpperCase() || "—",
    },
    {
      id: "state",
      header: "Outcome",
      sortable: true,
      accessor: (r) => str(r.state),
      cell: (r) => <Badge tone="neutral">{str(r.state, "—")}</Badge>,
    },
    {
      id: "profit",
      header: "Profit",
      sortable: true,
      accessor: (r) => num(r.profit, 0),
      cell: (r) => moneyCell(r.profit),
    },
  ];

  const dealCols: DeskColumn<Row>[] = [
    {
      id: "time",
      header: "Date / time",
      sortable: true,
      accessor: (r) => str(r.time),
      cell: (r) => (
        <span className="tabular text-[var(--fg-muted)]">
          {str(r.time, "—").slice(0, 19) || "—"}
        </span>
      ),
    },
    {
      id: "symbol",
      header: "Symbol",
      sortable: true,
      mobilePrimary: true,
      accessor: (r) => str(r.symbol),
      cell: (r) => <span className="font-medium">{str(r.symbol)}</span>,
    },
    {
      id: "side",
      header: "Direction",
      sortable: true,
      accessor: (r) => str(r.side),
      cell: (r) => str(r.side).toUpperCase() || "—",
    },
    {
      id: "volume",
      header: "Volume",
      sortable: true,
      accessor: (r) => num(r.volume, 0),
      cell: (r) => <span className="tabular">{str(r.volume, "—")}</span>,
    },
    {
      id: "profit",
      header: "Profit",
      sortable: true,
      accessor: (r) => num(r.profit, 0),
      cell: (r) => moneyCell(r.profit),
    },
    {
      id: "commission",
      header: "Commission",
      sortable: true,
      accessor: (r) => num(r.commission, 0),
      cell: (r) => (
        <span className="tabular text-[var(--fg-muted)]">
          {formatCurrency(num(r.commission, 0))}
        </span>
      ),
    },
    {
      id: "swap",
      header: "Swap",
      sortable: true,
      accessor: (r) => num(r.swap, 0),
      cell: (r) => (
        <span className="tabular text-[var(--fg-muted)]">
          {formatCurrency(num(r.swap, 0))}
        </span>
      ),
    },
    {
      id: "net",
      header: "Net P&L",
      sortable: true,
      accessor: (r) => dealNet(r),
      cell: (r) => moneyCell(dealNet(r)),
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Trading"
        title="History"
        description="Closed orders and broker deal ledger. Deposits, withdrawals, and balance adjustments are not shown as trade executions."
        actions={
          <Button variant="secondary" size="sm" asChild>
            <Link href="/positions">Open positions</Link>
          </Button>
        }
      />
      <SessionStrip className="mb-4" />
      <DeskQueryState
        isLoading={q.isLoading && session.connected}
        isError={q.isError}
        errorMessage="Unable to load trading history from the broker session."
        onRetry={() => q.refetch()}
        skeleton="page"
      >
        <PageMotion className="space-y-4">
          <StaggerGrid className="grid gap-4 sm:grid-cols-3">
            <StaggerItem>
              <StatCard label="Orders" value={String(orders.length)} />
            </StaggerItem>
            <StaggerItem>
              <StatCard label="Deals" value={String(deals.length)} />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Net realized P&L"
                value={formatCurrency(pnl)}
                tone={pnl >= 0 ? "up" : "down"}
                hint="Profit + commission + swap from returned deals"
              />
            </StaggerItem>
          </StaggerGrid>
          {!session.connected ? (
            <DeskEmpty
              icon={History}
              title="Broker not connected"
              description="Order and deal history appear after the connected MT5 session returns ledger data."
              actionLabel="Connect broker"
              actionHref="/broker"
            />
          ) : (
            <div className="grid gap-4 xl:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Orders</CardTitle>
                </CardHeader>
                <CardContent>
                  <DeskDataTable
                    columns={orderCols}
                    rows={orders}
                    rowKey={(r, i) => str(r.ticket, String(i))}
                    searchKeys={(r) => `${str(r.symbol)} ${str(r.state)} ${str(r.side)}`}
                    searchPlaceholder="Filter orders…"
                    pageSize={10}
                    aria-label="Order history"
                    empty={
                      <DeskEmpty
                        icon={History}
                        title="No order history"
                        description="Synced closed orders appear here when the broker returns them."
                      />
                    }
                  />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Deals</CardTitle>
                </CardHeader>
                <CardContent>
                  <DeskDataTable
                    columns={dealCols}
                    rows={deals}
                    rowKey={(r, i) => str(r.ticket, `${str(r.time)}-${i}`)}
                    searchKeys={(r) => `${str(r.symbol)} ${str(r.side)} ${str(r.time)}`}
                    searchPlaceholder="Filter deals…"
                    pageSize={10}
                    aria-label="Deal history"
                    empty={
                      <DeskEmpty
                        icon={History}
                        title="No completed trades"
                        description="Deal fills, commissions, and swap appear after terminal sync. Nothing is invented."
                        actionLabel="Open broker"
                        actionHref="/broker"
                      />
                    }
                  />
                </CardContent>
              </Card>
            </div>
          )}
        </PageMotion>
      </DeskQueryState>
    </div>
  );
}
