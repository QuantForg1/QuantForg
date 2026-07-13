"use client";

import { memo, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Bookmark, ChevronDown, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { brokersApi, mt5Api } from "@/lib/api/endpoints";
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

const CATS = ["all", "forex", "crypto", "indices", "commodities", "stocks"] as const;

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
}: {
  connected: boolean;
  selected: string;
  onSelect: (symbol: string) => void;
  preset: WorkspacePresetId;
  onPresetChange: (p: WorkspacePresetId) => void;
}) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<(typeof CATS)[number]>("all");
  const [favorites, setFavorites] = useState<string[]>(() =>
    typeof window === "undefined" ? [] : loadFavorites(),
  );
  const [watchlists, setWatchlists] = useState<NamedWatchlist[]>(() =>
    typeof window === "undefined" ? [] : loadWatchlists(),
  );
  const [activeListId, setActiveListId] = useState("default");
  const [showFavOnly, setShowFavOnly] = useState(false);

  const symbolsQ = useQuery({
    queryKey: ["mt5-symbols"],
    queryFn: mt5Api.symbols,
    retry: false,
    enabled: connected,
  });
  const brokersQ = useQuery({
    queryKey: ["brokers"],
    queryFn: brokersApi.list,
    retry: false,
  });
  const mt5Q = useQuery({
    queryKey: ["mt5-status"],
    queryFn: mt5Api.status,
    retry: false,
  });

  const symbols = useMemo(() => asList(symbolsQ.data).map(asRecord), [symbolsQ.data]);
  const activeList = watchlists.find((w) => w.id === activeListId) ?? watchlists[0];

  const filtered = useMemo(() => {
    return symbols.filter((s) => {
      const code = str(s.code);
      if (showFavOnly && !favorites.includes(code)) return false;
      if (
        !showFavOnly &&
        activeList &&
        activeList.symbols.length > 0 &&
        !activeList.symbols.includes(code)
      ) {
        return false;
      }
      const cls = classifySymbol(code);
      if (cat !== "all" && cls !== cat) return false;
      if (!q.trim()) return true;
      return `${code} ${str(s.description)}`.toLowerCase().includes(q.trim().toLowerCase());
    });
  }, [symbols, cat, q, favorites, showFavOnly, activeList]);

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

  const brokerName = (() => {
    const first = asList(brokersQ.data)[0];
    return str(asRecord(first).name, "MT5");
  })();

  return (
    <aside className="flex h-full min-h-0 flex-col border-r border-[var(--border)] bg-[var(--bg-elevated)]/60" aria-label="Market sidebar">
      <div className="space-y-2 border-b border-[var(--border)] p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Workspace
          </p>
          <Badge tone={connected ? "success" : "warning"} className="text-[10px]">
            {connected ? "Live" : "Offline"}
          </Badge>
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
        <label className="block space-y-1">
          <span className="text-[11px] text-[var(--fg-subtle)]">Broker</span>
          <div className="flex gap-1">
            <select
              className="flex h-8 min-w-0 flex-1 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-xs"
              aria-label="Broker selector"
              defaultValue="mt5"
            >
              <option value="mt5">
                MT5 {mt5Q.data?.connected ? "· connected" : "· offline"}
              </option>
              {asList(brokersQ.data).map((b) => {
                const row = asRecord(b);
                return (
                  <option key={str(row.id, str(row.slug))} value={str(row.id, str(row.slug))}>
                    {str(row.name, brokerName)}
                  </option>
                );
              })}
            </select>
            <Button size="sm" variant="secondary" className="h-8 px-2" asChild>
              <Link href="/mt5" aria-label="Manage MT5 connection">
                <Cable className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>
        </label>
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
                window.location.href = "/mt5";
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
                        <ChevronDown className="h-3.5 w-3.5 rotate-[-90deg]" />
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
});
