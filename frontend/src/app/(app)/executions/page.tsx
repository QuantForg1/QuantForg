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
import { SessionStrip } from "@/components/broker/session-strip";
import { useTradingSession } from "@/providers/trading-session-provider";
import { portfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatCurrency, formatNumber } from "@/lib/utils";

type Row = Record<string, unknown>;

export default function ExecutionsPage() {
  const session = useTradingSession();
  const q = useQuery({
    queryKey: ["history"],
    queryFn: portfolioApi.history,
    retry: false,
    staleTime: 20_000,
    enabled: session.connected,
  });
  const deals =
    asList(q.data?.deals).map(asRecord).length > 0
      ? asList(q.data?.deals).map(asRecord)
      : session.historyDeals;
  const pnl = deals.reduce((s, d) => s + num(d.profit, 0), 0);

  const columns: DeskColumn<Row>[] = [
    {
      id: "time",
      header: "Time",
      sortable: true,
      accessor: (r) => str(r.time),
      cell: (r) => <span className="tabular text-[var(--fg-muted)]">{str(r.time).slice(0, 19)}</span>,
    },
    {
      id: "ticket",
      header: "Ticket",
      sortable: true,
      accessor: (r) => str(r.ticket),
      cell: (r) => <span className="tabular">{str(r.ticket)}</span>,
    },
    {
      id: "symbol",
      header: "Symbol",
      sortable: true,
      accessor: (r) => str(r.symbol),
      cell: (r) => <span className="font-medium">{str(r.symbol)}</span>,
    },
    {
      id: "side",
      header: "Side",
      sortable: true,
      accessor: (r) => str(r.side),
      cell: (r) => (
        <Badge tone={str(r.side).toLowerCase() === "buy" ? "success" : "warning"}>
          {str(r.side)}
        </Badge>
      ),
    },
    {
      id: "volume",
      header: "Volume",
      sortable: true,
      accessor: (r) => num(r.volume, 0),
      cell: (r) => <span className="tabular">{str(r.volume)}</span>,
    },
    {
      id: "price",
      header: "Price",
      sortable: true,
      accessor: (r) => num(r.price ?? r.open_price, 0),
      cell: (r) => (
        <span className="tabular">{formatNumber(num(r.price ?? r.open_price, 0), 2)}</span>
      ),
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
      <PageHeader
        title="Executions"
        description="Fill tape and deal history from the live session."
        actions={
          <Button variant="secondary" size="sm" asChild>
            <Link href="/terminal">Terminal</Link>
          </Button>
        }
      />
      <SessionStrip className="mb-4" />
      <DeskQueryState
        isLoading={q.isLoading}
        isError={q.isError}
        errorMessage="Unable to load executions."
        onRetry={() => q.refetch()}
        skeleton="page"
      >
        <PageMotion>
          <StaggerGrid className="grid gap-4 sm:grid-cols-3">
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
            <StaggerItem>
              <StatCard
                label="Symbols"
                value={String(new Set(deals.map((d) => str(d.symbol))).size)}
              />
            </StaggerItem>
          </StaggerGrid>
          <Card>
            <CardHeader>
              <CardTitle>Execution tape</CardTitle>
            </CardHeader>
            <CardContent>
              <DeskDataTable
                columns={columns}
                rows={deals}
                rowKey={(r, i) => str(r.ticket, String(i))}
                searchKeys={(r) => `${str(r.symbol)} ${str(r.side)} ${str(r.ticket)}`}
                searchPlaceholder="Filter executions…"
                pageSize={12}
                aria-label="Execution history"
                empty={
                  <DeskEmpty
                    icon={History}
                    title="No executions yet"
                    description="Deal fills appear after MT5 sync."
                    actionLabel="Open broker"
                    actionHref="/broker"
                  />
                }
              />
            </CardContent>
          </Card>
        </PageMotion>
      </DeskQueryState>
    </div>
  );
}
