"use client";

import {
  memo,
  useMemo,
  useState,
  type KeyboardEvent,
  type ReactElement,
  type ReactNode,
} from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export type DeskColumn<T> = {
  id: string;
  header: string;
  sortable?: boolean;
  /** Pin first column optically for scan speed */
  sticky?: boolean;
  className?: string;
  accessor?: (row: T) => string | number | null | undefined;
  cell: (row: T) => ReactNode;
};

export type DeskTableDensity = "comfortable" | "compact";

type SortDir = "asc" | "desc";

export const DeskDataTable = memo(function DeskDataTable<T>({
  columns,
  rows,
  rowKey,
  searchPlaceholder = "Filter rows…",
  searchKeys,
  pageSize = 10,
  density = "compact",
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
  density?: DeskTableDensity;
  empty?: ReactNode;
  className?: string;
  "aria-label"?: string;
}) {
  const [query, setQuery] = useState("");
  const [sortId, setSortId] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(0);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

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
  const cellPad = density === "compact" ? "px-2.5 py-1.5" : "px-3 py-2";

  const toggleSort = (id: string) => {
    if (sortId === id) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortId(id);
      setSortDir("asc");
    }
    setPage(0);
  };

  const onRowKeyDown = (e: KeyboardEvent<HTMLTableRowElement>, key: string) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setSelectedKey(key);
    }
  };

  if (rows.length === 0 && empty) return <>{empty}</>;

  return (
    <div className={cn("space-y-[var(--space-2)]", className)}>
      {searchKeys ? (
        <div className="relative max-w-sm">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--fg-subtle)]"
            aria-hidden
          />
          <Input
            className="h-8 pl-8 text-[12px]"
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

      <div className="overflow-auto rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)]">
        <table
          className={cn(
            "w-full min-w-[640px] text-left",
            density === "compact" ? "text-[12px]" : "text-[13px]",
          )}
          aria-label={ariaLabel}
        >
          <thead className="sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--surface-2)]">
            <tr className="text-[var(--fg-subtle)]">
              {columns.map((col) => {
                const active = sortId === col.id;
                return (
                  <th
                    key={col.id}
                    scope="col"
                    className={cn(
                      cellPad,
                      "text-[10px] font-medium uppercase tracking-[0.08em]",
                      col.sticky &&
                        "sticky left-0 z-20 bg-[var(--surface-2)] shadow-[1px_0_0_0_var(--border)]",
                      col.className,
                    )}
                  >
                    {col.sortable ? (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 transition-colors duration-[var(--duration-fast)] ease-[var(--ease-os)] hover:text-[var(--fg)]"
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
                  className="px-3 py-8 text-center text-sm text-[var(--fg-muted)]"
                >
                  No rows match this filter.
                </td>
              </tr>
            ) : (
              pageRows.map((row, i) => {
                const key = rowKey(row, safePage * pageSize + i);
                const selected = selectedKey === key;
                return (
                  <tr
                    key={key}
                    tabIndex={0}
                    aria-selected={selected}
                    onClick={() => setSelectedKey(key)}
                    onKeyDown={(e) => onRowKeyDown(e, key)}
                    className={cn(
                      "border-t border-[var(--border)] transition-colors duration-[var(--duration-fast)] ease-[var(--ease-os)] hover:bg-[var(--surface-2)]/70 focus-visible:bg-[var(--accent-soft)] focus-visible:outline-none",
                      selected && "bg-[var(--accent-soft)]/50",
                    )}
                  >
                    {columns.map((col) => (
                      <td
                        key={col.id}
                        className={cn(
                          cellPad,
                          "align-middle",
                          col.sticky &&
                            "sticky left-0 z-[1] bg-[var(--surface)] shadow-[1px_0_0_0_var(--border)]",
                          selected && col.sticky && "bg-[color-mix(in_srgb,var(--accent-soft)_50%,var(--surface))]",
                          col.className,
                        )}
                      >
                        {col.cell(row)}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-[var(--fg-subtle)]">
        <span className="tabular">
          {filtered.length} row{filtered.length === 1 ? "" : "s"}
          {query ? " filtered" : ""}
          {selectedKey ? " · row selected" : ""}
        </span>
        <div className="flex items-center gap-1.5">
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 px-0"
            disabled={safePage <= 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            aria-label="Previous page"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </Button>
          <span className="min-w-[3.5rem] text-center tabular">
            {safePage + 1} / {pageCount}
          </span>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 px-0"
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
  density?: DeskTableDensity;
  empty?: ReactNode;
  className?: string;
  "aria-label"?: string;
}) => ReactElement;
