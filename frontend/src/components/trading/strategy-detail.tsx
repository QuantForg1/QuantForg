"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Library } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { DeskQueryState } from "@/components/desk/query-state";
import { strategyApi } from "@/lib/api/endpoints";
import {
  displayValue,
  findMarketplaceEntry,
  marketplaceEntries,
  PERFORMANCE_LANES,
} from "@/lib/marketplace/catalog";

const LANE_LABEL: Record<(typeof PERFORMANCE_LANES)[number], string> = {
  live: "Verified live",
  demo: "Verified demo",
  backtest: "Backtest",
  simulated: "Simulated",
  unverified: "Unverified",
};

export function StrategyDetail({ strategyKey }: { strategyKey: string }) {
  const query = useQuery({
    queryKey: ["strategy-catalog"],
    queryFn: () => strategyApi.catalog(),
    retry: false,
  });
  const entry = useMemo(
    () => findMarketplaceEntry(marketplaceEntries(query.data), strategyKey),
    [query.data, strategyKey],
  );

  return (
    <div className="qf-desk min-w-0 space-y-5 overflow-x-hidden">
      <PageHeader
        eyebrow="Strategies"
        title={entry?.name ?? "Strategy"}
        description="A catalog entry is not an order, a subscription, or permission to deploy the strategy."
        actions={
          <Link className="text-sm text-[var(--accent)] underline-offset-2 hover:underline" href="/marketplace">
            Back to marketplace
          </Link>
        }
      />
      <DeskQueryState
        isLoading={query.isLoading}
        isError={query.isError}
        errorMessage="The strategy catalog could not be loaded."
        onRetry={() => void query.refetch()}
        isEmpty={!query.isLoading && !query.isError && entry == null}
        empty={{
          icon: Library,
          title: "Strategy not in the catalog",
          description: "This key was not returned by the strategy catalog.",
        }}
      >
        {entry ? (
          <div className="space-y-4">
            <section className="rounded-md border border-[var(--border)] p-4">
              <h2 className="text-sm font-medium">Catalog record</h2>
              <p className="mt-2 break-words text-sm text-[var(--text-secondary)]">{entry.description}</p>
              <dl className="mt-3 space-y-2 text-sm">
                <Fact label="Category" value={entry.category} />
                <Fact label="Instrument" value={displayValue(entry.instrument)} />
                <Fact label="Timeframe" value={displayValue(entry.timeframe)} />
                <Fact label="Version" value={displayValue(entry.version)} />
                <Fact label="Status" value={displayValue(entry.status)} />
                <Fact label="Compatibility" value={displayValue(entry.compatibility)} />
                <Fact label="Risk" value={displayValue(entry.riskCharacteristics)} />
                <Fact label="Release notes" value={displayValue(entry.releaseNotes)} />
                <Fact label="Sales" value="Off" />
                <Fact label="Copy trading" value="Off" />
              </dl>
            </section>
            <section className="rounded-md border border-[var(--border)] p-4">
              <h2 className="text-sm font-medium">Version history</h2>
              {entry.versions.length === 0 ? (
                <p className="mt-2 text-sm text-[var(--text-secondary)]">Version history unavailable</p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {entry.versions.map((version) => (
                    <li key={`${version.version}-${version.releasedAt}`} className="text-sm">
                      <p className="font-medium">{version.version}</p>
                      <p className="text-[var(--text-secondary)]">{version.releasedAt}</p>
                      <p>{displayValue(version.releaseNotes)}</p>
                      <p className="text-[var(--text-secondary)]">
                        Compatibility: {displayValue(version.compatibility)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="rounded-md border border-[var(--border)] p-4" aria-labelledby="performance-lanes">
              <h2 id="performance-lanes" className="text-sm font-medium">Performance</h2>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                These records are not combined into one result.
              </p>
              <ul className="mt-3 space-y-2">
                {PERFORMANCE_LANES.map((lane) => (
                  <li key={lane} className="flex flex-wrap justify-between gap-2 text-sm">
                    <span>{LANE_LABEL[lane]}</span>
                    <span className="text-[var(--text-secondary)]">
                      {entry.performance[lane] === "unavailable"
                        ? "Performance unavailable"
                        : entry.performance[lane]}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
            <p className="text-sm text-[var(--text-secondary)]">
              Opening this page does not change a risk profile, connect a broker, or send an order.
            </p>
          </div>
        ) : null}
      </DeskQueryState>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[11rem_minmax(0,1fr)]">
      <dt className="text-[var(--text-secondary)]">{label}</dt>
      <dd className="min-w-0 break-words">{value}</dd>
    </div>
  );
}
