import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Bell,
  Building2,
  CreditCard,
  Headphones,
  LayoutDashboard,
  Radio,
  ScrollText,
  Settings2,
  Shield,
  SlidersHorizontal,
  Users,
} from "lucide-react";

export const ADMIN_SIDEBAR_WIDTH = "16.5rem";

/** True when the app should render the enterprise Admin Portal shell (not trader rail). */
export function isAdminPath(pathname: string | null | undefined): boolean {
  if (!pathname) return false;
  return pathname === "/admin" || pathname.startsWith("/admin/");
}

export type AdminNavItem = {
  label: string;
  href: string;
  hint?: string;
  icon: LucideIcon;
};

export type AdminNavGroup = {
  title: string;
  items: AdminNavItem[];
};

/**
 * Enterprise Admin navigation.
 * Deep links into existing COP / ops routes — no parallel business logic.
 */
export const ADMIN_NAV_GROUPS: AdminNavGroup[] = [
  {
    title: "Overview",
    items: [
      {
        label: "Dashboard",
        href: "/admin",
        hint: "Platform KPIs, health, recent admin activity",
        icon: LayoutDashboard,
      },
    ],
  },
  {
    title: "User Management",
    items: [
      {
        label: "Users",
        href: "/admin/users",
        hint: "Search, filters, fleet CRM table",
        icon: Users,
      },
      {
        label: "COP fleet (legacy)",
        href: "/admin/customer-ops#fleet",
        hint: "Original Customer Operations fleet tab",
        icon: Users,
      },
      {
        label: "COP workspace",
        href: "/admin/customer-ops#workspace",
        hint: "UUID lookup in Customer Operations",
        icon: Users,
      },
    ],
  },
  {
    title: "Plans & Subscriptions",
    items: [
      {
        label: "Plans & subscriptions",
        href: "/admin/plans",
        hint: "Catalog pricing, revenue KPIs, manual license grant",
        icon: CreditCard,
      },
      {
        label: "Licenses (COP)",
        href: "/admin/customer-ops#licenses",
        hint: "Assignment, expiry, renewal status",
        icon: CreditCard,
      },
      {
        label: "Enterprise billing",
        href: "/admin/enterprise",
        hint: "SaaS controls and entitlements",
        icon: CreditCard,
      },
    ],
  },
  {
    title: "Broker Management",
    items: [
      {
        label: "Connected brokers",
        href: "/admin/customer-ops#brokers",
        hint: "Ownership, health, sync (credentials redacted)",
        icon: Building2,
      },
    ],
  },
  {
    title: "Trading & Robot",
    items: [
      {
        label: "Live trading control",
        href: "/admin/live-trading",
        hint: "DISABLED · ARM · ENABLE · KILL (safeguards intact)",
        icon: Radio,
      },
      {
        label: "NOC / workers",
        href: "/admin/noc",
        hint: "Observe-only operations command",
        icon: Activity,
      },
    ],
  },
  {
    title: "Risk & Configuration",
    items: [
      {
        label: "Owner control",
        href: "/admin/control",
        hint: "Policy, risk gates, live authorization",
        icon: SlidersHorizontal,
      },
      {
        label: "Reliability",
        href: "/admin/reliability",
        hint: "Safety gates and readiness",
        icon: Shield,
      },
    ],
  },
  {
    title: "Support Management",
    items: [
      {
        label: "Support desk",
        href: "/admin/support",
        hint: "Tickets, AI history, human handoff",
        icon: Headphones,
      },
      {
        label: "COP support queue",
        href: "/admin/customer-ops#support",
        hint: "Institutional support store",
        icon: Headphones,
      },
    ],
  },
  {
    title: "Notifications",
    items: [
      {
        label: "Platform notifications",
        href: "/admin/customer-ops#notifications",
        hint: "User and administrative alerts",
        icon: Bell,
      },
    ],
  },
  {
    title: "System Settings",
    items: [
      {
        label: "Enterprise settings",
        href: "/admin/enterprise",
        hint: "Feature access and SaaS config",
        icon: Settings2,
      },
      {
        label: "Audit logs",
        href: "/admin/customer-ops#audit",
        hint: "Administrative action history",
        icon: ScrollText,
      },
    ],
  },
];

export function adminNavActive(
  pathname: string,
  hash: string,
  href: string,
): boolean {
  const normalizedHash = hash.replace(/^#/, "");
  const [path, frag] = href.split("#");

  if (frag) {
    const pathMatch =
      pathname === path ||
      (path !== "/admin" && pathname.startsWith(`${path}/`));
    return pathMatch && normalizedHash === frag;
  }

  if (path === "/admin") {
    return pathname === "/admin";
  }

  return pathname === path || pathname.startsWith(`${path}/`);
}
