import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

/**
 * Supabase OAuth may land on `/` with `?code=` or `?error=` before the callback page.
 * Preserve the full query when forwarding to `/auth/callback`.
 */
export function middleware(request: NextRequest) {
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