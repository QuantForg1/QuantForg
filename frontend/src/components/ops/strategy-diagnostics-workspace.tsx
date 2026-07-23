"use client";

import { useQuery } from "@tanstack/react-query";
import { ScanSearch } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { iteOpsApi } from "@/lib/api/endpoints";
import {
  buildStrategyDiagnosticsModel,
  fmtDiff,
  fmtScore,
  type ConfluenceComponents,
  type DiagnosticCycle,
} from "@/lib/strategy-diagnostics";
import { cn } from "@/lib/utils";

const COMPONENT_ROWS: Array<{ key: keyof ConfluenceComponents; label: string }> = [
  { key: "smc", label: "SMC" },
  { key: "liquidity_sweep", label: "Liquidity Sweep" },
  { key: "bos", label: "BOS" },
  { key: "choch", label: "CHOCH" },
  { key: "order_block", label: "Order Block" },
  { key: "fair_value_gap", label: "Fair Value Gap" },
  { key: "trend_alignment", label: "Trend Alignment" },
  { key: "volume", label: "Volume" },
  { key: "news_filter", label: "News Filter" },
];

function toneForDiff(diff: number | null): "ok" | "warn" | "bad" | "neutral" {
  if (diff == null) return "neutral";
  if (diff >= 0) return "ok";
  if (diff > -15) return "warn";
  return "bad";
}

function Row({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "ok" | "warn" | "bad" | "neutral";
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-[var(--border)]/60 py-1.5 last:border-0">
      <span className="text-[11px] uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
        {label}
      </span>
      <span
        className={cn(
          "max-w-[70%] truncate text-right font-mono text-[12px] text-[var(--fg)]",
          tone === "ok" && "text-[var(--success)]",
          tone === "warn" && "text-[var(--warning)]",
          tone === "bad" && "text-[var(--danger)]",
        )}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

function CycleIdentity({ cycle }: { cycle: DiagnosticCycle }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <MetricCard label="Market Session" value={cycle.marketSession} />
      <MetricCard label="Signal ID" value={cycle.signalId} />
      <MetricCard
        label="Decision"
        value={cycle.decisionAction}
        tone={cycle.executed ? "ok" : cycle.rejected ? "bad" : "neutral"}
      />
      <MetricCard label="Trend H4" value={cycle.trend.h4} />
      <MetricCard label="Trend H1" value={cycle.trend.h1} />
      <MetricCard label="Trend M15" value={cycle.trend.m15} />
      <MetricCard label="Trend M5" value={cycle.trend.m5} />
      <MetricCard
        label="MTF Aligned"
        value={
          cycle.trend.aligned == null
            ? "—"
            : cycle.trend.aligned
              ? "YES"
              : "NO"
        }
        tone={
          cycle.trend.aligned == null
            ? "neutral"
            : cycle.trend.aligned
              ? "ok"
              : "bad"
        }
      />
      <MetricCard
        label="Outcome"
        value={cycle.cycleOutcome}
        tone={cycle.executed ? "ok" : "warn"}
      />
    </div>
  );
}

function QualityPanel({ cycle }: { cycle: DiagnosticCycle }) {
  const q = cycle.quality;
  return (
    <OpsPanel title="Quality Analysis">
      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard
          label="Trade Quality"
          value={fmtScore(q.score)}
          tone={q.passed ? "ok" : "bad"}
          large
        />
        <MetricCard
          label="Required Quality"
          value={fmtScore(q.required)}
          tone="neutral"
          large
        />
        <MetricCard
          label="Difference"
          value={fmtDiff(q.difference)}
          tone={toneForDiff(q.difference)}
          large
        />
      </div>
    </OpsPanel>
  );
}

function ConfluencePanel({ cycle }: { cycle: DiagnosticCycle }) {
  const c = cycle.confluence;
  return (
    <OpsPanel title="Confluence Analysis">
      <div className="mb-3 grid gap-3 sm:grid-cols-3">
        <MetricCard
          label="Total Confluence"
          value={fmtScore(c.total)}
          tone={c.passed ? "ok" : "bad"}
          large
        />
        <MetricCard
          label="Required Confluence"
          value={fmtScore(c.required)}
          large
        />
        <MetricCard
          label="Difference"
          value={fmtDiff(c.difference)}
          tone={toneForDiff(c.difference)}
          large
        />
      </div>
      <div className="border border-[var(--border)] bg-[var(--bg)]/30 px-3 py-1">
        {COMPONENT_ROWS.map((row) => (
          <Row
            key={row.key}
            label={row.label}
            value={fmtScore(c.components[row.key])}
            tone={
              c.components[row.key] == null
                ? "neutral"
                : (c.components[row.key] as number) >= 70
                  ? "ok"
                  : (c.components[row.key] as number) >= 40
                    ? "warn"
                    : "bad"
            }
          />
        ))}
      </div>
    </OpsPanel>
  );
}

function DecisionPanel({ cycle }: { cycle: DiagnosticCycle }) {
  const labels =
    cycle.rejection.allLabels.length > 0
      ? cycle.rejection.allLabels
      : [
          cycle.rejection.primaryLabel,
          cycle.rejection.secondaryLabel,
          cycle.rejection.tertiaryLabel,
        ].filter(Boolean) as string[];

  return (
    <OpsPanel title="Decision Analysis">
      {cycle.executed ? (
        <p className="text-[13px] text-[var(--success)]">
          Signal forwarded / executed — no rejection board for this cycle.
        </p>
      ) : labels.length === 0 ? (
        <p className="text-[13px] text-[var(--fg-muted)]">
          No structured rejection reasons on this cycle.
        </p>
      ) : (
        <div className="space-y-2">
          <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Rejected because
          </p>
          <ul className="space-y-1.5">
            {labels.slice(0, 3).map((label) => (
              <li
                key={label}
                className="flex items-start gap-2 font-mono text-[13px] text-[var(--danger)]"
              >
                <span aria-hidden>❌</span>
                <span>{label}</span>
              </li>
            ))}
          </ul>
          <div className="mt-3 grid gap-1 border-t border-[var(--border)] pt-2">
            <Row
              label="Primary"
              value={cycle.rejection.primaryLabel ?? "—"}
              tone="bad"
            />
            <Row
              label="Secondary"
              value={cycle.rejection.secondaryLabel ?? "—"}
              tone="warn"
            />
            <Row
              label="Tertiary"
              value={cycle.rejection.tertiaryLabel ?? "—"}
            />
          </div>
        </div>
      )}
    </OpsPanel>
  );
}

export function StrategyDiagnosticsWorkspace() {
  const q = useQuery({
    queryKey: ["ite-ops-strategy-diagnostics"],
    queryFn: () => iteOpsApi.strategyDiagnostics(100),
    retry: false,
    refetchInterval: 8_000,
  });

  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Strategy diagnostics unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }

  const model = buildStrategyDiagnosticsModel(q.data);
  const stats = model.statistics;
  const latest = model.latest;

  if (model.empty || !latest) {
    return (
      <div className="space-y-4">
        <DeskEmpty
          title="Waiting for diagnostic cycles"
          description="The ITE loop has not recorded strategy diagnostics yet. This desk observes live decisions only — it never lowers thresholds or forces trades."
          icon={ScanSearch}
        />
        {model.smartInsights.length > 0 && (
          <OpsPanel title="Smart Insight">
            <ul className="space-y-2">
              {model.smartInsights.map((line) => (
                <li key={line} className="text-[13px] text-[var(--fg-muted)]">
                  {line}
                </li>
              ))}
            </ul>
          </OpsPanel>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">ADVISORY ONLY</Badge>
        <Badge tone="warning">NO ENGINE MUTATION</Badge>
        <span className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Last {stats.window} cycles · diagnose NO_TRADE
        </span>
      </div>

      <OpsPanel title="Cycle Record">
        <CycleIdentity cycle={latest} />
      </OpsPanel>

      <div className="grid gap-4 xl:grid-cols-2">
        <QualityPanel cycle={latest} />
        <DecisionPanel cycle={latest} />
      </div>

      <ConfluencePanel cycle={latest} />

      <OpsPanel title="Statistics · Last 100 Cycles">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Signals Generated"
            value={String(stats.signalsGenerated)}
          />
          <MetricCard
            label="Signals Rejected"
            value={String(stats.signalsRejected)}
            tone="warn"
          />
          <MetricCard
            label="Signals Executed"
            value={String(stats.signalsExecuted)}
            tone={stats.signalsExecuted > 0 ? "ok" : "neutral"}
          />
          <MetricCard
            label="Execution Rate"
            value={`${stats.executionRatePct}%`}
          />
          <MetricCard
            label="Average Quality"
            value={fmtScore(stats.averageQuality)}
          />
          <MetricCard
            label="Average Confluence"
            value={fmtScore(stats.averageConfluence)}
          />
          <MetricCard
            label="Cycles In Window"
            value={String(stats.cyclesInWindow)}
          />
          <MetricCard
            label="Required Gates"
            value={`Q${model.thresholds.requiredQuality} / C${model.thresholds.requiredConfluence}`}
          />
        </div>
        <div className="mt-4 border border-[var(--border)] bg-[var(--bg)]/30 px-3 py-2">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            Top Rejection Reasons
          </p>
          {stats.topRejectionReasons.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">No rejects yet.</p>
          ) : (
            stats.topRejectionReasons.map((r) => (
              <Row
                key={r.code}
                label={r.label}
                value={`${r.count} · ${r.sharePct}%`}
                tone="bad"
              />
            ))
          )}
        </div>
      </OpsPanel>

      <OpsPanel title="Smart Insight">
        <ul className="space-y-2">
          {model.smartInsights.map((line) => (
            <li
              key={line}
              className="border-b border-[var(--border)]/50 pb-2 text-[13px] leading-relaxed text-[var(--fg)] last:border-0 last:pb-0"
            >
              {line}
            </li>
          ))}
        </ul>
      </OpsPanel>

      <OpsPanel title="Recent Cycles">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                <th className="px-2 py-2 font-medium">Session</th>
                <th className="px-2 py-2 font-medium">Signal</th>
                <th className="px-2 py-2 font-medium">H4</th>
                <th className="px-2 py-2 font-medium">H1</th>
                <th className="px-2 py-2 font-medium">M15</th>
                <th className="px-2 py-2 font-medium">M5</th>
                <th className="px-2 py-2 font-medium">Q</th>
                <th className="px-2 py-2 font-medium">C</th>
                <th className="px-2 py-2 font-medium">Primary reject</th>
              </tr>
            </thead>
            <tbody>
              {model.cycles.slice(0, 25).map((c) => (
                <tr
                  key={`${c.recordedAt}-${c.signalId}`}
                  className="border-b border-[var(--border)]/50 font-mono text-[11px]"
                >
                  <td className="px-2 py-1.5">{c.marketSession}</td>
                  <td className="max-w-[120px] truncate px-2 py-1.5" title={c.signalId}>
                    {c.signalId}
                  </td>
                  <td className="px-2 py-1.5">{c.trend.h4}</td>
                  <td className="px-2 py-1.5">{c.trend.h1}</td>
                  <td className="px-2 py-1.5">{c.trend.m15}</td>
                  <td className="px-2 py-1.5">{c.trend.m5}</td>
                  <td className="px-2 py-1.5">{fmtScore(c.quality.score)}</td>
                  <td className="px-2 py-1.5">{fmtScore(c.confluence.total)}</td>
                  <td className="max-w-[200px] truncate px-2 py-1.5 text-[var(--danger)]">
                    {c.rejection.primaryLabel ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </OpsPanel>
    </div>
  );
}
