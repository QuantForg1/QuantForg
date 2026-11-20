"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Library } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { DeskQueryState } from "@/components/desk/query-state";
import { strategyApi } from "@/lib/api/endpoints";
import {
  displayValue,
  filterMarketplace,
  marketplaceEntries,
} from "@/lib/marketplace/catalog";

export function StrategyMarketplace() {
  const query = useQuery({
    queryKey: ["strategy-catalog"],
    queryFn: () => strategyApi.catalog(),
    retry: false,
  });
  const [text, setText] = useState("");
  const [category, setCategory] = useState("");
  const entries = useMemo(() => marketplaceEntries(query.data), [query.data]);
  const categories = useMemo(
    () => [...new Set(entries.map((entry) => entry.category))].sort(),
    [entries],
  );
  const visible = filterMarketplace(entries, text, category);

  return (
    <div className="qf-desk min-w-0 space-y-5 overflow-x-hidden">
      <PageHeader
        eyebrow="Strategies"
        title="Strategy marketplace"
        description="Catalog names and descriptions only. Live, demo, backtest, simulated, and unverified results stay separate, and none is shown unless a verified record exists."
      />
      <DeskQueryState
        isLoading={query.isLoading}
        isError={query.isError}
        errorMessage="The strategy catalog could not be loaded."
        onRetry={() => void query.refetch()}
        isEmpty={!query.isLoading && !query.isError && entries.length === 0}
        empty={{
          icon: Library,
          title: "No strategies in the catalog",
          description: "The catalog returned no strategies.",
        }}
      >
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Search strategies"
            aria-label="Search strategies"
            className="min-w-0 flex-1 rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          />
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            aria-label="Strategy category"
            className="min-w-0 rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm sm:max-w-xs"
          >
            <option value="">All categories</option>
            {categories.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
        <ul className="grid gap-3 md:grid-cols-2">
          {visible.map((entry) => (
            <li key={entry.key} className="min-w-0 rounded-md border border-[var(--border)] p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-sm font-medium">
                  <Link className="underline-offset-2 hover:underline" href={`/marketplace/${encodeURIComponent(entry.key)}`}>
                    {entry.name}
                  </Link>
                </h2>
                <span className="text-xs text-[var(--text-secondary)]">{entry.category}</span>
              </div>
              <p className="mt-2 break-words text-sm text-[var(--text-secondary)]">{entry.description}</p>
              <dl className="mt-3 space-y-1 text-xs text-[var(--text-secondary)]">
                <div className="flex flex-wrap justify-between gap-2">
                  <dt>Instrument</dt>
                  <dd>{displayValue(entry.instrument)}</dd>
                </div>
                <div className="flex flex-wrap justify-between gap-2">
                  <dt>Timeframe</dt>
                  <dd>{displayValue(entry.timeframe)}</dd>
                </div>
                <div className="flex flex-wrap justify-between gap-2">
                  <dt>Version</dt>
                  <dd>{displayValue(entry.version)}</dd>
                </div>
              </dl>
              <p className="mt-3 text-xs text-[var(--text-secondary)]">
                Performance lanes stay separate. Sales and copy trading are off.
              </p>
            </li>
          ))}
        </ul>
        {entries.length > 0 && visible.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">No strategies match this search.</p>
        ) : null}
      </DeskQueryState>
    </div>
  );
}
