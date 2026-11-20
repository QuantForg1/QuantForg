/** Remembers a referral code from a shared link until the visitor signs up. */

const KEY = "qf_ref";
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;

export function normalizeRefCode(raw: string | null | undefined): string | null {
  const code = (raw ?? "").trim().toUpperCase();
  return /^[A-Z0-9-]{1,32}$/.test(code) ? code : null;
}

type Stored = { code: string; at: number };

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function rememberRefCode(raw: string | null | undefined, now = Date.now()): string | null {
  const code = normalizeRefCode(raw);
  const s = storage();
  if (!code || !s) return null;
  try {
    // First link wins: a later link must not steal an earlier referral.
    if (pendingRefCode(now)) return pendingRefCode(now);
    s.setItem(KEY, JSON.stringify({ code, at: now } satisfies Stored));
  } catch {
    return null;
  }
  return code;
}

export function pendingRefCode(now = Date.now()): string | null {
  const s = storage();
  if (!s) return null;
  try {
    const parsed = JSON.parse(s.getItem(KEY) ?? "null") as Stored | null;
    if (!parsed || typeof parsed.at !== "number" || now - parsed.at > MAX_AGE_MS) return null;
    return normalizeRefCode(parsed.code);
  } catch {
    return null;
  }
}

export function clearRefCode(): void {
  try {
    storage()?.removeItem(KEY);
  } catch {
    /* storage unavailable */
  }
}
