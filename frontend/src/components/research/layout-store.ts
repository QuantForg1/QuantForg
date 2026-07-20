/** Research OS layout — institutional research workflow, not a page collage. */

import { TRADING_SYMBOL, resolveTradingSymbol } from "@/lib/trading/gold-only";

export type ResearchStage =
  | "idea"
  | "observe"
  | "validate"
  | "backtest"
  | "walkforward"
  | "risk"
  | "ai"
  | "promote";

export type ResearchLayoutState = {
  stage: ResearchStage;
  symbol: string;
  strategyKey: string;
  aiCollapsed: boolean;
};

export const RESEARCH_LAYOUT_KEY = "qf.research.layout.v1";

export const DEFAULT_RESEARCH_LAYOUT: ResearchLayoutState = {
  stage: "idea",
  symbol: TRADING_SYMBOL,
  strategyKey: "",
  aiCollapsed: false,
};

export const RESEARCH_STAGES: {
  id: ResearchStage;
  label: string;
  hotkey: string;
}[] = [
  { id: "idea", label: "Idea", hotkey: "1" },
  { id: "observe", label: "Observe", hotkey: "2" },
  { id: "validate", label: "Validate", hotkey: "3" },
  { id: "backtest", label: "Backtest", hotkey: "4" },
  { id: "walkforward", label: "Walk Fwd", hotkey: "5" },
  { id: "risk", label: "Risk", hotkey: "6" },
  { id: "ai", label: "AI Review", hotkey: "7" },
  { id: "promote", label: "Promote", hotkey: "8" },
];

export function loadResearchLayout(): ResearchLayoutState {
  if (typeof window === "undefined") return DEFAULT_RESEARCH_LAYOUT;
  try {
    const raw = localStorage.getItem(RESEARCH_LAYOUT_KEY);
    if (!raw) return DEFAULT_RESEARCH_LAYOUT;
    const parsed = JSON.parse(raw) as Partial<ResearchLayoutState>;
    const merged = { ...DEFAULT_RESEARCH_LAYOUT, ...parsed };
    return { ...merged, symbol: resolveTradingSymbol(merged.symbol) };
  } catch {
    return DEFAULT_RESEARCH_LAYOUT;
  }
}

export function saveResearchLayout(state: ResearchLayoutState) {
  try {
    localStorage.setItem(RESEARCH_LAYOUT_KEY, JSON.stringify(state));
  } catch {
    /* ignore */
  }
}
