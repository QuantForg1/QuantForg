"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { autonomousTradingControlApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import {
  Phase7Banner,
  Phase7Error,
  Phase7Loading,
  Phase7ModuleNav,
  Phase7Stat,
} from "./shared";

const MODES = [
  "OBSERVE_ONLY",
  "ASSISTED",
  "CONTROLLED_AUTOMATION",
  "RESTRICTED_OR_DISABLED",
] as const;

export function Phase7ControlDesk() {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["p7-modes"],
    queryFn: autonomousTradingControlApi.modes,
    retry: false,
    staleTime: 5_000,
  });

  const setM = useMutation({
    mutationFn: (mode: string) =>
      autonomousTradingControlApi.setMode(mode, "ui_mode_change"),
    onSuccess: (data) => {
      toast.success(`Mode → ${str(asRecord(data).mode)} (not LIVE)`);
      void qc.invalidateQueries({ queryKey: ["p7-modes"] });
      void qc.invalidateQueries({ queryKey: ["p7-summary"] });
    },
    onError: (err: Error) =>
      toast.error("Mode change failed", { description: err.message }),
  });

  if (q.isLoading) return <Phase7Loading />;
  if (q.isError) return <Phase7Error message="Autonomy modes unavailable." />;

  const data = asRecord(q.data);
  const history = asList(data.history);
  const current = str(data.mode) || "OBSERVE_ONLY";

  return (
    <div>
      <Phase7ModuleNav current="/autonomy-control" />
      <Phase7Banner tone="warn">
        Default OBSERVE_ONLY. Mode changes are audited and never silently
        activate LIVE automation. CONTROLLED_AUTOMATION records intent only —
        Phase 7 live dispatch stays false. UI toggle is not sufficient without
        backend authorization.
      </Phase7Banner>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Phase7Stat label="Current mode" value={current} />
        <Phase7Stat label="Default" value={str(data.default_mode)} />
        <Phase7Stat
          label="Order send"
          value={data.never_order_send === false ? "enabled" : "blocked"}
        />
        <Phase7Stat
          label="Live dispatch"
          value={data.phase7_live_dispatch === true ? "ON" : "OFF"}
        />
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        {MODES.map((m) => (
          <Button
            key={m}
            size="sm"
            variant={current === m ? "default" : "secondary"}
            disabled={setM.isPending || current === m}
            onClick={() => setM.mutate(m)}
          >
            {m}
          </Button>
        ))}
      </div>
      <div className="space-y-1">
        <div className="mb-2 text-[10px] uppercase text-muted-foreground">
          Mode history
        </div>
        {history.length === 0 ? (
          <div className="text-sm text-muted-foreground">No history.</div>
        ) : (
          history
            .slice()
            .reverse()
            .map((item, i) => {
              const row = asRecord(item);
              return (
                <div
                  key={i}
                  className="font-mono text-xs text-muted-foreground"
                >
                  {str(row.at)} · {str(row.mode)} · {str(row.actor)}
                </div>
              );
            })
        )}
      </div>
    </div>
  );
}
