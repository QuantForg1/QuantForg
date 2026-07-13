/**
 * Closed-beta onboarding state (localStorage only — no settings API change).
 */

const CHECKLIST_KEY = "qf.onboarding.checklist.v1";
const TOUR_KEY = "qf.onboarding.tour.dismissed.v1";
const PAPER_TUTORIAL_KEY = "qf.onboarding.paper.tutorial.v1";
const RELEASE_SEEN_KEY = "qf.onboarding.release.seen.v1";
const FIRST_RUN_DISMISSED_KEY = "qf.onboarding.first_run.dismissed.v1";

export type ChecklistId =
  | "invite"
  | "tour"
  | "paper"
  | "broker"
  | "feedback"
  | "whats_new";

export type ChecklistState = Record<ChecklistId, boolean>;

const DEFAULT_CHECKLIST: ChecklistState = {
  invite: false,
  tour: false,
  paper: false,
  broker: false,
  feedback: false,
  whats_new: false,
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
  setChecklistItem("tour", true);
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
  setChecklistItem("paper", true);
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
  setChecklistItem("whats_new", true);
}

export const CHECKLIST_ITEMS: {
  id: ChecklistId;
  title: string;
  href: string;
  description: string;
}[] = [
  {
    id: "tour",
    title: "Take the product tour",
    href: "/get-started",
    description: "Five-minute overview of the desk",
  },
  {
    id: "paper",
    title: "Place a paper trade",
    href: "/paper",
    description: "Learn fills without live risk",
  },
  {
    id: "broker",
    title: "Connect a broker (MT5)",
    href: "/get-started#broker",
    description: "Wizard → compatibility → /mt5",
  },
  {
    id: "feedback",
    title: "Send beta feedback",
    href: "/support#feedback",
    description: "Use the in-app feedback control",
  },
  {
    id: "whats_new",
    title: "Read release notes",
    href: "/whats-new",
    description: "Closed beta changelog highlights",
  },
];
