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
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { PageMotion, StaggerGrid, StaggerItem } from "@/components/desk/motion";
import { portfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatCurrency } from "@/lib/utils";

type Row = Record<string, unknown>;

export default function PositionsPage() {
  const q = useQuery({
    queryKey: ["positions"],
    queryFn: () => portfolioApi.positions(),
    retry: false,
  });
  const positions = asList(q.data).map(asRecord);
  const totalPnl = positions.reduce((s, p) => s + num(p.profit, 0), 0);

  const columns: DeskColumn<Row>[] = [
    {
      id: "ticket",
      header: "Ticket",
      sortable: true,
      accessor: (r) => str(r.ticket),
      cell: (r) => <span className="tabular text-[var(--fg-muted)]">{str(r.ticket)}</span>,
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
      id: "open",
      header: "Open",
      sortable: true,
      accessor: (r) => num(r.open_price, 0),
      cell: (r) => <span className="tabular">{str(r.open_price)}</span>,
    },
    {
      id: "current",
      header: "Current",
      sortable: true,
      accessor: (r) => num(r.current_price, 0),
      cell: (r) => <span className="tabular">{str(r.current_price)}</span>,
    },
    {
      id: "sl",
      header: "SL",
      cell: (r) => str(r.stop_loss),
    },
    {
      id: "tp",
      header: "TP",
      cell: (r) => str(r.take_profit),
    },
    {
      id: "pnl",
      header: "PnL",
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
        title="Positions"
        description="Open exposure across symbols and sides."
        actions={
          <Button variant="secondary" size="sm" asChild>
            <Link href="/execution">Trade</Link>
          </Button>
        }
      />
      {q.isLoading ? (
        <DeskSkeleton variant="page" />
      ) : q.isError ? (
        <DeskError message="Unable to load positions." onRetry={() => q.refetch()} />
      ) : (
        <PageMotion>
          <StaggerGrid className="grid gap-4 sm:grid-cols-3">
            <StaggerItem>
              <StatCard label="Open" value={String(positions.length)} />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Unrealized PnL"
                value={formatCurrency(totalPnl)}
                tone={totalPnl >= 0 ? "up" : "down"}
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
                    description="Live positions appear after MT5 sync."
                    actionLabel="Go to MT5"
                    onAction={() => {
                      window.location.href = "/mt5";
                    }}
                    secondaryLabel="Paper trade"
                    onSecondary={() => {
                      window.location.href = "/paper";
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
