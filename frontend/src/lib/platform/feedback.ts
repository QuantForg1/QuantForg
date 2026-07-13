import { getBrowserInfo, getBuildVersion, sanitizePayload } from "@/lib/observability/context";
import { recordAudit } from "@/lib/observability/audit";
import { getStoredUser } from "@/lib/auth/session";

export type FeedbackCategory = "bug" | "feature" | "general";

export type FeedbackItem = {
  id: string;
  category: FeedbackCategory;
  message: string;
  email?: string;
  browser: string;
  build_version: string;
  route: string;
  user_id: string | null;
  created_at: string;
};

const STORAGE_KEY = "qf.ops.feedback.v1";
const MAX = 50;

export function listFeedback(): FeedbackItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as FeedbackItem[]) : [];
  } catch {
    return [];
  }
}

export async function submitFeedback(input: {
  category: FeedbackCategory;
  message: string;
  email?: string;
}): Promise<FeedbackItem> {
  const user = getStoredUser();
  const item: FeedbackItem = {
    id: `fb_${Date.now()}`,
    category: input.category,
    message: input.message.trim().slice(0, 4000),
    email: input.email?.trim().slice(0, 200) || undefined,
    browser: getBrowserInfo(),
    build_version: getBuildVersion(),
    route: typeof window !== "undefined" ? window.location.pathname : "/",
    user_id: user?.id ?? null,
    created_at: new Date().toISOString(),
  };

  if (typeof window !== "undefined") {
    const next = [item, ...listFeedback()].slice(0, MAX);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  recordAudit("feedback_submit", "success", `Feedback: ${input.category}`, {
    category: input.category,
    length: item.message.length,
  });

  const webhook = process.env.NEXT_PUBLIC_FEEDBACK_WEBHOOK_URL?.trim();
  if (webhook) {
    try {
      await fetch(webhook, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(sanitizePayload(item)),
        keepalive: true,
      });
    } catch {
      /* stored locally regardless */
    }
  }

  return item;
}
