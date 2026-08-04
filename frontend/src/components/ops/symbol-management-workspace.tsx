"use client";

import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  Search,
  Star,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";
import { PageMotion } from "@/components/desk/motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { symbolManagementApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

type SymbolRow = {
  symbol: string;
  asset_class: string;
  enabled: boolean;
  favorite: boolean;
  tradable: boolean;
  trade_mode: string;
  spread: unknown;
  status: string;
  session: string;
  last_update: string;
  priority: number;
};

const FILTERS = [
  "all",
  "forex",
  "crypto",
  "metals",
  "indices",
  "energy",
  "favorites",
] as const;

function asRows(payload: Record<string, unknown> | undefined): SymbolRow[] {
  const items = payload?.items;
  if (!Array.isArray(items)) return [];
  return items
    .filter((x): x is Record<string, unknown> => !!x && typeof x === "object")
    .map((x) => ({
      symbol: String(x.symbol ?? ""),
      asset_class: String(x.asset_class ?? "other"),
      enabled: Boolean(x.enabled),
      favorite: Boolean(x.favorite),
      tradable: Boolean(x.tradable),
      trade_mode: String(x.trade_mode ?? "—"),
      spread: x.spread,
      status: String(x.status ?? "—"),
      session: String(x.session ?? "—"),
      last_update: String(x.last_update ?? "—"),
      priority: Number(x.priority ?? 1000),
    }))
    .filter((r) => r.symbol);
}

export function SymbolManagementWorkspace() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [dragSym, setDragSym] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["symbol-management", q, filter],
    queryFn: () =>
      symbolManagementApi.list({
        q: q || undefined,
        asset_class: filter === "all" ? undefined : filter,
        favorites: filter === "favorites",
      }),
    refetchInterval: 15_000,
  });

  const rows = useMemo(() => asRows(query.data), [query.data]);
  const enabledCount = Number(query.data?.enabled_count ?? 0);
  const total = Number(query.data?.total ?? rows.length);

  const invalidate = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ["symbol-management"] });
  }, [qc]);

  const updateMut = useMutation({
    mutationFn: (args: { symbol: string; body: Record<string, unknown> }) =>
      symbolManagementApi.update(args.symbol, args.body),
    onSuccess: () => {
      invalidate();
      toast.success("Symbol updated");
    },
    onError: (e: Error) => toast.error(e.message || "Update failed"),
  });

  const bulkMut = useMutation({
    mutationFn: (body: Record<string, unknown>) => symbolManagementApi.bulk(body),
    onSuccess: () => {
      invalidate();
      setSelected(new Set());
      toast.success("Bulk update applied");
    },
    onError: (e: Error) => toast.error(e.message || "Bulk update failed"),
  });

  const reorderMut = useMutation({
    mutationFn: (ordered: string[]) => symbolManagementApi.reorder(ordered),
    onSuccess: () => {
      invalidate();
      toast.success("Priority saved");
    },
    onError: (e: Error) => toast.error(e.message || "Reorder failed"),
  });

  const toggleSelect = (sym: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(sym)) next.delete(sym);
      else next.add(sym);
      return next;
    });
  };

  const movePriority = (sym: string, dir: -1 | 1) => {
    const ordered = rows.map((r) => r.symbol);
    const idx = ordered.indexOf(sym);
    const j = idx + dir;
    if (idx < 0 || j < 0 || j >= ordered.length) return;
    const next = [...ordered];
    const tmp = next[idx]!;
    next[idx] = next[j]!;
    next[j] = tmp;
    reorderMut.mutate(next);
  };

  const onDrop = (target: string) => {
    if (!dragSym || dragSym === target) {
      setDragSym(null);
      return;
    }
    const ordered = rows.map((r) => r.symbol);
    const from = ordered.indexOf(dragSym);
    const to = ordered.indexOf(target);
    if (from < 0 || to < 0) {
      setDragSym(null);
      return;
    }
    const next = [...ordered];
    next.splice(from, 1);
    next.splice(to, 0, dragSym);
    setDragSym(null);
    reorderMut.mutate(next);
  };

  return (
    <PageMotion>
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
            <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
              Total symbols
            </p>
            <p className="mt-1 font-mono text-2xl text-[var(--fg)]">{total}</p>
          </div>
          <div className="border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
            <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
              Enabled
            </p>
            <p className="mt-1 font-mono text-2xl text-[var(--accent)]">
              {enabledCount}
            </p>
          </div>
          <div className="border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
            <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
              Session
            </p>
            <p className="mt-1 font-mono text-lg text-[var(--fg)]">
              {String(query.data?.session ?? "—")}
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative max-w-md flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search symbols…"
              className="pl-9"
              aria-label="Search symbols"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((f) => (
              <Button
                key={f}
                size="sm"
                variant={filter === f ? "default" : "outline"}
                onClick={() => setFilter(f)}
              >
                {f}
              </Button>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={selected.size === 0 || bulkMut.isPending}
            onClick={() =>
              bulkMut.mutate({
                symbols: [...selected],
                enable: true,
                reason: "bulk_enable",
              })
            }
          >
            Bulk enable
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={selected.size === 0 || bulkMut.isPending}
            onClick={() =>
              bulkMut.mutate({
                symbols: [...selected],
                enable: false,
                reason: "bulk_disable",
              })
            }
          >
            Bulk disable
          </Button>
          <span className="self-center text-[11px] text-[var(--fg-subtle)]">
            Drag rows to set scan priority · Owner/Admin write
          </span>
        </div>

        <div className="overflow-x-auto border border-[var(--border)] bg-[var(--surface)]">
          <table className="w-full min-w-[960px] text-left text-sm">
            <thead className="border-b border-[var(--border)] bg-[var(--surface-2)] text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              <tr>
                <th className="px-3 py-2">Sel</th>
                <th className="px-3 py-2">Pri</th>
                <th className="px-3 py-2">Symbol</th>
                <th className="px-3 py-2">Class</th>
                <th className="px-3 py-2">Enabled</th>
                <th className="px-3 py-2">Tradable</th>
                <th className="px-3 py-2">Mode</th>
                <th className="px-3 py-2">Spread</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Session</th>
                <th className="px-3 py-2">Updated</th>
                <th className="px-3 py-2">Fav</th>
              </tr>
            </thead>
            <tbody>
              {query.isLoading ? (
                <tr>
                  <td colSpan={12} className="px-3 py-8 text-center text-[var(--fg-muted)]">
                    Loading broker symbols…
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={12} className="px-3 py-8 text-center text-[var(--fg-muted)]">
                    No symbols discovered yet. Wait for LIVE gateway catalogue.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr
                    key={row.symbol}
                    draggable
                    onDragStart={() => setDragSym(row.symbol)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={() => onDrop(row.symbol)}
                    className={cn(
                      "border-b border-[var(--border)]/70 transition-colors",
                      dragSym === row.symbol && "bg-[var(--accent-soft)]",
                      !row.enabled && "opacity-60",
                    )}
                  >
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selected.has(row.symbol)}
                        onChange={() => toggleSelect(row.symbol)}
                        aria-label={`Select ${row.symbol}`}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1 font-mono text-xs">
                        <span>{row.priority}</span>
                        <button
                          type="button"
                          className="text-[var(--fg-subtle)] hover:text-[var(--accent)]"
                          aria-label={`Raise ${row.symbol} priority`}
                          onClick={() => movePriority(row.symbol, -1)}
                        >
                          <ArrowUp className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          className="text-[var(--fg-subtle)] hover:text-[var(--accent)]"
                          aria-label={`Lower ${row.symbol} priority`}
                          onClick={() => movePriority(row.symbol, 1)}
                        >
                          <ArrowDown className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                    <td className="px-3 py-2 font-mono font-semibold text-[var(--fg)]">
                      {row.symbol}
                    </td>
                    <td className="px-3 py-2 capitalize text-[var(--fg-muted)]">
                      {row.asset_class}
                    </td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 text-[var(--accent)]"
                        onClick={() =>
                          updateMut.mutate({
                            symbol: row.symbol,
                            body: {
                              enabled: !row.enabled,
                              reason: row.enabled
                                ? "disable_symbol"
                                : "enable_symbol",
                            },
                          })
                        }
                        aria-label={
                          row.enabled
                            ? `Disable ${row.symbol}`
                            : `Enable ${row.symbol}`
                        }
                      >
                        {row.enabled ? (
                          <ToggleRight className="h-5 w-5" />
                        ) : (
                          <ToggleLeft className="h-5 w-5 text-[var(--fg-subtle)]" />
                        )}
                        <span className="text-xs">
                          {row.enabled ? "On" : "Off"}
                        </span>
                      </button>
                    </td>
                    <td className="px-3 py-2">
                      <Badge tone={row.tradable ? "success" : "neutral"}>
                        {row.tradable ? "Yes" : "No"}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{row.trade_mode}</td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {row.spread == null || row.spread === ""
                        ? "—"
                        : String(row.spread)}
                    </td>
                    <td className="px-3 py-2">
                      <Badge
                        tone={
                          row.status === "enabled"
                            ? "success"
                            : row.status === "disabled"
                              ? "neutral"
                              : "warning"
                        }
                      >
                        {row.status}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{row.session}</td>
                    <td
                      className="max-w-[140px] truncate px-3 py-2 font-mono text-[10px] text-[var(--fg-subtle)]"
                      title={row.last_update}
                    >
                      {row.last_update}
                    </td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        onClick={() =>
                          updateMut.mutate({
                            symbol: row.symbol,
                            body: {
                              favorite: !row.favorite,
                              reason: "toggle_favorite",
                            },
                          })
                        }
                        aria-label={`Favorite ${row.symbol}`}
                      >
                        <Star
                          className={cn(
                            "h-4 w-4",
                            row.favorite
                              ? "fill-[var(--accent)] text-[var(--accent)]"
                              : "text-[var(--fg-subtle)]",
                          )}
                        />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </PageMotion>
  );
}
