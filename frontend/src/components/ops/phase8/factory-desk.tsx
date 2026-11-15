"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { quantitativeResearchControlApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import {
  Phase8Banner,
  Phase8Empty,
  Phase8Error,
  Phase8Loading,
  Phase8ModuleNav,
  Phase8Stat,
} from "./shared";

export function Phase8FactoryDesk() {
  const templates = useQuery({
    queryKey: ["p8-templates"],
    queryFn: quantitativeResearchControlApi.templates,
    retry: false,
  });
  const hypM = useMutation({
    mutationFn: () =>
      quantitativeResearchControlApi.hypothesize({
        family: "trend_following",
        symbol: "XAUUSD",
      }),
    onSuccess: (data) => {
      const row = asRecord(data);
      toast.success("Hypothesis recorded (research artifact, not LIVE)");
      if (row.profitability_claimed === true) {
        toast.error("Safety violation: profitability claimed");
      }
    },
    onError: (err: Error) =>
      toast.error("Hypothesize failed", { description: err.message }),
  });

  if (templates.isLoading) return <Phase8Loading />;
  if (templates.isError) return <Phase8Error message="Factory unavailable." />;

  const data = asRecord(templates.data);
  const rows = asList(data.templates);

  return (
    <div>
      <Phase8ModuleNav current="/strategy-factory" />
      <Phase8Banner tone="warn">
        Strategy Factory product shell. Specs are research artifacts until
        approved. AI hypotheses never claim profitability and never auto-deploy
        LIVE. Never executes arbitrary code.
      </Phase8Banner>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Phase8Stat label="Families" value={rows.length} />
        <Phase8Stat
          label="Arbitrary code"
          value={
            asRecord(data.validator).never_executes_arbitrary_code === false
              ? "allowed"
              : "blocked"
          }
        />
        <Phase8Stat label="Auto LIVE" value="blocked" />
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        <Button size="sm" disabled={hypM.isPending} onClick={() => hypM.mutate()}>
          AI hypothesize (advisory)
        </Button>
        <Button size="sm" variant="secondary" asChild>
          <Link href="/quantforg-strategy-factory">Open full QSF</Link>
        </Button>
      </div>
      {rows.length === 0 ? (
        <Phase8Empty message="No templates." />
      ) : (
        <div className="space-y-2">
          {rows.map((item, i) => {
            const row = asRecord(item);
            return (
              <div
                key={i}
                className="rounded-md border border-border/60 px-3 py-2 text-sm"
              >
                <span className="font-mono text-xs">{str(row.family)}</span>
                <span className="ml-2 text-xs text-muted-foreground">
                  code={row.executable_code_allowed ? "yes" : "no"}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
