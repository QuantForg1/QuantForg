"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Bot, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { multiAgentAiApi } from "@/lib/api/endpoints";
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

export function MultiAgentAiWorkspace() {
  const qc = useQueryClient();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [riskOk, setRiskOk] = useState(true);
  const [safetyOk, setSafetyOk] = useState(true);

  const statusQ = useQuery({
    queryKey: ["multi-agent-status"],
    queryFn: () => multiAgentAiApi.status(),
    staleTime: 15_000,
  });

  const eventsQ = useQuery({
    queryKey: ["multi-agent-events"],
    queryFn: () => multiAgentAiApi.events(40),
    staleTime: 8_000,
  });

  const memoryQ = useQuery({
    queryKey: ["multi-agent-memory"],
    queryFn: () => multiAgentAiApi.memory(30),
    staleTime: 10_000,
  });

  const govQ = useQuery({
    queryKey: ["multi-agent-governance"],
    queryFn: () => multiAgentAiApi.governance(),
    staleTime: 30_000,
  });

  const collabM = useMutation({
    mutationFn: () =>
      multiAgentAiApi.collaborate({
        side: "buy",
        spread: 0.4,
        confidence: 72,
        regime: "trend",
        strategy_id: "ma-demo",
        strategy_signal: "buy",
        portfolio_exposure: 20,
        open_positions: 1,
        execution_mode: "LIVE",
        news_blackout: false,
        kill_switch: false,
        risk_engine_passed: riskOk,
        safety_engine_passed: safetyOk,
      }),
    onSuccess: async (data) => {
      setResult(data);
      toast.success(
        `Coordinator → ${str(data.decision, "HOLD")} (advisory)`,
      );
      await qc.invalidateQueries({ queryKey: ["multi-agent-status"] });
      await qc.invalidateQueries({ queryKey: ["multi-agent-events"] });
      await qc.invalidateQueries({ queryKey: ["multi-agent-memory"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Collaborate failed"),
  });

  const caps = asRecord(statusQ.data?.capabilities);
  const agents = asList(result?.agents);
  const voting = asRecord(asRecord(result).voting);
  const events = asList(asRecord(eventsQ.data).events);
  const memory = asList(asRecord(memoryQ.data).records);
  const gov = asRecord(govQ.data);
  const checklist = asList(gov.checklist);

  if (statusQ.isLoading && !statusQ.data) return <DeskSkeleton rows={6} />;
  if (statusQ.isError && !statusQ.data) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "Multi-Agent AI unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <Bot className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">{TRADING_SYMBOL} agents</span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Collaborate
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          No order_send
        </Badge>
        {caps.never_bypass_risk === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            Risk authoritative
          </Badge>
        ) : null}
        {caps.memory_never_rewrites_rules === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            Memory read-only rules
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "multi-agent-ai-v1")}
        </span>
        <Button
          size="sm"
          disabled={collabM.isPending}
          onClick={() => collabM.mutate()}
        >
          Run collaboration
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Authority inputs">
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
            <p className="text-[10px] text-[var(--fg-subtle)]">
              Risk and Safety outcomes are supplied from existing engines.
              Agents advise; engines remain authoritative.
            </p>
          </div>
        </Panel>

        <Panel title="Coordinator">
          {!result ? (
            <DeskEmpty
              icon={Bot}
              title="No session"
              description="Run collaboration to vote and decide"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Decision</span>
                <span className="font-mono">{str(result.decision, "HOLD")}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Allow path</span>
                <span className="font-mono">
                  {String(result.allow_execution_path ?? false)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Approve wt</span>
                <span className="font-mono">
                  {str(voting.approve_weight, "0")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Reject wt</span>
                <span className="font-mono">
                  {str(voting.reject_weight, "0")}
                </span>
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                Session {str(result.session_id, "—")}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="Governance">
          <div className="space-y-1.5 text-xs">
            <div className="flex items-center gap-2">
              <Shield className="size-3.5 text-[var(--fg-muted)]" />
              <span className="font-mono">{str(gov.status, "—")}</span>
            </div>
            <ul className="max-h-36 space-y-1 overflow-auto text-[10px] text-[var(--fg-subtle)]">
              {checklist.map((c) => {
                const row = asRecord(c);
                return (
                  <li key={str(row.step, str(row.text, "step"))}>
                    {str(row.step, "")}. {str(row.text, "")}
                  </li>
                );
              })}
            </ul>
          </div>
        </Panel>
      </div>

      <Panel title="Agent votes">
        {!agents.length ? (
          <DeskEmpty
            icon={Bot}
            title="No agent outputs"
            description="Each agent produces explainable votes"
          />
        ) : (
          <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {agents.map((a) => {
              const row = asRecord(a);
              const vote = str(row.vote, "HOLD");
              return (
                <li
                  key={str(row.agent, "agent")}
                  className={cn(
                    "border px-2 py-2",
                    vote === "REJECT"
                      ? "border-[var(--danger)]/40"
                      : "border-[var(--border)]",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium">
                      {str(row.agent, "—")}
                    </span>
                    <Badge
                      tone={
                        vote === "APPROVE"
                          ? "success"
                          : vote === "REJECT"
                            ? "danger"
                            : "neutral"
                      }
                      className="text-[9px] uppercase"
                    >
                      {vote}
                    </Badge>
                  </div>
                  <p className="mt-1 font-mono text-[10px] text-[var(--fg-subtle)]">
                    conf {str(row.confidence, "0")}
                    {row.authoritative === true ? " · authoritative" : ""}
                  </p>
                  <p className="mt-1 text-[10px] text-[var(--fg-muted)] line-clamp-2">
                    {asList(row.reasons)
                      .map((r) => str(r, ""))
                      .filter(Boolean)
                      .join(" · ") || "—"}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel title="Event bus">
          {!events.length ? (
            <DeskEmpty
              icon={Bot}
              title="No events"
              description="Agents communicate through auditable events"
            />
          ) : (
            <ul className="max-h-48 space-y-1 overflow-auto font-mono text-[10px]">
              {events.slice(0, 30).map((e) => {
                const row = asRecord(e);
                return (
                  <li
                    key={`${str(row.event_id, "ev")}-${str(row.sequence, "0")}`}
                    className="border-b border-[var(--border)]/60 py-1"
                  >
                    <span className="text-[var(--fg-subtle)]">
                      {str(row.agent, "—")}
                    </span>{" "}
                    {str(row.event_type, "event")}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel title="AI Memory">
          {!memory.length ? (
            <DeskEmpty
              icon={Bot}
              title="No memory"
              description="Observations and reports only — never rewrites rules"
            />
          ) : (
            <ul className="max-h-48 space-y-1 overflow-auto font-mono text-[10px]">
              {memory
                .slice()
                .reverse()
                .slice(0, 25)
                .map((m) => {
                  const row = asRecord(m);
                  return (
                    <li
                      key={str(row.memory_id, "mem")}
                      className="border-b border-[var(--border)]/60 py-1"
                    >
                      {str(row.kind, "observation")} · {str(row.agent, "—")} ·
                      rules={String(row.rewrites_rules ?? false)}
                    </li>
                  );
                })}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
