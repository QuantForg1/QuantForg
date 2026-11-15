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
} from "./shared";

export function Phase7ApprovalsDesk() {
  const qc = useQueryClient();
  const [decisionId, setDecisionId] = useState("");

  const q = useQuery({
    queryKey: ["p7-approvals"],
    queryFn: autonomousTradingControlApi.approvals,
    retry: false,
    staleTime: 8_000,
  });

  const createM = useMutation({
    mutationFn: () =>
      autonomousTradingControlApi.createApproval({
        decision_id: decisionId,
        bound_params: {
          symbol: "XAUUSD",
          direction: "BUY",
          volume: 0.01,
          stop_loss: 1,
          take_profit: 2,
          account_id: "bound",
        },
      }),
    onSuccess: () => {
      toast.success("Approval created (Approved ≠ LIVE)");
      setDecisionId("");
      void qc.invalidateQueries({ queryKey: ["p7-approvals"] });
    },
    onError: (err: Error) =>
      toast.error("Create failed", { description: err.message }),
  });

  const actM = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      autonomousTradingControlApi.approvalAction(id, action),
    onSuccess: () => {
      toast.success("Approval updated (never LIVE)");
      void qc.invalidateQueries({ queryKey: ["p7-approvals"] });
    },
    onError: (err: Error) =>
      toast.error("Action failed", { description: err.message }),
  });

  if (q.isLoading) return <Phase7Loading />;
  if (q.isError) return <Phase7Error message="Approvals unavailable." />;

  const rows = asList(asRecord(q.data).approvals);

  return (
    <div>
      <Phase7ModuleNav current="/decision-approvals" />
      <Phase7Banner tone="ok">
        Approvals bind exact order parameters. Material changes invalidate prior
        approval. Expired/rejected cannot execute. Approved ≠ LIVE.
      </Phase7Banner>
      <div className="mb-4 flex flex-wrap gap-2">
        <Input
          className="h-8 w-56"
          placeholder="decision_id"
          value={decisionId}
          onChange={(e) => setDecisionId(e.target.value)}
        />
        <Button
          size="sm"
          disabled={!decisionId || createM.isPending}
          onClick={() => createM.mutate()}
        >
          Propose approval
        </Button>
      </div>
      {rows.length === 0 ? (
        <Phase7Empty message="No pending approvals." />
      ) : (
        <div className="space-y-2">
          {rows.map((item, i) => {
            const row = asRecord(item);
            const id = str(row.id);
            const status = str(row.status);
            return (
              <div
                key={id || i}
                className="rounded-md border border-border/60 bg-card/30 px-3 py-2"
              >
                <div className="font-mono text-xs">
                  {id} · {status} · decision={str(row.decision_id)}
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {["Approve", "Reject", "Request Review", "Expire", "Cancel"].map(
                    (action) => (
                      <Button
                        key={action}
                        size="sm"
                        variant="secondary"
                        className="h-7 text-xs"
                        disabled={actM.isPending || status === "Approved"}
                        onClick={() =>
                          actM.mutate({
                            id,
                            action,
                          })
                        }
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
