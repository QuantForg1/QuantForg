/** Terminal OS layout persistence — trader tabs only. */

export type TerminalPresetId = "default" | "chart-focus" | "tape-focus";

export type TerminalBlotterTab = "positions" | "orders" | "history" | "journal";

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

export const TERMINAL_LAYOUT_KEY = "qf.terminal.layout.v1";
export const TERMINAL_SYMBOL_KEY = "qf.workspace.symbol";

export const DEFAULT_TERMINAL_LAYOUT: TerminalLayoutState = {
  preset: "default",
  leftWidth: 260,
  rightWidth: 340,
  bottomHeight: 220,
  leftCollapsed: false,
  rightCollapsed: false,
  bottomCollapsed: false,
  chartFullscreen: false,
  chartType: "candles",
  timeframe: "H1",
  showVolume: true,
  bottomTab: "positions",
  counselCollapsed: false,
};

const TRADER_TABS: TerminalBlotterTab[] = [
  "positions",
  "orders",
  "history",
  "journal",
];

export const PRESET_TERMINAL: Record<
  TerminalPresetId,
  Partial<TerminalLayoutState>
> = {
  default: {
    preset: "default",
    leftWidth: 260,
    rightWidth: 340,
    bottomHeight: 220,
    leftCollapsed: false,
    rightCollapsed: false,
    bottomCollapsed: false,
    chartFullscreen: false,
    counselCollapsed: false,
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
    leftWidth: 240,
    rightWidth: 320,
    bottomHeight: 300,
    leftCollapsed: false,
    rightCollapsed: false,
    bottomCollapsed: false,
    counselCollapsed: false,
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
    const raw =
      localStorage.getItem(TERMINAL_LAYOUT_KEY) ||
      localStorage.getItem("qf.workspace.layout.v2");
    if (!raw) return DEFAULT_TERMINAL_LAYOUT;
    const parsed = JSON.parse(raw) as Partial<TerminalLayoutState> & {
      bottomTab?: unknown;
    };
    return {
      ...DEFAULT_TERMINAL_LAYOUT,
      ...parsed,
      bottomTab: normalizeTab(parsed.bottomTab),
      counselCollapsed: Boolean(parsed.counselCollapsed),
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
