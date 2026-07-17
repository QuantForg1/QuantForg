"use client";

import { useQuery } from "@tanstack/react-query";
import { History } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
  const pnl = deals.reduce((s, d) => s + num(d.profit, 0), 0);

  const orderCols: DeskColumn<Row>[] = [
    {
      id: "ticket",
      header: "Ticket",
      sortable: true,
      accessor: (r) => str(r.ticket),
      cell: (r) => str(r.ticket),
    },
    {
      id: "symbol",
      header: "Symbol",
      sortable: true,
      accessor: (r) => str(r.symbol),
      cell: (r) => str(r.symbol),
    },
    {
      id: "side",
      header: "Side",
      sortable: true,
      accessor: (r) => str(r.side),
      cell: (r) => str(r.side),
    },
    {
      id: "state",
      header: "State",
      sortable: true,
      accessor: (r) => str(r.state),
      cell: (r) => <Badge tone="neutral">{str(r.state)}</Badge>,
    },
    {
      id: "profit",
      header: "Profit",
      sortable: true,
      accessor: (r) => num(r.profit, 0),
      cell: (r) => formatCurrency(num(r.profit, 0)),
    },
  ];

  const dealCols: DeskColumn<Row>[] = [
    {
      id: "time",
      header: "Time",
      sortable: true,
      accessor: (r) => str(r.time),
      cell: (r) => str(r.time).slice(0, 16),
    },
    {
      id: "symbol",
      header: "Symbol",
      sortable: true,
      accessor: (r) => str(r.symbol),
      cell: (r) => str(r.symbol),
    },
    {
      id: "side",
      header: "Side",
      sortable: true,
      accessor: (r) => str(r.side),
      cell: (r) => str(r.side),
    },
    {
      id: "volume",
      header: "Volume",
      sortable: true,
      accessor: (r) => num(r.volume, 0),
      cell: (r) => <span className="tabular">{str(r.volume)}</span>,
    },
    {
      id: "profit",
      header: "Profit",
      sortable: true,
      accessor: (r) => num(r.profit, 0),
      cell: (r) => (
        <span
          className={
            num(r.profit, 0) >= 0 ? "tabular text-[var(--success)]" : "tabular text-[var(--danger)]"
          }
        >
          {formatCurrency(num(r.profit, 0))}
        </span>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="History" description="Closed orders and deals from the terminal ledger." />
      <SessionStrip className="mb-4" />
      <DeskQueryState
        isLoading={q.isLoading}
        isError={q.isError}
        errorMessage="Unable to load history."
        onRetry={() => q.refetch()}
        skeleton="page"
      >
        <PageMotion>
          <StaggerGrid className="grid gap-4 sm:grid-cols-3">
            <StaggerItem>
              <StatCard label="Orders" value={String(orders.length)} />
            </StaggerItem>
            <StaggerItem>
              <StatCard label="Deals" value={String(deals.length)} />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Realized PnL"
                value={formatCurrency(pnl)}
                tone={pnl >= 0 ? "up" : "down"}
              />
            </StaggerItem>
          </StaggerGrid>
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
                  searchKeys={(r) => `${str(r.symbol)} ${str(r.state)}`}
                  pageSize={10}
                  aria-label="Order history"
                  empty={
                    <DeskEmpty
                      icon={History}
                      title="No order history"
                      description="Synced closed orders appear here."
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
                  rowKey={(r, i) => str(r.ticket, String(i))}
                  searchKeys={(r) => `${str(r.symbol)} ${str(r.side)}`}
                  pageSize={10}
                  aria-label="Deal history"
                  empty={
                    <DeskEmpty
                      icon={History}
                      title="No deals synced yet"
                      description="Deal fills appear here after terminal sync."
                      actionLabel="Open broker"
                      actionHref="/broker"
                    />
                  }
                />
              </CardContent>
            </Card>
          </div>
        </PageMotion>
      </DeskQueryState>
    </div>
  );
}
