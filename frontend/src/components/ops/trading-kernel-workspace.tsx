"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Layers3, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { tradingKernelApi } from "@/lib/api/endpoints";
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

export function TradingKernelWorkspace() {
  const qc = useQueryClient();
  const [cycle, setCycle] = useState<Record<string, unknown> | null>(null);
  const [replay, setReplay] = useState<Record<string, unknown> | null>(null);
  const [riskOk, setRiskOk] = useState(true);
  const [safetyOk, setSafetyOk] = useState(true);
  const [decision, setDecision] = useState<"HOLD" | "APPROVE" | "REJECT">(
    "HOLD",
  );

  const statusQ = useQuery({
    queryKey: ["trading-kernel-status"],
    queryFn: () => tradingKernelApi.status(),
    staleTime: 15_000,
  });

  const eventsQ = useQuery({
    queryKey: ["trading-kernel-events"],
    queryFn: () => tradingKernelApi.events(40),
    staleTime: 8_000,
  });

  const certQ = useQuery({
    queryKey: ["trading-kernel-cert"],
    queryFn: () => tradingKernelApi.certification(),
    staleTime: 30_000,
  });

  const flagsQ = useQuery({
    queryKey: ["trading-kernel-flags"],
    queryFn: () => tradingKernelApi.featureFlags(),
    staleTime: 20_000,
  });

  const cycleM = useMutation({
    mutationFn: () =>
      tradingKernelApi.cycle({
        side: "buy",
        spread: 0.4,
        confidence: 70,
        news_blackout: false,
        kill_switch: false,
        risk_engine_passed: riskOk,
        safety_engine_passed: safetyOk,
        decision,
      }),
    onSuccess: async (data) => {
      setCycle(data);
      setReplay(null);
      toast.success(`Kernel cycle → ${str(data.decision, "HOLD")} (advisory)`);
      await qc.invalidateQueries({ queryKey: ["trading-kernel-status"] });
      await qc.invalidateQueries({ queryKey: ["trading-kernel-events"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Cycle failed"),
  });

  const stageReplayM = useMutation({
    mutationFn: (traceId: string) => tradingKernelApi.stageReplay(traceId),
    onSuccess: (data) => {
      setReplay(data);
      toast.info("Stage replay loaded (read-only)");
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Stage replay failed"),
  });

  const detReplayM = useMutation({
    mutationFn: (traceId: string) =>
      tradingKernelApi.deterministicReplay(traceId),
    onSuccess: (data) => {
      setReplay(data);
      toast.info(
        data.deterministic
          ? "Deterministic replay matched"
          : `Replay ${str(data.status, "mismatch")}`,
      );
    },
    onError: (e) =>
      toast.error(
        e instanceof ApiError ? e.message : "Deterministic replay failed",
      ),
  });

  const caps = asRecord(statusQ.data?.capabilities);
  const state = asRecord(statusQ.data?.state);
  const graph = asRecord(asRecord(cycle).graph);
  const nodes = asList(graph.nodes);
  const events = asList(asRecord(eventsQ.data).events);
  const cert = asRecord(certQ.data);
  const flags = asRecord(asRecord(flagsQ.data).flags);
  const recent = asList(statusQ.data?.recent_cycles);
  const traceId = str(cycle?.trace_id, "");

  if (statusQ.isLoading && !statusQ.data) return <DeskSkeleton rows={6} />;
  if (statusQ.isError && !statusQ.data) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "Trading Kernel unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <Layers3 className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">{TRADING_SYMBOL} kernel</span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Orchestrates only
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          No order_send
        </Badge>
        {caps.never_bypass_risk === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            Risk untouched
          </Badge>
        ) : null}
        {caps.never_bypass_safety === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            Safety untouched
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "trading-kernel-v1")} ·{" "}
          {str(state.state, "IDLE")}
        </span>
        <Button
          size="sm"
          disabled={cycleM.isPending}
          onClick={() => cycleM.mutate()}
        >
          Run cycle
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Cycle inputs">
          <div className="space-y-2 text-xs">
            <label className="flex items-center justify-between gap-2">
              <span className="text-[var(--fg-muted)]">Risk Engine passed</span>
              <input
                type="checkbox"
                checked={riskOk}
                onChange={(e) => setRiskOk(e.target.checked)}
                className="size-3.5"
              />
            </label>
            <label className="flex items-center justify-between gap-2">
              <span className="text-[var(--fg-muted)]">Safety Engine passed</span>
              <input
                type="checkbox"
                checked={safetyOk}
                onChange={(e) => setSafetyOk(e.target.checked)}
                className="size-3.5"
              />
            </label>
            <label className="flex items-center justify-between gap-2">
              <span className="text-[var(--fg-muted)]">Advisory decision</span>
              <select
                value={decision}
                onChange={(e) =>
                  setDecision(e.target.value as "HOLD" | "APPROVE" | "REJECT")
                }
                className="border border-[var(--border)] bg-[var(--bg)] px-2 py-1 font-mono text-[11px]"
              >
                <option value="HOLD">HOLD</option>
                <option value="APPROVE">APPROVE</option>
                <option value="REJECT">REJECT</option>
              </select>
            </label>
            <p className="text-[10px] text-[var(--fg-subtle)]">
              Risk/Safety outcomes are supplied facts from existing engines —
              kernel never evaluates or bypasses them.
            </p>
          </div>
        </Panel>

        <Panel title="Decision graph">
          {!cycle ? (
            <DeskEmpty
              icon={Layers3}
              title="No cycle"
              description="Run a kernel cycle to build the graph"
            />
          ) : (
            <ul className="space-y-1.5">
              {nodes.map((n) => {
                const row = asRecord(n);
                return (
                  <li
                    key={str(row.stage, str(row.id, "node"))}
                    className={cn(
                      "flex items-center justify-between border px-2 py-1.5 font-mono text-[11px]",
                      row.ok === true
                        ? "border-[var(--border)]"
                        : "border-[var(--danger)]/40",
                    )}
                  >
                    <span>{str(row.stage, "—")}</span>
                    <span className="text-[var(--fg-subtle)] truncate max-w-[60%]">
                      {str(row.detail, "")}
                    </span>
                  </li>
                );
              })}
              <li className="pt-1 text-[10px] text-[var(--fg-subtle)]">
                Decision: {str(cycle.decision, "HOLD")} · allow path:{" "}
                {String(cycle.allow_execution_path ?? false)} (advisory)
              </li>
            </ul>
          )}
        </Panel>

        <Panel title="Certification">
          {!Object.keys(cert).length ? (
            <DeskEmpty icon={Shield} title="No certification payload" description="Certification feed unavailable" />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Status</span>
                <span className="font-mono">{str(cert.status, "—")}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Promote LIVE</span>
                <span className="font-mono">
                  {String(cert.auto_promote ?? false)}
                </span>
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                {str(cert.detail, "Operator checklist only — never auto LIVE")}
              </p>
              <Button asChild size="sm" variant="outline" className="mt-1">
                <Link href="/production-readiness">Open readiness</Link>
              </Button>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel
          title="Event bus"
          action={
            traceId ? (
              <div className="flex gap-1">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={stageReplayM.isPending}
                  onClick={() => stageReplayM.mutate(traceId)}
                >
                  Stage replay
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={detReplayM.isPending}
                  onClick={() => detReplayM.mutate(traceId)}
                >
                  Deterministic
                </Button>
              </div>
            ) : null
          }
        >
          {!events.length ? (
            <DeskEmpty
              icon={Layers3}
              title="No events"
              description="Auditable kernel events appear after cycles"
            />
          ) : (
            <ul className="max-h-56 space-y-1 overflow-auto font-mono text-[10px]">
              {events.slice(0, 25).map((e) => {
                const row = asRecord(e);
                return (
                  <li
                    key={`${str(row.event_id, "ev")}-${str(row.sequence, "0")}`}
                    className="border-b border-[var(--border)]/60 py-1"
                  >
                    <span className="text-[var(--fg-subtle)]">
                      {str(row.stage, "—")}
                    </span>{" "}
                    {str(row.event_type, str(row.type, "event"))} ·{" "}
                    {str(row.trace_id, "").slice(0, 16)}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel title="Feature flags · plugins · replay">
          <div className="mb-2 flex flex-wrap gap-1">
            {Object.entries(flags).map(([k, v]) => (
              <Badge
                key={k}
                tone={v === true ? "success" : "neutral"}
                className="text-[9px] font-mono"
              >
                {k}={String(v)}
              </Badge>
            ))}
            {!Object.keys(flags).length ? (
              <span className="text-[10px] text-[var(--fg-subtle)]">
                No flags loaded
              </span>
            ) : null}
          </div>
          <p className="mb-2 text-[10px] text-[var(--fg-subtle)]">
            Plugins isolated · recent cycles: {recent.length}
          </p>
          {!replay ? (
            <DeskEmpty
              icon={Layers3}
              title="No replay"
              description="Run stage or deterministic replay on a cycle trace"
            />
          ) : (
            <pre className="max-h-48 overflow-auto border border-[var(--border)] bg-[var(--bg)] p-2 font-mono text-[10px] text-[var(--fg-muted)]">
              {JSON.stringify(replay, null, 2)}
            </pre>
          )}
        </Panel>
      </div>
    </div>
  );
}
