"use client";

import { useQuery } from "@tanstack/react-query";
import { Gauge } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, bool, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function GapBlock({
  title,
  children,
  passed,
}: {
  title: string;
  children: React.ReactNode;
  passed?: boolean;
}) {
  return (
    <div
      className={cn(
        "border px-3 py-3",
        passed
          ? "border-[var(--success)]/30 bg-[var(--success)]/5"
          : "border-[var(--border)] bg-[var(--bg)]/40",
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-[12px] font-semibold uppercase tracking-[0.12em] text-[var(--fg)]">
          {title}
        </h3>
        <Badge tone={passed ? "success" : "warning"}>
          {passed ? "PASS" : "MISSING"}
        </Badge>
      </div>
      <dl className="space-y-1 font-mono text-[12px] tabular-nums text-[var(--fg-muted)]">
        {children}
      </dl>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-[var(--fg-subtle)]">{label}</dt>
      <dd className="text-[var(--fg)]">{value}</dd>
    </div>
  );
}

function OpportunityMeter({ meter }: { meter: Record<string, unknown> }) {
  const level = str(meter.level, "RED");
  const label = str(meter.label, "Far From Entry");
  return (
    <div
      className={cn(
        "flex flex-col items-start gap-2 border px-4 py-4",
        level === "GREEN" && "border-[var(--success)]/40 bg-[var(--success)]/10",
        level === "YELLOW" && "border-[var(--warning)]/40 bg-[var(--warning)]/10",
        level === "RED" && "border-[var(--danger)]/40 bg-[var(--danger)]/10",
      )}
    >
      <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
        Opportunity Meter
      </p>
      <p
        className={cn(
          "text-[22px] font-semibold tracking-tight",
          level === "GREEN" && "text-[var(--success)]",
          level === "YELLOW" && "text-[var(--warning)]",
          level === "RED" && "text-[var(--danger)]",
        )}
      >
        {level}
      </p>
      <p className="text-[14px] text-[var(--fg)]">{label}</p>
    </div>
  );
}

function OpportunityCard({ opp }: { opp: Record<string, unknown> }) {
  const gaps = asRecord(opp.gaps);
  const mtf = asRecord(gaps.mtf);
  const quality = asRecord(gaps.quality);
  const confluence = asRecord(gaps.confluence);
  const risk = asRecord(gaps.risk);
  const wait = asRecord(opp.estimated_time_until_next_eligible_setup);
  const meter = asRecord(opp.opportunity_meter);
  const execute = bool(opp.execute_trade);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p
            className={cn(
              "text-[15px] font-semibold",
              execute ? "text-[var(--success)]" : "text-[var(--fg)]",
            )}
          >
            {str(opp.headline)}
          </p>
          <p className="mt-0.5 font-mono text-[11px] text-[var(--fg-subtle)]">
            {str(opp.recorded_at)}
            {opp.signal_id ? ` · ${str(opp.signal_id).slice(0, 12)}` : ""}
            {opp.decision_action ? ` · ${str(opp.decision_action)}` : ""}
          </p>
        </div>
        <Badge tone={execute ? "success" : "danger"}>
          {execute ? "EXECUTE_TRADE" : "NO_TRADE"}
        </Badge>
      </header>

      <OpportunityMeter meter={meter} />

      {!execute ? (
        <div className="grid gap-3 md:grid-cols-2">
          <GapBlock title="MTF" passed={bool(mtf.passed)}>
            <Row label="Current" value={str(mtf.current, "—")} />
            <Row label="Need" value={str(mtf.need, "—")} />
            <Row label="Missing" value={str(mtf.missing, "—")} />
            {mtf.estimated_confirmation ? (
              <Row
                label="Estimated confirmation"
                value={str(mtf.estimated_confirmation)}
              />
            ) : null}
          </GapBlock>

          <GapBlock title="Quality" passed={bool(quality.passed)}>
            <Row label="Current" value={str(quality.current, "—")} />
            <Row label="Need" value={str(quality.need, "—")} />
            <Row label="Missing" value={str(quality.missing, "—")} />
          </GapBlock>

          <GapBlock title="Confluence" passed={bool(confluence.passed)}>
            <Row label="Current" value={str(confluence.current, "—")} />
            <Row label="Need" value={str(confluence.need, "—")} />
            <Row label="Missing" value={str(confluence.missing, "—")} />
          </GapBlock>

          <GapBlock title="Risk" passed={bool(risk.passed)}>
            <Row
              label="Current Lots"
              value={str(risk.current_lots || risk.raw_lots, "—")}
            />
            <Row label="Required" value={str(risk.required_lots, "0.01")} />
            <Row
              label="Additional Equity Needed"
              value={str(
                risk.additional_equity_needed_display ||
                  (risk.additional_equity_needed
                    ? `$${str(risk.additional_equity_needed)}`
                    : "—"),
              )}
            />
          </GapBlock>
        </div>
      ) : null}

      <OpsPanel title="Estimated Time Until Next Eligible Setup">
        <div className="grid gap-3 sm:grid-cols-3">
          <MetricCard
            label="Average waiting time"
            value={str(wait.average_waiting_time_display, "—")}
          />
          <MetricCard
            label="Probability next 1 hour"
            value={
              wait.probability_next_1_hour_pct != null
                ? `${num(wait.probability_next_1_hour_pct)}%`
                : "—"
            }
          />
          <MetricCard
            label="Probability next NY session"
            value={
              wait.probability_next_ny_session_pct != null
                ? `${num(wait.probability_next_ny_session_pct)}%`
                : "—"
            }
          />
        </div>
        <p className="mt-3 text-[11px] text-[var(--fg-subtle)]">
          {str(wait.note, "Historical diagnostics only — engines unchanged.")}
        </p>
      </OpsPanel>
    </div>
  );
}

export function AdaptiveOpportunityWorkspace() {
  const q = useQuery({
    queryKey: ["ite-ops-adaptive-opportunity"],
    queryFn: () => iteOpsApi.adaptiveOpportunity(40),
    retry: false,
    refetchInterval: 8_000,
  });

  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Adaptive Opportunity unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }

  const root = asRecord(q.data);
  const latest = asRecord(root.latest);
  const evaluations = asList(root.evaluations).map(asRecord);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">ADAPTIVE OPPORTUNITY</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">THRESHOLDS UNCHANGED</Badge>
      </div>

      <OpsPanel title="Current evaluation">
        {latest.gaps ? (
          <OpportunityCard opp={latest} />
        ) : (
          <DeskEmpty
            icon={Gauge}
            title="No live evaluations yet"
            description="Gap analysis appears for every live ITE evaluation recorded by Strategy Diagnostics."
          />
        )}
      </OpsPanel>

      {evaluations.length > 1 ? (
        <OpsPanel title={`Recent (${evaluations.length})`}>
          <div className="space-y-3">
            {evaluations.slice(1, 8).map((row, i) => {
              const opp = asRecord(row.opportunity);
              const meter = asRecord(opp.opportunity_meter);
              return (
                <div
                  key={`${str(row.signal_id, String(i))}-${str(row.recorded_at)}`}
                  className="flex flex-wrap items-center justify-between gap-2 border border-[var(--border)] px-3 py-2"
                >
                  <div>
                    <p className="font-mono text-[11px] text-[var(--fg-subtle)]">
                      {str(row.recorded_at)} · {str(row.decision_action)}
                    </p>
                    <p className="text-[12px] text-[var(--fg)]">
                      {str(opp.headline)}
                    </p>
                  </div>
                  <Badge
                    tone={
                      str(meter.level) === "GREEN"
                        ? "success"
                        : str(meter.level) === "YELLOW"
                          ? "warning"
                          : "danger"
                    }
                  >
                    {str(meter.level)} · {str(meter.label)}
                  </Badge>
                </div>
              );
            })}
          </div>
        </OpsPanel>
      ) : null}
    </div>
  );
}
