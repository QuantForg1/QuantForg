"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { GitBranch } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/dashboard/stat-card";
import { LazyBarChart, LazyEquityChart } from "@/components/charts/lazy";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DeskEmpty, DeskTable } from "@/components/desk/primitives";
import { DeskQueryState } from "@/components/desk/query-state";
import { walkforwardApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, mapEquityCurve, metric, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { loadBarsFromMt5Gateway } from "@/lib/mt5/bars-from-gateway";

export default function WalkForwardPage() {
  const qc = useQueryClient();
  const [symbol, setSymbol] = useState(TRADING_SYMBOL);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const listQ = useQuery({
    queryKey: ["walkforward"],
    queryFn: walkforwardApi.list,
    retry: false,
  });
  const detailQ = useQuery({
    queryKey: ["walkforward", selectedId],
    queryFn: () => walkforwardApi.get(selectedId!),
    enabled: Boolean(selectedId),
    retry: false,
  });

  const run = useMutation({
    mutationFn: walkforwardApi.run,
    onSuccess: async (data) => {
      const id = str(asRecord(data).id);
      toast.success("Walk-forward run finished");
      setSelectedId(id);
      await qc.invalidateQueries({ queryKey: ["walkforward"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Walk-forward failed"),
  });

  const runFromMt5 = async () => {
    try {
      const bars = await loadBarsFromMt5Gateway(symbol, "M15", 240);
      if (!bars.length) {
        toast.error("No MT5 candles for this symbol — connect gateway and retry.");
        return;
      }
      run.mutate({
        request_id: `wf-${Date.now()}`,
        symbol,
        timeframe: "m15",
        bars,
        in_sample_bars: 40,
        out_of_sample_bars: 20,
        step_bars: 20,
        optimize_params: true,
      });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Unable to load MT5 candles");
    }
  };

  const items = asList(listQ.data).map(asRecord);
  const report = asRecord(detailQ.data ?? items[0]);
  const robustness = asRecord(report.robustness);
  const aggIs = asRecord(report.aggregated_is);
  const aggOos = asRecord(report.aggregated_oos);
  const curve = mapEquityCurve(report.combined_equity);
  const folds = asList(report.folds).map(asRecord);
  const stability = folds.map((f, i) => ({
    label: `F${i + 1}`,
    value: num(asRecord(f.oos_metrics).total_return_pct, 0),
  }));
  const promotion = str(report.promotion, "");
  const pass =
    promotion === "promote_to_paper" ||
    metric(robustness, "robustness_score") >= 0.6;

  return (
    <div>
      <PageHeader
        title="Walk Forward"
        description="Out-of-sample validation, robustness scoring, and parameter stability."
        actions={
          <Button size="sm" disabled={run.isPending} onClick={() => void runFromMt5()}>
            Run validation
          </Button>
        }
      />

      <div className="mb-4 space-y-1.5">
        <Label>Symbol</Label>
        <Input className="w-40" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
        <p className="qf-caption text-[var(--fg-subtle)]">
          Bars load from MT5 gateway only — never generated in the browser.
        </p>
      </div>

      <DeskQueryState
        isLoading={listQ.isLoading}
        isError={listQ.isError}
        errorMessage="Unable to load walk-forward results."
        onRetry={() => listQ.refetch()}
        skeleton="list"
        skeletonRows={4}
      >
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Robustness Score"
              value={fmt(metric(robustness, "robustness_score"), 3)}
            />
            <StatCard
              label="Optimization Score"
              value={fmt(metric(robustness, "consistency_score"), 3)}
              hint={`Overfit ${fmt(metric(robustness, "overfitting_score"), 3)}`}
            />
            <StatCard
              label="Training (IS)"
              value={pct(metric(aggIs, "total_return_pct"))}
              hint={`Sharpe ${fmt(metric(aggIs, "sharpe_ratio"))}`}
            />
            <StatCard
              label="Testing (OOS)"
              value={pct(metric(aggOos, "total_return_pct"))}
              hint={`Sharpe ${fmt(metric(aggOos, "sharpe_ratio"))}`}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={pass ? "success" : "danger"}>{pass ? "PASS" : "FAIL"}</Badge>
            {promotion ? <Badge tone="accent">{promotion.replaceAll("_", " ")}</Badge> : null}
            <Badge tone="neutral">{str(report.status, "idle")}</Badge>
          </div>

          <div className="grid gap-4 xl:grid-cols-[0.7fr_1.3fr]">
            <Card>
              <CardHeader>
                <CardTitle>Runs</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {items.length === 0 ? (
                  <DeskEmpty
                    icon={GitBranch}
                    title="No walk-forward runs"
                    description="Run validation to score robustness across folds."
                  />
                ) : (
                  items.map((item) => {
                    const id = str(item.id);
                    return (
                      <button
                        key={id}
                        type="button"
                        onClick={() => setSelectedId(id)}
                        className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm ${
                          selectedId === id || (!selectedId && id === str(report.id))
                            ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                            : "border-[var(--border)]"
                        }`}
                      >
                        <span>
                          {str(item.symbol)} · folds {str(item.fold_count, "—")}
                        </span>
                        <Badge tone="neutral">{str(item.promotion, str(item.status))}</Badge>
                      </button>
                    );
                  })
                )}
              </CardContent>
            </Card>
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Walk Forward Equity</CardTitle>
                </CardHeader>
                <CardContent>
                  <LazyEquityChart data={curve} emptyLabel="No combined equity yet" />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Parameter Stability</CardTitle>
                </CardHeader>
                <CardContent>
                  <LazyBarChart data={stability} />
                  <p className="mt-2 text-xs text-[var(--fg-subtle)]">
                    Stability {fmt(metric(robustness, "parameter_stability"), 3)} · positive OOS folds{" "}
                    {str(robustness.positive_oos_folds, "—")}
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Fold report</CardTitle>
            </CardHeader>
            <CardContent>
              {folds.length === 0 ? (
                <p className="text-sm text-[var(--fg-muted)]">No folds in selection.</p>
              ) : (
                <DeskTable
                  columns={["Fold", "IS return", "OOS return", "OOS Sharpe", "Trades"]}
                  rows={folds.map((f, i) => {
                    const ism = asRecord(f.is_metrics);
                    const oosm = asRecord(f.oos_metrics);
                    return [
                      `F${i + 1}`,
                      pct(metric(ism, "total_return_pct")),
                      pct(metric(oosm, "total_return_pct")),
                      fmt(metric(oosm, "sharpe_ratio")),
                      str(oosm.trade_count, "—"),
                    ];
                  })}
                />
              )}
            </CardContent>
          </Card>
        </motion.div>
      </DeskQueryState>
    </div>
  );
}

function fmt(v: number, d = 2) {
  return Number.isFinite(v) ? formatNumber(v, d) : "—";
}
function pct(v: number) {
  return Number.isFinite(v) ? `${formatNumber(v, 2)}%` : "—";
}
