"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Layers } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskDataTable, type DeskColumn } from "@/components/desk/data-table";
import { DeskEmpty } from "@/components/desk/primitives";
import { DeskQueryState } from "@/components/desk/query-state";
import { PageMotion, StaggerGrid, StaggerItem } from "@/components/desk/motion";
import { RealtimeConnectionBadge, RealtimeMeta } from "@/components/realtime/connection-badge";
import { usePositionsStream } from "@/hooks/realtime";
import { useTradingSession } from "@/providers/trading-session-provider";
import { SessionStrip } from "@/components/broker/session-strip";
import { portfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatCurrency } from "@/lib/utils";

type Row = Record<string, unknown>;

export default function PositionsPage() {
  const realtime = usePositionsStream();
  const session = useTradingSession();
  const q = useQuery({
    queryKey: ["positions"],
    queryFn: () => portfolioApi.positions(),
    retry: false,
    staleTime: 12_000,
    enabled: session.connected,
  });
  const fromApi = asList(q.data).map(asRecord);
  const positions = fromApi.length > 0 ? fromApi : session.positions;
  const totalPnl = positions.reduce((s, p) => s + num(p.profit, 0), 0);

  const columns: DeskColumn<Row>[] = [
    {
      id: "ticket",
      header: "Ticket",
      sortable: true,
      sticky: true,
      accessor: (r) => str(r.ticket),
      cell: (r) => <span className="tabular text-[var(--fg-muted)]">{str(r.ticket)}</span>,
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
      cell: (r) => (
        <Badge tone={str(r.side).toLowerCase() === "buy" ? "success" : "danger"}>
          {str(r.side).toUpperCase() || "—"}
        </Badge>
      ),
    },
    {
      id: "volume",
      header: "Volume",
      sortable: true,
      accessor: (r) => num(r.volume, 0),
      cell: (r) => <span className="tabular">{str(r.volume, "—")}</span>,
    },
    {
      id: "open",
      header: "Entry",
      sortable: true,
      accessor: (r) => num(r.open_price, 0),
      cell: (r) => <span className="tabular">{str(r.open_price, "—")}</span>,
    },
    {
      id: "current",
      header: "Current",
      sortable: true,
      accessor: (r) => num(r.current_price, 0),
      cell: (r) => <span className="tabular">{str(r.current_price, "—")}</span>,
    },
    {
      id: "sl",
      header: "Stop-loss",
      cell: (r) => <span className="tabular">{str(r.stop_loss, "—")}</span>,
    },
    {
      id: "tp",
      header: "Take-profit",
      cell: (r) => <span className="tabular">{str(r.take_profit, "—")}</span>,
    },
    {
      id: "pnl",
      header: "Floating P&L",
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
    {
      id: "status",
      header: "Status",
      cell: () => <Badge tone="success">Open</Badge>,
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Trading"
        title="Positions"
        description="Open broker positions with entry, protective stops, and floating P&L from the connected MT5 session. Values stay blank until a live session returns them."
        actions={
          <div className="flex items-center gap-2">
            <RealtimeConnectionBadge status={realtime} />
            <Button variant="secondary" size="sm" asChild>
              <Link href="/broker">Broker</Link>
            </Button>
            <Button size="sm" asChild>
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <RealtimeMeta status={realtime} className="mb-3" />
      <SessionStrip className="mb-4" />
      <DeskQueryState
        isLoading={q.isLoading && session.connected}
        isError={q.isError}
        errorMessage="Unable to load positions from the broker session."
        onRetry={() => q.refetch()}
        skeleton="page"
      >
        <PageMotion className="space-y-4">
          <StaggerGrid className="grid gap-4 sm:grid-cols-3">
            <StaggerItem>
              <StatCard
                label="Open positions"
                value={String(positions.length)}
                hint={session.connected ? "From connected session" : "Connect a broker to sync"}
              />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Floating P&L"
                value={formatCurrency(totalPnl)}
                tone={totalPnl >= 0 ? "up" : "down"}
                hint="Unrealized — not a closed result"
              />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Symbols"
                value={String(new Set(positions.map((p) => str(p.symbol))).size)}
              />
            </StaggerItem>
          </StaggerGrid>
          <Card>
            <CardHeader>
              <CardTitle>Open positions</CardTitle>
            </CardHeader>
            <CardContent>
              {!session.connected ? (
                <DeskEmpty
                  icon={Layers}
                  title="Broker not connected"
                  description="Open positions appear after you connect an MT5 account you own. QuantForg does not invent exposure."
                  actionLabel="Connect broker"
                  actionHref="/broker"
                />
              ) : (
                <DeskDataTable
                  columns={columns}
                  rows={positions}
                  rowKey={(r, i) => str(r.ticket, String(i))}
                  searchKeys={(r) => `${str(r.symbol)} ${str(r.side)} ${str(r.ticket)}`}
                  searchPlaceholder="Filter positions…"
                  pageSize={12}
                  aria-label="Open positions"
                  empty={
                    <DeskEmpty
                      icon={Layers}
                      title="No open positions"
                      description="When the broker session reports open trades, they appear here with stops and floating P&L."
                      actionLabel="Open Terminal"
                      actionHref="/terminal"
                      secondaryLabel="Broker Accounts"
                      secondaryHref="/broker"
                    />
                  }
                />
              )}
            </CardContent>
          </Card>
        </PageMotion>
      </DeskQueryState>
    </div>
  );
}
