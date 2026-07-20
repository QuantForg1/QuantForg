/** Persisted Advanced Trading Workspace layout. */

import {
  TRADING_SYMBOL,
  isGoldSymbol,
  MULTI_SYMBOL_ENABLED,
} from "@/lib/trading/gold-only";

export type WorkspacePresetId = "default" | "chart-focus" | "tape-focus";

export type WorkspaceLayoutState = {
  preset: WorkspacePresetId;
  leftWidth: number;
  rightWidth: number;
  bottomHeight: number;
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  bottomCollapsed: boolean;
  chartFullscreen: boolean;
  chartType: "candles" | "line" | "area";
  timeframe: string;
  showVolume: boolean;
  bottomTab:
    | "positions"
    | "orders"
    | "history"
    | "journal"
    | "execution"
    | "gateway"
    | "broker"
    | "system"
    | "notifications";
};

export const WORKSPACE_LAYOUT_KEY = "qf.workspace.layout.v2";
export const WORKSPACE_SYMBOL_KEY = "qf.workspace.symbol";
export const WORKSPACE_FAV_KEY = "qf.execution.watch.favorites";
export const WORKSPACE_WATCHLIST_KEY = "qf.workspace.watchlists";

export const DEFAULT_LAYOUT: WorkspaceLayoutState = {
  preset: "default",
  leftWidth: 300,
  rightWidth: 360,
  bottomHeight: 240,
  leftCollapsed: false,
  rightCollapsed: false,
  bottomCollapsed: false,
  chartFullscreen: false,
  chartType: "candles",
  timeframe: "H1",
  showVolume: true,
  bottomTab: "positions",
};

export const PRESET_LAYOUTS: Record<WorkspacePresetId, Partial<WorkspaceLayoutState>> = {
  default: {
    preset: "default",
    leftWidth: 280,
    rightWidth: 340,
    bottomHeight: 220,
    leftCollapsed: false,
    rightCollapsed: false,
    bottomCollapsed: false,
    chartFullscreen: false,
  },
  "chart-focus": {
    preset: "chart-focus",
    leftWidth: 220,
    rightWidth: 300,
    bottomHeight: 160,
    leftCollapsed: false,
    rightCollapsed: true,
    bottomCollapsed: true,
    chartFullscreen: false,
  },
  "tape-focus": {
    preset: "tape-focus",
    leftWidth: 300,
    rightWidth: 360,
    bottomHeight: 280,
    leftCollapsed: false,
    rightCollapsed: false,
    bottomCollapsed: false,
    chartFullscreen: false,
  },
};

export function loadWorkspaceLayout(): WorkspaceLayoutState {
  if (typeof window === "undefined") return DEFAULT_LAYOUT;
  try {
    const raw = localStorage.getItem(WORKSPACE_LAYOUT_KEY);
    if (!raw) return DEFAULT_LAYOUT;
    return { ...DEFAULT_LAYOUT, ...(JSON.parse(raw) as Partial<WorkspaceLayoutState>) };
  } catch {
    return DEFAULT_LAYOUT;
  }
}

export function saveWorkspaceLayout(state: WorkspaceLayoutState) {
  try {
    localStorage.setItem(WORKSPACE_LAYOUT_KEY, JSON.stringify(state));
  } catch {
    /* ignore quota */
  }
}

export type NamedWatchlist = { id: string; name: string; symbols: string[] };

export function loadWatchlists(): NamedWatchlist[] {
  const defaultList: NamedWatchlist[] = [
    { id: "default", name: "Main", symbols: [TRADING_SYMBOL] },
  ];
  if (typeof window === "undefined") return defaultList;
  try {
    const raw = localStorage.getItem(WORKSPACE_WATCHLIST_KEY);
    if (!raw) return defaultList;
    const lists = JSON.parse(raw) as NamedWatchlist[];
    if (MULTI_SYMBOL_ENABLED) return lists;
    return lists.map((w) => ({
      ...w,
      symbols: w.symbols.filter((s) => isGoldSymbol(s)).length
        ? w.symbols.filter((s) => isGoldSymbol(s))
        : [TRADING_SYMBOL],
    }));
  } catch {
    return defaultList;
  }
}

export function saveWatchlists(lists: NamedWatchlist[]) {
  try {
    localStorage.setItem(WORKSPACE_WATCHLIST_KEY, JSON.stringify(lists));
  } catch {
    /* ignore */
  }
}
