/** Terminal OS layout V5 — chart · ticket · AI · blotter only. */

export type TerminalPresetId = "default" | "chart-focus" | "tape-focus";

export type TerminalBlotterTab = "positions" | "orders" | "executions";

export type TerminalLayoutState = {
  preset: TerminalPresetId;
  rightWidth: number;
  bottomHeight: number;
  rightCollapsed: boolean;
  bottomCollapsed: boolean;
  chartFullscreen: boolean;
  chartType: "candles" | "line" | "area";
  timeframe: string;
  showVolume: boolean;
  bottomTab: TerminalBlotterTab;
  counselCollapsed: boolean;
  /** Mobile: bottom-sheet order ticket open */
  mobileTicketOpen: boolean;
};

export const TERMINAL_LAYOUT_KEY = "qf.terminal.layout.v5";
export const TERMINAL_SYMBOL_KEY = "qf.workspace.symbol";

export const DEFAULT_TERMINAL_LAYOUT: TerminalLayoutState = {
  preset: "default",
  rightWidth: 320,
  bottomHeight: 148,
  rightCollapsed: false,
  bottomCollapsed: false,
  chartFullscreen: false,
  chartType: "candles",
  timeframe: "H1",
  showVolume: true,
  bottomTab: "positions",
  counselCollapsed: true,
  mobileTicketOpen: false,
};

const TRADER_TABS: TerminalBlotterTab[] = ["positions", "orders", "executions"];

export const PRESET_TERMINAL: Record<
  TerminalPresetId,
  Partial<TerminalLayoutState>
> = {
  default: {
    preset: "default",
    rightWidth: 320,
    bottomHeight: 148,
    rightCollapsed: false,
    bottomCollapsed: false,
    chartFullscreen: false,
    counselCollapsed: true,
  },
  "chart-focus": {
    preset: "chart-focus",
    rightCollapsed: true,
    bottomCollapsed: true,
    counselCollapsed: true,
    chartFullscreen: false,
  },
  "tape-focus": {
    preset: "tape-focus",
    rightWidth: 300,
    bottomHeight: 220,
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
      rightWidth: Math.min(
        380,
        Math.max(280, Number(parsed.rightWidth) || DEFAULT_TERMINAL_LAYOUT.rightWidth),
      ),
      bottomHeight: Math.min(
        280,
        Math.max(120, Number(parsed.bottomHeight) || DEFAULT_TERMINAL_LAYOUT.bottomHeight),
      ),
      mobileTicketOpen: false,
    };
  } catch {
    return DEFAULT_TERMINAL_LAYOUT;
  }
}

export function saveTerminalLayout(state: TerminalLayoutState) {
  try {
    const { mobileTicketOpen, ...persist } = state;
    void mobileTicketOpen;
    localStorage.setItem(TERMINAL_LAYOUT_KEY, JSON.stringify(persist));
  } catch {
    /* ignore quota */
  }
}
