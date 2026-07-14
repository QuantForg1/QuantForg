"use client";

import { useQuery } from "@tanstack/react-query";
import { ListOrdered } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DeskDataTable, type DeskColumn } from "@/components/desk/data-table";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { PageMotion, StaggerGrid, StaggerItem } from "@/components/desk/motion";
import { RealtimeConnectionBadge, RealtimeMeta } from "@/components/realtime/connection-badge";
import { SessionStrip } from "@/components/broker/session-strip";
import { useOrdersStream } from "@/hooks/realtime";
import { useTradingSession } from "@/providers/trading-session-provider";
import { portfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";

type Row = Record<string, unknown>;

export default function OrdersPage() {
  const realtime = useOrdersStream();
  const session = useTradingSession();
  const q = useQuery({
    queryKey: ["orders"],
    queryFn: portfolioApi.orders,
    retry: false,
    staleTime: 12_000,
    enabled: session.connected,
  });
  const orders =
    asList(q.data).map(asRecord).length > 0
      ? asList(q.data).map(asRecord)
      : session.orders;

  const columns: DeskColumn<Row>[] = [
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
      cell: (r) => <Badge tone="neutral">{str(r.side)}</Badge>,
    },
    {
      id: "type",
      header: "Type",
      sortable: true,
      accessor: (r) => str(r.order_type),
      cell: (r) => str(r.order_type),
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
      accessor: (r) => num(r.price, 0),
      cell: (r) => <span className="tabular">{str(r.price)}</span>,
    },
    { id: "sl", header: "SL", cell: (r) => str(r.stop_loss) },
    { id: "tp", header: "TP", cell: (r) => str(r.take_profit) },
    {
      id: "created",
      header: "Created",
      sortable: true,
      accessor: (r) => str(r.created_at),
      cell: (r) => str(r.created_at).slice(0, 16),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Orders"
        description="Pending working orders from the synced terminal."
        actions={<RealtimeConnectionBadge status={realtime} />}
      />
      <RealtimeMeta status={realtime} className="mb-3" />
      <SessionStrip className="mb-4" />
      {q.isLoading ? (
        <DeskSkeleton variant="page" />
      ) : q.isError ? (
        <DeskError message="Unable to load orders." onRetry={() => q.refetch()} />
      ) : (
        <PageMotion>
          <StaggerGrid className="grid gap-4 sm:grid-cols-3">
            <StaggerItem>
              <StatCard label="Pending" value={String(orders.length)} />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Buy side"
                value={String(
                  orders.filter((o) => str(o.side).toLowerCase().includes("buy")).length,
                )}
              />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Sell side"
                value={String(
                  orders.filter((o) => str(o.side).toLowerCase().includes("sell")).length,
                )}
              />
            </StaggerItem>
          </StaggerGrid>
          <Card>
            <CardHeader>
              <CardTitle>Working orders</CardTitle>
            </CardHeader>
            <CardContent>
              <DeskDataTable
                columns={columns}
                rows={orders}
                rowKey={(r, i) => str(r.ticket, String(i))}
                searchKeys={(r) => `${str(r.symbol)} ${str(r.side)} ${str(r.order_type)}`}
                searchPlaceholder="Filter orders…"
                pageSize={12}
                aria-label="Working orders"
                empty={
                  <DeskEmpty
                    icon={ListOrdered}
                    title="No pending orders"
                    description="Limit and stop orders will appear here after sync."
                    actionLabel="Open execution"
                    onAction={() => {
                      window.location.href = "/execution";
                    }}
                  />
                }
              />
            </CardContent>
          </Card>
        </PageMotion>
      )}
    </div>
  );
}
