import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Next.js 16 edge proxy (replaces middleware.ts — both cannot coexist).
 *
 * - Keep `/` on the React HomeLanding.
 * - If Supabase OAuth/magic-link lands on `/?code=` or `/?error=`, forward to
 *   `/auth/callback` with the original query string (defense-in-depth).
 */
export function proxy(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  if (pathname !== "/") {
    return NextResponse.next();
  }

  const hasOAuthParams =
    searchParams.has("code") ||
    searchParams.has("error") ||
    searchParams.has("error_description");
  if (!hasOAuthParams) {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = "/auth/callback";
  return NextResponse.redirect(url);
}

export const config = {
  matcher: "/",
};
