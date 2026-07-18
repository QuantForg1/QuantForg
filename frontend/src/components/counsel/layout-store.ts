/** Counsel OS layout — decision engine, not a chatbot. */

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
  symbol: "EURUSD",
  focus: "pulse",
  silenceExpanded: true,
};

export function loadCounselLayout(): CounselLayoutState {
  if (typeof window === "undefined") return DEFAULT_COUNSEL_LAYOUT;
  try {
    const raw = localStorage.getItem(COUNSEL_LAYOUT_KEY);
    if (!raw) return DEFAULT_COUNSEL_LAYOUT;
    return { ...DEFAULT_COUNSEL_LAYOUT, ...(JSON.parse(raw) as Partial<CounselLayoutState>) };
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
