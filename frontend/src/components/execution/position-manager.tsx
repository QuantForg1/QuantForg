"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers } from "lucide-react";
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
import { durationLabel } from "@/lib/dashboard/derive";
import { formatCurrency, formatNumber } from "@/lib/utils";

type Row = Record<string, unknown>;

export function PositionManager({ connected }: { connected: boolean }) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [partialVol, setPartialVol] = useState("0.01");
  const [slTp, setSlTp] = useState({ sl: "", tp: "" });
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<null | {
    title: string;
    description: string;
    action: () => Promise<void>;
    tone?: "default" | "danger";
  }>(null);

  const positionsQ = useQuery({
    queryKey: ["positions"],
    queryFn: () => portfolioApi.positions(),
    retry: false,
  });

  const positions = useMemo(() => asList(positionsQ.data).map(asRecord), [positionsQ.data]);

  const submitClose = async (row: Row, volume?: string) => {
    const side = str(row.side).toLowerCase() === "buy" ? "sell" : "buy";
    const vol = volume || str(row.volume, "0.01");
    const payload = {
      request_id: `close_${str(row.ticket)}_${Date.now()}`,
      symbol: str(row.symbol),
      side,
      order_type: "market",
      volume: vol,
      price: null,
      stop_loss: null,
      take_profit: null,
      slippage: 10,
      magic: 0,
      comment: `close:${str(row.ticket)}`,
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
    const outcome = str(asRecord(result).outcome);
    if (outcome === "disabled") {
      toast.message("Live send disabled", {
        description: str(asRecord(result).message, "EXECUTION_ENABLED is false."),
      });
      return;
    }
    if (outcome !== "success") {
      throw new ApiError(str(asRecord(result).message, outcome), 400, outcome);
    }
    const { recordAudit } = await import("@/lib/observability/audit");
    recordAudit("position_close", "success", "Position close submitted", {
      ticket: str(row.ticket),
      symbol: str(row.symbol),
      volume: vol,
    });
    toast.success("Close submitted", {
      description: `Ticket ${str(asRecord(result).order_ticket)}`,
    });
    await qc.invalidateQueries({ queryKey: ["positions"] });
    await qc.invalidateQueries({ queryKey: ["portfolio"] });
  };

  const submitSlTp = async (row: Row) => {
    const payload = {
      request_id: `sltp_${str(row.ticket)}_${Date.now()}`,
      symbol: str(row.symbol),
      side: str(row.side).toLowerCase() === "buy" ? "buy" : "sell",
      order_type: "market",
      volume: str(row.volume, "0.01"),
      price: null,
      stop_loss: slTp.sl || null,
      take_profit: slTp.tp || null,
      slippage: 10,
      magic: 0,
      comment: `modify-sltp:${str(row.ticket)}`,
    };
    const v = await mt5Api.validateOrder(payload);
    if (!v.valid) {
      throw new ApiError("SL/TP validation failed", 400, "invalid_stops");
    }
    const check = await executionApi.check(payload);
    toast.message(`SL/TP safety: ${str(asRecord(check).decision)}`, {
      description:
        "Modify goes through the Execution Gateway when enabled; otherwise validation + check only.",
    });
    if (str(asRecord(check).decision) !== "reject") {
      const result = await executionApi.submit(payload);
      toast.message(str(asRecord(result).outcome), {
        description: str(asRecord(result).message),
      });
    }
  };

  const pipMove = (row: Row) => {
    const open = num(row.open_price);
    const current = num(row.current_price);
    if (!Number.isFinite(open) || !Number.isFinite(current)) return NaN;
    const digits = String(open).includes(".") ? (String(open).split(".")[1]?.length ?? 5) : 5;
    const point = digits >= 3 ? 0.0001 : 0.01;
    const raw = current - open;
    const signed = str(row.side).toLowerCase() === "sell" ? -raw : raw;
    return signed / point;
  };

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const columns: DeskColumn<Row>[] = [
    {
      id: "sel",
      header: "",
      cell: (r) => {
        const id = str(r.ticket);
        return (
          <input
            type="checkbox"
            checked={selected.has(id)}
            onChange={() => toggle(id)}
            aria-label={`Select position ${id}`}
          />
        );
      },
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
      id: "entry",
      header: "Entry",
      cell: (r) => <span className="tabular">{str(r.open_price)}</span>,
    },
    {
      id: "current",
      header: "Current",
      cell: (r) => <span className="tabular">{str(r.current_price)}</span>,
    },
    {
      id: "pips",
      header: "Pips",
      sortable: true,
      accessor: (r) => pipMove(r),
      cell: (r) => {
        const p = pipMove(r);
        return (
          <span
            className={
              Number.isFinite(p) && p >= 0
                ? "tabular text-[var(--success)]"
                : "tabular text-[var(--danger)]"
            }
          >
            {Number.isFinite(p) ? formatNumber(p, 1) : "—"}
          </span>
        );
      },
    },
    {
      id: "pnl",
      header: "Floating PnL",
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
    { id: "sl", header: "SL", cell: (r) => str(r.stop_loss) },
    { id: "tp", header: "TP", cell: (r) => str(r.take_profit) },
    {
      id: "duration",
      header: "Duration",
      cell: (r) => durationLabel(r.opened_at),
    },
    {
      id: "actions",
      header: "Actions",
      cell: (r) => (
        <div className="flex flex-wrap gap-1">
          <Button
            size="sm"
            variant="ghost"
            disabled={!connected || busy}
            onClick={() =>
              setConfirm({
                title: `Close ${str(r.symbol)}`,
                description: `Market close full volume ${str(r.volume)} via Execution Gateway.`,
                tone: "danger",
                action: async () => {
                  setBusy(true);
                  try {
                    await submitClose(r);
                    setConfirm(null);
                  } catch (e) {
                    toast.error(e instanceof ApiError ? e.message : "Close failed");
                  } finally {
                    setBusy(false);
                  }
                },
              })
            }
          >
            Close
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={!connected || busy}
            onClick={() =>
              setConfirm({
                title: `Partial close ${str(r.symbol)}`,
                description: `Close ${partialVol} lots (opposite market) via gateway.`,
                tone: "danger",
                action: async () => {
                  setBusy(true);
                  try {
                    await submitClose(r, partialVol);
                    setConfirm(null);
                  } catch (e) {
                    toast.error(e instanceof ApiError ? e.message : "Partial close failed");
                  } finally {
                    setBusy(false);
                  }
                },
              })
            }
          >
            Partial
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={!connected || busy}
            onClick={() => {
              setSlTp({ sl: str(r.stop_loss, ""), tp: str(r.take_profit, "") });
              setConfirm({
                title: `Edit SL/TP · ${str(r.symbol)}`,
                description: `Validate and submit SL/TP update for ticket ${str(r.ticket)}.`,
                action: async () => {
                  setBusy(true);
                  try {
                    await submitSlTp(r);
                    setConfirm(null);
                  } catch (e) {
                    toast.error(e instanceof ApiError ? e.message : "SL/TP update failed");
                  } finally {
                    setBusy(false);
                  }
                },
              });
            }}
          >
            SL/TP
          </Button>
        </div>
      ),
    },
  ];

  return (
    <Card>
      <CardHeader className="flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
        <CardTitle>Live Position Manager</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <Input
            className="h-8 w-24"
            value={partialVol}
            onChange={(e) => setPartialVol(e.target.value)}
            aria-label="Partial close volume"
            disabled={!connected}
          />
          <Button
            size="sm"
            variant="danger"
            disabled={!connected || busy || selected.size === 0}
            onClick={() =>
              setConfirm({
                title: `Close ${selected.size} selected`,
                description: "Opposite-side market closes via Execution Gateway for each selection.",
                tone: "danger",
                action: async () => {
                  setBusy(true);
                  try {
                    for (const id of selected) {
                      const row = positions.find((p) => str(p.ticket) === id);
                      if (row) await submitClose(row);
                    }
                    setSelected(new Set());
                    setConfirm(null);
                  } catch (e) {
                    toast.error(e instanceof ApiError ? e.message : "Close selected failed");
                  } finally {
                    setBusy(false);
                  }
                },
              })
            }
          >
            Close selected
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={!connected || busy || positions.length === 0}
            onClick={() =>
              setConfirm({
                title: "Close all positions",
                description: "This will attempt market closes for every open position.",
                tone: "danger",
                action: async () => {
                  setBusy(true);
                  try {
                    for (const row of positions) await submitClose(row);
                    setConfirm(null);
                  } catch (e) {
                    toast.error(e instanceof ApiError ? e.message : "Close all failed");
                  } finally {
                    setBusy(false);
                  }
                },
              })
            }
          >
            Close all
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {!connected ? (
          <DeskEmpty
            icon={Layers}
            title="Trading disabled while disconnected"
            description="Connect MT5 to manage live positions."
            actionLabel="Connect MT5"
            onAction={() => {
              window.location.href = "/mt5";
            }}
          />
        ) : positionsQ.isLoading ? (
          <DeskSkeleton rows={4} />
        ) : positionsQ.isError ? (
          <DeskError message="Unable to load positions." onRetry={() => positionsQ.refetch()} />
        ) : (
          <>
            {confirm?.title.includes("SL/TP") ? (
              <div className="mb-3 grid gap-2 sm:grid-cols-2">
                <Input
                  placeholder="Stop loss"
                  value={slTp.sl}
                  onChange={(e) => setSlTp((s) => ({ ...s, sl: e.target.value }))}
                  aria-label="Stop loss"
                />
                <Input
                  placeholder="Take profit"
                  value={slTp.tp}
                  onChange={(e) => setSlTp((s) => ({ ...s, tp: e.target.value }))}
                  aria-label="Take profit"
                />
              </div>
            ) : null}
            <DeskDataTable
              columns={columns}
              rows={positions}
              rowKey={(r, i) => str(r.ticket, String(i))}
              searchKeys={(r) => `${str(r.symbol)} ${str(r.side)} ${str(r.ticket)}`}
              searchPlaceholder="Filter positions…"
              pageSize={8}
              aria-label="Open positions"
              empty={
                <DeskEmpty
                  icon={Layers}
                  title="No open positions"
                  description="Synced MT5 positions will appear here."
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
