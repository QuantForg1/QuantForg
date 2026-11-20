"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Library } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { DeskQueryState } from "@/components/desk/query-state";
import { strategyApi } from "@/lib/api/endpoints";
import { filterMarketplace, marketplaceEntries } from "@/lib/marketplace/catalog";

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
    <div className="qf-desk min-w-0 space-y-5">
      <PageHeader
        eyebrow="Strategies"
        title="Strategy catalog"
        description="Names and descriptions from the strategy catalog. Performance is unavailable until verified evidence exists."
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
            className="rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          >
            <option value="">All categories</option>
            {categories.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
        <ul className="divide-y divide-[var(--border)]">
          {visible.map((entry) => (
            <li key={entry.key} className="space-y-1 py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-sm font-medium">{entry.name}</h2>
                <span className="text-xs text-[var(--text-secondary)]">{entry.category}</span>
              </div>
              <p className="text-sm text-[var(--text-secondary)]">{entry.description}</p>
              <p className="text-xs text-[var(--text-secondary)]">
                Performance unavailable. Sales and copy trading are off.
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
