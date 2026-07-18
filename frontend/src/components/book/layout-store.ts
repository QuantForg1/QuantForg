/** Book OS layout — portfolio operating system, not a dashboard. */

export type BookFocusPanel =
  | "health"
  | "timeline"
  | "risk"
  | "exposure"
  | "positions";

export type BookLayoutState = {
  counselCollapsed: boolean;
  focus: BookFocusPanel;
};

export const BOOK_LAYOUT_KEY = "qf.book.layout.v1";

export const DEFAULT_BOOK_LAYOUT: BookLayoutState = {
  counselCollapsed: false,
  focus: "health",
};

export function loadBookLayout(): BookLayoutState {
  if (typeof window === "undefined") return DEFAULT_BOOK_LAYOUT;
  try {
    const raw = localStorage.getItem(BOOK_LAYOUT_KEY);
    if (!raw) return DEFAULT_BOOK_LAYOUT;
    const parsed = JSON.parse(raw) as Partial<BookLayoutState>;
    return { ...DEFAULT_BOOK_LAYOUT, ...parsed };
  } catch {
    return DEFAULT_BOOK_LAYOUT;
  }
}

export function saveBookLayout(state: BookLayoutState) {
  try {
    localStorage.setItem(BOOK_LAYOUT_KEY, JSON.stringify(state));
  } catch {
    /* ignore */
  }
}
