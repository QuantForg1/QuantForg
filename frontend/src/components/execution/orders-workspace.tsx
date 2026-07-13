"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ListOrdered } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { DeskDataTable, type DeskColumn } from "@/components/desk/data-table";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { ConfirmDialog } from "@/components/execution/confirm-dialog";
import { executionApi, mt5Api, portfolioApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatRelativeTime } from "@/lib/utils";

type Row = Record<string, unknown>;

export function OrdersWorkspace({ connected }: { connected: boolean }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [modifyPrice, setModifyPrice] = useState("");
  const [confirm, setConfirm] = useState<null | {
    title: string;
    description: string;
    action: () => Promise<void>;
    tone?: "default" | "danger";
  }>(null);

  const ordersQ = useQuery({
    queryKey: ["orders"],
    queryFn: portfolioApi.orders,
    retry: false,
  });

  const orders = useMemo(() => asList(ordersQ.data).map(asRecord), [ordersQ.data]);

  const gatewayAction = async (row: Row, intent: "cancel" | "modify") => {
    const payload = {
      request_id: `${intent}_${str(row.ticket)}_${Date.now()}`,
      symbol: str(row.symbol),
      side: str(row.side).toLowerCase().includes("sell") ? "sell" : "buy",
      order_type: str(row.order_type, "limit"),
      volume: str(row.volume, "0.01"),
      price: intent === "modify" ? modifyPrice || str(row.price) : str(row.price) || null,
      stop_loss: str(row.stop_loss) === "—" ? null : str(row.stop_loss, "") || null,
      take_profit: str(row.take_profit) === "—" ? null : str(row.take_profit, "") || null,
      slippage: 10,
      magic: 0,
      comment: `${intent}:${str(row.ticket)}`,
    };
    await mt5Api.validateOrder(payload);
    const check = await executionApi.check(payload);
    if (str(asRecord(check).decision) === "reject") {
      throw new ApiError(
        asList(asRecord(check).rejection_reasons).map(String).join(" · ") || "Rejected",
        400,
        "execution_rejected",
      );
    }
    const result = await executionApi.submit(payload);
    toast.message(str(asRecord(result).outcome), {
      description: str(asRecord(result).message),
    });
    await qc.invalidateQueries({ queryKey: ["orders"] });
  };

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
      cell: (r) => str(r.symbol),
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
    {
      id: "trigger",
      header: "Trigger",
      cell: (r) => (
        <Badge tone="accent">{str(r.state ?? r.order_type, "pending")}</Badge>
      ),
    },
    {
      id: "expiry",
      header: "Expiration",
      cell: (r) => str(r.expiration ?? r.expiry ?? r.time_expiration, "GTC"),
    },
    {
      id: "created",
      header: "Created",
      sortable: true,
      accessor: (r) => str(r.created_at),
      cell: (r) => formatRelativeTime(str(r.created_at)),
    },
    {
      id: "actions",
      header: "Actions",
      cell: (r) => (
        <div className="flex gap-1">
          <Button
            size="sm"
            variant="ghost"
            disabled={!connected || busy}
            onClick={() => {
              setModifyPrice(str(r.price, ""));
              setConfirm({
                title: `Modify order ${str(r.ticket)}`,
                description: "Re-validate and submit modified pending order via Execution Gateway.",
                action: async () => {
                  setBusy(true);
                  try {
                    await gatewayAction(r, "modify");
                    setConfirm(null);
                  } catch (e) {
                    toast.error(e instanceof ApiError ? e.message : "Modify failed");
                  } finally {
                    setBusy(false);
                  }
                },
              });
            }}
          >
            Modify
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={!connected || busy}
            onClick={() =>
              setConfirm({
                title: `Cancel order ${str(r.ticket)}`,
                description:
                  "Cancellation is routed through the Execution Gateway (disabled until EXECUTION_ENABLED).",
                tone: "danger",
                action: async () => {
                  setBusy(true);
                  try {
                    await gatewayAction(r, "cancel");
                    setConfirm(null);
                  } catch (e) {
                    toast.error(e instanceof ApiError ? e.message : "Cancel failed");
                  } finally {
                    setBusy(false);
                  }
                },
              })
            }
          >
            Cancel
          </Button>
        </div>
      ),
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Orders Workspace</CardTitle>
      </CardHeader>
      <CardContent>
        {!connected ? (
          <DeskEmpty
            icon={ListOrdered}
            title="Orders unavailable offline"
            description="Connect MT5 to load and manage pending orders."
            actionLabel="Connect MT5"
            onAction={() => {
              window.location.href = "/mt5";
            }}
          />
        ) : ordersQ.isLoading ? (
          <DeskSkeleton rows={4} />
        ) : ordersQ.isError ? (
          <DeskError message="Unable to load orders." onRetry={() => ordersQ.refetch()} />
        ) : (
          <>
            {confirm?.title.startsWith("Modify") ? (
              <div className="mb-3">
                <Input
                  value={modifyPrice}
                  onChange={(e) => setModifyPrice(e.target.value)}
                  placeholder="New price"
                  aria-label="Modified order price"
                />
              </div>
            ) : null}
            <DeskDataTable
              columns={columns}
              rows={orders}
              rowKey={(r, i) => str(r.ticket, String(i))}
              searchKeys={(r) => `${str(r.symbol)} ${str(r.side)} ${str(r.order_type)}`}
              searchPlaceholder="Filter pending orders…"
              pageSize={8}
              aria-label="Pending orders"
              empty={
                <DeskEmpty
                  icon={ListOrdered}
                  title="No pending orders"
                  description="Working limit and stop orders will appear after sync."
                />
              }
            />
          </>
        )}
      </CardContent>

      <ConfirmDialog
        open={Boolean(confirm)}
        onOpenChange={(open) => {
          if (!open) setConfirm(null);
        }}
        title={confirm?.title ?? ""}
        description={confirm?.description ?? ""}
        confirmLabel="Confirm"
        tone={confirm?.tone}
        busy={busy}
        onConfirm={async () => {
          if (confirm) await confirm.action();
        }}
      />
    </Card>
  );
}
