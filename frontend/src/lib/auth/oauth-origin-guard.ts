const LOCALHOST_PATTERN = /localhost|127\.0\.0\.1/i;

/** True when the browser host is production QuantForg (apex or www). */
export function isQuantforgProductionHost(hostname: string): boolean {
  const host = hostname.toLowerCase();
  return host === "quantforg.com" || host === "www.quantforg.com";
}

/** Detect localhost in OAuth authorize redirect_to query values. */
export function authorizeUrlHasLocalhostRedirect(authorizeUrl: string): boolean {
  try {
    const parsed = new URL(authorizeUrl);
    const redirectTo =
      parsed.searchParams.get("redirect_to") ??
      parsed.searchParams.get("redirect_uri") ??
      "";
    return LOCALHOST_PATTERN.test(redirectTo);
  } catch {
    return LOCALHOST_PATTERN.test(authorizeUrl);
  }
}

export function assertProductionOAuthOrigins(input: {
  hostname: string;
  clientOrigin: string;
  authorizeUrl: string;
}): void {
  if (!isQuantforgProductionHost(input.hostname)) {
    return;
  }
  if (LOCALHOST_PATTERN.test(input.clientOrigin)) {
    throw new Error(
      "OAuth is misconfigured: this page is on quantforg.com but the app origin resolved to localhost. Set NEXT_PUBLIC_APP_URL to https://www.quantforg.com on Vercel.",
    );
  }
  if (authorizeUrlHasLocalhostRedirect(input.authorizeUrl)) {
    throw new Error(
      "OAuth is misconfigured: Google authorize URL targets a localhost redirect. Fix Supabase Site URL and Redirect URLs — use https://www.quantforg.com/auth/callback, not localhost.",
    );
  }
}