"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { LazyEquityChart } from "@/components/charts/lazy";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DeskEmpty, DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { paperApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import {
  asList,
  asRecord,
  mapEquityCurve,
  metric,
  num,
  str,
  toneFromNumber,
} from "@/lib/desk";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { FlaskConical } from "lucide-react";
import { FeatureGate } from "@/components/platform/feature-gate";
import { PaperTradingTutorial } from "@/components/platform/paper-tutorial";

export default function PaperPage() {
  const qc = useQueryClient();
  const [symbol, setSymbol] = useState("EURUSD");
  const [volume, setVolume] = useState("0.10");

  const perfQ = useQuery({
    queryKey: ["paper-performance"],
    queryFn: paperApi.performance,
    retry: false,
  });
  const posQ = useQuery({
    queryKey: ["paper-positions"],
    queryFn: paperApi.positions,
    retry: false,
  });
  const histQ = useQuery({
    queryKey: ["paper-history"],
    queryFn: paperApi.history,
    retry: false,
  });

  const place = useMutation({
    mutationFn: paperApi.place,
    onSuccess: async () => {
      toast.success("Paper order submitted");
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["paper-performance"] }),
        qc.invalidateQueries({ queryKey: ["paper-positions"] }),
        qc.invalidateQueries({ queryKey: ["paper-history"] }),
      ]);
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Paper order failed"),
  });

  const perf = asRecord(perfQ.data?.performance);
  const portfolio = asRecord(perfQ.data?.portfolio);
  const posPayload = asRecord(posQ.data);
  const positions = asList(posPayload.items ?? posQ.data).map(asRecord);
  const hist = asRecord(histQ.data);
  const trades = asList(hist.trades).map(asRecord);
  const orders = asList(hist.orders).map(asRecord);
  const today = new Date().toISOString().slice(0, 10);
  const tradesToday = trades.filter((t) => str(t.closed_at ?? t.opened_at, "").startsWith(today));

  const balance = metric(perf, "balance") || metric(portfolio, "balance");
  const equity = metric(perf, "equity") || metric(portfolio, "equity");
  const curve = mapEquityCurve(
    trades
      .slice()
      .reverse()
      .reduce<{ t: string; equity: number }[]>((acc, t, i) => {
        const prev = acc.length ? acc[acc.length - 1].equity : metric(portfolio, "initial_balance") || 10000;
        acc.push({
          t: str(t.closed_at ?? t.opened_at, String(i + 1)).slice(5, 16),
          equity: prev + num(t.pnl, 0),
        });
        return acc;
      }, []),
  );

  const submit = (side: "buy" | "sell", reduceId?: string) => {
    place.mutate({
      symbol,
      side,
      order_type: "market",
      volume,
      ...(reduceId ? { reduce_position_id: reduceId } : {}),
    });
  };

  const resetPortfolio = () => {
    place.mutate({
      symbol,
      side: "buy",
      order_type: "market",
      volume: "0.01",
      initial_balance: "10000",
    });
    toast.message("Reset requested", {
      description: "A new paper portfolio is created when initial_balance is provided on first order.",
    });
  };

  const loading = perfQ.isLoading && posQ.isLoading;

  return (
    <FeatureGate flag="paper" label="Paper Trading">
    <div>
      <PageHeader
        title="Paper Trading"
        description="Simulate fills against live quotes without touching live execution."
        actions={
          <>
            <Button
              size="sm"
              disabled={place.isPending}
              onClick={() => submit("buy")}
            >
              Buy
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={place.isPending}
              onClick={() => submit("sell")}
            >
              Sell
            </Button>
            <Button size="sm" variant="outline" onClick={resetPortfolio}>
              Reset Portfolio
            </Button>
          </>
        }
      />

      <PaperTradingTutorial />

      {loading ? (
        <DeskSkeleton rows={5} />
      ) : perfQ.isError && posQ.isError ? (
        <DeskError message="Unable to load paper desk." onRetry={() => perfQ.refetch()} />
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <StatCard label="Balance" value={Number.isFinite(balance) ? formatCurrency(balance) : "—"} />
            <StatCard
              label="Equity"
              value={Number.isFinite(equity) ? formatCurrency(equity) : "—"}
              tone={toneFromNumber(metric(perf, "floating_pnl"))}
            />
            <StatCard label="Open Positions" value={String(positions.length || posPayload.count || 0)} />
            <StatCard label="Orders" value={String(orders.length)} />
            <StatCard label="Trades Today" value={String(tradesToday.length)} />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.4fr_0.8fr]">
            <Card>
              <CardHeader>
                <CardTitle>Equity Curve</CardTitle>
              </CardHeader>
              <CardContent>
                <LazyEquityChart data={curve} emptyLabel="Place paper trades to build an equity curve" />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Order ticket</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1.5">
                  <Label>Symbol</Label>
                  <Input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
                </div>
                <div className="space-y-1.5">
                  <Label>Volume</Label>
                  <Input value={volume} onChange={(e) => setVolume(e.target.value)} />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Button disabled={place.isPending} onClick={() => submit("buy")}>
                    Buy market
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={place.isPending}
                    onClick={() => submit("sell")}
                  >
                    Sell market
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Open Positions</CardTitle>
              <Badge tone="accent">{positions.length}</Badge>
            </CardHeader>
            <CardContent>
              {posQ.isLoading ? (
                <DeskSkeleton rows={2} />
              ) : positions.length === 0 ? (
                <DeskEmpty
                  icon={FlaskConical}
                  title="No open paper positions"
                  description="Submit a buy or sell to open a simulated position."
                />
              ) : (
                <DeskTable
                  columns={["Symbol", "Side", "Volume", "Entry", "PnL", ""]}
                  rows={positions.map((p) => [
                    str(p.symbol),
                    <Badge key="side" tone={str(p.side) === "buy" ? "success" : "warning"}>
                      {str(p.side)}
                    </Badge>,
                    str(p.remaining_volume ?? p.volume),
                    str(p.entry_price),
                    <span
                      key="pnl"
                      className={
                        num(p.floating_pnl, 0) >= 0
                          ? "text-[var(--success)]"
                          : "text-[var(--danger)]"
                      }
                    >
                      {formatCurrency(num(p.floating_pnl, 0))}
                    </span>,
                    <Button
                      key="close"
                      size="sm"
                      variant="ghost"
                      disabled={place.isPending}
                      onClick={() => submit(str(p.side) === "buy" ? "sell" : "buy", str(p.id))}
                    >
                      Close
                    </Button>,
                  ])}
                />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Trade History</CardTitle>
            </CardHeader>
            <CardContent>
              {histQ.isLoading ? (
                <DeskSkeleton rows={2} />
              ) : trades.length === 0 ? (
                <p className="text-sm text-[var(--fg-muted)]">No closed paper trades yet.</p>
              ) : (
                <DeskTable
                  columns={["Symbol", "Side", "Volume", "Entry", "Exit", "PnL"]}
                  rows={trades.slice(0, 20).map((t) => [
                    str(t.symbol),
                    str(t.side),
                    str(t.volume),
                    str(t.entry_price),
                    str(t.exit_price),
                    <span
                      key="p"
                      className={
                        num(t.pnl, 0) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"
                      }
                    >
                      {formatNumber(num(t.pnl, 0), 2)}
                    </span>,
                  ])}
                />
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
    </FeatureGate>
  );
}
