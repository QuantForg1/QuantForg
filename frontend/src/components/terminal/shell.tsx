"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Keyboard,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { WorkspaceLeftRail } from "@/components/workspace/left-rail";
import { WorkspaceChart } from "@/components/workspace/chart-panel";
import { SplitHandle, useResizeSplit } from "@/components/workspace/splitters";
import { TerminalSessionBar } from "@/components/terminal/session-bar";
import { TerminalCounselStrip } from "@/components/terminal/counsel-strip";
import { TerminalRightRail } from "@/components/terminal/right-rail";
import { TerminalBlotter } from "@/components/terminal/blotter";
import {
  DEFAULT_TERMINAL_LAYOUT,
  PRESET_TERMINAL,
  TERMINAL_SYMBOL_KEY,
  loadTerminalLayout,
  saveTerminalLayout,
  type TerminalLayoutState,
  type TerminalPresetId,
  type TerminalBlotterTab,
} from "@/components/terminal/layout-store";
import type { OrderTicketHandle } from "@/components/execution/order-ticket";
import { useExecutionStream } from "@/hooks/realtime";
import { useTradingSession } from "@/providers/trading-session-provider";
import { mt5Api } from "@/lib/api/endpoints";
import { asRecord, num } from "@/lib/desk";
import { TRADING_SYMBOL, resolveTradingSymbol } from "@/lib/trading/gold-only";

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

const DESK_LINKS = [
  { href: "/analytics", label: "Analytics" },
  { href: "/risk-center", label: "Risk" },
  { href: "/auto-trading", label: "Auto" },
  { href: "/monitoring", label: "Monitor" },
] as const;

const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: "B / S", action: "Buy / Sell (confirm)" },
  { keys: "1–2", action: "Blotter tabs" },
  { keys: "[ / ]", action: "Toggle left / right rail" },
  { keys: "\\", action: "Toggle blotter" },
  { keys: "C", action: "Toggle AI decision strip" },
  { keys: "F", action: "Chart fullscreen" },
  { keys: "Esc", action: "Cancel / exit fullscreen" },
  { keys: "?", action: "This help" },
  { keys: "⌘1–4", action: "OS desks (Terminal → Counsel)" },
];

/**
 * QuantForg Terminal OS — flagship zero-scroll trading surface.
 * Chart · Ticket · AI Decision · Positions · Quick Risk only.
 * Preserves MT5 execution, lightweight-charts, live book, websockets.
 */
export function TerminalShell() {
  const searchParams = useSearchParams();
  const [layout, setLayout] = useState<TerminalLayoutState>(DEFAULT_TERMINAL_LAYOUT);
  const [symbol, setSymbol] = useState(TRADING_SYMBOL);
  const [hydrated, setHydrated] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const ticketRef = useRef<OrderTicketHandle | null>(null);
  const layoutRef = useRef(layout);

  useEffect(() => {
    layoutRef.current = layout;
  }, [layout]);

  useEffect(() => {
    const stored = loadTerminalLayout();
    setLayout(stored);
    try {
      const fromUrl = searchParams.get("symbol")?.trim();
      const fromLs = localStorage.getItem(TERMINAL_SYMBOL_KEY);
      setSymbol(resolveTradingSymbol(fromUrl || fromLs));
    } catch {
      /* ignore */
    }
    setHydrated(true);
    // Intentionally once on mount — URL symbol is an initial hint.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- hydrate once
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveTerminalLayout(layout);
  }, [layout, hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(TERMINAL_SYMBOL_KEY, symbol);
    } catch {
      /* ignore */
    }
  }, [symbol, hydrated]);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1023px)");
    const apply = () => {
      if (mq.matches) {
        setLayout((prev) => ({
          ...prev,
          leftCollapsed: true,
          rightCollapsed: true,
        }));
      }
    };
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  const realtime = useExecutionStream(symbol);
  const session = useTradingSession();
  const connected = session.connected;

  // Tick via realtime channel only — avoid duplicate shell poller.
  const tickQ = useQuery({
    queryKey: ["mt5-tick", symbol],
    queryFn: () => mt5Api.tick(symbol),
    retry: false,
    enabled: connected && Boolean(symbol),
    staleTime: 2_500,
    refetchInterval: false,
  });

  const tick = asRecord(tickQ.data);
  const bid = num(tick.bid);
  const ask = num(tick.ask);
  const lastPrice = useMemo(() => {
    if (Number.isFinite(bid) && Number.isFinite(ask)) return (bid + ask) / 2;
    const last = num(tick.last);
    return Number.isFinite(last) ? last : undefined;
  }, [bid, ask, tick.last]);

  const patchLayout = useCallback((partial: Partial<TerminalLayoutState>) => {
    setLayout((prev) => ({ ...prev, ...partial }));
  }, []);

  const applyPreset = useCallback((preset: TerminalPresetId) => {
    setLayout((prev) => ({ ...prev, ...PRESET_TERMINAL[preset] }));
  }, []);

  const onLeftDelta = useCallback((d: number) => {
    setLayout((prev) => ({
      ...prev,
      leftWidth: Math.min(280, Math.max(152, prev.leftWidth + d)),
    }));
  }, []);
  const onRightDelta = useCallback((d: number) => {
    setLayout((prev) => ({
      ...prev,
      rightWidth: Math.min(340, Math.max(260, prev.rightWidth - d)),
    }));
  }, []);
  const onBottomDelta = useCallback((d: number) => {
    setLayout((prev) => ({
      ...prev,
      bottomHeight: Math.min(200, Math.max(112, prev.bottomHeight - d)),
    }));
  }, []);

  const leftSplit = useResizeSplit(onLeftDelta);
  const rightSplit = useResizeSplit(onRightDelta);
  const bottomSplit = useResizeSplit(onBottomDelta);

  const setBlotterTab = useCallback(
    (bottomTab: TerminalBlotterTab) => {
      patchLayout({ bottomTab, bottomCollapsed: false });
    },
    [patchLayout],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const current = layoutRef.current;
      if (e.key === "Escape") {
        ticketRef.current?.cancelDialog();
        if (current.chartFullscreen) patchLayout({ chartFullscreen: false });
        setHelpOpen(false);
        return;
      }
      if (isTypingTarget(e.target)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      const k = e.key.toLowerCase();
      if (k === "b") {
        e.preventDefault();
        ticketRef.current?.buy();
        return;
      }
      if (k === "s") {
        e.preventDefault();
        ticketRef.current?.sell();
        return;
      }
      if (k === "1") {
        e.preventDefault();
        setBlotterTab("positions");
        return;
      }
      if (k === "2") {
        e.preventDefault();
        setBlotterTab("orders");
        return;
      }
      if (e.key === "[") {
        e.preventDefault();
        patchLayout({ leftCollapsed: !current.leftCollapsed });
        return;
      }
      if (e.key === "]") {
        e.preventDefault();
        patchLayout({ rightCollapsed: !current.rightCollapsed });
        return;
      }
      if (e.key === "\\") {
        e.preventDefault();
        patchLayout({ bottomCollapsed: !current.bottomCollapsed });
        return;
      }
      if (k === "c") {
        e.preventDefault();
        patchLayout({ counselCollapsed: !current.counselCollapsed });
        return;
      }
      if (k === "f") {
        e.preventDefault();
        patchLayout({ chartFullscreen: !current.chartFullscreen });
        return;
      }
      if (e.key === "?" || (e.shiftKey && e.key === "/")) {
        e.preventDefault();
        setHelpOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [patchLayout, setBlotterTab]);

  const showLeft = !layout.leftCollapsed && !layout.chartFullscreen;
  const showRight = !layout.rightCollapsed && !layout.chartFullscreen;
  const showBottom = !layout.bottomCollapsed && !layout.chartFullscreen;
  const showCounsel = !layout.chartFullscreen;

  const bidOk = Number.isFinite(bid) ? bid : undefined;
  const askOk = Number.isFinite(ask) ? ask : undefined;

  return (
    <div
      className="flex h-full min-h-0 flex-col overflow-hidden bg-[var(--bg)]"
      role="application"
      aria-label="QuantForg Terminal"
    >
      <header className="shrink-0">
        <div className="flex h-8 items-center justify-between gap-2 border-b border-[var(--border)] px-2">
          <div className="flex min-w-0 items-center gap-3">
            <h1 className="shrink-0 text-xs font-semibold tracking-tight text-[var(--fg)]">
              Terminal
            </h1>
            <nav
              className="hidden items-center gap-2 sm:flex"
              aria-label="Secondary desks"
            >
              {DESK_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)] transition-colors hover:text-[var(--fg)]"
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-0.5">
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 px-0"
              aria-label={layout.leftCollapsed ? "Expand watchlist" : "Collapse watchlist"}
              onClick={() => patchLayout({ leftCollapsed: !layout.leftCollapsed })}
            >
              {layout.leftCollapsed ? (
                <PanelLeftOpen className="h-4 w-4" />
              ) : (
                <PanelLeftClose className="h-4 w-4" />
              )}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 px-0"
              aria-label={layout.rightCollapsed ? "Expand ticket" : "Collapse ticket"}
              onClick={() => patchLayout({ rightCollapsed: !layout.rightCollapsed })}
            >
              {layout.rightCollapsed ? (
                <PanelRightOpen className="h-4 w-4" />
              ) : (
                <PanelRightClose className="h-4 w-4" />
              )}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-[11px]"
              onClick={() => patchLayout({ bottomCollapsed: !layout.bottomCollapsed })}
            >
              {layout.bottomCollapsed ? "Positions" : "Hide"}
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
        <TerminalSessionBar
          symbol={symbol}
          bid={bidOk}
          ask={askOk}
          realtime={realtime}
        />
        {showCounsel ? (
          <TerminalCounselStrip
            symbol={symbol}
            bid={bidOk}
            ask={askOk}
            collapsed={layout.counselCollapsed}
            onToggle={() =>
              patchLayout({ counselCollapsed: !layout.counselCollapsed })
            }
          />
        ) : null}
      </header>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {showLeft ? (
          <>
            <div style={{ width: layout.leftWidth }} className="min-h-0 shrink-0 overflow-hidden">
              <WorkspaceLeftRail
                connected={connected}
                selected={symbol}
                onSelect={setSymbol}
                preset={layout.preset}
                onPresetChange={applyPreset}
                hideStatusChrome
              />
            </div>
            <SplitHandle
              orientation="vertical"
              label="Resize watchlist"
              onStartDrag={leftSplit.start("x")}
              onStep={onLeftDelta}
            />
          </>
        ) : null}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <div className="min-h-0 flex-1 overflow-hidden">
            <WorkspaceChart
              symbol={symbol}
              connected={connected}
              timeframe={layout.timeframe}
              onTimeframeChange={(timeframe) => patchLayout({ timeframe })}
              chartType={layout.chartType}
              onChartTypeChange={(chartType) => patchLayout({ chartType })}
              showVolume={layout.showVolume}
              onShowVolumeChange={(showVolume) => patchLayout({ showVolume })}
              fullscreen={layout.chartFullscreen}
              onFullscreenChange={(chartFullscreen) =>
                patchLayout({ chartFullscreen })
              }
              lastPrice={lastPrice}
            />
          </div>

          {showBottom ? (
            <>
              <SplitHandle
                orientation="horizontal"
                label="Resize blotter"
                onStartDrag={bottomSplit.start("y")}
                onStep={onBottomDelta}
              />
              <div
                style={{ height: layout.bottomHeight }}
                className="min-h-0 shrink-0 overflow-hidden"
              >
                <TerminalBlotter
                  tab={layout.bottomTab}
                  onTabChange={setBlotterTab}
                />
              </div>
            </>
          ) : null}
        </div>

        {showRight ? (
          <>
            <SplitHandle
              orientation="vertical"
              label="Resize ticket"
              onStartDrag={rightSplit.start("x")}
              onStep={(d) => onRightDelta(-d)}
            />
            <div style={{ width: layout.rightWidth }} className="min-h-0 shrink-0 overflow-hidden">
              <TerminalRightRail
                symbol={symbol}
                onSymbolChange={setSymbol}
                connected={connected}
                bid={bidOk}
                ask={askOk}
                ticketRef={ticketRef}
              />
            </div>
          </>
        ) : null}
      </div>

      <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
        <DialogContent className="max-w-md">
          <DialogTitle>Terminal shortcuts</DialogTitle>
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
