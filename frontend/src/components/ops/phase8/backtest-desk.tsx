"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { quantitativeResearchControlApi } from "@/lib/api/endpoints";
import { asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import {
  Phase8Banner,
  Phase8Error,
  Phase8Loading,
  Phase8ModuleNav,
  Phase8Stat,
  Phase8TabBar,
} from "./shared";

type Tab = "backtest" | "walkforward" | "montecarlo";

const TABS: { id: Tab; label: string }[] = [
  { id: "backtest", label: "Backtest" },
  { id: "walkforward", label: "Walk-forward" },
  { id: "montecarlo", label: "Monte Carlo" },
];

export function Phase8BacktestDesk() {
  const [tab, setTab] = useState<Tab>("backtest");
  const qc = useQueryClient();
  const bt = useQuery({
    queryKey: ["p8-bt"],
    queryFn: quantitativeResearchControlApi.backtestsOverview,
    retry: false,
  });
  const wf = useQuery({
    queryKey: ["p8-wf"],
    queryFn: quantitativeResearchControlApi.walkforwardOverview,
    retry: false,
  });
  const mc = useQuery({
    queryKey: ["p8-mc"],
    queryFn: quantitativeResearchControlApi.montecarloOverview,
    retry: false,
  });

  const runBt = useMutation({
    mutationFn: () =>
      quantitativeResearchControlApi.runBacktest({
        symbol: "XAUUSD",
        timeframe: "H1",
      }),
    onSuccess: (data) => {
      toast.success(
        `Experiment ${str(asRecord(data).experiment_id)} (not LIVE)`,
      );
      void qc.invalidateQueries({ queryKey: ["p8-bt"] });
    },
    onError: (err: Error) =>
      toast.error("Backtest compose failed", { description: err.message }),
  });

  const runMc = useMutation({
    mutationFn: () =>
      quantitativeResearchControlApi.runMontecarlo({
        iterations: 100,
        seed: 42,
        assumptions: ["caller must supply distribution"],
      }),
    onSuccess: () => toast.success("Monte Carlo compose recorded"),
    onError: (err: Error) =>
      toast.error("MC failed", { description: err.message }),
  });

  if (bt.isLoading) return <Phase8Loading />;
  if (bt.isError) return <Phase8Error message="Backtesting unavailable." />;

  const b = asRecord(bt.data);
  const w = asRecord(wf.data);
  const m = asRecord(mc.data);

  return (
    <div>
      <Phase8ModuleNav current="/strategy-backtesting" />
      <Phase8Banner tone="warn">
        Backtests are not guaranteed future performance. Walk-forward isolates
        OOS/holdout. Monte Carlo states assumptions — not guaranteed
        probabilities. Never order_send.
      </Phase8Banner>
      <Phase8TabBar tabs={TABS} value={tab} onChange={setTab} />
      {tab === "backtest" ? (
        <>
          <div className="mb-4 grid gap-3 sm:grid-cols-3">
            <Phase8Stat
              label="Fabricated"
              value={b.fabricated === true ? "yes" : "no"}
            />
            <Phase8Stat
              label="Backtest=LIVE"
              value={b.backtest_is_not_live === false ? "yes" : "no"}
            />
            <Phase8Stat label="Empty" value={b.empty === true ? "yes" : "no"} />
          </div>
          <Button
            size="sm"
            disabled={runBt.isPending}
            onClick={() => runBt.mutate()}
          >
            Record backtest experiment
          </Button>
        </>
      ) : null}
      {tab === "walkforward" ? (
        <div className="grid gap-3 sm:grid-cols-3">
          <Phase8Stat
            label="Holdout"
            value={str(asRecord(w.labels).holdout) || "—"}
          />
          <Phase8Stat
            label="Fabricated"
            value={w.fabricated === true ? "yes" : "no"}
          />
          <Phase8Stat
            label="Tune on test"
            value={
              asRecord(w.rules).test_data_not_used_to_tune_before_validation ===
              false
                ? "allowed"
                : "blocked"
            }
          />
        </div>
      ) : null}
      {tab === "montecarlo" ? (
        <>
          <div className="mb-4 grid gap-3 sm:grid-cols-2">
            <Phase8Stat
              label="Guaranteed probs"
              value={
                m.not_guaranteed_future_probabilities === false ? "yes" : "no"
              }
            />
            <Phase8Stat
              label="Fabricated"
              value={m.fabricated === true ? "yes" : "no"}
            />
          </div>
          <Button
            size="sm"
            disabled={runMc.isPending}
            onClick={() => runMc.mutate()}
          >
            Run MC compose
          </Button>
        </>
      ) : null}
    </div>
  );
}
