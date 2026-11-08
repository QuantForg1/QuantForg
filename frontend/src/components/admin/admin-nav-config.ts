import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Bell,
  Building2,
  CreditCard,
  FileSearch,
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
 * Canonical Admin Portal navigation.
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
        label: "Customer Operations",
        href: "/admin/customer-ops",
        hint: "Fleet, workspace, licenses, brokers, support",
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
        label: "Licenses",
        href: "/admin/customer-ops#licenses",
        hint: "Assignment, expiry, renewal status",
        icon: CreditCard,
      },
    ],
  },
  {
    title: "Broker Management",
    items: [
      {
        label: "Connected brokers",
        href: "/admin/brokers",
        hint: "Ownership, health, sync (credentials redacted)",
        icon: Building2,
      },
    ],
  },
  {
    title: "Trading & Robot",
    items: [
      {
        label: "Owner control & robot",
        href: "/admin/control",
        hint: "Policy, risk gates, live authorization panel",
        icon: SlidersHorizontal,
      },
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
      {
        label: "Live trading evidence",
        href: "/admin/live-trading-evidence",
        hint: "Evidence program — observe only",
        icon: FileSearch,
      },
    ],
  },
  {
    title: "Risk & Configuration",
    items: [
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
    title: "System",
    items: [
      {
        label: "Enterprise settings",
        href: "/admin/enterprise",
        hint: "SaaS controls, access, compliance",
        icon: Settings2,
      },
      {
        label: "Continuous improvement",
        href: "/admin/continuous-improvement",
        hint: "CIP desk — observe only",
        icon: Activity,
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
