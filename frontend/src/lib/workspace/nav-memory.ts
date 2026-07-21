/** QuantForg OS V4 — workspace memory (favorites, pins, recents, symbols). */

export type NavMemoryItem = {
  href: string;
  label: string;
  at: number;
};

const KEYS = {
  favorites: "qf.nav.favorites.v1",
  pinned: "qf.nav.pinned.v1",
  recent: "qf.nav.recent.v1",
  symbols: "qf.symbols.recent.v1",
} as const;

const MAX_RECENT = 12;
const MAX_SYMBOLS = 8;

function readList(key: string): NavMemoryItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (x): x is NavMemoryItem =>
          !!x &&
          typeof x === "object" &&
          typeof (x as NavMemoryItem).href === "string" &&
          typeof (x as NavMemoryItem).label === "string",
      )
      .map((x) => ({
        href: x.href,
        label: x.label,
        at: typeof x.at === "number" ? x.at : Date.now(),
      }));
  } catch {
    return [];
  }
}

function writeList(key: string, items: NavMemoryItem[]) {
  try {
    localStorage.setItem(key, JSON.stringify(items));
  } catch {
    /* quota */
  }
}

function readStrings(key: string): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is string => typeof x === "string" && x.trim().length > 0);
  } catch {
    return [];
  }
}

function writeStrings(key: string, items: string[]) {
  try {
    localStorage.setItem(key, JSON.stringify(items));
  } catch {
    /* quota */
  }
}

export function getFavorites(): NavMemoryItem[] {
  return readList(KEYS.favorites);
}

export function getPinned(): NavMemoryItem[] {
  return readList(KEYS.pinned);
}

export function getRecentPages(): NavMemoryItem[] {
  return readList(KEYS.recent);
}

export function getRecentSymbols(): string[] {
  return readStrings(KEYS.symbols);
}

export function toggleFavorite(item: Omit<NavMemoryItem, "at">): NavMemoryItem[] {
  const list = getFavorites();
  const exists = list.some((x) => x.href === item.href);
  const next = exists
    ? list.filter((x) => x.href !== item.href)
    : [{ ...item, at: Date.now() }, ...list].slice(0, 16);
  writeList(KEYS.favorites, next);
  return next;
}

export function isFavorite(href: string): boolean {
  return getFavorites().some((x) => x.href === href);
}

export function togglePinned(item: Omit<NavMemoryItem, "at">): NavMemoryItem[] {
  const list = getPinned();
  const exists = list.some((x) => x.href === item.href);
  const next = exists
    ? list.filter((x) => x.href !== item.href)
    : [{ ...item, at: Date.now() }, ...list].slice(0, 8);
  writeList(KEYS.pinned, next);
  return next;
}

export function isPinned(href: string): boolean {
  return getPinned().some((x) => x.href === href);
}

export function pushRecentPage(item: Omit<NavMemoryItem, "at">): NavMemoryItem[] {
  const list = getRecentPages().filter((x) => x.href !== item.href);
  const next = [{ ...item, at: Date.now() }, ...list].slice(0, MAX_RECENT);
  writeList(KEYS.recent, next);
  return next;
}

export function pushRecentSymbol(symbol: string): string[] {
  const s = symbol.trim().toUpperCase();
  if (!s) return getRecentSymbols();
  const next = [s, ...getRecentSymbols().filter((x) => x !== s)].slice(0, MAX_SYMBOLS);
  writeStrings(KEYS.symbols, next);
  return next;
}

export function labelForHref(href: string, fallback?: string): string {
  const known: Record<string, string> = {
    "/terminal": "Terminal",
    "/portfolio": "Portfolio",
    "/research": "Research",
    "/journal": "Journal",
    "/broker": "Broker",
    "/monitoring": "Monitoring",
    "/analytics": "Analytics",
    "/orders": "Orders",
    "/positions": "Positions",
    "/executions": "Executions",
    "/ai-signals": "AI Signals",
    "/settings": "Settings",
    "/notifications": "Notifications",
    "/risk-center": "Risk",
    "/gateway": "Gateway",
  };
  return known[href] ?? fallback ?? href;
}
