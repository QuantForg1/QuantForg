import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Edge proxy — keep `/` on the React HomeLanding (reference marketing page).
 * Static `/go-live-landing.html` remains available for direct/Lighthouse checks.
 */
export function proxy(_request: NextRequest) {
  return NextResponse.next();
}

export const config = {
  matcher: "/",
};
