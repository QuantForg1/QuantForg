"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { quantitativeResearchControlApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useState } from "react";
import {
  PHASE8_MODULES,
  Phase8Banner,
  Phase8Empty,
  Phase8Error,
  Phase8Loading,
  Phase8ModuleNav,
  Phase8Stat,
} from "./shared";

export function Phase8HubDesk() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const summary = useQuery({
    queryKey: ["p8-summary"],
    queryFn: quantitativeResearchControlApi.summary,
    retry: false,
    staleTime: 10_000,
  });
  const projects = useQuery({
    queryKey: ["p8-projects"],
    queryFn: quantitativeResearchControlApi.projects,
    retry: false,
    staleTime: 10_000,
  });
  const createM = useMutation({
    mutationFn: () =>
      quantitativeResearchControlApi.createProject({
        name,
        hypothesis: "Research draft hypothesis",
        instruments: ["XAUUSD"],
      }),
    onSuccess: () => {
      toast.success("Project created (research-only)");
      setName("");
      void qc.invalidateQueries({ queryKey: ["p8-projects"] });
      void qc.invalidateQueries({ queryKey: ["p8-summary"] });
    },
    onError: (err: Error) =>
      toast.error("Create failed", { description: err.message }),
  });

  if (summary.isLoading) return <Phase8Loading />;
  if (summary.isError) return <Phase8Error message="Research hub unavailable." />;

  const s = asRecord(summary.data);
  const rows = asList(asRecord(projects.data).projects);

  return (
    <div>
      <Phase8ModuleNav current="/quant-research" />
      <Phase8Banner tone="ok">
        Quantitative Research Control. Research-only — never order_send, never
        auto LIVE deploy. Backtest success is not approval. Compose existing
        QSF / Quant Studio / validation engines.
      </Phase8Banner>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Phase8Stat label="Projects" value={Number(s.projects || 0)} />
        <Phase8Stat label="Experiments" value={Number(s.experiments || 0)} />
        <Phase8Stat
          label="Pending reviews"
          value={Number(s.pending_reviews || 0)}
        />
        <Phase8Stat
          label="Order send"
          value={s.never_order_send === false ? "enabled" : "blocked"}
        />
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        <Input
          className="h-8 w-56"
          placeholder="Project name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Button
          size="sm"
          disabled={!name || createM.isPending}
          onClick={() => createM.mutate()}
        >
          New project
        </Button>
      </div>
      <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {PHASE8_MODULES.map((m) => (
          <Link
            key={m.href}
            href={m.href}
            className="rounded-md border border-border/60 bg-card/30 px-3 py-3 text-sm hover:border-accent/40"
          >
            {m.label}
          </Link>
        ))}
      </div>
      {rows.length === 0 ? (
        <Phase8Empty message="No research projects yet." />
      ) : (
        <div className="space-y-2">
          {rows.map((item, i) => {
            const row = asRecord(item);
            return (
              <div
                key={str(row.id) || i}
                className="rounded-md border border-border/60 px-3 py-2 font-mono text-xs"
              >
                {str(row.name)} · {str(row.status)} · {str(row.id)}
              </div>
            );
          })}
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" asChild>
          <Link href="/quantforg-strategy-factory">Open QSF</Link>
        </Button>
        <Button size="sm" variant="secondary" asChild>
          <Link href="/strategy-lifecycle">Strategy Lifecycle</Link>
        </Button>
        <Button size="sm" variant="secondary" asChild>
          <Link href="/autonomous-trading">Phase 7 Autonomy</Link>
        </Button>
      </div>
    </div>
  );
}
