"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Keyboard, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { SessionBar } from "@/components/broker/session-bar";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { PortfolioHealth, exposureFromPositions } from "@/components/book/portfolio-health";
import { PortfolioOverview } from "@/components/book/portfolio-overview";
import { PortfolioIntelligenceLab } from "@/components/book/portfolio-intelligence-lab";
import { RiskDna } from "@/components/book/risk-dna";
import { ExposureMap } from "@/components/book/exposure-map";
import { EquityTimeline } from "@/components/book/equity-timeline";
import { PositionIntelligence } from "@/components/book/position-intelligence";
import { PortfolioCounsel } from "@/components/book/portfolio-counsel";
import { BookEmpty } from "@/components/book/empty-state";
import {
  DEFAULT_BOOK_LAYOUT,
  loadBookLayout,
  saveBookLayout,
  type BookFocusPanel,
  type BookLayoutState,
} from "@/components/book/layout-store";
import { buildEquitySeries } from "@/lib/dashboard/derive";
import { portfolioApi, portfolioIntelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, metric, num } from "@/lib/desk";
import { useTradingSession } from "@/providers/trading-session-provider";
import { useBookStream } from "@/hooks/realtime";
import { cn } from "@/lib/utils";

function isTypingTarget(el: EventTarget | null) {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    el.isContentEditable
  );
}

const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: "1", action: "Focus Portfolio Health" },
  { keys: "2", action: "Focus Equity Timeline" },
  { keys: "3", action: "Focus Risk DNA" },
  { keys: "4", action: "Focus Exposure Map" },
  { keys: "5", action: "Focus Position Intelligence" },
  { keys: "C", action: "Toggle Portfolio Counsel" },
  { keys: "R", action: "Refresh book data" },
  { keys: "?", action: "This help" },
  { keys: "⌘2", action: "Book (OS desk)" },
];

/**
 * Book OS — institutional portfolio operating system.
 * Zero page scroll; panels scroll internally. Terminal architecture untouched.
 */
export function BookShell() {
  const session = useTradingSession();
  const realtime = useBookStream(session.connected);
  const [layout, setLayout] = useState<BookLayoutState>(DEFAULT_BOOK_LAYOUT);
  const [hydrated, setHydrated] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    setLayout(loadBookLayout());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveBookLayout(layout);
  }, [layout, hydrated]);

  const patchLayout = useCallback((partial: Partial<BookLayoutState>) => {
    setLayout((prev) => ({ ...prev, ...partial }));
  }, []);

  const portfolioQ = useQuery({
    queryKey: ["portfolio"],
    queryFn: portfolioApi.get,
    retry: false,
    staleTime: 12_000,
    enabled: session.connected,
  });

  const historyQ = useQuery({
    queryKey: ["history"],
    queryFn: portfolioApi.history,
    retry: false,
    staleTime: 8_000,
    enabled: session.connected,
  });

  const intelQ = useQuery({
    queryKey: ["portfolio-intelligence-dashboard"],
    queryFn: () => portfolioIntelligenceApi.dashboard(0.95),
    retry: false,
    staleTime: 30_000,
  });

  const account = asRecord(portfolioQ.data?.account);
  const positions = useMemo(() => {
    const fromApi = asList(portfolioQ.data?.positions).map(asRecord);
    return fromApi.length ? fromApi : session.positions;
  }, [portfolioQ.data, session.positions]);

  const deals = useMemo(() => {
    const fromApi = asList(historyQ.data?.deals).map(asRecord);
    return fromApi.length ? fromApi : session.historyDeals;
  }, [historyQ.data, session.historyDeals]);

  const equity = metric(account, "equity") || num(session.equity);
  const balance = metric(account, "balance") || num(session.balance);
  const freeMargin = metric(account, "free_margin") || num(session.freeMargin);
  const marginLevel = metric(account, "margin_level") || num(session.marginLevel);
  const floating =
    metric(account, "profit") ||
    positions.reduce((s, p) => s + num(p.profit, 0), 0) ||
    num(session.profit);

  const exposure = useMemo(() => exposureFromPositions(positions), [positions]);

  const equitySeries = useMemo(() => {
    if (!Number.isFinite(equity) || !deals.length) return [];
    return buildEquitySeries(deals, equity);
  }, [deals, equity]);

  const intelligence = intelQ.data ? asRecord(intelQ.data) : null;

  const refreshAll = useCallback(() => {
    void portfolioQ.refetch();
    void historyQ.refetch();
    void intelQ.refetch();
    void session.invalidateAll();
  }, [portfolioQ, historyQ, intelQ, session]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setHelpOpen(false);
        return;
      }
      if (isTypingTarget(e.target)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      const focusMap: Record<string, BookFocusPanel> = {
        "1": "health",
        "2": "timeline",
        "3": "risk",
        "4": "exposure",
        "5": "positions",
      };
      if (focusMap[k]) {
        e.preventDefault();
        patchLayout({ focus: focusMap[k] });
        return;
      }
      if (k === "c") {
        e.preventDefault();
        patchLayout({ counselCollapsed: !layout.counselCollapsed });
        return;
      }
      if (k === "r") {
        e.preventDefault();
        refreshAll();
        return;
      }
      if (e.key === "?" || (e.shiftKey && e.key === "/")) {
        e.preventDefault();
        setHelpOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [layout.counselCollapsed, patchLayout, refreshAll]);

  const loading =
    session.connected && (portfolioQ.isLoading || historyQ.isLoading);
  const hardError = session.connected && portfolioQ.isError;

  const focus = layout.focus;

  return (
    <div
      className="flex h-full min-h-0 flex-col overflow-hidden bg-[var(--bg)]"
      role="application"
      aria-label="QuantForg Book"
    >
      <header className="shrink-0">
        <div className="flex h-9 items-center justify-between gap-2 border-b border-[var(--border)] px-3">
          <div className="flex items-center gap-3">
            <h1 className="text-xs font-semibold tracking-tight text-[var(--fg)]">
              Book
            </h1>
            <span className="qf-caption hidden sm:inline">
              Portfolio operating system
            </span>
            {realtime.transport ? (
              <span className="qf-caption tabular text-[var(--fg-subtle)]">
                {realtime.transport}
              </span>
            ) : null}
          </div>
          <div className="flex items-center gap-0.5">
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 px-0"
              aria-label="Refresh book"
              onClick={refreshAll}
            >
              <RefreshCw
                className={cn(
                  "h-3.5 w-3.5",
                  (portfolioQ.isFetching || session.refreshing) && "animate-spin",
                )}
              />
            </Button>
            <Button size="sm" variant="secondary" className="h-7 px-2 text-[11px]" asChild>
              <Link href="/terminal">Terminal</Link>
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 px-0"
              aria-label="Keyboard shortcuts"
              onClick={() => setHelpOpen(true)}
            >
              <Keyboard className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <SessionBar />
        <PortfolioCounsel
          connected={session.connected}
          equity={equity}
          freeMargin={freeMargin}
          marginLevel={marginLevel}
          floating={floating}
          positionCount={positions.length}
          intelligence={intelligence}
          collapsed={layout.counselCollapsed}
          onToggle={() =>
            patchLayout({ counselCollapsed: !layout.counselCollapsed })
          }
        />
      </header>

      <div className="min-h-0 flex-1 overflow-hidden p-2 sm:p-3">
        {!session.connected ? (
          <BookEmpty
            className="h-full rounded-md border border-[var(--border)] bg-[var(--surface)]"
            title="No live book"
            description="Attach MT5 in Broker to load equity, risk, and positions. Book never invents balances."
            action={
              <Button size="sm" variant="secondary" asChild>
                <Link href="/broker">Open Broker</Link>
              </Button>
            }
          />
        ) : loading ? (
          <div className="flex h-full items-center justify-center">
            <DeskSkeleton rows={5} />
          </div>
        ) : hardError ? (
          <div className="flex h-full items-center justify-center p-4">
            <DeskError
              message="Unable to load portfolio. Sync the session and retry."
              onRetry={() => void portfolioQ.refetch()}
            />
          </div>
        ) : (
          <div className="grid h-full min-h-0 grid-rows-[auto_auto_minmax(0,1fr)_minmax(0,1fr)] gap-2">
            <div className="min-h-0 max-h-[40%] space-y-2 overflow-y-auto overflow-x-auto">
              <PortfolioOverview
                account={account}
                positions={positions}
                deals={deals}
              />
              <PortfolioIntelligenceLab />
            </div>
            <PortfolioHealth
              focused={focus === "health"}
              metrics={{
                equity,
                balance,
                freeMargin,
                marginLevel,
                floating,
                positionCount: positions.length,
                exposure,
                connected: session.connected,
              }}
            />

            <div className="grid min-h-0 gap-2 lg:grid-cols-2">
              <EquityTimeline
                series={equitySeries}
                focused={focus === "timeline"}
              />
              <RiskDna
                intelligence={intelligence}
                marginLevel={marginLevel}
                freeMargin={freeMargin}
                focused={focus === "risk"}
              />
            </div>

            <div className="grid min-h-0 gap-2 lg:grid-cols-2">
              <ExposureMap
                positions={positions}
                freeMargin={Number.isFinite(freeMargin) ? freeMargin : 0}
                intelligence={intelligence}
                focused={focus === "exposure"}
              />
              <PositionIntelligence
                positions={positions}
                focused={focus === "positions"}
              />
            </div>
          </div>
        )}
      </div>

      <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
        <DialogContent className="max-w-md">
          <DialogTitle>Book shortcuts</DialogTitle>
          <ul className="mt-3 space-y-2">
            {SHORTCUTS.map((row) => (
              <li
                key={row.keys}
                className="flex items-baseline justify-between gap-4 text-sm"
              >
                <kbd className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-1.5 py-0.5 font-mono text-[11px]">
                  {row.keys}
                </kbd>
                <span className="text-[var(--fg-muted)]">{row.action}</span>
              </li>
            ))}
          </ul>
        </DialogContent>
      </Dialog>
    </div>
  );
}
