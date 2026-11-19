/**
 * Routes an ordinary customer may open inside the authenticated app.
 *
 * The app holds ~300 pages; most are owner/operator desks, research labs and
 * legacy acceptance pages. Customers reach only the product desks below; any
 * other in-app URL redirects to Overview. Owner/admin keep every page. This is
 * a UX boundary: privileged APIs are still enforced on the server.
 */
export const CUSTOMER_ROUTES: readonly string[] = [
  // Rail desks
  "/dashboard",
  "/intelligence",
  "/signals",
  "/book",
  "/broker",
  "/research",
  "/strategy",
  "/robot-control-center",
  "/settings",
  // Linked from those desks / command palette
  "/positions",
  "/orders",
  "/portfolio",
  "/markets",
  "/symbols",
  "/journal",
  "/trading-journal",
  "/counsel",
  "/notifications",
  "/support",
  "/profile",
  "/get-started",
  "/whats-new",
  "/shortcuts",
  "/wallet",
  "/ai-trading-intelligence",
  "/decision-evidence",
  "/ai-robot",
  "/trade-replay",
  "/analytics",
  "/trust",
];

export function isCustomerRoute(pathname: string): boolean {
  const path = (pathname.split("?")[0] || "/").replace(/\/$/, "") || "/";
  return CUSTOMER_ROUTES.some(
    (route) => path === route || path.startsWith(`${route}/`),
  );
}

export function isPrivilegedRole(role: string | null | undefined): boolean {
  const r = String(role ?? "").trim().toLowerCase();
  return r === "owner" || r === "admin";
}
