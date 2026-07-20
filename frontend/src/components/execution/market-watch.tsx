"use client";

import { memo, useEffect, useMemo, useState } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Bookmark, Search } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { mt5Api } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { classifySymbol, symbolSpread } from "@/lib/dashboard/derive";
import { formatNumber } from "@/lib/utils";
import {
  TRADING_SYMBOL,
  MULTI_SYMBOL_ENABLED,
  filterTradingSymbolRecords,
  goldOnlySearchQuery,
  resolveTradingSymbol,
} from "@/lib/trading/gold-only";
import { Cable } from "lucide-react";

const ALL_CATS = [
  "all",
  "forex",
  "indices",
  "commodities",
  "crypto",
  "stocks",
  "etf",
  "futures",
] as const;

type MarketCategory = (typeof ALL_CATS)[number];

const GOLD_ONLY_CATS = ["all"] as const satisfies readonly MarketCategory[];

const VISIBLE_CATS = MULTI_SYMBOL_ENABLED ? ALL_CATS : GOLD_ONLY_CATS;
const FAV_KEY = "qf.execution.watch.favorites";
const PAGE_SIZE = 100;

export const MarketWatch = memo(function MarketWatch({
  connected,
  selected,
  onSelect,
  latencyMs,
}: {
  connected: boolean;
  selected: string;
  onSelect: (symbol: string) => void;
  latencyMs?: string;
}) {
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [cat, setCat] = useState<MarketCategory>("all");
  const [favorites, setFavorites] = useState<string[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(FAV_KEY);
      if (raw) setFavorites(JSON.parse(raw) as string[]);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQ(q.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [q]);

  const searchQ = goldOnlySearchQuery(debouncedQ);

  const symbolsQ = useInfiniteQuery({
    queryKey: ["mt5-symbols", searchQ],
    queryFn: ({ pageParam }) =>
      mt5Api.symbols({
        q: searchQ ?? TRADING_SYMBOL,
        offset: pageParam,
        limit: PAGE_SIZE,
        include_quotes: false,
      }),
    initialPageParam: 0,
    getNextPageParam: (last) =>
      last.has_more ? last.offset + last.limit : undefined,
    retry: false,
    enabled: connected && (MULTI_SYMBOL_ENABLED || searchQ !== null),
    staleTime: 45_000,
  });

  const tickQ = useQuery({
    queryKey: ["mt5-tick", selected],
    queryFn: () => mt5Api.tick(selected),
    retry: false,
    enabled: connected && Boolean(selected),
    refetchInterval: connected && selected ? 3_000 : false,
  });

  const symbols = useMemo(
    () =>
      filterTradingSymbolRecords(
        (symbolsQ.data?.pages ?? []).flatMap((page) =>
          asList(page.items).map(asRecord),
        ),
      ),
    [symbolsQ.data],
  );
  const tick = asRecord(tickQ.data);
  const total = symbolsQ.data?.pages?.[0]?.total ?? symbols.length;

  const filtered = useMemo(() => {
    return symbols.filter((s) => {
      const code = str(s.code);
      const cls = classifySymbol(code);
      if (cat !== "all" && cls !== cat) return false;
      return true;
    });
  }, [symbols, cat]);

  const ordered = useMemo(() => {
    const favs = filtered.filter((s) => favorites.includes(str(s.code)));
    const rest = filtered.filter((s) => !favorites.includes(str(s.code)));
    return [...favs, ...rest];
  }, [filtered, favorites]);

  const toggleFav = (code: string) => {
    const next = favorites.includes(code)
      ? favorites.filter((f) => f !== code)
      : [...favorites, code];
    setFavorites(next);
    localStorage.setItem(FAV_KEY, JSON.stringify(next));
  };

  const liveBid = num(tick.bid, num(symbols.find((s) => str(s.code) === selected)?.bid));
  const liveAsk = num(tick.ask, num(symbols.find((s) => str(s.code) === selected)?.ask));
  const liveSpread = Number.isFinite(liveBid) && Number.isFinite(liveAsk) ? liveAsk - liveBid : NaN;

  return (
    <Card className="flex h-full min-h-[28rem] flex-col">
      <CardHeader className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle>Market Watch</CardTitle>
          <div className="flex items-center gap-2">
            {latencyMs && latencyMs !== "—" ? (
              <span className="text-[10px] tabular text-[var(--fg-subtle)]">
                {latencyMs} ms
              </span>
            ) : null}
            <Badge tone={connected ? "success" : "warning"}>
              {connected ? "Live" : "Offline"}
            </Badge>
          </div>
        </div>
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--fg-subtle)]"
            aria-hidden
          />
          <Input
            className="h-9 pl-9"
            placeholder={MULTI_SYMBOL_ENABLED ? "Search symbols…" : "Search XAUUSD…"}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search market watch"
            disabled={!connected}
          />
        </div>
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Symbol categories">
          {VISIBLE_CATS.map((c) => (
            <Button
              key={c}
              size="sm"
              role="tab"
              aria-selected={cat === c}
              variant={cat === c ? "default" : "ghost"}
              className="h-7 capitalize"
              onClick={() => setCat(c)}
              disabled={!connected}
            >
              {c}
            </Button>
          ))}
        </div>
        {connected && selected ? (
          <div className="grid grid-cols-3 gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-xs">
            <div>
              <p className="text-[var(--fg-subtle)]">Bid</p>
              <p className="tabular text-sm font-semibold text-[var(--danger)]">
                {Number.isFinite(liveBid) ? formatNumber(liveBid, 5) : "—"}
              </p>
            </div>
            <div>
              <p className="text-[var(--fg-subtle)]">Ask</p>
              <p className="tabular text-sm font-semibold text-[var(--success)]">
                {Number.isFinite(liveAsk) ? formatNumber(liveAsk, 5) : "—"}
              </p>
            </div>
            <div>
              <p className="text-[var(--fg-subtle)]">Spread</p>
              <p className="tabular text-sm font-semibold">
                {Number.isFinite(liveSpread) ? formatNumber(liveSpread, 5) : "—"}
              </p>
            </div>
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-hidden">
        {!connected ? (
          <DeskEmpty
            icon={Cable}
            title="Broker disconnected"
            description="Connect MT5 to load the symbol universe and live quotes."
            actionLabel="Connect MT5"
            actionHref="/broker"
          />
        ) : symbolsQ.isLoading ? (
          <DeskSkeleton rows={8} />
        ) : symbolsQ.isError ? (
          <DeskError message="Unable to load symbols." onRetry={() => symbolsQ.refetch()} />
        ) : ordered.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--fg-muted)]">No symbols match.</p>
        ) : (
          <div className="flex max-h-[22rem] flex-col gap-2">
            <div className="overflow-y-auto rounded-lg border border-[var(--border)]">
              <table className="w-full text-left text-xs" aria-label="Market watch">
                <thead className="sticky top-0 z-10 bg-[var(--surface-2)]/95 backdrop-blur">
                  <tr className="text-[var(--fg-subtle)]">
                    <th className="px-2 py-2 font-medium">Symbol</th>
                    <th className="px-2 py-2 font-medium">Bid</th>
                    <th className="px-2 py-2 font-medium">Ask</th>
                    <th className="px-2 py-2 font-medium">Spread</th>
                    <th className="px-2 py-2 font-medium">Δ</th>
                    <th className="px-2 py-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {ordered.map((s) => {
                    const code = str(s.code);
                    const active = code === selected;
                    const bid = num(s.bid);
                    const ask = num(s.ask);
                    const spread = symbolSpread(s);
                    const fav = favorites.includes(code);
                    return (
                      <tr
                        key={code}
                        className={`cursor-pointer border-t border-[var(--border)] transition hover:bg-[var(--surface-2)]/80 ${
                          active ? "bg-[var(--accent-soft)]" : ""
                        }`}
                        onClick={() => onSelect(resolveTradingSymbol(code))}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onSelect(resolveTradingSymbol(code));
                          }
                        }}
                        tabIndex={0}
                        aria-selected={active}
                      >
                        <td className="px-2 py-1.5 font-medium">{code}</td>
                        <td className="tabular px-2 py-1.5 text-[var(--danger)]">
                          {Number.isFinite(bid) ? formatNumber(bid, 5) : "—"}
                        </td>
                        <td className="tabular px-2 py-1.5 text-[var(--success)]">
                          {Number.isFinite(ask) ? formatNumber(ask, 5) : "—"}
                        </td>
                        <td className="tabular px-2 py-1.5">
                          {Number.isFinite(spread) ? formatNumber(spread, 5) : "—"}
                        </td>
                        <td
                          className="px-2 py-1.5 text-[var(--fg-subtle)]"
                          title="Daily change not provided by symbol API"
                        >
                          —
                        </td>
                        <td className="px-1 py-1.5">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0"
                            aria-label={fav ? `Unfavorite ${code}` : `Favorite ${code}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleFav(code);
                            }}
                          >
                            <Bookmark
                              className={
                                fav
                                  ? "h-3.5 w-3.5 fill-[var(--accent)] text-[var(--accent)]"
                                  : "h-3.5 w-3.5"
                              }
                            />
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between gap-2 text-[11px] text-[var(--fg-subtle)]">
              <span>
                Showing {ordered.length}
                {total ? ` of ${total}` : ""} symbols
              </span>
              {symbolsQ.hasNextPage ? (
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7"
                  disabled={symbolsQ.isFetchingNextPage}
                  onClick={() => void symbolsQ.fetchNextPage()}
                >
                  {symbolsQ.isFetchingNextPage ? "Loading…" : "Load more"}
                </Button>
              ) : null}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
});
