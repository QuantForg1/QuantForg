import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Bell,
  BookOpen,
  Bot,
  Briefcase,
  Building2,
  Gauge,
  LayoutTemplate,
  NotebookPen,
  Scale,
  Settings,
  Shield,
  FlaskConical,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Short job description for command palette */
  hint?: string;
};

export type NavGroup = {
  title: string;
  items: NavItem[];
};

/**
 * QuantForg OS — maximum eight primary surfaces.
 * Everything else is drawer, modal, redirect, or admin-only.
 */
export const appNav: NavGroup[] = [
  {
    title: "Desks",
    items: [
      {
        href: "/terminal",
        label: "Terminal",
        icon: LayoutTemplate,
        hint: "Trade — chart, ticket, blotter",
      },
      {
        href: "/book",
        label: "Book",
        icon: Briefcase,
        hint: "Portfolio, risk, P&L",
      },
      {
        href: "/research",
        label: "Research",
        icon: FlaskConical,
        hint: "Build, test, validate",
      },
      {
        href: "/counsel",
        label: "Counsel",
        icon: Scale,
        hint: "Decision intelligence",
      },
      {
        href: "/journal",
        label: "Journal",
        icon: NotebookPen,
        hint: "Orders history & session memory",
      },
      {
        href: "/broker",
        label: "Broker",
        icon: Building2,
        hint: "Live MT5 account dashboard",
      },
    ],
  },
  {
    title: "System",
    items: [
      {
        href: "/notifications",
        label: "Inbox",
        icon: Bell,
        hint: "Alerts",
      },
      {
        href: "/settings",
        label: "Settings",
        icon: Settings,
        hint: "Profile, org, prefs",
      },
    ],
  },
];

export const commandItems: NavItem[] = [
  ...appNav.flatMap((g) => g.items),
  { href: "/orders", label: "Orders blotter", icon: BookOpen, hint: "Opens in Terminal" },
  { href: "/positions", label: "Positions", icon: Briefcase, hint: "Opens in Terminal" },
  {
    href: "/analytics",
    label: "Analytics",
    icon: Activity,
    hint: "Returns · volatility · exposure",
  },
  {
    href: "/risk-center",
    label: "Risk Center",
    icon: Shield,
    hint: "Pre-trade checks · session exposure",
  },
  {
    href: "/auto-trading",
    label: "Auto Trading",
    icon: Bot,
    hint: "Operator auto-trade controls · PME",
  },
  {
    href: "/monitoring",
    label: "Monitoring",
    icon: Gauge,
    hint: "Gateway · reliability · health",
  },
  {
    href: "/ops",
    label: "Operations control",
    icon: Building2,
    hint: "ITE control plane · kill switch · modes",
  },
  {
    href: "/execution/diagnostics",
    label: "Execution diagnostics",
    icon: Building2,
    hint: "Validation · Risk · MT5 audit",
  },
  { href: "/support", label: "Support", icon: Settings },
];
