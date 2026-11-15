"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { autonomousTradingControlApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Phase7Banner,
  Phase7Empty,
  Phase7Error,
  Phase7Loading,
  Phase7ModuleNav,
  Phase7Stat,
} from "./shared";

export function Phase7TradingDesk() {
  const qc = useQueryClient();
  const [direction, setDirection] = useState("BUY");
  const [regime, setRegime] = useState("ranging");

  const summary = useQuery({
    queryKey: ["p7-summary"],
    queryFn: autonomousTradingControlApi.summary,
    retry: false,
    staleTime: 10_000,
  });
  const decisions = useQuery({
    queryKey: ["p7-decisions"],
    queryFn: autonomousTradingControlApi.decisions,
    retry: false,
    staleTime: 10_000,
  });

  const createM = useMutation({
    mutationFn: () =>
      autonomousTradingControlApi.createDecision({
        symbol: "XAUUSD",
        direction,
        strategy: "advisory_compose",
        market_regime: regime,
        confidence: 55,
        supporting_evidence: ["phase7_ui", `regime=${regime}`],
        entry_conditions: ["manual_advisory_evaluate"],
        proposed_stop_loss: 1,
        proposed_take_profit: 2,
        risk_reward_estimate: 2,
        strategy_approved: false,
        market_data_stale: false,
        market_data_missing: false,
      }),
    onSuccess: (data) => {
      toast.success(`Decision ${str(asRecord(data).outcome) || "recorded"}`);
      void qc.invalidateQueries({ queryKey: ["p7-decisions"] });
      void qc.invalidateQueries({ queryKey: ["p7-summary"] });
    },
    onError: (err: Error) =>
      toast.error("Evaluate failed", { description: err.message }),
  });

  if (summary.isLoading || decisions.isLoading) return <Phase7Loading />;
  if (summary.isError) {
    return <Phase7Error message="Autonomous trading hub unavailable." />;
  }

  const s = asRecord(summary.data);
  const rows = asList(asRecord(decisions.data).decisions);

  return (
    <div>
      <Phase7ModuleNav current="/autonomous-trading" />
      <Phase7Banner tone="ok">
        Autonomous decision workspace. Default OBSERVE_ONLY. NO TRADE is a valid
        outcome. Never order_send. AUTHORIZED ≠ LIVE submit. Phase 7 live
        dispatch remains false.
      </Phase7Banner>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Phase7Stat label="Mode" value={str(s.mode) || "OBSERVE_ONLY"} />
        <Phase7Stat
          label="Pending approvals"
          value={Number(s.pending_approvals || 0)}
        />
        <Phase7Stat
          label="Recent decisions"
          value={Number(s.recent_decisions || 0)}
        />
        <Phase7Stat
          label="Live dispatch"
          value={s.phase7_live_dispatch === true ? "ON" : "OFF"}
        />
      </div>
      <div className="mb-4 flex flex-wrap items-end gap-2">
        <div>
          <div className="mb-1 text-[10px] uppercase text-muted-foreground">
            Direction
          </div>
          <Input
            className="h-8 w-28"
            value={direction}
            onChange={(e) => setDirection(e.target.value.toUpperCase())}
          />
        </div>
        <div>
          <div className="mb-1 text-[10px] uppercase text-muted-foreground">
            Regime
          </div>
          <Input
            className="h-8 w-36"
            value={regime}
            onChange={(e) => setRegime(e.target.value)}
          />
        </div>
        <Button
          size="sm"
          disabled={createM.isPending}
          onClick={() => createM.mutate()}
        >
          Evaluate candidate
        </Button>
      </div>
      {rows.length === 0 ? (
        <Phase7Empty message="No decisions yet. Evaluate to produce advisory outcomes including NO TRADE." />
      ) : (
        <div className="space-y-2">
          {rows.map((item, i) => {
            const row = asRecord(item);
            return (
              <div
                key={str(row.decision_id) || i}
                className="rounded-md border border-border/60 bg-card/30 px-3 py-2 text-sm"
              >
                <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs">
                  <span>{str(row.outcome)}</span>
                  <span>{str(row.symbol)}</span>
                  <span>{str(row.direction) || "—"}</span>
                  <span>conf={str(row.confidence) || "—"}</span>
                  <span className="text-muted-foreground">
                    {str(row.decision_id)}
                  </span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  eligibility={str(row.execution_eligibility)} · approval=
                  {row.required_approval ? "required" : "optional"}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
