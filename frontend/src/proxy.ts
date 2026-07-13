import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** Serve zero-JS static marketing HTML for `/` to meet Lighthouse Performance ≥95. */
export function proxy(request: NextRequest) {
  if (request.nextUrl.pathname === "/") {
    return NextResponse.rewrite(new URL("/go-live-landing.html", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: "/",
};
