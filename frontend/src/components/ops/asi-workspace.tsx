"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Brain, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { adaptiveScalpingIntelligenceApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
        {action}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

export function AsiWorkspace() {
  const qc = useQueryClient();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const statusQ = useQuery({
    queryKey: ["asi-status"],
    queryFn: () => adaptiveScalpingIntelligenceApi.status(),
    staleTime: 15_000,
  });

  const historyQ = useQuery({
    queryKey: ["asi-history"],
    queryFn: () => adaptiveScalpingIntelligenceApi.history(12),
    staleTime: 10_000,
  });

  const evaluateM = useMutation({
    mutationFn: () => {
      const liveHistory = asList(asRecord(historyQ.data).items).map(asRecord);
      return adaptiveScalpingIntelligenceApi.evaluate({
        side: "buy",
        session: "london",
        hour_utc: new Date().getUTCHours(),
        weekday: [
          "monday",
          "tuesday",
          "wednesday",
          "thursday",
          "friday",
          "saturday",
          "sunday",
        ][new Date().getUTCDay() === 0 ? 6 : new Date().getUTCDay() - 1],
        regime: "unknown",
        volatility: "unknown",
        personality_hint: "unknown",
        pattern_id: "unspecified",
        live_confidence: 0,
        live_opportunity: null,
        capital_facts: {},
        decision_context: {
          decision: "NO_TRADE",
          reason: "Evaluate using live ASI history only — no fabricated sample rows",
        },
        historical_observations: liveHistory,
        closed_trades: [],
        opportunity_catalog: liveHistory.slice(0, 8).map((h) => ({
          opportunity_id: str(h.opportunity_id, str(h.id)),
          pattern_id: str(h.pattern_id),
        })),
      });
    },
    onSuccess: async (data) => {
      setResult(data);
      toast.success(str(data.summary, "ASI evaluated"));
      await qc.invalidateQueries({ queryKey: ["asi-status"] });
      await qc.invalidateQueries({ queryKey: ["asi-history"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "ASI evaluate failed"),
  });

  const caps = asRecord(statusQ.data?.capabilities);
  const modules = asRecord(asRecord(result).modules);
  const moduleEntries = Object.entries(modules);
  const history = asList(asRecord(historyQ.data).items);
  const insufficient = asList(asRecord(result).insufficient_modules);
  const available = asList(asRecord(result).available_modules);

  if (statusQ.isLoading && !statusQ.data) return <DeskSkeleton rows={6} />;
  if (statusQ.isError && !statusQ.data) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "ASI unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <Brain className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">{TRADING_SYMBOL} ASI</span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Advisory
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          No order_send
        </Badge>
        {caps.never_fabricate_statistics === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            No fabricated stats
          </Badge>
        ) : null}
        <Badge tone="neutral" className="text-[9px] uppercase">
          Live history only
        </Badge>
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "asi")}
        </span>
        <Button
          size="sm"
          disabled={evaluateM.isPending}
          onClick={() => evaluateM.mutate()}
        >
          Evaluate
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Summary">
          {!result ? (
            <DeskEmpty
              icon={Brain}
              title="No evaluation"
              description="Run adaptive intelligence on supplied facts"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <p className="text-[var(--fg-muted)]">
                {str(result.summary, "—")}
              </p>
              <div className="flex justify-between">
                <span className="text-[var(--fg-subtle)]">Available</span>
                <span className="font-mono">{available.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-subtle)]">Insufficient</span>
                <span className="font-mono">{insufficient.length}</span>
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                Audit {str(result.audit_id, "—")}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="Guarantees">
          <ul className="space-y-1 text-[10px] text-[var(--fg-muted)]">
            <li>Live vs historical labeled on every module</li>
            <li>Insufficient history reported — never guessed</li>
            <li>Never auto-modifies rules or risk policies</li>
            <li>Execution / Auto Trading / Decision / Risk / Safety untouched</li>
          </ul>
        </Panel>

        <Panel title="History">
          {!history.length ? (
            <DeskEmpty
              icon={Shield}
              title="No runs"
              description="Auditable evaluations"
            />
          ) : (
            <ul className="max-h-36 space-y-1 overflow-auto font-mono text-[10px]">
              {history.map((h) => {
                const row = asRecord(h);
                return (
                  <li
                    key={str(row.audit_id, "h")}
                    className="border-b border-[var(--border)]/60 py-1"
                  >
                    {str(row.audit_id, "—")} · avail {str(row.available, "0")}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Intelligence modules">
        {!moduleEntries.length ? (
          <DeskEmpty
            icon={Brain}
            title="No modules"
            description="Personality → coach"
          />
        ) : (
          <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
            {moduleEntries.map(([key, val]) => {
              const row = asRecord(val);
              const source = str(row.source, "none");
              return (
                <li
                  key={key}
                  className={cn(
                    "border px-2 py-2",
                    row.status === "insufficient_history"
                      ? "border-[var(--warning)]/40"
                      : "border-[var(--border)]",
                  )}
                >
                  <p className="text-[10px] font-medium leading-tight">
                    {str(row.module, key).replace(/_/g, " ")}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-[var(--fg-subtle)]">
                    {str(row.status, "—")} · {source}
                  </p>
                  <p className="mt-1 text-[9px] text-[var(--fg-muted)] line-clamp-2">
                    {str(row.recommendation, "")}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}
