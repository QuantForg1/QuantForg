"use client";

import { memo, useEffect, useMemo, useState } from "react";
import { ChevronDown, Search, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { resolveTradingSymbol } from "@/lib/trading/gold-only";
import { WORKSPACE_FAV_KEY } from "@/components/workspace/layout-store";

const QUICK_SYMBOLS = [
  "EURUSD",
  "GBPUSD",
  "USDJPY",
  "XAUUSD",
  "BTCUSD",
  "ETHUSD",
  "AUDUSD",
  "USDCAD",
  "USDCHF",
  "NZDUSD",
] as const;

const RECENT_KEY = "qf.terminal.recent.symbols.v1";
const MAX_RECENT = 8;

function loadList(key: string): string[] {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function saveList(key: string, rows: string[]) {
  try {
    localStorage.setItem(key, JSON.stringify(rows));
  } catch {
    /* ignore */
  }
}

function pushRecent(code: string) {
  const next = [code, ...loadList(RECENT_KEY).filter((s) => s !== code)].slice(
    0,
    MAX_RECENT,
  );
  saveList(RECENT_KEY, next);
}

/**
 * Terminal symbol switcher — dropdown + quick chips.
 * Client-only; no page refresh; does not touch Trading Core.
 */
export const TerminalSymbolSwitcher = memo(function TerminalSymbolSwitcher({
  symbol,
  onSelect,
  className,
}: {
  symbol: string;
  onSelect: (code: string) => void;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [favorites, setFavorites] = useState<string[]>([]);
  const [recent, setRecent] = useState<string[]>([]);

  useEffect(() => {
    setFavorites(loadList(WORKSPACE_FAV_KEY));
    setRecent(loadList(RECENT_KEY));
  }, [symbol, open]);

  const pick = (raw: string) => {
    const code = resolveTradingSymbol(raw);
    pushRecent(code);
    setRecent(loadList(RECENT_KEY));
    onSelect(code);
    setOpen(false);
    setQ("");
  };

  const toggleFav = (code: string) => {
    const next = favorites.includes(code)
      ? favorites.filter((f) => f !== code)
      : [...favorites, code];
    setFavorites(next);
    saveList(WORKSPACE_FAV_KEY, next);
  };

  const pool = useMemo(() => {
    const set = new Set<string>([
      ...QUICK_SYMBOLS,
      ...favorites,
      ...recent,
      symbol,
    ]);
    return [...set];
  }, [favorites, recent, symbol]);

  const filtered = useMemo(() => {
    const needle = q.trim().toUpperCase();
    if (!needle) return pool;
    return pool.filter((s) => s.includes(needle));
  }, [pool, q]);

  return (
    <div className={cn("relative flex min-w-0 items-center gap-1", className)}>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="h-6 gap-1 px-2 font-mono text-[11px]"
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen((v) => !v)}
      >
        {symbol}
        <ChevronDown className="h-3 w-3 opacity-70" aria-hidden />
      </Button>

      <div className="hidden items-center gap-0.5 lg:flex">
        {QUICK_SYMBOLS.slice(0, 6).map((code) => (
          <button
            key={code}
            type="button"
            onClick={() => pick(code)}
            className={cn(
              "rounded px-1 py-0.5 font-mono text-[10px] transition-colors",
              code === symbol
                ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                : "text-[var(--fg-subtle)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]",
            )}
          >
            {code}
          </button>
        ))}
      </div>

      {open ? (
        <div
          className="absolute left-0 top-full z-40 mt-1 w-[min(22rem,calc(100vw-2rem))] border border-[var(--border)] bg-[var(--surface)] shadow-lg"
          role="listbox"
        >
          <div className="flex items-center gap-2 border-b border-[var(--border)] px-2 py-1.5">
            <Search className="h-3.5 w-3.5 text-[var(--fg-subtle)]" aria-hidden />
            <Input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && filtered[0]) pick(filtered[0]);
                if (e.key === "Escape") setOpen(false);
              }}
              placeholder="Search symbols"
              className="h-7 border-0 bg-transparent px-0 text-[12px] shadow-none focus-visible:ring-0"
            />
          </div>

          {recent.length ? (
            <div className="border-b border-[var(--border)] px-2 py-1.5">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Recent
              </p>
              <div className="flex flex-wrap gap-1">
                {recent.map((code) => (
                  <button
                    key={`r-${code}`}
                    type="button"
                    onClick={() => pick(code)}
                    className="rounded border border-[var(--border)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--fg-muted)] hover:text-[var(--fg)]"
                  >
                    {code}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {favorites.length ? (
            <div className="border-b border-[var(--border)] px-2 py-1.5">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Favorites
              </p>
              <div className="flex flex-wrap gap-1">
                {favorites.map((code) => (
                  <button
                    key={`f-${code}`}
                    type="button"
                    onClick={() => pick(code)}
                    className="rounded border border-[var(--border)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--accent)]"
                  >
                    {code}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <ul className="max-h-56 overflow-y-auto py-1">
            {filtered.map((code) => {
              const fav = favorites.includes(code);
              return (
                <li key={code} className="flex items-center gap-1 px-1">
                  <button
                    type="button"
                    role="option"
                    aria-selected={code === symbol}
                    onClick={() => pick(code)}
                    className={cn(
                      "min-w-0 flex-1 rounded px-2 py-1.5 text-left font-mono text-[12px]",
                      code === symbol
                        ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                        : "text-[var(--fg)] hover:bg-[var(--surface-2)]",
                    )}
                  >
                    {code}
                  </button>
                  <button
                    type="button"
                    className="rounded p-1 text-[var(--fg-subtle)] hover:text-[var(--accent)]"
                    aria-label={fav ? `Unfavorite ${code}` : `Favorite ${code}`}
                    onClick={() => toggleFav(code)}
                  >
                    <Star
                      className={cn("h-3.5 w-3.5", fav && "fill-current text-[var(--accent)]")}
                    />
                  </button>
                </li>
              );
            })}
            {!filtered.length ? (
              <li className="px-3 py-2 text-[12px] text-[var(--fg-muted)]">
                No matches — type a symbol and press Enter
              </li>
            ) : null}
          </ul>

          <div className="border-t border-[var(--border)] px-2 py-1.5">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
              Quick switch
            </p>
            <div className="flex flex-wrap gap-1">
              {QUICK_SYMBOLS.map((code) => (
                <button
                  key={`q-${code}`}
                  type="button"
                  onClick={() => pick(code)}
                  className="rounded border border-[var(--border)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--fg-muted)] hover:text-[var(--fg)]"
                >
                  {code}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      {open ? (
        <button
          type="button"
          className="fixed inset-0 z-30 cursor-default bg-transparent"
          aria-label="Close symbol menu"
          onClick={() => setOpen(false)}
        />
      ) : null}
    </div>
  );
});
