import { authApi } from "@/lib/api/endpoints";
import { saveSession, type AuthSession } from "@/lib/auth/session";

export type EmailConfirmHashResult =
  | { kind: "signup"; session: AuthSession }
  | { kind: "recovery" }
  | { kind: "none" };

/**
 * Supabase email confirmation / recovery often redirects to the Site URL with
 * implicit tokens in the URL hash (`#access_token=…&type=signup`). Hash is
 * never sent to the server, so this must run client-side.
 */
export async function consumeAuthHashSession(): Promise<EmailConfirmHashResult> {
  if (typeof window === "undefined") return { kind: "none" };
  const raw = window.location.hash.replace(/^#/, "");
  if (!raw) return { kind: "none" };
  const hash = new URLSearchParams(raw);
  const access = hash.get("access_token");
  const refresh = hash.get("refresh_token");
  const type = (hash.get("type") || "").toLowerCase();
  if (!access) return { kind: "none" };

  if (type === "recovery") {
    return { kind: "recovery" };
  }

  window.sessionStorage.setItem("qf_access_token", access);
  if (refresh) window.sessionStorage.setItem("qf_refresh_token", refresh);

  const user = await authApi.me();
  const session: AuthSession = {
    access_token: access,
    refresh_token: refresh || "",
    expires_in: Number(hash.get("expires_in") || 3600),
    token_type: "bearer",
    user,
  };
  saveSession(session, { remember: true });
  window.history.replaceState(
    null,
    "",
    `${window.location.pathname}${window.location.search}`,
  );
  return { kind: "signup", session };
}
