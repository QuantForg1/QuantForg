/**
 * Progressive onboarding state (localStorage only — no settings API change).
 */

const CHECKLIST_KEY = "qf.onboarding.checklist.v2";
const TOUR_KEY = "qf.onboarding.tour.dismissed.v1";
const PAPER_TUTORIAL_KEY = "qf.onboarding.paper.tutorial.v1";
const RELEASE_SEEN_KEY = "qf.onboarding.release.seen.v1";
const FIRST_RUN_DISMISSED_KEY = "qf.onboarding.first_run.dismissed.v1";

export type ChecklistId =
  | "welcome"
  | "markets"
  | "signals"
  | "broker"
  | "preferences"
  | "live_ready";

export type ChecklistState = Record<ChecklistId, boolean>;

const DEFAULT_CHECKLIST: ChecklistState = {
  welcome: false,
  markets: false,
  signals: false,
  broker: false,
  preferences: false,
  live_ready: false,
};

function readJson<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function getChecklist(): ChecklistState {
  return { ...DEFAULT_CHECKLIST, ...readJson(CHECKLIST_KEY, {}) };
}

export function setChecklistItem(id: ChecklistId, done: boolean): ChecklistState {
  const next = { ...getChecklist(), [id]: done };
  if (typeof window !== "undefined") {
    localStorage.setItem(CHECKLIST_KEY, JSON.stringify(next));
  }
  return next;
}

export function checklistProgress(state: ChecklistState = getChecklist()): {
  done: number;
  total: number;
  complete: boolean;
} {
  const ids = Object.keys(DEFAULT_CHECKLIST) as ChecklistId[];
  const done = ids.filter((id) => state[id]).length;
  return { done, total: ids.length, complete: done === ids.length };
}

export function isTourDismissed(): boolean {
  if (typeof window === "undefined") return true;
  return localStorage.getItem(TOUR_KEY) === "1";
}

export function dismissTour(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOUR_KEY, "1");
  setChecklistItem("welcome", true);
}

export function reopenTour(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOUR_KEY);
}

export function isPaperTutorialDismissed(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(PAPER_TUTORIAL_KEY) === "1";
}

export function dismissPaperTutorial(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(PAPER_TUTORIAL_KEY, "1");
}

export function isFirstRunDismissed(): boolean {
  if (typeof window === "undefined") return true;
  return localStorage.getItem(FIRST_RUN_DISMISSED_KEY) === "1";
}

export function dismissFirstRun(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(FIRST_RUN_DISMISSED_KEY, "1");
}

export function getSeenReleaseVersion(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(RELEASE_SEEN_KEY);
}

export function markReleaseSeen(version: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(RELEASE_SEEN_KEY, version);
}

export const CHECKLIST_ITEMS: {
  id: ChecklistId;
  title: string;
  href: string;
  description: string;
}[] = [
  {
    id: "welcome",
    title: "Welcome to QuantForg",
    href: "/get-started",
    description: "See how research, markets, and trading fit together",
  },
  {
    id: "markets",
    title: "Explore markets",
    href: "/markets",
    description: "Browse the research universe — no broker required",
  },
  {
    id: "signals",
    title: "View research signals",
    href: "/signals",
    description: "Read market intelligence independently of MT5",
  },
  {
    id: "broker",
    title: "Connect a broker when ready",
    href: "/broker",
    description: "Optional. Required only for live account and execution",
  },
  {
    id: "preferences",
    title: "Configure trading preferences",
    href: "/settings",
    description: "Theme, alerts, and workspace defaults",
  },
  {
    id: "live_ready",
    title: "Enable live trading only when ready",
    href: "/broker",
    description: "Never automatic. Requires broker, risk checks, and authorization",
  },
];
