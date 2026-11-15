"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { quantitativeResearchControlApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Phase8Banner,
  Phase8Empty,
  Phase8Error,
  Phase8Loading,
  Phase8ModuleNav,
  Phase8Stat,
} from "./shared";

export function Phase8GovernanceDesk() {
  const qc = useQueryClient();
  const [sid, setSid] = useState("strat-demo");
  const [ver, setVer] = useState("0.1.0");
  const pipe = useQuery({
    queryKey: ["p8-pipe"],
    queryFn: quantitativeResearchControlApi.validationPipeline,
    retry: false,
  });
  const appr = useQuery({
    queryKey: ["p8-appr"],
    queryFn: quantitativeResearchControlApi.approvals,
    retry: false,
  });
  const paper = useQuery({
    queryKey: ["p8-paper"],
    queryFn: quantitativeResearchControlApi.paperOverview,
    retry: false,
  });
  const createM = useMutation({
    mutationFn: () =>
      quantitativeResearchControlApi.createApproval({
        strategy_id: sid,
        strategy_version: ver,
        bound_params: {
          strategy_id: sid,
          strategy_version: ver,
          parameters_hash: "abc",
          symbol: "XAUUSD",
        },
        stage: "Human Approval",
      }),
    onSuccess: () => {
      toast.success("Approval created (Approved ≠ LIVE)");
      void qc.invalidateQueries({ queryKey: ["p8-appr"] });
    },
    onError: (err: Error) =>
      toast.error("Create failed", { description: err.message }),
  });
  const actM = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      quantitativeResearchControlApi.approvalAction(id, action),
    onSuccess: () => {
      toast.success("Updated (never LIVE deploy)");
      void qc.invalidateQueries({ queryKey: ["p8-appr"] });
    },
    onError: (err: Error) =>
      toast.error("Action failed", { description: err.message }),
  });

  if (pipe.isLoading) return <Phase8Loading />;
  if (pipe.isError) return <Phase8Error message="Governance unavailable." />;

  const p = asRecord(pipe.data);
  const stages = asList(p.stages);
  const approvals = asList(asRecord(appr.data).approvals);
  const paperRules = asRecord(asRecord(paper.data).rules);

  return (
    <div>
      <Phase8ModuleNav current="/research-governance" />
      <Phase8Banner tone="ok">
        Formal validation pipeline. Successful backtest is not automatic
        approval. Material parameter changes invalidate prior approval. Paper ≠
        LIVE.
      </Phase8Banner>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Phase8Stat label="Stages" value={stages.length} />
        <Phase8Stat label="Approvals" value={approvals.length} />
        <Phase8Stat
          label="Paper=LIVE"
          value={paperRules.paper_is_not_live === false ? "yes" : "no"}
        />
      </div>
      <div className="mb-4 space-y-1">
        {stages.map((item, i) => {
          const row = asRecord(item);
          return (
            <div key={i} className="font-mono text-xs text-muted-foreground">
              {i + 1}. {str(row.stage)} · {str(row.status)}
            </div>
          );
        })}
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        <Input
          className="h-8 w-40"
          value={sid}
          onChange={(e) => setSid(e.target.value)}
        />
        <Input
          className="h-8 w-28"
          value={ver}
          onChange={(e) => setVer(e.target.value)}
        />
        <Button
          size="sm"
          disabled={createM.isPending}
          onClick={() => createM.mutate()}
        >
          Propose approval
        </Button>
      </div>
      {approvals.length === 0 ? (
        <Phase8Empty message="No governance approvals." />
      ) : (
        <div className="space-y-2">
          {approvals.map((item, i) => {
            const row = asRecord(item);
            const id = str(row.id);
            return (
              <div
                key={id || i}
                className="rounded-md border border-border/60 px-3 py-2"
              >
                <div className="font-mono text-xs">
                  {id} · {str(row.status)} · {str(row.strategy_id)}@
                  {str(row.strategy_version)}
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {["Approve", "Reject", "Request Review", "Cancel"].map(
                    (action) => (
                      <Button
                        key={action}
                        size="sm"
                        variant="secondary"
                        className="h-7 text-xs"
                        disabled={actM.isPending}
                        onClick={() => actM.mutate({ id, action })}
                      >
                        {action}
                      </Button>
                    ),
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
