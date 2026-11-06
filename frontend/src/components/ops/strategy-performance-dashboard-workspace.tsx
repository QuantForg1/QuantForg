"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { LineChart } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskBarChart } from "@/components/charts/bar-chart";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel, StatusPill } from "@/components/ops/auto-trading-ops-ui";
import { iteOpsApi } from "@/lib/api/endpoints";
import {
  buildStrategyPerformanceDashboardModel,
  classificationTone,
  formatExpectancy,
  formatMoney,
  formatPct,
  formatPf,
  pnlTone,
  scorecardChartRows,
  type PeriodBucketView,
  type StrategyCardView,
  type StrategyPerformanceDashboardModel,
} from "@/lib/strategy-attribution-performance";
import { cn } from "@/lib/utils";

type PeriodKey = "post_pr182" | "post_pr180_pre_pr182" | "pre_pr180" | "all_recorded";

function periodFromModel(
  model: StrategyPerformanceDashboardModel,
  key: PeriodKey,
): PeriodBucketView {
  if (key === "post_pr182") return model.overview;
  const hit = model.periods.find((p) => p.label === key);
  return hit ?? model.overview;
}

function ClassificationBadge({ label }: { label: string }) {
  const tone = classificationTone(label);
  const badgeTone =
    tone === "ok"
      ? "success"
      : tone === "bad"
        ? "danger"
        : tone === "warn"
          ? "warning"
          : "neutral";
  return <Badge tone={badgeTone}>{label}</Badge>;
}

function OverviewGrid({ bucket }: { bucket: PeriodBucketView }) {
  const coverage =
    bucket.attributionCoveragePct == null
      ? "—"
      : `${bucket.attributionCoveragePct.toFixed(1)}%`;
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
      <MetricCard label="Closed trades" value={String(bucket.n)} large />
      <MetricCard
        label="Realized net P&L"
        value={formatMoney(bucket.realizedNetPnl)}
        tone={pnlTone(bucket.realizedNetPnl)}
        large
      />
      <MetricCard
        label="Unrealized P&L"
        value="Not included"
        tone="neutral"
      />
      <MetricCard
        label="Profit factor"
        value={formatPf(bucket.profitFactor)}
        tone={
          bucket.profitFactor == null
            ? "neutral"
            : bucket.profitFactor >= 1
              ? "ok"
              : "bad"
        }
      />
      <MetricCard label="Win rate" value={formatPct(bucket.winRate)} />
      <MetricCard label="Average win" value={formatMoney(bucket.avgWin)} tone="ok" />
      <MetricCard label="Average loss" value={formatMoney(bucket.avgLoss)} tone="bad" />
      <MetricCard
        label="Net expectancy"
        value={formatExpectancy(bucket.expectancy)}
        tone={pnlTone(bucket.expectancy)}
      />
      <MetricCard
        label="Max drawdown"
        value={formatMoney(bucket.maxDrawdown)}
        tone="warn"
      />
      <MetricCard
        label="Consecutive losses"
        value={
          bucket.maxConsecutiveLosses == null
            ? "—"
            : String(bucket.maxConsecutiveLosses)
        }
      />
      <MetricCard label="Attribution coverage" value={coverage} tone="accent" />
      <MetricCard
        label="Incomplete costs"
        value={String(bucket.incompleteCostRecords)}
        tone={bucket.incompleteCostRecords > 0 ? "warn" : "ok"}
      />
    </div>
  );
}

function SideCompare({ bucket }: { bucket: PeriodBucketView }) {
  const sides = [
    { key: "BUY", side: bucket.buy, tone: "buy" as const },
    { key: "SELL", side: bucket.sell, tone: "sell" as const },
  ];
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {sides.map(({ key, side, tone }) => (
        <div
          key={key}
          className="rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-2)] p-3"
        >
          <div className="mb-3 flex items-center justify-between gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              {key}
            </p>
            <ClassificationBadge label={side.classification} />
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <MetricCard label="Trades" value={String(side.n)} tone={tone} />
            <MetricCard
              label="Net P&L"
              value={formatMoney(side.net)}
              tone={pnlTone(side.net)}
            />
            <MetricCard label="Win rate" value={formatPct(side.winRate)} />
            <MetricCard label="Profit factor" value={formatPf(side.profitFactor)} />
            <MetricCard label="Expectancy" value={formatExpectancy(side.expectancy)} />
            <MetricCard label="Avg win" value={formatMoney(side.avgWin)} />
            <MetricCard label="Avg loss" value={formatMoney(side.avgLoss)} />
            <MetricCard label="Max DD" value={formatMoney(side.maxDrawdown)} />
          </div>
        </div>
      ))}
    </div>
  );
}

function StrategyCard({ card }: { card: StrategyCardView }) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-2)] p-3",
        card.isInsufficientData && "opacity-80",
        card.isUnattributed && "border-[var(--warning)]/40",
      )}
    >
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-mono text-[13px] text-[var(--fg)]">
            {card.strategyId ?? "unattributed"}
          </p>
          <p className="text-[11px] text-[var(--fg-muted)]">{card.strategyName}</p>
        </div>
        <ClassificationBadge label={card.classification} />
      </div>
      {card.isInsufficientData ? (
        <p className="mb-3 text-[12px] text-[var(--fg-subtle)]">
          Insufficient data — sample size {card.sampleSize}. Not zero performance.
        </p>
      ) : null}
      <div className="grid gap-2 sm:grid-cols-2">
        <MetricCard label="Closed" value={String(card.closedTrades)} />
        <MetricCard
          label="Net P&L"
          value={card.isInsufficientData ? "n/a" : formatMoney(card.netPnl)}
          tone={card.isInsufficientData ? "neutral" : pnlTone(card.netPnl)}
        />
        <MetricCard
          label="Win rate"
          value={card.isInsufficientData ? "n/a" : formatPct(card.winRate)}
        />
        <MetricCard
          label="Profit factor"
          value={card.isInsufficientData ? "n/a" : formatPf(card.profitFactor)}
        />
        <MetricCard
          label="Expectancy"
          value={card.isInsufficientData ? "n/a" : formatExpectancy(card.expectancy)}
        />
        <MetricCard label="Sample" value={String(card.sampleSize)} />
        <MetricCard label="Avg win" value={formatMoney(card.avgWin)} />
        <MetricCard label="Avg loss" value={formatMoney(card.avgLoss)} />
        <MetricCard label="Max DD" value={formatMoney(card.maxDrawdown)} />
        <MetricCard
          label="Attribution"
          value={card.attributionConfidence}
          tone={card.isUnattributed ? "warn" : "accent"}
        />
        <MetricCard label="BUY n / net" value={`${card.buyN} / ${formatMoney(card.buyNet)}`} />
        <MetricCard
          label="SELL n / net"
          value={`${card.sellN} / ${formatMoney(card.sellNet)}`}
        />
      </div>
    </div>
  );
}

export function StrategyPerformanceDashboardWorkspace() {
  const [periodKey, setPeriodKey] = useState<PeriodKey>("post_pr182");
  const query = useQuery({
    queryKey: ["ite-ops-strategy-attribution-performance"],
    queryFn: () => iteOpsApi.strategyAttributionPerformance(),
    refetchInterval: 30_000,
    staleTime: 10_000,
  });

  const model = useMemo(() => {
    if (!query.data) return null;
    return buildStrategyPerformanceDashboardModel(query.data);
  }, [query.data]);

  if (query.isLoading) {
    return <DeskSkeleton rows={8} />;
  }
  if (query.isError) {
    return (
      <DeskError
        message="Strategy performance unavailable — authenticated attribution API did not respond. No mock metrics are shown."
        onRetry={() => void query.refetch()}
      />
    );
  }
  if (!model) {
    return (
      <DeskEmpty
        icon={LineChart}
        title="No performance payload"
        description="Waiting for broker-confirmed durable outcomes."
      />
    );
  }

  const bucket = periodFromModel(model, periodKey);
  const chartCards =
    periodKey === "all_recorded"
      ? model.scorecards
      : model.scorecards;
  const chartData = scorecardChartRows(chartCards);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">ADVISORY ONLY</Badge>
        <Badge tone="warning">NO ENGINE MUTATION</Badge>
        <StatusPill label="Attribution API" ok={!query.isError} />
        <StatusPill
          label={`M1 LIVE submit ${model.m1.liveSubmitLabel}`}
          ok={!model.m1.liveSubmit}
          warn={Boolean(model.m1.liveSubmit)}
        />
        <span className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Account {model.brokerLogin ?? "unknown"} · {model.instrument} ·{" "}
          {model.reportingPeriod}
          {model.asOf ? ` · as of ${model.asOf}` : ""}
        </span>
      </div>

      <OpsPanel
        title="Reporting period"
        action={
          <div className="flex flex-wrap gap-1">
            {(
              [
                ["post_pr182", "Post #182"],
                ["post_pr180_pre_pr182", "Post #180 / pre #182"],
                ["pre_pr180", "Pre #180"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setPeriodKey(key)}
                className={cn(
                  "rounded-[var(--radius-sm)] border px-2 py-1 text-[10px] uppercase tracking-[0.08em]",
                  periodKey === key
                    ? "border-[var(--accent)]/50 bg-[var(--accent-soft)] text-[var(--accent)]"
                    : "border-[var(--border)] text-[var(--fg-muted)]",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        }
      >
        <p className="mb-3 text-[12px] text-[var(--fg-muted)]">
          Broker account isolation preserved. {model.accountNote}
        </p>
        <OverviewGrid bucket={bucket} />
        <p className="mt-3 text-[11px] text-[var(--fg-subtle)]">
          Classification: {bucket.classification}. Realized P&L only — unrealized open
          exposure is excluded. {bucket.dataQualityNote}
        </p>
      </OpsPanel>

      <OpsPanel title="BUY / SELL comparison">
        <SideCompare bucket={bucket} />
      </OpsPanel>

      <OpsPanel title="Five-pack strategy scorecards · post-PR #182">
        {model.scorecards.every((c) => c.isInsufficientData) ? (
          <p className="mb-3 text-[12px] text-[var(--fg-subtle)]">
            No attributed post-#182 sample yet. Empty is not zero performance.
          </p>
        ) : null}
        <div className="mb-4">
          <DeskBarChart data={chartData} />
        </div>
        <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
          {model.scorecards.map((card) => (
            <StrategyCard key={card.strategyId ?? "x"} card={card} />
          ))}
        </div>
      </OpsPanel>

      {model.unattributed ? (
        <OpsPanel title="Unattributed trades">
          <p className="mb-3 text-[12px] text-[var(--fg-muted)]">
            Never assigned to a guessed strategy. Unknown remains unknown.
          </p>
          <StrategyCard card={model.unattributed} />
        </OpsPanel>
      ) : null}

      <OpsPanel title="Capital protection">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Active BUY anchors"
            value={
              model.capitalProtection.buyActiveAnchors == null
                ? "—"
                : String(model.capitalProtection.buyActiveAnchors)
            }
          />
          <MetricCard
            label="Active SELL anchors"
            value={
              model.capitalProtection.sellActiveAnchors == null
                ? "—"
                : String(model.capitalProtection.sellActiveAnchors)
            }
          />
          <MetricCard
            label="BUY store trusted"
            value={
              model.capitalProtection.buyTrusted == null
                ? "—"
                : model.capitalProtection.buyTrusted
                  ? "YES"
                  : "NO"
            }
            tone={
              model.capitalProtection.buyTrusted == null
                ? "neutral"
                : model.capitalProtection.buyTrusted
                  ? "ok"
                  : "bad"
            }
          />
          <MetricCard
            label="SELL store trusted"
            value={
              model.capitalProtection.sellTrusted == null
                ? "—"
                : model.capitalProtection.sellTrusted
                  ? "YES"
                  : "NO"
            }
            tone={
              model.capitalProtection.sellTrusted == null
                ? "neutral"
                : model.capitalProtection.sellTrusted
                  ? "ok"
                  : "bad"
            }
          />
          <MetricCard
            label="Reversal-like closes"
            value={
              model.capitalProtection.reversalCloses == null
                ? "—"
                : String(model.capitalProtection.reversalCloses)
            }
          />
          <MetricCard
            label="Historical cascade blocks"
            value="Unavailable"
            tone="warn"
          />
        </div>
        <p className="mt-3 text-[11px] text-[var(--fg-subtle)]">
          Blocked entries are not completed trades. No $ saved claim without
          counterfactual price analysis. {model.capitalProtection.buyNote}{" "}
          {model.capitalProtection.sellNote}
        </p>
      </OpsPanel>

      <OpsPanel title="M1 evaluation (separate from five-pack fills)">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="M1 micro enabled"
            value={
              model.m1.microEnabled == null
                ? "—"
                : model.m1.microEnabled
                  ? "ON"
                  : "OFF"
            }
          />
          <MetricCard
            label="M1 LIVE OMS submit"
            value={model.m1.liveSubmitLabel}
            tone={model.m1.liveSubmit ? "bad" : "ok"}
          />
          <MetricCard label="M1 status" value={model.m1.status} />
          <MetricCard label="Broker-confirmed M1 fills" value="Not claimed" tone="warn" />
        </div>
        <p className="mt-3 text-[12px] text-[var(--fg-muted)]">{model.m1.displayRule}</p>
        <p className="mt-1 text-[11px] text-[var(--fg-subtle)]">{model.m1.recommendation}</p>
      </OpsPanel>
    </div>
  );
}
