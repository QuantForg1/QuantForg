"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DeskEmpty,
  DeskError,
  DeskSkeleton,
  DeskTable,
} from "@/components/desk/primitives";
import { NocPanel, NocRow } from "@/components/ops/noc/noc-primitives";
import { continuousImprovementApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";
import {
  canAccessIteOps,
  iteOpsAccessDeniedMessage,
} from "@/lib/auth/ite-ops-access";

type Section =
  | "overview"
  | "validation"
  | "trading"
  | "learning"
  | "release"
  | "scorecard"
  | "trends"
  | "reports";

function fmt(v: unknown, fallback = "—"): string {
  if (v === null || v === undefined || v === "") return fallback;
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") return Number.isFinite(v) ? String(v) : fallback;
  return String(v);
}

/**
 * Institutional Live Validation & Continuous Improvement — RC4 ops desk.
 * Observe-only. Never fabricates metrics. Never mutates trading.
 */
export function ContinuousImprovementProgram() {
  const { user } = useAuth();
  const allowed = canAccessIteOps(user);
  const [section, setSection] = useState<Section>("overview");

  const programQ = useQuery({
    queryKey: ["continuous-improvement-program"],
    queryFn: () => continuousImprovementApi.program(),
    enabled: allowed,
    refetchInterval: 20_000,
    retry: false,
  });

  const data = asRecord(programQ.data);
  const flags = asRecord(data.flags);
  const validation = asRecord(data.continuous_validation);
  const components = asRecord(validation.components);
  const trading = asRecord(data.trading_effectiveness);
  const learning = asRecord(data.learning_review);
  const release = asRecord(data.release_confidence);
  const scorecard = asRecord(data.operational_scorecard);
  const categories = asRecord(scorecard.categories);
  const trends = asRecord(data.historical_trends);
  const valTrends = asRecord(trends.validation_trends);
  const reports = asRecord(data.auto_reports);

  const sections = useMemo(
    () =>
      [
        ["overview", "Overview"],
        ["validation", "Validation"],
        ["trading", "Effectiveness"],
        ["learning", "Learning"],
        ["release", "Release"],
        ["scorecard", "Scorecard"],
        ["trends", "Trends"],
        ["reports", "Reports"],
      ] as const,
    [],
  );

  if (!allowed) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(
          user,
          undefined,
          "Continuous Improvement",
        )}
      />
    );
  }
  if (programQ.isLoading && !programQ.data) return <DeskSkeleton rows={12} />;
  if (programQ.error && !programQ.data) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(
          user,
          programQ.error,
          "Continuous Improvement",
        )}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="accent">CI v1</Badge>
        <Badge tone="success">
          trading · {fmt(flags.modifies_trading, "false")}
        </Badge>
        <Badge tone="success">
          fabricate · {fmt(flags.fabricates_metrics, "false")}
        </Badge>
        <Button asChild size="sm" variant="outline">
          <Link href="/admin/noc">
            <Activity className="mr-1 size-3.5" />
            NOC
          </Link>
        </Button>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {sections.map(([id, label]) => (
          <Button
            key={id}
            size="sm"
            variant={section === id ? "secondary" : "ghost"}
            onClick={() => setSection(id)}
          >
            {label}
          </Button>
        ))}
      </div>

      {section === "overview" ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <NocPanel id="ci-val" title="Production Validation">
            <NocRow label="Overall" value={fmt(validation.overall)} />
            <NocRow
              label="Components OK"
              value={`${fmt(validation.ok_count)} / ${fmt(validation.target_count)}`}
            />
            <NocRow
              label="History samples"
              value={fmt(validation.history_count, "0")}
            />
          </NocPanel>
          <NocPanel id="ci-trade" title="Trading Effectiveness">
            <NocRow label="Win rate" value={fmt(trading.win_rate)} />
            <NocRow label="Profit factor" value={fmt(trading.profit_factor)} />
            <NocRow label="Expectancy" value={fmt(trading.expectancy)} />
            <NocRow
              label="Measured fields"
              value={fmt(trading.measured_count, "0")}
            />
          </NocPanel>
          <NocPanel id="ci-score" title="Operational Scorecard">
            <NocRow
              label="Overall score"
              value={fmt(scorecard.overall_score)}
            />
            <NocRow
              label="Release confidence"
              value={fmt(release.confidence)}
            />
            <NocRow
              label="Recommendations"
              value={fmt(asList(learning.recommendations).length, "0")}
            />
          </NocPanel>
        </div>
      ) : null}

      {section === "validation" ? (
        <DeskTable
          columns={["Component", "Status", "OK", "Detail"]}
          rows={Object.entries(components).map(([name, row]) => {
            const r = asRecord(row);
            return [name, str(r.status, "—"), fmt(r.ok), str(r.detail, "—")];
          })}
        />
      ) : null}

      {section === "trading" ? (
        <NocPanel id="ci-eff" title="Trading Effectiveness (real evidence)">
          <NocRow
            label="Signals generated"
            value={fmt(trading.signals_generated)}
          />
          <NocRow
            label="Signals rejected"
            value={fmt(trading.signals_rejected)}
          />
          <NocRow
            label="Signals approved"
            value={fmt(trading.signals_approved)}
          />
          <NocRow label="Trades opened" value={fmt(trading.trades_opened)} />
          <NocRow label="Trades closed" value={fmt(trading.trades_closed)} />
          <NocRow label="Win rate" value={fmt(trading.win_rate)} />
          <NocRow label="Loss rate" value={fmt(trading.loss_rate)} />
          <NocRow label="Average RR" value={fmt(trading.average_rr)} />
          <NocRow label="Profit factor" value={fmt(trading.profit_factor)} />
          <NocRow label="Expectancy" value={fmt(trading.expectancy)} />
          <NocRow
            label="Note"
            value={str(trading.note, "Never fabricated")}
          />
        </NocPanel>
      ) : null}

      {section === "learning" ? (
        <div className="space-y-3">
          <NocPanel id="ci-learn" title="Learning Review">
            <NocRow
              label="Success patterns"
              value={fmt(asList(learning.top_success_patterns).length, "0")}
            />
            <NocRow
              label="Failure patterns"
              value={fmt(asList(learning.top_failure_patterns).length, "0")}
            />
            <NocRow
              label="Blocking gates"
              value={fmt(
                asList(learning.most_common_blocking_gates).length,
                "0",
              )}
            />
            <NocRow label="Auto-applies" value="false" tone="ok" />
          </NocPanel>
          {asList(learning.most_common_blocking_gates).length === 0 ? (
            <DeskEmpty
              icon={Activity}
              title="No blocking gates sampled"
              description="Gates appear when strategy diagnostics history is available."
            />
          ) : (
            <DeskTable
              columns={["Gate", "Count"]}
              rows={asList(learning.most_common_blocking_gates).map((row) => {
                const r = asRecord(row);
                return [str(r.gate), fmt(r.count)];
              })}
            />
          )}
          {asList(learning.recommendations).length > 0 ? (
            <DeskTable
              columns={["Summary", "Priority", "Review only"]}
              rows={asList(learning.recommendations)
                .slice(0, 15)
                .map((row) => {
                  const r = asRecord(row);
                  return [
                    str(r.summary, "—"),
                    fmt(r.priority),
                    fmt(r.operator_review_only, "yes"),
                  ];
                })}
            />
          ) : null}
        </div>
      ) : null}

      {section === "release" ? (
        <NocPanel id="ci-rel" title="Release Confidence">
          <NocRow label="Confidence" value={fmt(release.confidence)} />
          <NocRow
            label="Deployments recorded"
            value={fmt(release.deployment_count, "0")}
          />
          <NocRow
            label="Rollbacks recorded"
            value={fmt(release.rollback_count, "0")}
          />
          <NocRow
            label="Open incidents"
            value={fmt(
              asRecord(release.production_incidents).open,
              "0",
            )}
          />
          <NocRow
            label="Recovery time (s avg)"
            value={fmt(release.recovery_time_seconds_avg)}
          />
        </NocPanel>
      ) : null}

      {section === "scorecard" ? (
        <DeskTable
          columns={["Category", "Score", "Status"]}
          rows={Object.entries(categories).map(([name, row]) => {
            const r = asRecord(row);
            return [name, fmt(r.score), str(r.status, "—")];
          })}
        />
      ) : null}

      {section === "trends" ? (
        <DeskTable
          columns={["Window", "Samples", "Avg OK %"]}
          rows={["24h", "7d", "30d", "90d", "1y"].map((w) => {
            const r = asRecord(valTrends[w]);
            return [w, fmt(r.sample_count, "0"), fmt(r.avg_ok_ratio_percent)];
          })}
        />
      ) : null}

      {section === "reports" ? (
        <div className="grid gap-3 md:grid-cols-2">
          {(
            [
              ["daily_production_summary", "Daily Production"],
              ["weekly_executive_summary", "Weekly Executive"],
              ["monthly_platform_review", "Monthly Platform"],
              ["quarterly_operational_review", "Quarterly Operational"],
            ] as const
          ).map(([key, label]) => {
            const r = asRecord(reports[key]);
            return (
              <NocPanel key={key} id={`ci-rpt-${key}`} title={label}>
                <NocRow label="As of" value={fmt(r.as_of)} />
                <NocRow
                  label="Validation"
                  value={fmt(r.validation_overall)}
                />
                <NocRow
                  label="Scorecard"
                  value={fmt(r.scorecard_overall)}
                />
                <NocRow
                  label="Win rate"
                  value={fmt(asRecord(r.trading).win_rate)}
                />
                <NocRow
                  label="Release confidence"
                  value={fmt(r.release_confidence)}
                />
              </NocPanel>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
