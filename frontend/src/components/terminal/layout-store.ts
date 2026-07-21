/** Terminal OS layout — trading-only surface. */

export type TerminalPresetId = "default" | "chart-focus" | "tape-focus";

/** Positions-first blotter — history/journal live on Journal desk. */
export type TerminalBlotterTab = "positions" | "orders";

export type TerminalLayoutState = {
  preset: TerminalPresetId;
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
  bottomTab: TerminalBlotterTab;
  counselCollapsed: boolean;
};

export const TERMINAL_LAYOUT_KEY = "qf.terminal.layout.v2";
export const TERMINAL_SYMBOL_KEY = "qf.workspace.symbol";

export const DEFAULT_TERMINAL_LAYOUT: TerminalLayoutState = {
  preset: "default",
  leftWidth: 240,
  rightWidth: 360,
  bottomHeight: 180,
  leftCollapsed: false,
  rightCollapsed: false,
  bottomCollapsed: false,
  chartFullscreen: false,
  chartType: "candles",
  timeframe: "H1",
  showVolume: true,
  bottomTab: "positions",
  counselCollapsed: true,
};

const TRADER_TABS: TerminalBlotterTab[] = ["positions", "orders"];

export const PRESET_TERMINAL: Record<
  TerminalPresetId,
  Partial<TerminalLayoutState>
> = {
  default: {
    preset: "default",
    leftWidth: 240,
    rightWidth: 360,
    bottomHeight: 180,
    leftCollapsed: false,
    rightCollapsed: false,
    bottomCollapsed: false,
    chartFullscreen: false,
    counselCollapsed: true,
  },
  "chart-focus": {
    preset: "chart-focus",
    leftCollapsed: true,
    rightCollapsed: true,
    bottomCollapsed: true,
    counselCollapsed: true,
    chartFullscreen: false,
  },
  "tape-focus": {
    preset: "tape-focus",
    leftWidth: 220,
    rightWidth: 340,
    bottomHeight: 260,
    leftCollapsed: false,
    rightCollapsed: false,
    bottomCollapsed: false,
    counselCollapsed: true,
  },
};

function normalizeTab(raw: unknown): TerminalBlotterTab {
  if (typeof raw === "string" && TRADER_TABS.includes(raw as TerminalBlotterTab)) {
    return raw as TerminalBlotterTab;
  }
  return "positions";
}

export function loadTerminalLayout(): TerminalLayoutState {
  if (typeof window === "undefined") return DEFAULT_TERMINAL_LAYOUT;
  try {
    const raw = localStorage.getItem(TERMINAL_LAYOUT_KEY);
    if (!raw) return DEFAULT_TERMINAL_LAYOUT;
    const parsed = JSON.parse(raw) as Partial<TerminalLayoutState> & {
      bottomTab?: unknown;
    };
    return {
      ...DEFAULT_TERMINAL_LAYOUT,
      ...parsed,
      bottomTab: normalizeTab(parsed.bottomTab),
      counselCollapsed:
        parsed.counselCollapsed === undefined
          ? true
          : Boolean(parsed.counselCollapsed),
    };
  } catch {
    return DEFAULT_TERMINAL_LAYOUT;
  }
}

export function saveTerminalLayout(state: TerminalLayoutState) {
  try {
    localStorage.setItem(TERMINAL_LAYOUT_KEY, JSON.stringify(state));
  } catch {
    /* ignore quota */
  }
}
