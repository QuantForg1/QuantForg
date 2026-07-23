"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { aqcApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/ai-quant-copilot", label: "Home" },
  { href: "/ai-quant-copilot/ask", label: "Ask" },
  { href: "/ai-quant-copilot/investigations", label: "Investigations" },
  { href: "/ai-quant-copilot/evidence", label: "Evidence" },
  { href: "/ai-quant-copilot/timeline", label: "Timeline" },
  { href: "/ai-quant-copilot/reports", label: "Reports" },
  { href: "/ai-quant-copilot/recommendations", label: "Recommendations" },
  { href: "/ai-quant-copilot/history", label: "History" },
] as const;

export function AqcNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/ai-quant-copilot"
            ? pathname === link.href
            : pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "px-3 py-1.5 text-[12px] uppercase tracking-[0.1em]",
              active
                ? "border border-[var(--border-strong)] bg-[var(--surface-2)] text-[var(--fg)]"
                : "text-[var(--fg-muted)] hover:text-[var(--fg)]",
            )}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}

function useAqcDashboard() {
  return useQuery({
    queryKey: ["aqc", "dashboard"],
    queryFn: () => aqcApi.dashboard(),
    refetchInterval: 60_000,
  });
}

export function AqcHomeWorkspace() {
  const q = useAqcDashboard();
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "AQC unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }

  const root = asRecord(q.data);
  const sections = asRecord(root.sections);
  const availability = asRecord(asRecord(root.context).availability);
  const investigations = asList(root.investigations).map(asRecord);
  const correlations = asRecord(root.correlations);

  return (
    <div className="space-y-4">
      <AqcNav />
      <div className="flex flex-wrap gap-2">
        <Badge tone="neutral">AI QUANT COPILOT</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">EXPLAIN ONLY</Badge>
        <Badge tone="warning">HUMANS DECIDE</Badge>
      </div>
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Operational AI for investigations and evidence across ICC, diagnostics,
        AQS, warehouse, and portfolio. Never executes trades or modifies
        production.
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Sources online"
          value={str(asRecord(root.context).source_count, "—")}
        />
        <MetricCard
          label="Investigations"
          value={String(investigations.length)}
        />
        <MetricCard
          label="Correlations"
          value={String(asList(correlations.correlations).length)}
        />
        <MetricCard
          label="Conversations"
          value={String(
            asList(asRecord(sections.conversation_history)).length,
          )}
        />
      </div>

      <OpsPanel title="Source availability">
        <div className="flex flex-wrap gap-2">
          {Object.entries(availability).map(([k, v]) => (
            <Badge key={k} tone={v ? "success" : "warning"}>
              {k}:{v ? "ok" : "—"}
            </Badge>
          ))}
        </div>
      </OpsPanel>

      <OpsPanel title="Recent investigations">
        <ul className="space-y-2">
          {investigations.slice(0, 8).map((inv) => (
            <li
              key={str(inv.id)}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge tone="neutral">{str(inv.final_decision)}</Badge>
              <span>{str(inv.title)}</span>
            </li>
          ))}
          {!investigations.length ? (
            <li className="text-[12px] text-[var(--fg-muted)]">
              No investigation cycles in current snapshot.
            </li>
          ) : null}
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button asChild size="sm" variant="outline">
            <Link href="/ai-quant-copilot/ask">Ask Copilot</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/ai-quant-copilot/investigations">Investigations</Link>
          </Button>
        </div>
      </OpsPanel>
    </div>
  );
}

export function AqcAskWorkspace() {
  const [question, setQuestion] = useState(
    "Why was no trade opened today? Show the evidence.",
  );
  const [answer, setAnswer] = useState<Record<string, unknown> | null>(null);
  const ask = useMutation({
    mutationFn: () => aqcApi.ask(question),
    onSuccess: (data) => setAnswer(asRecord(data)),
  });

  return (
    <div className="space-y-4">
      <AqcNav />
      <OpsPanel title="Ask Copilot">
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            aria-label="Ask AQC"
            className="flex-1 border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px]"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <Button
            size="sm"
            variant="secondary"
            disabled={ask.isPending || !question.trim()}
            onClick={() => ask.mutate()}
          >
            Ask
          </Button>
        </div>
        {answer ? (
          <div className="mt-3 space-y-2 border border-[var(--border)] px-3 py-3 text-[13px]">
            <p className="text-[var(--fg)]">{str(answer.answer)}</p>
            <div className="flex flex-wrap gap-2 text-[11px]">
              <Badge tone="neutral">
                source:{str(answer.source_subsystem)}
              </Badge>
              <Badge tone="success">
                confidence:{str(answer.confidence)}
              </Badge>
            </div>
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-[11px] text-[var(--fg-muted)]">
              {JSON.stringify(answer.evidence, null, 2)}
            </pre>
            <p className="text-[11px] text-[var(--fg-subtle)]">
              Advisory only — never modifies production.
            </p>
          </div>
        ) : null}
      </OpsPanel>
    </div>
  );
}

export function AqcInvestigationsWorkspace() {
  const q = useQuery({
    queryKey: ["aqc", "investigations"],
    queryFn: () => aqcApi.investigations(40),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const rows = asList(asRecord(q.data).investigations).map(asRecord);

  return (
    <div className="space-y-4">
      <AqcNav />
      <OpsPanel title="Incident investigations">
        <ul className="space-y-3">
          {rows.map((inv) => (
            <li
              key={str(inv.id)}
              className="border border-[var(--border)] px-3 py-3 text-[12px]"
            >
              <div className="mb-2 flex flex-wrap gap-2">
                <Badge tone="neutral">{str(inv.final_decision)}</Badge>
                <span className="font-medium">{str(inv.title)}</span>
              </div>
              <ol className="space-y-1 border-l border-[var(--border)] pl-3">
                {asList(inv.timeline)
                  .map(asRecord)
                  .map((step) => (
                    <li key={str(step.order)}>
                      <span className="text-[var(--fg-muted)]">
                        {str(step.stage)}
                      </span>{" "}
                      → {str(step.status)} — {str(step.reason)}
                    </li>
                  ))}
              </ol>
            </li>
          ))}
          {!rows.length ? (
            <li className="text-[var(--fg-muted)]">
              No investigations available.
            </li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function AqcEvidenceWorkspace() {
  const q = useQuery({
    queryKey: ["aqc", "evidence"],
    queryFn: () => aqcApi.evidence(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);

  return (
    <div className="space-y-4">
      <AqcNav />
      <OpsPanel title="Evidence viewer">
        <pre className="max-h-[480px] overflow-auto whitespace-pre-wrap text-[11px] text-[var(--fg-muted)]">
          {JSON.stringify(
            {
              evidence: root.evidence,
              execution_explain: root.execution_explain,
            },
            null,
            2,
          )}
        </pre>
      </OpsPanel>
    </div>
  );
}

export function AqcTimelineWorkspace() {
  const q = useQuery({
    queryKey: ["aqc", "timeline"],
    queryFn: () => aqcApi.timeline(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const rows = asList(asRecord(q.data).timeline).map(asRecord);

  return (
    <div className="space-y-4">
      <AqcNav />
      <OpsPanel title="Operational timeline">
        <ul className="space-y-2">
          {rows.map((e, i) => (
            <li
              key={`${str(e.timestamp)}-${i}`}
              className="border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <div className="flex flex-wrap gap-2">
                <Badge tone="neutral">{str(e.subsystem)}</Badge>
                <span className="text-[var(--fg-muted)]">
                  {str(e.timestamp)}
                </span>
              </div>
              <p className="mt-1">{str(e.event)}</p>
            </li>
          ))}
          {!rows.length ? (
            <li className="text-[var(--fg-muted)]">No timeline events.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function AqcReportsWorkspace() {
  const q = useQuery({
    queryKey: ["aqc", "reports"],
    queryFn: () => aqcApi.reports(20),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const rows = asList(asRecord(q.data).reports).map(asRecord);

  return (
    <div className="space-y-4">
      <AqcNav />
      <OpsPanel title="Executive reports">
        <ul className="space-y-2">
          {rows.map((r) => (
            <li
              key={str(r.report_id)}
              className="border border-[var(--border)] px-3 py-2 text-[12px]"
            >
              <div className="flex flex-wrap gap-2">
                <Badge tone="neutral">{str(r.period || r.kind)}</Badge>
                <span>{str(r.title)}</span>
              </div>
              <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-[11px] text-[var(--fg-muted)]">
                {JSON.stringify(r.trading || r, null, 2)}
              </pre>
            </li>
          ))}
          {!rows.length ? (
            <li className="text-[var(--fg-muted)]">No reports yet.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function AqcRecommendationsWorkspace() {
  const [status, setStatus] = useState("");
  const [minConf, setMinConf] = useState("");
  const [area, setArea] = useState("");
  const q = useQuery({
    queryKey: ["aqc", "recommendations", status, minConf, area],
    queryFn: () =>
      aqcApi.recommendations({
        status: status || undefined,
        minConfidence: minConf ? Number(minConf) : undefined,
        researchArea: area || undefined,
      }),
  });

  return (
    <div className="space-y-4">
      <AqcNav />
      <OpsPanel title="AQS recommendation explorer">
        <div className="mb-3 flex flex-wrap gap-2">
          <input
            aria-label="Status filter"
            placeholder="Status"
            className="border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-[12px]"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          />
          <input
            aria-label="Min confidence"
            placeholder="Min confidence"
            className="border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-[12px]"
            value={minConf}
            onChange={(e) => setMinConf(e.target.value)}
          />
          <input
            aria-label="Research area"
            placeholder="Research area"
            className="border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-[12px]"
            value={area}
            onChange={(e) => setArea(e.target.value)}
          />
        </div>
        {q.isLoading ? <DeskSkeleton rows={4} /> : null}
        {q.isError ? (
          <DeskError
            message={
              q.error instanceof Error ? q.error.message : "Unavailable"
            }
            onRetry={() => void q.refetch()}
          />
        ) : null}
        <ul className="space-y-2">
          {asList(asRecord(q.data).recommendations)
            .map(asRecord)
            .map((r) => (
              <li
                key={str(r.id)}
                className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
              >
                <Badge tone="neutral">{str(r.type)}</Badge>
                <Badge tone="warning">{str(r.status)}</Badge>
                <span>{str(r.title)}</span>
              </li>
            ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function AqcHistoryWorkspace() {
  const q = useQuery({
    queryKey: ["aqc", "conversations"],
    queryFn: () => aqcApi.conversations(50),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const rows = asList(asRecord(q.data).conversations).map(asRecord);

  return (
    <div className="space-y-4">
      <AqcNav />
      <OpsPanel title="Conversation history">
        <ul className="space-y-2">
          {rows.map((c) => (
            <li
              key={str(c.id)}
              className="border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <p className="text-[var(--fg-muted)]">Q: {str(c.question)}</p>
              <p className="mt-1">A: {str(c.answer)}</p>
              <div className="mt-1 flex flex-wrap gap-2 text-[11px]">
                <Badge tone="neutral">{str(c.source_subsystem)}</Badge>
                <Badge tone="success">
                  confidence:{str(c.confidence)}
                </Badge>
              </div>
            </li>
          ))}
          {!rows.length ? (
            <li className="text-[var(--fg-muted)]">
              No conversations yet — ask the Copilot.
            </li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}
