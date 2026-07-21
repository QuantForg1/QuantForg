import type { LucideIcon } from "lucide-react";
import {
  Activity,
  AlertTriangle,
  Bell,
  BookOpen,
  Briefcase,
  Building2,
  Calendar,
  CandlestickChart,
  FileText,
  FlaskConical,
  Gauge,
  History,
  Keyboard,
  Layers3,
  LayoutTemplate,
  LineChart,
  ListOrdered,
  NotebookPen,
  PieChart,
  Radar,
  Scale,
  ScanSearch,
  Settings,
  Shield,
  Sparkles,
  Target,
  Workflow,
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
 * QuantForg OS V3 — workspace information architecture.
 * Each route has one responsibility. Terminal remains the sole live execution surface.
 */
export const appNav: NavGroup[] = [
  {
    title: "Trading",
    items: [
      {
        href: "/terminal",
        label: "Terminal",
        icon: LayoutTemplate,
        hint: "Chart · ticket · blotter",
      },
      {
        href: "/alerts",
        label: "Alerts",
        icon: Bell,
        hint: "Price and session alerts",
      },
      {
        href: "/orders",
        label: "Orders",
        icon: ListOrdered,
        hint: "Working and pending orders",
      },
      {
        href: "/positions",
        label: "Positions",
        icon: Layers3,
        hint: "Open exposure blotter",
      },
      {
        href: "/executions",
        label: "Executions",
        icon: History,
        hint: "Fills and deal tape",
      },
    ],
  },
  {
    title: "Portfolio",
    items: [
      {
        href: "/portfolio",
        label: "Portfolio",
        icon: Briefcase,
        hint: "Equity · health · book OS",
      },
      {
        href: "/performance",
        label: "Performance",
        icon: LineChart,
        hint: "Equity path and returns",
      },
      {
        href: "/exposure",
        label: "Exposure",
        icon: Target,
        hint: "Symbol and side exposure",
      },
      {
        href: "/risk-center",
        label: "Risk",
        icon: Shield,
        hint: "Pre-trade and session risk",
      },
      {
        href: "/allocation",
        label: "Allocation",
        icon: PieChart,
        hint: "Capital allocation map",
      },
    ],
  },
  {
    title: "Research",
    items: [
      {
        href: "/research",
        label: "Research",
        icon: FlaskConical,
        hint: "Idea → promote pipeline",
      },
      {
        href: "/ai-signals",
        label: "AI Signals",
        icon: Sparkles,
        hint: "Decision intelligence signals",
      },
      {
        href: "/economic-calendar",
        label: "Economic Calendar",
        icon: Calendar,
        hint: "Macro event calendar",
      },
      {
        href: "/market-scanner",
        label: "Market Scanner",
        icon: Radar,
        hint: "Live market scan",
      },
      {
        href: "/screeners",
        label: "Screeners",
        icon: ScanSearch,
        hint: "Saved screen criteria",
      },
    ],
  },
  {
    title: "Operations",
    items: [
      {
        href: "/monitoring",
        label: "Monitoring",
        icon: Gauge,
        hint: "Production ops · live execution",
      },
      {
        href: "/gateway",
        label: "Gateway",
        icon: Workflow,
        hint: "MT5 gateway control",
      },
      {
        href: "/broker",
        label: "Broker",
        icon: Building2,
        hint: "Connect · diagnose · settings",
      },
      {
        href: "/execution/diagnostics",
        label: "Execution Audit",
        icon: FileText,
        hint: "Validation · risk · MT5 audit",
      },
      {
        href: "/logs",
        label: "Logs",
        icon: BookOpen,
        hint: "Operational log stream",
      },
      {
        href: "/incidents",
        label: "Incidents",
        icon: AlertTriangle,
        hint: "Active and resolved incidents",
      },
    ],
  },
  {
    title: "History",
    items: [
      {
        href: "/journal",
        label: "Journal",
        icon: NotebookPen,
        hint: "Trade memory and notes",
      },
      {
        href: "/trade-replay",
        label: "Trade Replay",
        icon: CandlestickChart,
        hint: "Replay closed trades",
      },
      {
        href: "/analytics",
        label: "Analytics",
        icon: Activity,
        hint: "Win rate · expectancy · DD",
      },
      {
        href: "/reports",
        label: "Reports",
        icon: FileText,
        hint: "Exportable performance reports",
      },
    ],
  },
  {
    title: "System",
    items: [
      {
        href: "/settings",
        label: "Settings",
        icon: Settings,
        hint: "Profile, org, prefs",
      },
      {
        href: "/notifications",
        label: "Notifications",
        icon: Bell,
        hint: "Inbox and delivery",
      },
      {
        href: "/integrations",
        label: "Integrations",
        icon: Workflow,
        hint: "Connected services",
      },
      {
        href: "/shortcuts",
        label: "Keyboard Shortcuts",
        icon: Keyboard,
        hint: "Global and desk shortcuts",
      },
    ],
  },
];

/** Compact mobile bottom bar — one-hand primary surfaces. */
export const mobileTabNav: NavItem[] = [
  {
    href: "/terminal",
    label: "Trade",
    icon: LayoutTemplate,
    hint: "Terminal",
  },
  {
    href: "/portfolio",
    label: "Book",
    icon: Briefcase,
    hint: "Portfolio",
  },
  {
    href: "/research",
    label: "Research",
    icon: FlaskConical,
    hint: "Research",
  },
  {
    href: "/journal",
    label: "Journal",
    icon: NotebookPen,
    hint: "Journal",
  },
  {
    href: "/broker",
    label: "Broker",
    icon: Building2,
    hint: "Broker",
  },
];

export const commandItems: NavItem[] = [
  ...appNav.flatMap((g) => g.items),
  {
    href: "/counsel",
    label: "Counsel",
    icon: Scale,
    hint: "Decision intelligence (advise only)",
  },
  {
    href: "/auto-trading",
    label: "Auto Trading",
    icon: Sparkles,
    hint: "Operator auto-trade controls",
  },
  {
    href: "/ops",
    label: "Ops control",
    icon: Gauge,
    hint: "ITE control plane · kill switch",
  },
];
