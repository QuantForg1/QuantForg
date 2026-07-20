/** Counsel OS layout — decision engine, not a chatbot. */

import { TRADING_SYMBOL, resolveTradingSymbol } from "@/lib/trading/gold-only";

export type CounselFocus =
  | "pulse"
  | "context"
  | "recommendation"
  | "impact"
  | "timeline"
  | "memory"
  | "silence";

export type CounselLayoutState = {
  symbol: string;
  focus: CounselFocus;
  silenceExpanded: boolean;
};

export const COUNSEL_LAYOUT_KEY = "qf.counsel.layout.v1";

export const DEFAULT_COUNSEL_LAYOUT: CounselLayoutState = {
  symbol: TRADING_SYMBOL,
  focus: "pulse",
  silenceExpanded: true,
};

export function loadCounselLayout(): CounselLayoutState {
  if (typeof window === "undefined") return DEFAULT_COUNSEL_LAYOUT;
  try {
    const raw = localStorage.getItem(COUNSEL_LAYOUT_KEY);
    if (!raw) return DEFAULT_COUNSEL_LAYOUT;
    const merged = {
      ...DEFAULT_COUNSEL_LAYOUT,
      ...(JSON.parse(raw) as Partial<CounselLayoutState>),
    };
    return { ...merged, symbol: resolveTradingSymbol(merged.symbol) };
  } catch {
    return DEFAULT_COUNSEL_LAYOUT;
  }
}

export function saveCounselLayout(state: CounselLayoutState) {
  try {
    localStorage.setItem(COUNSEL_LAYOUT_KEY, JSON.stringify(state));
  } catch {
    /* ignore */
  }
}
