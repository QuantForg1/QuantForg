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
import { executionApi, portfolioApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatRelativeTime } from "@/lib/utils";
import { isReadOnlyMode } from "@/lib/platform/beta";

type Row = Record<string, unknown>;

function isPendingOrder(row: Row): boolean {
  const type = str(row.order_type, "").toLowerCase();
  const state = str(row.state ?? row.status, "").toLowerCase();
  if (type.includes("market") && !type.includes("stop") && !type.includes("limit")) {
    return false;
  }
  if (state && /filled|closed|canceled|cancelled|rejected|done|executed/.test(state)) {
    return false;
  }
  return true;
}

export function OrdersWorkspace({ connected }: { connected: boolean }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [modifyForm, setModifyForm] = useState({ price: "", sl: "", tp: "" });
  const [confirm, setConfirm] = useState<null | {
    title: string;
    description: string;
    action: () => Promise<void>;
    tone?: "default" | "danger";
    mode?: "modify" | "cancel";
  }>(null);

  const ordersQ = useQuery({
    queryKey: ["orders"],
    queryFn: portfolioApi.orders,
    retry: false,
  });

  const orders = useMemo(
    () => asList(ordersQ.data).map(asRecord).filter(isPendingOrder),
    [ordersQ.data],
  );

  const gatewayAction = async (
    row: Row,
    intent: "cancel" | "modify",
    overrides?: { price?: string; sl?: string; tp?: string },
  ) => {
    if (isReadOnlyMode()) {
      throw new ApiError("Read-only mode blocks order changes", 403, "read_only");
    }
    if (intent === "cancel") {
      const result = await executionApi.cancel({
        request_id: `cancel_${str(row.ticket)}_${Date.now()}`,
        ticket: Number(str(row.ticket)),
        symbol: str(row.symbol),
      });
      const outcome = str(asRecord(result).outcome);
      const { recordAudit } = await import("@/lib/observability/audit");
      recordAudit(
        "order_cancel",
        outcome === "success" ? "success" : "info",
        "Pending order cancel submitted",
        { ticket: str(row.ticket), symbol: str(row.symbol), outcome },
      );
      toast.message(outcome, { description: str(asRecord(result).message) });
      const { invalidatePostTrade } = await import("@/lib/execution/post-trade-invalidate");
      await invalidatePostTrade(qc);
      return;
    }

    const price = overrides?.price || modifyForm.price || str(row.price);
    const stopLoss = overrides?.sl || modifyForm.sl || null;
    const takeProfit = overrides?.tp || modifyForm.tp || null;
    const result = await executionApi.manage({
      request_id: `modify_${str(row.ticket)}_${Date.now()}`,
      action: "modify",
      symbol: str(row.symbol),
      ticket: Number(str(row.ticket)) || null,
      side: str(row.side).toLowerCase().includes("sell") ? "sell" : "buy",
      order_type: str(row.order_type, "limit"),
      volume: str(row.volume, "0.01"),
      price,
      stop_loss: stopLoss || null,
      take_profit: takeProfit || null,
      slippage: 10,
      magic: 0,
      comment: "",
    });
    const outcome = str(asRecord(result).outcome);
    const { recordAudit } = await import("@/lib/observability/audit");
    recordAudit(
      "order_submit",
      outcome === "success" ? "success" : "info",
      "Pending order modify submitted",
      {
        ticket: str(row.ticket),
        symbol: str(row.symbol),
        outcome,
        price,
        stop_loss: stopLoss,
        take_profit: takeProfit,
      },
    );
    toast.message(outcome, {
      description: str(asRecord(result).message),
    });
    const { invalidatePostTrade } = await import("@/lib/execution/post-trade-invalidate");
    await invalidatePostTrade(qc);
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
      id: "sl",
      header: "SL",
      cell: (r) => <span className="tabular">{str(r.stop_loss, "—")}</span>,
    },
    {
      id: "tp",
      header: "TP",
      cell: (r) => <span className="tabular">{str(r.take_profit, "—")}</span>,
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
              setModifyForm({
                price: str(r.price, ""),
                sl: str(r.stop_loss, "") === "—" ? "" : str(r.stop_loss, ""),
                tp: str(r.take_profit, "") === "—" ? "" : str(r.take_profit, ""),
              });
              setConfirm({
                title: `Modify order ${str(r.ticket)}`,
                description:
                  "Update price / SL / TP, then re-validate and submit via Execution Gateway.",
                mode: "modify",
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
                title: `Cancel pending ${str(r.ticket)}`,
                description:
                  "Cancel is routed through Execution Gateway (live send requires EXECUTION_ENABLED).",
                tone: "danger",
                mode: "cancel",
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
            actionHref="/broker"
          />
        ) : ordersQ.isLoading ? (
          <DeskSkeleton rows={4} />
        ) : ordersQ.isError ? (
          <DeskError message="Unable to load orders." onRetry={() => ordersQ.refetch()} />
        ) : (
          <>
            <p className="mb-3 text-xs text-[var(--fg-muted)]">
              Pending limit/stop orders only. Filled market orders are managed from Positions
              (close / partial / SL / TP).
            </p>
            {confirm?.mode === "modify" ? (
              <div className="mb-3 grid gap-2 sm:grid-cols-3">
                <Input
                  value={modifyForm.price}
                  onChange={(e) => setModifyForm((s) => ({ ...s, price: e.target.value }))}
                  placeholder="Price"
                  aria-label="Modified order price"
                />
                <Input
                  value={modifyForm.sl}
                  onChange={(e) => setModifyForm((s) => ({ ...s, sl: e.target.value }))}
                  placeholder="Stop loss"
                  aria-label="Modified stop loss"
                />
                <Input
                  value={modifyForm.tp}
                  onChange={(e) => setModifyForm((s) => ({ ...s, tp: e.target.value }))}
                  placeholder="Take profit"
                  aria-label="Modified take profit"
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
