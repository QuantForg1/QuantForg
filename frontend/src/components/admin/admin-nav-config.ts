import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Bell,
  Building2,
  CreditCard,
  Headphones,
  LayoutDashboard,
  Radio,
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

export const ADMIN_NAV_GROUPS: AdminNavGroup[] = [
  {
    title: "Overview",
    items: [
      {
        label: "Overview",
        href: "/admin",
        hint: "Platform KPIs and health",
        icon: LayoutDashboard,
      },
    ],
  },
  {
    title: "Customers",
    items: [
      {
        label: "User Management",
        href: "/admin/customer-ops#fleet",
        hint: "Fleet and customer workspace",
        icon: Users,
      },
      {
        label: "Plans & Subscriptions",
        href: "/admin/customer-ops#licenses",
        hint: "License center",
        icon: CreditCard,
      },
      {
        label: "Broker Management",
        href: "/admin/customer-ops#brokers",
        hint: "Broker connections",
        icon: Building2,
      },
    ],
  },
  {
    title: "Operations",
    items: [
      {
        label: "Trading & Robot",
        href: "/admin/live-trading",
        hint: "Read-only live trading overview",
        icon: Radio,
      },
      {
        label: "Risk & Configuration",
        href: "/admin/control",
        hint: "Owner policy and risk gates",
        icon: SlidersHorizontal,
      },
      {
        label: "Support Management",
        href: "/admin/support",
        hint: "Tickets, status, and replies",
        icon: Headphones,
      },
      {
        label: "Notifications",
        href: "/admin/customer-ops#notifications",
        hint: "Institutional notification center",
        icon: Bell,
      },
    ],
  },
  {
    title: "System",
    items: [
      {
        label: "Enterprise",
        href: "/admin/enterprise",
        hint: "SaaS platform controls",
        icon: Settings2,
      },
      {
        label: "Reliability",
        href: "/admin/reliability",
        hint: "Safety gates and readiness",
        icon: Shield,
      },
      {
        label: "NOC",
        href: "/admin/noc",
        hint: "Operations command observe-only",
        icon: Activity,
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
