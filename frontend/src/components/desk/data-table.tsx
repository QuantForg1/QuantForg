"use client";

import { memo, useMemo, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export type DeskColumn<T> = {
  id: string;
  header: string;
  sortable?: boolean;
  className?: string;
  accessor?: (row: T) => string | number | null | undefined;
  cell: (row: T) => ReactNode;
};

type SortDir = "asc" | "desc";

export const DeskDataTable = memo(function DeskDataTable<T>({
  columns,
  rows,
  rowKey,
  searchPlaceholder = "Filter rows…",
  searchKeys,
  pageSize = 10,
  empty,
  className,
  "aria-label": ariaLabel = "Data table",
}: {
  columns: DeskColumn<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  searchPlaceholder?: string;
  searchKeys?: (row: T) => string;
  pageSize?: number;
  empty?: ReactNode;
  className?: string;
  "aria-label"?: string;
}) {
  const [query, setQuery] = useState("");
  const [sortId, setSortId] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    let next = rows;
    if (q && searchKeys) {
      next = rows.filter((row) => searchKeys(row).toLowerCase().includes(q));
    }
    if (sortId) {
      const col = columns.find((c) => c.id === sortId);
      if (col?.accessor) {
        next = [...next].sort((a, b) => {
          const av = col.accessor!(a);
          const bv = col.accessor!(b);
          const an = typeof av === "number" ? av : String(av ?? "").toLowerCase();
          const bn = typeof bv === "number" ? bv : String(bv ?? "").toLowerCase();
          if (an < bn) return sortDir === "asc" ? -1 : 1;
          if (an > bn) return sortDir === "asc" ? 1 : -1;
          return 0;
        });
      }
    }
    return next;
  }, [rows, query, searchKeys, sortId, sortDir, columns]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(safePage * pageSize, safePage * pageSize + pageSize);

  const toggleSort = (id: string) => {
    if (sortId === id) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortId(id);
      setSortDir("asc");
    }
    setPage(0);
  };

  if (rows.length === 0 && empty) return <>{empty}</>;

  return (
    <div className={cn("space-y-3", className)}>
      {searchKeys ? (
        <div className="relative max-w-sm">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]"
            aria-hidden
          />
          <Input
            className="pl-9"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(0);
            }}
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
          />
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="w-full min-w-[640px] text-left text-sm" aria-label={ariaLabel}>
          <thead className="sticky top-0 z-10 bg-[var(--surface-2)]/95 backdrop-blur">
            <tr className="border-b border-[var(--border)] text-[var(--fg-subtle)]">
              {columns.map((col) => {
                const active = sortId === col.id;
                return (
                  <th
                    key={col.id}
                    scope="col"
                    className={cn(
                      "px-3 py-2.5 text-xs font-medium uppercase tracking-wide",
                      col.className,
                    )}
                  >
                    {col.sortable ? (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 transition hover:text-[var(--fg)]"
                        onClick={() => toggleSort(col.id)}
                        aria-label={`Sort by ${col.header}`}
                      >
                        {col.header}
                        {active ? (
                          sortDir === "asc" ? (
                            <ArrowUp className="h-3 w-3" aria-hidden />
                          ) : (
                            <ArrowDown className="h-3 w-3" aria-hidden />
                          )
                        ) : (
                          <ArrowUpDown className="h-3 w-3 opacity-40" aria-hidden />
                        )}
                      </button>
                    ) : (
                      col.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-3 py-10 text-center text-sm text-[var(--fg-muted)]"
                >
                  No rows match this filter.
                </td>
              </tr>
            ) : (
              pageRows.map((row, i) => (
                <tr
                  key={rowKey(row, safePage * pageSize + i)}
                  className="border-t border-[var(--border)] transition-colors hover:bg-[var(--surface-2)]/70"
                >
                  {columns.map((col) => (
                    <td
                      key={col.id}
                      className={cn("px-3 py-2.5 align-middle", col.className)}
                    >
                      {col.cell(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--fg-subtle)]">
        <span>
          {filtered.length} row{filtered.length === 1 ? "" : "s"}
          {query ? " filtered" : ""}
        </span>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            disabled={safePage <= 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            aria-label="Previous page"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </Button>
          <span className="tabular">
            {safePage + 1} / {pageCount}
          </span>
          <Button
            size="sm"
            variant="ghost"
            disabled={safePage >= pageCount - 1}
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            aria-label="Next page"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}) as <T>(props: {
  columns: DeskColumn<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  searchPlaceholder?: string;
  searchKeys?: (row: T) => string;
  pageSize?: number;
  empty?: ReactNode;
  className?: string;
  "aria-label"?: string;
}) => React.ReactElement;
