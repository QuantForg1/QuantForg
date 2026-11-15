"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { institutionalIntelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Phase6Banner,
  Phase6Empty,
  Phase6Error,
  Phase6Loading,
  Phase6ModuleNav,
  Phase6Stat,
  Phase6TabBar,
} from "./shared";

type Tab = "queue" | "propose" | "rules";

const TABS: { id: Tab; label: string }[] = [
  { id: "queue", label: "Queue" },
  { id: "propose", label: "Propose" },
  { id: "rules", label: "Rules" },
];

const NEXT: Record<string, string[]> = {
  Proposed: ["Under Review", "Rejected", "Expired"],
  "Under Review": ["Approved", "Rejected", "Expired"],
  Approved: ["Applied", "Expired", "Rejected"],
};

export function Phase6DecisionDesk() {
  const [tab, setTab] = useState<Tab>("queue");
  const [title, setTitle] = useState("");
  const [reason, setReason] = useState("");
  const qc = useQueryClient();

  const q = useQuery({
    queryKey: ["p6-decision"],
    queryFn: institutionalIntelligenceApi.decision,
    retry: false,
    staleTime: 10_000,
  });

  const createM = useMutation({
    mutationFn: () =>
      institutionalIntelligenceApi.createRecommendation({
        recommendation: title,
        reasoning_summary: reason,
        supporting_evidence: ["phase6_ui"],
        risks_and_limitations: [
          "Advisory only",
          "Approved does not authorize LIVE",
        ],
        expected_benefits: ["Explainable decision support"],
        required_approval: true,
        confidence: 50,
      }),
    onSuccess: () => {
      toast.success("Recommendation proposed");
      setTitle("");
      setReason("");
      void qc.invalidateQueries({ queryKey: ["p6-decision"] });
      setTab("queue");
    },
    onError: (err: Error) =>
      toast.error("Propose failed", { description: err.message }),
  });

  const statusM = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      institutionalIntelligenceApi.setRecommendationStatus(id, status),
    onSuccess: () => {
      toast.success("Status updated (Approved ≠ LIVE)");
      void qc.invalidateQueries({ queryKey: ["p6-decision"] });
    },
    onError: (err: Error) =>
      toast.error("Status update failed", { description: err.message }),
  });

  if (q.isLoading) return <Phase6Loading />;
  if (q.isError) {
    return <Phase6Error message="Decision intelligence overview unavailable." />;
  }

  const data = asRecord(q.data);
  const rows = asList(data.recommendations);
  const rules = asRecord(data.rules);

  return (
    <div>
      <Phase6ModuleNav current="/decision-intelligence" />
      <Phase6Banner tone="warn">
        AI remains advisory. Approval does not authorize LIVE execution, risk
        increases, or auto-rebalance.
      </Phase6Banner>
      <Phase6TabBar tabs={TABS} value={tab} onChange={setTab} />

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Phase6Stat label="Recommendations" value={rows.length} />
        <Phase6Stat
          label="Approved = LIVE"
          value={rules.approved_does_not_authorize_live === false ? "yes" : "no"}
        />
        <Phase6Stat
          label="Advisory default"
          value={rules.advisory_by_default === false ? "no" : "yes"}
        />
      </div>

      {tab === "queue" &&
        (rows.length === 0 ? (
          <Phase6Empty message="No recommendations yet — propose one or keep empty." />
        ) : (
          <ul className="divide-y divide-border/50 rounded-md border border-border/60">
            {rows.map((item, i) => {
              const row = asRecord(item);
              const id = str(row.id);
              const status = str(row.status) || "Proposed";
              const next = NEXT[status] || [];
              return (
                <li key={i} className="space-y-2 px-3 py-3 text-sm">
                  <div className="font-medium">
                    {str(row.recommendation) || `Rec ${i + 1}`}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {status} · confidence {str(row.confidence) || "—"}
                  </div>
                  {next.length > 0 && id ? (
                    <div className="flex flex-wrap gap-1">
                      {next.map((s) => (
                        <Button
                          key={s}
                          size="sm"
                          variant="outline"
                          className="h-7 text-xs"
                          disabled={statusM.isPending}
                          onClick={() => statusM.mutate({ id, status: s })}
                        >
                          → {s}
                        </Button>
                      ))}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ))}

      {tab === "propose" && (
        <div className="max-w-xl space-y-3">
          <Input
            placeholder="Recommendation"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <Input
            placeholder="Reasoning summary"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <Button
            size="sm"
            disabled={!title.trim() || !reason.trim() || createM.isPending}
            onClick={() => createM.mutate()}
          >
            Propose
          </Button>
        </div>
      )}

      {tab === "rules" && (
        <ul className="list-disc space-y-2 pl-5 text-sm text-muted-foreground">
          <li>Statuses: Proposed → Under Review → Approved / Rejected / Expired / Applied</li>
          <li>Approved never enables order_send or LIVE deploy</li>
          <li>Legacy Decision Center workspace remains available below / linked</li>
        </ul>
      )}
    </div>
  );
}
