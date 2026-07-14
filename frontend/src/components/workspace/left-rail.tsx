"use client";

import { memo, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Bookmark, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { mt5Api } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { classifySymbol } from "@/lib/dashboard/derive";
import { formatNumber } from "@/lib/utils";
import {
  loadWatchlists,
  saveWatchlists,
  type NamedWatchlist,
  type WorkspacePresetId,
  WORKSPACE_FAV_KEY,
} from "@/components/workspace/layout-store";
import { Cable } from "lucide-react";

const CATS = [
  "all",
  "favorites",
  "forex",
  "indices",
  "crypto",
  "gold",
  "silver",
  "oil",
  "stocks",
  "commodities",
] as const;

function matchesCategory(code: string, cat: (typeof CATS)[number]): boolean {
  const u = code.toUpperCase();
  if (cat === "all" || cat === "favorites") return true;
  if (cat === "gold") return u.includes("XAU") || u.includes("GOLD");
  if (cat === "silver") return u.includes("XAG") || u.includes("SILVER");
  if (cat === "oil") return /XTI|XBR|OIL|BRENT|WTI|NATGAS/.test(u);
  return classifySymbol(code) === cat;
}

function loadFavorites(): string[] {
  try {
    const raw = localStorage.getItem(WORKSPACE_FAV_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

export const WorkspaceLeftRail = memo(function WorkspaceLeftRail({
  connected,
  selected,
  onSelect,
  preset,
  onPresetChange,
  latencyMs,
}: {
  connected: boolean;
  selected: string;
  onSelect: (symbol: string) => void;
  preset: WorkspacePresetId;
  onPresetChange: (p: WorkspacePresetId) => void;
  latencyMs?: string;
}) {
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [cat, setCat] = useState<(typeof CATS)[number]>("all");
  const [favorites, setFavorites] = useState<string[]>(() =>
    typeof window === "undefined" ? [] : loadFavorites(),
  );
  const [watchlists, setWatchlists] = useState<NamedWatchlist[]>(() =>
    typeof window === "undefined" ? [] : loadWatchlists(),
  );
  const [activeListId, setActiveListId] = useState("default");
  const [showFavOnly, setShowFavOnly] = useState(false);

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedQ(q.trim()), 250);
    return () => window.clearTimeout(t);
  }, [q]);

  const symbolsQ = useInfiniteQuery({
    queryKey: ["mt5-symbols", debouncedQ],
    queryFn: ({ pageParam }) =>
      mt5Api.symbols({
        q: debouncedQ,
        offset: pageParam,
        limit: 100,
        include_quotes: false,
      }),
    initialPageParam: 0,
    getNextPageParam: (last) => (last.has_more ? last.offset + last.limit : undefined),
    retry: false,
    enabled: connected,
    staleTime: 45_000,
  });
  const tickQ = useQuery({
    queryKey: ["mt5-tick", selected],
    queryFn: () => mt5Api.tick(selected),
    retry: false,
    enabled: connected && Boolean(selected),
  });

  const symbols = useMemo(
    () =>
      (symbolsQ.data?.pages ?? []).flatMap((page) => asList(page.items).map(asRecord)),
    [symbolsQ.data],
  );
  const activeList = watchlists.find((w) => w.id === activeListId) ?? watchlists[0];
  const tick = asRecord(tickQ.data);

  const filtered = useMemo(() => {
    const favMode = cat === "favorites" || showFavOnly;
    return symbols.filter((s) => {
      const code = str(s.code);
      if (favMode && !favorites.includes(code)) return false;
      if (
        !favMode &&
        activeList &&
        activeList.symbols.length > 0 &&
        !activeList.symbols.includes(code)
      ) {
        return false;
      }
      if (!matchesCategory(code, cat)) return false;
      return true;
    });
  }, [symbols, cat, favorites, showFavOnly, activeList]);

  const ordered = useMemo(() => {
    const favs = filtered.filter((s) => favorites.includes(str(s.code)));
    const rest = filtered.filter((s) => !favorites.includes(str(s.code)));
    return [...favs, ...rest].slice(0, 250);
  }, [filtered, favorites]);

  const toggleFav = (code: string) => {
    const next = favorites.includes(code)
      ? favorites.filter((f) => f !== code)
      : [...favorites, code];
    setFavorites(next);
    localStorage.setItem(WORKSPACE_FAV_KEY, JSON.stringify(next));
  };

  const addToWatchlist = (code: string) => {
    const next = watchlists.map((w) => {
      if (w.id !== (activeList?.id ?? "default")) return w;
      if (w.symbols.includes(code)) return w;
      return { ...w, symbols: [...w.symbols, code] };
    });
    setWatchlists(next);
    saveWatchlists(next);
  };

  const brokerName = "MT5";

  return (
    <aside className="flex h-full min-h-0 flex-col border-r border-[var(--border)] bg-[var(--bg-elevated)]/60" aria-label="Market watch">
      <div className="space-y-2 border-b border-[var(--border)] p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Market Watch
          </p>
          <div className="flex items-center gap-1.5">
            {latencyMs && latencyMs !== "—" ? (
              <span className="text-[10px] tabular text-[var(--fg-subtle)]">{latencyMs} ms</span>
            ) : null}
            <Badge tone={connected ? "success" : "warning"} className="text-[10px]">
              {connected ? "Live" : "Offline"}
            </Badge>
          </div>
        </div>
        <label className="block space-y-1">
          <span className="text-[11px] text-[var(--fg-subtle)]">Layout preset</span>
          <select
            className="flex h-8 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-xs"
            value={preset}
            onChange={(e) => onPresetChange(e.target.value as WorkspacePresetId)}
            aria-label="Workspace selector"
          >
            <option value="default">Default</option>
            <option value="chart-focus">Chart focus</option>
            <option value="tape-focus">Tape focus</option>
          </select>
        </label>
        <div className="flex items-center justify-between gap-2 text-[11px] text-[var(--fg-muted)]">
          <span>{brokerName} · live session</span>
          <Button size="sm" variant="secondary" className="h-7 px-2" asChild>
            <Link href="/broker" aria-label="Manage broker connection">
              <Cable className="h-3.5 w-3.5" />
            </Link>
          </Button>
        </div>
        {connected && selected ? (
          <div className="grid grid-cols-3 gap-1 rounded-md border border-[var(--border)] bg-[var(--surface)]/80 px-2 py-1.5 text-[10px]">
            <div>
              <p className="text-[var(--fg-subtle)]">Bid</p>
              <p className="tabular text-[var(--danger)]">
                {Number.isFinite(num(tick.bid)) ? formatNumber(num(tick.bid), 5) : "—"}
              </p>
            </div>
            <div>
              <p className="text-[var(--fg-subtle)]">Ask</p>
              <p className="tabular text-[var(--success)]">
                {Number.isFinite(num(tick.ask)) ? formatNumber(num(tick.ask), 5) : "—"}
              </p>
            </div>
            <div>
              <p className="text-[var(--fg-subtle)]">Spread</p>
              <p className="tabular">
                {Number.isFinite(num(tick.bid)) && Number.isFinite(num(tick.ask))
                  ? formatNumber(num(tick.ask) - num(tick.bid), 5)
                  : "—"}
              </p>
            </div>
          </div>
        ) : null}
        <label className="block space-y-1">
          <span className="text-[11px] text-[var(--fg-subtle)]">Watchlist</span>
          <select
            className="flex h-8 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-xs"
            value={activeListId}
            onChange={(e) => setActiveListId(e.target.value)}
            aria-label="Watchlists"
          >
            {watchlists.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
                {w.symbols.length ? ` (${w.symbols.length})` : ""}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="space-y-2 border-b border-[var(--border)] p-3">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--fg-subtle)]"
            aria-hidden
          />
          <Input
            className="h-8 pl-8 text-xs"
            placeholder="Search markets…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search symbols"
            disabled={!connected}
          />
        </div>
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Market categories">
          {CATS.map((c) => (
            <Button
              key={c}
              size="sm"
              role="tab"
              aria-selected={cat === c}
              variant={cat === c ? "default" : "ghost"}
              className="h-6 capitalize px-2 text-[10px]"
              onClick={() => setCat(c)}
            >
              {c}
            </Button>
          ))}
        </div>
        <Button
          size="sm"
          variant={showFavOnly ? "default" : "ghost"}
          className="h-7 w-full justify-start gap-1.5 text-xs"
          onClick={() => setShowFavOnly((v) => !v)}
          aria-pressed={showFavOnly}
        >
          <Bookmark className="h-3.5 w-3.5" />
          Favorites {favorites.length ? `(${favorites.length})` : ""}
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {!connected ? (
          <div className="p-3">
            <DeskEmpty
              icon={Cable}
              title="No market feed"
              description="Connect MT5 to load the symbol universe."
              actionLabel="Connect"
              onAction={() => {
                window.location.href = "/broker";
              }}
            />
          </div>
        ) : symbolsQ.isLoading ? (
          <div className="p-3">
            <DeskSkeleton rows={10} />
          </div>
        ) : symbolsQ.isError ? (
          <div className="p-3">
            <DeskError message="Symbols unavailable." onRetry={() => symbolsQ.refetch()} />
          </div>
        ) : (
          <ul className="divide-y divide-[var(--border)]" aria-label="Watchlist symbols">
            {ordered.map((s) => {
              const code = str(s.code);
              const active = code === selected;
              const fav = favorites.includes(code);
              const bid = num(s.bid);
              const ask = num(s.ask);
              return (
                <li key={code}>
                  <div
                    className={`flex w-full items-stretch ${
                      active ? "bg-[var(--accent-soft)]" : "hover:bg-[var(--surface-2)]"
                    }`}
                  >
                    <button
                      type="button"
                      className="min-w-0 flex-1 px-3 py-2 text-left"
                      onClick={() => onSelect(code)}
                      aria-current={active ? "true" : undefined}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-xs font-semibold text-[var(--fg)]">
                          {code}
                        </span>
                        <span className="tabular text-[10px] text-[var(--fg-subtle)]">
                          {Number.isFinite(bid) ? formatNumber(bid, 5) : "—"}
                        </span>
                      </div>
                      <div className="mt-0.5 flex justify-between text-[10px] text-[var(--fg-subtle)]">
                        <span className="capitalize">{classifySymbol(code)}</span>
                        <span className="tabular text-[var(--success)]">
                          {Number.isFinite(ask) ? formatNumber(ask, 5) : "—"}
                        </span>
                      </div>
                    </button>
                    <div className="flex flex-col border-l border-[var(--border)]">
                      <button
                        type="button"
                        className="px-2 py-1 text-[var(--fg-subtle)] hover:text-[var(--accent)]"
                        aria-label={fav ? `Remove ${code} from favorites` : `Favorite ${code}`}
                        onClick={() => toggleFav(code)}
                      >
                        <Bookmark
                          className={`h-3.5 w-3.5 ${fav ? "fill-current text-[var(--accent)]" : ""}`}
                        />
                      </button>
                      <button
                        type="button"
                        className="px-2 py-1 text-[var(--fg-subtle)] hover:text-[var(--fg)]"
                        aria-label={`Add ${code} to watchlist`}
                        title="Add to watchlist"
                        onClick={() => addToWatchlist(code)}
                      >
                        <Plus className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        {connected && symbolsQ.hasNextPage ? (
          <div className="border-t border-[var(--border)] p-2">
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-full text-[11px]"
              disabled={symbolsQ.isFetchingNextPage}
              onClick={() => void symbolsQ.fetchNextPage()}
            >
              {symbolsQ.isFetchingNextPage ? "Loading…" : "Load more"}
            </Button>
          </div>
        ) : null}
      </div>
    </aside>
  );
});
