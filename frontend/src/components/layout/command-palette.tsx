"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import { Clock, Pin, Star } from "lucide-react";
import {
  appNav,
  commandCatalog,
  isTraderFacingHref,
  visiblePrimaryRail,
} from "@/components/layout/nav-config";
import { useNavMemory } from "@/hooks/use-nav-memory";
import { labelForHref } from "@/lib/workspace/nav-memory";
import { useAuth } from "@/providers/auth-provider";
import { canAccessIteOps } from "@/lib/auth/ite-ops-access";
import { marketUniverseApi, portfolioApi, tradingSessionApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import {
  MARKET_UNIVERSE_QUERY_KEY,
  isLiveBrokerCatalogue,
  instrumentSymbol,
  mergeCatalogueRows,
  positionExposureLabel,
  resolveConnectionPresentation,
  signalBoardDirection,
} from "@/lib/trading/trader-ux";

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const titleId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const memory = useNavMemory();
  const { user } = useAuth();
  const isOperator = canAccessIteOps(user);
  const deskRail = visiblePrimaryRail(isOperator);
  const pageGroups = isOperator
    ? appNav
    : appNav
        .map((group) => ({
          ...group,
          items: group.items.filter((item) => isTraderFacingHref(item.href)),
        }))
        .filter((group) => group.items.length > 0);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  useEffect(() => {
    if (!open) {
      setQuery("");
      return;
    }
    const t = window.setTimeout(() => inputRef.current?.focus(), 0);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onOpenChange(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.clearTimeout(t);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onOpenChange]);

  const iconByHref = useMemo(() => {
    const map = new Map<string, (typeof commandCatalog)[number]["icon"]>();
    for (const item of commandCatalog) map.set(item.href, item.icon);
    return map;
  }, []);

  const go = (href: string, label?: string) => {
    onOpenChange(false);
    memory.recordPage({ href, label: label ?? labelForHref(href) });
    router.push(href);
  };

  const sessionQ = useQuery({
    queryKey: ["trading-session"],
    queryFn: tradingSessionApi.session,
    retry: false,
    enabled: open,
  });
  const session = asRecord(sessionQ.data);
  const connection = resolveConnectionPresentation(session);
  const liveCatalogue = isLiveBrokerCatalogue(session);
  const mismatch = connection.state === "ACCOUNT_SESSION_MISMATCH";

  const universeQ = useQuery({
    queryKey: MARKET_UNIVERSE_QUERY_KEY,
    queryFn: () => marketUniverseApi.snapshot(),
    enabled: open && connection.connected && liveCatalogue && !mismatch,
    retry: false,
  });
  const portfolioQ = useQuery({
    queryKey: ["portfolio"],
    queryFn: portfolioApi.get,
    enabled: open && connection.connected && !mismatch,
    retry: false,
  });

  const symbols = useMemo(() => {
    const universe = asRecord(universeQ.data);
    const instruments = asList(universe.instruments).map(asRecord);
    if (String(universe.catalogue_source || "").toUpperCase() !== "LIVE_BROKER") return [];
    return mergeCatalogueRows(
      instruments,
      asList(asRecord(universe.opportunity_board).rows).map(asRecord),
    ).slice(0, 12);
  }, [universeQ.data]);

  const signalHits = useMemo(
    () =>
      symbols
        .filter((row) => {
          const dir = signalBoardDirection(row);
          return dir === "BUY" || dir === "SELL";
        })
        .slice(0, 8),
    [symbols],
  );

  const positions = useMemo(
    () => asList(asRecord(portfolioQ.data).positions).map(asRecord).slice(0, 8),
    [portfolioQ.data],
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-[color-mix(in_srgb,var(--bg)_50%,#000)] p-4 pt-[12vh] qf-motion-overlay"
      role="presentation"
    >
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        aria-label="Close command palette"
        onClick={() => onOpenChange(false)}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative z-10 w-full max-w-xl qf-elevate qf-motion-slide-up"
      >
        <h2 id={titleId} className="sr-only">
          Command palette
        </h2>
        <Command
          className="overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg-elevated)] shadow-[var(--shadow-elevated)]"
          label="Global search"
        >
          <Command.Input
            ref={inputRef}
            value={query}
            onValueChange={setQuery}
            placeholder="Jump to workspace, page, symbol, or action…"
            aria-label="Search pages, symbols, and actions"
            className="h-12 w-full border-b border-[var(--border)] bg-transparent px-4 text-sm text-[var(--fg)] outline-none placeholder:text-[var(--fg-muted)]"
          />
          <Command.List className="max-h-[min(28rem,58vh)] overflow-y-auto p-1.5">
            <Command.Empty className="px-3 py-8 text-center text-sm text-[var(--fg-muted)]">
              No matches. Try a page name, symbol, or action.
            </Command.Empty>

            {memory.pinned.length > 0 ? (
              <Command.Group heading="Pinned" className="qf-cmd-group">
                {memory.pinned.map((item) => (
                  <Command.Item
                    key={`pin-${item.href}`}
                    value={`pinned ${item.label} ${item.href}`}
                    onSelect={() => go(item.href, item.label)}
                    className="qf-cmd-item"
                  >
                    <Pin className="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" aria-hidden />
                    <span className="truncate">{item.label}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}

            {memory.favorites.length > 0 ? (
              <Command.Group heading="Favorites" className="qf-cmd-group">
                {memory.favorites.map((item) => (
                  <Command.Item
                    key={`fav-${item.href}`}
                    value={`favorite ${item.label} ${item.href}`}
                    onSelect={() => go(item.href, item.label)}
                    className="qf-cmd-item"
                  >
                    <Star className="h-3.5 w-3.5 shrink-0 text-[var(--warning)]" aria-hidden />
                    <span className="truncate">{item.label}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}

            {memory.recent.length > 0 ? (
              <Command.Group heading="Recent" className="qf-cmd-group">
                {memory.recent.slice(0, 6).map((item) => (
                  <Command.Item
                    key={`recent-${item.href}`}
                    value={`recent ${item.label} ${item.href}`}
                    onSelect={() => go(item.href, item.label)}
                    className="qf-cmd-item"
                  >
                    <Clock className="h-3.5 w-3.5 shrink-0" aria-hidden />
                    <span className="truncate">{item.label}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}

            <Command.Group heading="Workspaces" className="qf-cmd-group">
              {deskRail.map((item) => {
                const Icon = item.icon;
                return (
                  <Command.Item
                    key={`desk-${item.href}`}
                    value={`workspace ${item.label} ${item.hint ?? ""} ${item.href}`}
                    onSelect={() => go(item.href, item.label)}
                    className="qf-cmd-item"
                  >
                    <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
                    <span className="min-w-0 flex-1 truncate">{item.label}</span>
                    {item.shortcut ? (
                      <kbd className="rounded border border-[var(--border)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--fg-subtle)]">
                        ⌘{item.shortcut}
                      </kbd>
                    ) : null}
                  </Command.Item>
                );
              })}
            </Command.Group>

            <Command.Group heading="Markets" className="qf-cmd-group">
              <Command.Item
                value="markets broker catalogue instruments"
                onSelect={() => go("/markets", "Markets")}
                className="qf-cmd-item"
              >
                <span className="text-[var(--fg)]">Broker-discovered markets</span>
                <span className="text-[var(--fg-subtle)]">Open catalogue</span>
              </Command.Item>
              {symbols.map((row, i) => {
                const symbol = instrumentSymbol(row) || str(row.symbol, String(i));
                if (!symbol) return null;
                return (
                  <Command.Item
                    key={`sym-${symbol}`}
                    value={`symbol ${symbol} ${str(row.asset_class)} ${str(row.description)}`}
                    onSelect={() => go(`/symbols/${encodeURIComponent(symbol)}`, symbol)}
                    className="qf-cmd-item"
                  >
                    <span className="truncate font-medium">{symbol}</span>
                    <span className="text-[var(--fg-subtle)]">{str(row.asset_class, "")}</span>
                  </Command.Item>
                );
              })}
            </Command.Group>

            {signalHits.length > 0 ? (
              <Command.Group heading="Signals" className="qf-cmd-group">
                {signalHits.map((row, i) => {
                  const symbol = instrumentSymbol(row) || str(row.symbol, String(i));
                  const dir = signalBoardDirection(row);
                  return (
                    <Command.Item
                      key={`sig-${symbol}-${dir}`}
                      value={`signal ${symbol} ${dir} buy sell`}
                      onSelect={() => go("/signals", "Signals")}
                      className="qf-cmd-item"
                    >
                      <span className="truncate font-medium">{symbol}</span>
                      <span className="text-[var(--fg-subtle)]">{dir}</span>
                    </Command.Item>
                  );
                })}
              </Command.Group>
            ) : null}

            {positions.length > 0 ? (
              <Command.Group heading="Positions" className="qf-cmd-group">
                {positions.map((row, i) => {
                  const symbol = str(row.symbol, String(i));
                  const side = positionExposureLabel(row.side);
                  return (
                    <Command.Item
                      key={`pos-${str(row.ticket, symbol)}`}
                      value={`position ${symbol} ${side} portfolio`}
                      onSelect={() => go("/portfolio", "Portfolio")}
                      className="qf-cmd-item"
                    >
                      <span className="truncate font-medium">{symbol}</span>
                      <span className="text-[var(--fg-subtle)]">{side}</span>
                    </Command.Item>
                  );
                })}
              </Command.Group>
            ) : null}

            {pageGroups.map((group) => (
              <Command.Group
                key={group.title}
                heading={group.title}
                className="qf-cmd-group"
              >
                {group.items.map((item) => {
                  const Icon = iconByHref.get(item.href) ?? item.icon;
                  return (
                    <Command.Item
                      key={`page-${group.title}-${item.href}`}
                      value={`${group.title} ${item.label} ${item.hint ?? ""} ${item.href}`}
                      onSelect={() => go(item.href, item.label)}
                      className="qf-cmd-item"
                    >
                      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                      {item.hint ? (
                        <span className="hidden max-w-[40%] truncate text-[11px] text-[var(--fg-subtle)] sm:inline">
                          {item.hint}
                        </span>
                      ) : null}
                    </Command.Item>
                  );
                })}
              </Command.Group>
            ))}
          </Command.List>
          <div className="flex items-center justify-between gap-2 border-t border-[var(--border)] px-3 py-2">
            <p className="qf-caption">Jump anywhere · pin favorites from the rail</p>
            <div className="flex items-center gap-2 text-[10px] text-[var(--fg-subtle)]">
              <kbd className="rounded border border-[var(--border)] px-1.5 py-0.5 font-mono">↑↓</kbd>
              <span>move</span>
              <kbd className="rounded border border-[var(--border)] px-1.5 py-0.5 font-mono">↵</kbd>
              <span>open</span>
              <kbd className="rounded border border-[var(--border)] px-1.5 py-0.5 font-mono">esc</kbd>
            </div>
          </div>
        </Command>
      </div>
    </div>
  );
}
