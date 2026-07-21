"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { BookOpen, FlaskConical, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import {
  ecosystemApi,
  executionApi,
  intelligencePlatformApi,
  mt5Api,
  portfolioApi,
} from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

type PanelView = {
  panel_id: string;
  title: string;
  status: string;
  source: string;
  data: Record<string, unknown>;
  message: string;
};

function FeedEmpty({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <DeskEmpty
      icon={FlaskConical}
      title={title}
      description={description?.trim() || "No recorded research data"}
    />
  );
}

function Panel({
  title,
  status,
  children,
  action,
}: {
  title: string;
  status?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <div className="flex items-center gap-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            {title}
          </h2>
          {status ? (
            <Badge
              tone={
                status === "available"
                  ? "success"
                  : status === "unavailable"
                    ? "warning"
                    : "neutral"
              }
              className="text-[9px] uppercase tracking-wider"
            >
              {status}
            </Badge>
          ) : null}
        </div>
        {action}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function panelOf(
  dash: Record<string, unknown> | undefined,
  id: string,
): PanelView | null {
  const panels = asRecord(dash?.panels);
  const raw = asRecord(panels[id]);
  if (!raw.panel_id && !raw.title) return null;
  return {
    panel_id: str(raw.panel_id, id),
    title: str(raw.title, id),
    status: str(raw.status, "unavailable"),
    source: str(raw.source, ""),
    data: asRecord(raw.data),
    message: str(raw.message, ""),
  };
}

function extractRows(payload: unknown, keys: string[]): Record<string, unknown>[] {
  const root = asRecord(payload);
  for (const key of keys) {
    const list = asList(root[key]);
    if (list.length) return list.map((r) => asRecord(r));
  }
  if (Array.isArray(payload)) {
    return payload.map((r) => asRecord(r));
  }
  return [];
}

export function IntelligencePlatformWorkspace() {
  const qc = useQueryClient();
  const [kbTitle, setKbTitle] = useState("");
  const [kbBody, setKbBody] = useState("");
  const [auditId, setAuditId] = useState("");
  const [replaySnap, setReplaySnap] = useState<Record<string, unknown> | null>(
    null,
  );

  const journalQ = useQuery({
    queryKey: ["ip-execution-journal"],
    queryFn: () => executionApi.journal(40),
    staleTime: 15_000,
    retry: false,
  });
  const auditsQ = useQuery({
    queryKey: ["ip-execution-audits"],
    queryFn: () => executionApi.audits(40),
    staleTime: 15_000,
    retry: false,
  });
  const analyticsQ = useQuery({
    queryKey: ["ip-execution-analytics"],
    queryFn: () => executionApi.analytics(200),
    staleTime: 20_000,
    retry: false,
  });
  const candlesQ = useQuery({
    queryKey: ["ip-candles", TRADING_SYMBOL],
    queryFn: () => mt5Api.candles(TRADING_SYMBOL, "H1", 48),
    staleTime: 30_000,
    retry: false,
  });
  const weeklyQ = useQuery({
    queryKey: ["ip-weekly-report"],
    queryFn: () => ecosystemApi.reports("weekly"),
    staleTime: 60_000,
    retry: false,
  });
  const monthlyQ = useQuery({
    queryKey: ["ip-monthly-report"],
    queryFn: () => ecosystemApi.reports("monthly"),
    staleTime: 60_000,
    retry: false,
  });
  const historyQ = useQuery({
    queryKey: ["ip-portfolio-history"],
    queryFn: () => portfolioApi.history(),
    staleTime: 20_000,
    retry: false,
  });

  const liveFeeds = useMemo(() => {
    const journal =
      journalQ.data && !journalQ.isError
        ? extractRows(journalQ.data, ["entries", "journal", "items", "rows"])
        : null;
    const audits =
      auditsQ.data && !auditsQ.isError
        ? extractRows(auditsQ.data, ["audits", "items", "rows", "entries"])
        : null;
    const analytics =
      analyticsQ.data && !analyticsQ.isError
        ? asRecord(analyticsQ.data)
        : null;
    const candles =
      candlesQ.data && !candlesQ.isError
        ? asList(candlesQ.data).map((r) => asRecord(r))
        : null;
    const weekly =
      weeklyQ.data && !weeklyQ.isError ? asRecord(weeklyQ.data) : null;
    const monthly =
      monthlyQ.data && !monthlyQ.isError ? asRecord(monthlyQ.data) : null;
    const closed =
      historyQ.data && !historyQ.isError
        ? extractRows(historyQ.data, [
            "deals",
            "history_deals",
            "trades",
            "items",
          ])
        : null;
    return {
      execution_journal: journal,
      execution_audits: audits,
      execution_analytics: analytics,
      candles,
      weekly_report: weekly,
      monthly_report: monthly,
      closed_trades: closed,
    };
  }, [
    journalQ.data,
    journalQ.isError,
    auditsQ.data,
    auditsQ.isError,
    analyticsQ.data,
    analyticsQ.isError,
    candlesQ.data,
    candlesQ.isError,
    weeklyQ.data,
    weeklyQ.isError,
    monthlyQ.data,
    monthlyQ.isError,
    historyQ.data,
    historyQ.isError,
  ]);

  const dashQ = useQuery({
    queryKey: [
      "intelligence-platform-dashboard",
      liveFeeds.execution_journal?.length ?? "j",
      liveFeeds.execution_audits?.length ?? "a",
      liveFeeds.candles?.length ?? "c",
      liveFeeds.closed_trades?.length ?? "t",
      weeklyQ.isSuccess,
      monthlyQ.isSuccess,
      analyticsQ.isSuccess,
    ],
    queryFn: () => intelligencePlatformApi.dashboardWithFeeds(liveFeeds),
    staleTime: 8_000,
    refetchInterval: 20_000,
  });

  const statusQ = useQuery({
    queryKey: ["intelligence-platform-status"],
    queryFn: () => intelligencePlatformApi.status(),
    staleTime: 30_000,
  });

  const kbM = useMutation({
    mutationFn: () =>
      intelligencePlatformApi.addKnowledge({
        title: kbTitle,
        body: kbBody,
      }),
    onSuccess: async () => {
      setKbTitle("");
      setKbBody("");
      toast.success("Knowledge entry recorded");
      await qc.invalidateQueries({
        queryKey: ["intelligence-platform-dashboard"],
      });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Knowledge save failed"),
  });

  const loadBarsM = useMutation({
    mutationFn: async () => {
      const bars = asList(candlesQ.data).map((row) => {
        const r = asRecord(row);
        return {
          time: str(r.time ?? r.timestamp, ""),
          open: r.open,
          high: r.high,
          low: r.low,
          close: r.close,
          volume: r.volume ?? r.tick_volume,
        };
      });
      if (!bars.length) throw new Error("No recorded candles to load");
      return intelligencePlatformApi.replayLoad({
        strategy_key: "intelligence-platform",
        bars,
      });
    },
    onSuccess: (data) => {
      setReplaySnap(asRecord(data));
      toast.success("Lab replay loaded (production isolated)");
      void qc.invalidateQueries({
        queryKey: ["intelligence-platform-dashboard"],
      });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : String(e.message)),
  });

  const stepM = useMutation({
    mutationFn: () => intelligencePlatformApi.replayControl("step"),
    onSuccess: (data) => {
      setReplaySnap(asRecord(data));
      toast.info("Stepped one candle (lab only)");
    },
  });

  const diReplayM = useMutation({
    mutationFn: (id: string) => intelligencePlatformApi.decisionReplay(id),
    onSuccess: (data) => {
      toast.info(str(asRecord(data).reason, "Decision replay loaded"));
      void qc.invalidateQueries({
        queryKey: ["intelligence-platform-dashboard"],
      });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Replay failed"),
  });

  const dash = asRecord(dashQ.data);
  const caps = asRecord(statusQ.data?.capabilities);
  const replay = panelOf(dash, "replay_studio");
  const candles = panelOf(dash, "candle_playback");
  const decisions = panelOf(dash, "decision_inspector");
  const trades = panelOf(dash, "trade_review_center");
  const aiEval = panelOf(dash, "ai_evaluation_dashboard");
  const research = panelOf(dash, "research_workspace");
  const knowledge = panelOf(dash, "knowledge_base");
  const weekly = panelOf(dash, "weekly_reports");
  const monthly = panelOf(dash, "monthly_performance_reports");
  const promotion = panelOf(dash, "strategy_promotion_workflow");
  const registry = panelOf(dash, "strategy_registry_foundation");
  const governance = panelOf(dash, "ai_governance_audit");

  if (dashQ.isLoading && !dashQ.data) return <DeskSkeleton rows={8} />;
  if (dashQ.isError && !dashQ.data) {
    return (
      <DeskError
        message={
          dashQ.error instanceof ApiError
            ? dashQ.error.message
            : "Intelligence Platform unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <BookOpen className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium tracking-wide">
          Research environment
        </span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Never order_send
        </Badge>
        {caps.never_affects_production === true ? (
          <Badge tone="success" className="text-[9px] uppercase">
            Production isolated
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(dash.generated_at, "—")}
        </span>
        <Button size="sm" variant="outline" onClick={() => void dashQ.refetch()}>
          Refresh
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel
          title="Replay Studio"
          status={replay?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/trade-replay">Trade Replay</Link>
            </Button>
          }
        >
          {!replay || replay.status !== "available" ? (
            <FeedEmpty
              title={replay?.status === "empty" ? "No records" : "Unavailable"}
              description={replay?.message}
            />
          ) : (
            <div className="space-y-2 text-[11px]">
              <p className="text-[var(--fg-subtle)]">{replay.message}</p>
              <div className="flex flex-wrap gap-2 font-mono">
                <Badge tone="neutral">
                  audits: {str(replay.data.audit_count, "0")}
                </Badge>
                <Badge tone="neutral">
                  decisions: {str(replay.data.decision_count, "0")}
                </Badge>
              </div>
              <ul className="max-h-36 space-y-1 overflow-auto font-mono text-[10px]">
                {asList(replay.data.audits)
                  .slice(0, 8)
                  .map((row, i) => {
                    const r = asRecord(row);
                    return (
                      <li key={str(r.request_id, String(i))}>
                        {str(r.request_id, "—")} · {str(r.stage ?? r.status, "")}
                      </li>
                    );
                  })}
              </ul>
            </div>
          )}
        </Panel>

        <Panel title="Candle-by-Candle Playback" status={candles?.status}>
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={loadBarsM.isPending || !candlesQ.data}
                onClick={() => loadBarsM.mutate()}
              >
                Load MT5 H1 bars (lab)
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={stepM.isPending}
                onClick={() => stepM.mutate()}
              >
                Step candle
              </Button>
            </div>
            {!candles || candles.status === "unavailable" ? (
              <FeedEmpty title="No bars" description={candles?.message} />
            ) : (
              <div className="text-[11px]">
                <p className="text-[var(--fg-subtle)]">{candles.message}</p>
                <div className="mt-1 font-mono">
                  bars: {str(candles.data.candle_count, "0")} · invents:{" "}
                  {String(candles.data.invents_candles)}
                </div>
                {replaySnap ? (
                  <pre className="mt-2 max-h-28 overflow-auto border border-[var(--border)] bg-[var(--bg)] p-2 text-[10px]">
                    {JSON.stringify(replaySnap, null, 2)}
                  </pre>
                ) : null}
              </div>
            )}
          </div>
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel
          title="Decision Inspector"
          status={decisions?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/decision-intelligence">Decision Center</Link>
            </Button>
          }
        >
          <div className="mb-2 flex flex-wrap gap-2">
            <input
              value={auditId}
              onChange={(e) => setAuditId(e.target.value)}
              placeholder="audit_id"
              className="min-w-[160px] flex-1 border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-xs outline-none"
            />
            <Button
              size="sm"
              variant="outline"
              disabled={auditId.trim().length < 8 || diReplayM.isPending}
              onClick={() => diReplayM.mutate(auditId.trim())}
            >
              Replay decision
            </Button>
          </div>
          {!decisions || decisions.status !== "available" ? (
            <FeedEmpty
              title={decisions?.status === "empty" ? "No decisions" : "Unavailable"}
              description={decisions?.message}
            />
          ) : (
            <ul className="max-h-40 space-y-1 overflow-auto font-mono text-[11px]">
              {asList(decisions.data.decisions).map((row, i) => {
                const r = asRecord(row);
                return (
                  <li
                    key={str(r.audit_id, String(i))}
                    className="flex justify-between border-b border-[var(--border)]/60 py-1"
                  >
                    <span>{str(r.decision, "—")}</span>
                    <button
                      type="button"
                      className="text-[var(--fg-subtle)] hover:text-[var(--fg)]"
                      onClick={() => {
                        const id = str(r.audit_id, "");
                        setAuditId(id);
                        if (id.length >= 8) diReplayM.mutate(id);
                      }}
                    >
                      {str(r.audit_id, "").slice(0, 12)}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <Panel
          title="Trade Review Center"
          status={trades?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/journal">Journal</Link>
            </Button>
          }
        >
          {!trades || trades.status !== "available" ? (
            <FeedEmpty
              title={trades?.status === "empty" ? "No trades" : "Unavailable"}
              description={trades?.message}
            />
          ) : (
            <div className="space-y-2 text-[11px]">
              <div className="flex gap-2 font-mono">
                <Badge tone="neutral">
                  journal: {str(trades.data.journal_count, "0")}
                </Badge>
                <Badge tone="neutral">
                  closed: {str(trades.data.closed_count, "0")}
                </Badge>
              </div>
              <ul className="max-h-40 space-y-1 overflow-auto font-mono text-[10px]">
                {asList(trades.data.journal)
                  .slice(0, 8)
                  .map((row, i) => {
                    const r = asRecord(row);
                    return (
                      <li key={str(r.id ?? r.request_id, String(i))}>
                        {str(r.symbol, TRADING_SYMBOL)} {str(r.side ?? r.type, "")}{" "}
                        {str(r.status ?? r.result, "")}
                      </li>
                    );
                  })}
                {asList(trades.data.closed_trades)
                  .slice(0, 8)
                  .map((row, i) => {
                    const r = asRecord(row);
                    return (
                      <li key={`c-${str(r.ticket ?? r.deal, String(i))}`}>
                        deal {str(r.ticket ?? r.deal, "—")} ·{" "}
                        {str(r.profit ?? r.pnl, "—")}
                      </li>
                    );
                  })}
              </ul>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="AI Evaluation Dashboard" status={aiEval?.status}>
          {!aiEval || aiEval.status !== "available" ? (
            <FeedEmpty title="Unavailable" description={aiEval?.message} />
          ) : (
            <ul className="space-y-1 text-[11px]">
              {Object.entries(asRecord(aiEval.data.modules)).map(([name, body]) => (
                <li
                  key={name}
                  className="flex justify-between border-b border-[var(--border)]/60 py-1 font-mono"
                >
                  <span>{name.replace(/_/g, " ")}</span>
                  <span className="text-[var(--success)]">
                    {asRecord(body).ok ? "online" : "—"}
                  </span>
                </li>
              ))}
              {aiEval.data.analytics_status ? (
                <li className="pt-1 text-[10px] text-[var(--fg-subtle)]">
                  analytics: {str(aiEval.data.analytics_status)}
                </li>
              ) : null}
            </ul>
          )}
        </Panel>

        <Panel title="Research Workspace" status={research?.status}>
          <p className="mb-2 text-[11px] text-[var(--fg-subtle)]">
            {research?.message}
          </p>
          <Button asChild size="sm">
            <Link href={str(research?.data.href, "/research")}>
              {str(research?.data.label, "Open Research OS")}
            </Link>
          </Button>
        </Panel>

        <Panel title="Knowledge Base" status={knowledge?.status}>
          <div className="space-y-2">
            <input
              value={kbTitle}
              onChange={(e) => setKbTitle(e.target.value)}
              placeholder="Title"
              className="w-full border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-xs outline-none"
            />
            <textarea
              value={kbBody}
              onChange={(e) => setKbBody(e.target.value)}
              rows={3}
              placeholder="Research note…"
              className="w-full border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs outline-none"
            />
            <Button
              size="sm"
              disabled={!kbTitle.trim() || !kbBody.trim() || kbM.isPending}
              onClick={() => kbM.mutate()}
            >
              Record entry
            </Button>
            {!knowledge || knowledge.status !== "available" ? (
              <FeedEmpty title="Empty" description={knowledge?.message} />
            ) : (
              <ul className="max-h-32 space-y-1 overflow-auto text-[11px]">
                {asList(knowledge.data.entries).map((row) => {
                  const r = asRecord(row);
                  return (
                    <li
                      key={str(r.entry_id)}
                      className="border-b border-[var(--border)]/60 py-1"
                    >
                      <div className="font-medium">{str(r.title)}</div>
                      <div className="text-[10px] text-[var(--fg-subtle)]">
                        {str(r.author)} · {str(r.created_at).slice(0, 19)}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel
          title="Weekly Reports"
          status={weekly?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/analytics">Analytics</Link>
            </Button>
          }
        >
          {!weekly || weekly.status !== "available" ? (
            <FeedEmpty
              title={weekly?.status === "empty" ? "No report" : "Unavailable"}
              description={weekly?.message}
            />
          ) : (
            <pre className="max-h-40 overflow-auto border border-[var(--border)] bg-[var(--bg)] p-2 font-mono text-[10px]">
              {JSON.stringify(weekly.data.report, null, 2)}
            </pre>
          )}
        </Panel>

        <Panel title="Monthly Performance Reports" status={monthly?.status}>
          {!monthly || monthly.status !== "available" ? (
            <FeedEmpty
              title={monthly?.status === "empty" ? "Insufficient history" : "Unavailable"}
              description={monthly?.message}
            />
          ) : (
            <div className="space-y-2 text-[11px]">
              <p className="text-[var(--fg-subtle)]">{monthly.message}</p>
              {monthly.data.analytics_status ? (
                <Badge tone="neutral">
                  analytics: {str(monthly.data.analytics_status)}
                </Badge>
              ) : null}
              <pre className="max-h-36 overflow-auto border border-[var(--border)] bg-[var(--bg)] p-2 font-mono text-[10px]">
                {JSON.stringify(
                  {
                    report: monthly.data.report,
                    analytics: monthly.data.execution_analytics,
                  },
                  null,
                  2,
                )}
              </pre>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel
          title="Strategy Promotion Workflow"
          status={promotion?.status}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/strategy-lab">Strategy Lab</Link>
            </Button>
          }
        >
          {!promotion || promotion.status === "unavailable" ? (
            <FeedEmpty title="Unavailable" description={promotion?.message} />
          ) : (
            <div className="space-y-2 text-[11px]">
              <p className="text-[var(--fg-subtle)]">{promotion.message}</p>
              <Badge tone="success">live execution: never forwarded</Badge>
              <pre className="max-h-32 overflow-auto border border-[var(--border)] bg-[var(--bg)] p-2 font-mono text-[10px]">
                {JSON.stringify(promotion.data.dashboard, null, 2)}
              </pre>
            </div>
          )}
        </Panel>

        <Panel title="Strategy Registry Foundation" status={registry?.status}>
          {!registry || registry.status === "unavailable" ? (
            <FeedEmpty title="Unavailable" description={registry?.message} />
          ) : (
            <div className="text-[11px]">
              <div className="mb-1 font-mono">
                strategies: {str(registry.data.strategy_count, "0")}
              </div>
              <pre className="max-h-32 overflow-auto border border-[var(--border)] bg-[var(--bg)] p-2 font-mono text-[10px]">
                {JSON.stringify(registry.data.registry, null, 2)}
              </pre>
            </div>
          )}
        </Panel>

        <Panel title="AI Governance & Audit" status={governance?.status}>
          {!governance || governance.status !== "available" ? (
            <FeedEmpty
              title={governance?.status === "empty" ? "No audit rows" : "Unavailable"}
              description={governance?.message}
            />
          ) : (
            <div className="space-y-2 text-[11px]">
              <div className="flex items-center gap-1 text-[var(--fg-subtle)]">
                <Shield className="size-3.5" />
                {governance.message}
              </div>
              <div className={cn("flex flex-wrap gap-2 font-mono")}>
                <Badge tone="neutral">
                  audits: {str(governance.data.audit_count, "0")}
                </Badge>
                <Badge tone="neutral">
                  decisions: {str(governance.data.decision_audit_count, "0")}
                </Badge>
                <Badge tone="neutral">
                  timeline: {str(governance.data.timeline_count, "0")}
                </Badge>
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
